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

NO_RETRY = RetryPolicy(maximum_attempts=1)
DEFAULT_RETRY = RetryPolicy(
    maximum_attempts=5,
    backoff_coefficient=2.0,
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(minutes=1),
)
ACTIVITY_TIMEOUT = timedelta(minutes=1)
REVIEW_TIMEOUT = timedelta(seconds=35)


@workflow.defn
class BillProcessorWorkflow:
    def __init__(self) -> None:
        self._review_status: str = (
            "pending"  # pending | approved | rejected | timed_out
        )
        self._email_status: str = "failed"
        self._archive_status: str = "failed"

    @workflow.signal
    async def approve_email(self) -> None:
        self._review_status = "approved"

    @workflow.signal
    async def reject_email(self) -> None:
        self._review_status = "rejected"

    @workflow.query
    def email_review_status(self) -> str:
        return self._review_status

    @workflow.run
    async def run(self, file_path: str) -> WorkflowResult:
        compensations: list[tuple] = []

        workflow.logger.info("/n/n[1/10] Starting: %s", file_path)

        # ── File processing ──────────────────────────────────────────────
        bill: BillData = await workflow.execute_activity(
            extract_bill_data,
            file_path,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=NO_RETRY,
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
            retry_policy=DEFAULT_RETRY,
        )
        workflow.logger.info("[3/10] File renamed: %s", bill.processed_file_name)

        # ── Property Management (Apartments.com) ─────────────────────────
        tenant: TenantData = await workflow.execute_activity(
            get_tenant_data,
            bill.unit,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
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
                retry_policy=DEFAULT_RETRY,
            )
            compensations.append((undo_apartments_com_entry, [bill, tenant]))
            workflow.logger.info("[5/10] Apartments.com entry confirmed")

            # ── Accounting -------—-----───────────────────────────────────
            await workflow.execute_activity(
                update_monthly_expenses,
                bill,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            compensations.append((undo_monthly_expenses, [bill]))
            workflow.logger.info("[6/10] Monthly expenses updated")

            await workflow.execute_activity(
                update_income_expense_overview,
                bill,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            compensations.append((undo_income_expense_overview, [bill]))
            workflow.logger.info("[7/10] Income/expense overview updated")

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
                        retry_policy=DEFAULT_RETRY,
                    )
                except Exception:
                    workflow.logger.warning(
                        "Compensation %s failed — continuing", activity_fn.__name__
                    )
            raise
        # --- Saga Ends -------------------------------------------------------
        # ── Notification — best effort ───────────────────────────────────────
        try:
            draft_id: str = await workflow.execute_activity(
                draft_email_from_template,
                args=[bill, tenant],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            workflow.logger.info("[8/10] Email draft created: %s", draft_id)

            await workflow.execute_activity(
                attach_bill,
                args=[draft_id, bill],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            workflow.logger.info("[9/10] Bill attached to draft")

            # Human review gate
            workflow.logger.info(
                "Waiting for email review signal (timeout %s)...", REVIEW_TIMEOUT
            )
            try:
                await workflow.wait_condition(
                    lambda: self._review_status != "pending",
                    timeout=REVIEW_TIMEOUT,
                )
            except asyncio.TimeoutError:
                self._review_status = "timed_out"
            workflow.logger.info("Review status: %s", self._review_status)

            if self._review_status == "approved":
                await workflow.execute_activity(
                    send_email,
                    draft_id,
                    start_to_close_timeout=ACTIVITY_TIMEOUT,
                    retry_policy=DEFAULT_RETRY,
                )
                self._email_status = "sent"
                workflow.logger.info("Email sent")
            else:
                self._email_status = self._review_status  # "rejected" or "timed_out"
        except Exception:
            workflow.logger.warning("Courtesy email failed — continuing")

        # ── Archive — best effort ────────────────────────────────────────────
        try:
            await workflow.execute_activity(
                move_file_to_gdrive,
                bill,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
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
