import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.activities import (
        add_unit_and_date_range_to_file,
        attach_bill,
        draft_email_from_template,
        enter_bill_apartments_com,
        extract_bill_data,
        get_tenant_data,
        move_file_to_gdrive,
        send_email,
        undo_apartments_com_entry,
        undo_income_expense_overview,
        undo_monthly_expenses,
        update_income_expense_overview,
        update_monthly_expenses,
    )
    from app.shared.data import BillData, TenantData, WorkflowResult

# Retry policy with exponential backoff — start_to_close caps a single attempt, schedule_to_close caps the entire activity including retries
DEFAULT_RETRY = RetryPolicy(
    maximum_attempts=5,
    backoff_coefficient=2.0,
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(minutes=1),
)
ACTIVITY_TIMEOUT = timedelta(minutes=1)
SCHEDULE_TIMEOUT = timedelta(minutes=10)
REVIEW_TIMEOUT = timedelta(seconds=35)


# Workflow definition — @workflow.defn registers this class as a durable Temporal workflow
@workflow.defn
class BillProcessorWorkflow:
    def __init__(self) -> None:
        # Workflow state — instance variables persist across replays and can be updated by signals
        self._review_status: str = (
            "pending"  # pending | approved | rejected | timed_out
        )
        self._email_status: str = "failed"
        self._archive_status: str = "failed"

    # Signals — allow external callers to push events into a running workflow without polling
    @workflow.signal
    def approve_email(self) -> None:
        self._review_status = "approved"

    @workflow.signal
    def reject_email(self) -> None:
        self._review_status = "rejected"

    # Query — read-only inspection of workflow state; does not advance execution
    @workflow.query
    def email_review_status(self) -> str:
        return self._review_status

    # Workflow entry point — Temporal calls this single async method to execute the workflow
    @workflow.run
    async def run(self, file_path: str) -> WorkflowResult:
        # Saga compensation pattern — tracks completed activities to reverse on failure
        compensations: list[tuple] = []

        workflow.logger.info("\n\n[1/10] Starting: %s", file_path)

        # ── File processing ──────────────────────────────────────────────
        bill: BillData = await workflow.execute_activity(
            extract_bill_data,
            file_path,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            schedule_to_close_timeout=SCHEDULE_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )
        workflow.logger.info(
            "[2/10] Bill data extracted — unit=%s amount=%s date_range=%s",
            bill.unit,
            bill.amount,
            bill.date_range,
        )

        bill = await workflow.execute_activity(
            add_unit_and_date_range_to_file,
            bill,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            schedule_to_close_timeout=SCHEDULE_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )
        workflow.logger.info("[3/10] File renamed: %s", bill.processed_file_name)

        # ── Property Management (Apartments.com) ─────────────────────────
        tenant: TenantData = await workflow.execute_activity(
            get_tenant_data,
            bill.unit,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            schedule_to_close_timeout=SCHEDULE_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )
        workflow.logger.info(
            "[4/10] Tenant resolved: %s <%s>", tenant.name, tenant.email
        )

        # ---Saga Begins --------------------------------------------------
        try:
            await workflow.execute_activity(
                enter_bill_apartments_com,
                args=[bill, tenant],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                schedule_to_close_timeout=SCHEDULE_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            compensations.append((undo_apartments_com_entry, [bill, tenant]))
            workflow.logger.info("[5/10] Apartments.com entry confirmed")

            # ── Accounting -------—-----───────────────────────────────────
            await workflow.execute_activity(
                update_monthly_expenses,
                bill,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                schedule_to_close_timeout=SCHEDULE_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            compensations.append((undo_monthly_expenses, [bill]))
            workflow.logger.info("[6/10] Monthly expenses updated")

            await workflow.execute_activity(
                update_income_expense_overview,
                bill,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                schedule_to_close_timeout=SCHEDULE_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            compensations.append((undo_income_expense_overview, [bill]))
            workflow.logger.info("[7/10] Income/expense overview updated")

        # Saga rollback — runs compensation activities in reverse order to undo completed steps
        except Exception:
            workflow.logger.info(
                "Saga compensation triggered — reversing %d step(s)", len(compensations)
            )
            for activity_fn, activity_args in reversed(compensations):
                try:
                    await workflow.execute_activity(
                        activity_fn,
                        args=activity_args,
                        start_to_close_timeout=ACTIVITY_TIMEOUT,
                        schedule_to_close_timeout=SCHEDULE_TIMEOUT,
                        retry_policy=DEFAULT_RETRY,
                    )
                except Exception:
                    workflow.logger.warning(
                        "Compensation %s failed — continuing", activity_fn.__name__
                    )
            raise
        # --- Saga Ends -------------------------------------------------------

        # Best-effort section — failures are logged but do not propagate; the workflow always completes
        # ── Notification — best effort ───────────────────────────────────────
        try:
            # Idempotency key — derived from the workflow ID so retries reuse the same draft rather than creating duplicates
            idempotency_key = workflow.info().workflow_id
            draft_id: str = await workflow.execute_activity(
                draft_email_from_template,
                args=[bill, tenant, idempotency_key],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                schedule_to_close_timeout=SCHEDULE_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            workflow.logger.info("[8/10] Email draft created: %s", draft_id)

            await workflow.execute_activity(
                attach_bill,
                args=[draft_id, bill],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                schedule_to_close_timeout=SCHEDULE_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            workflow.logger.info("[9/10] Bill attached to draft")

            # Human review gate — wait_condition blocks the workflow until a signal arrives or the timeout fires
            workflow.logger.info(
                "Waiting for email review signal (timeout %s)...", REVIEW_TIMEOUT
            )
            try:
                await workflow.wait_condition(
                    lambda: self._review_status != "pending",
                    timeout=REVIEW_TIMEOUT,
                )
            # asyncio.TimeoutError is raised by wait_condition on timeout; convert it to a status string
            except asyncio.TimeoutError:
                self._review_status = "timed_out"
            workflow.logger.info("Review status: %s", self._review_status)

            if self._review_status == "approved":
                await workflow.execute_activity(
                    send_email,
                    draft_id,
                    start_to_close_timeout=ACTIVITY_TIMEOUT,
                    schedule_to_close_timeout=SCHEDULE_TIMEOUT,
                    retry_policy=DEFAULT_RETRY,
                )
                self._email_status = "sent"
                workflow.logger.info("Email sent")
            else:
                self._email_status = self._review_status  # "rejected" or "timed_out"
        except Exception:
            workflow.logger.warning("Courtesy email failed — continuing")

        # Best-effort section — failures are logged but do not propagate; the workflow always completes
        # ── Archive — best effort ────────────────────────────────────────────
        try:
            await workflow.execute_activity(
                move_file_to_gdrive,
                bill,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                schedule_to_close_timeout=SCHEDULE_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            self._archive_status = "archived"
            workflow.logger.info("[10/10] File archived to Google Drive")
        except Exception:
            workflow.logger.warning("Archive failed — continuing")

        workflow.logger.info(
            "Workflow complete — processed_file_name=%s", bill.processed_file_name
        )
        return WorkflowResult(
            bill=bill,
            email_status=self._email_status,
            archive_status=self._archive_status,
        )
