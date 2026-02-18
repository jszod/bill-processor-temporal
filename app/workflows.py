from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.activities import (
        extract_bill_data,
        prefix_unit_name_to_file,
        suffix_date_range_to_file,
        get_tenant_data,
        enter_bill_apartments_com,
        undo_apartments_com_entry,
        update_monthly_expenses,
        update_income_expense_overview,
        undo_monthly_expenses,
        undo_income_expense_overview,
        draft_email_from_template,
        attach_bill,
        send_email,
        move_file_to_gdrive,
    )
    from app.shared.data import BillData, TenantData

NO_RETRY = RetryPolicy(maximum_attempts=1)
DEFAULT_RETRY = RetryPolicy(
    maximum_attempts=5,
    backoff_coefficient=2.0,
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(minutes=1),
)
ACTIVITY_TIMEOUT = timedelta(minutes=5)


@workflow.defn
class BillProcessorWorkflow:
    @workflow.run
    async def run(self, file_path: str) -> str:
        compensations: list[tuple] = []

        try:
            # ── File processing ──────────────────────────────────────────────
            bill: BillData = await workflow.execute_activity(
                extract_bill_data,
                file_path,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=NO_RETRY,
            )

            bill = await workflow.execute_activity(
                prefix_unit_name_to_file,
                bill,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )

            bill = await workflow.execute_activity(
                suffix_date_range_to_file,
                bill,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )

            # ── Apartments.com ───────────────────────────────────────────────
            tenant: TenantData = await workflow.execute_activity(
                get_tenant_data,
                bill.unit,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )

            await workflow.execute_activity(
                enter_bill_apartments_com,
                args=[bill, tenant],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            compensations.append((undo_apartments_com_entry, [bill, tenant]))

            # ── Accounting (saga boundary) ───────────────────────────────────
            await workflow.execute_activity(
                update_monthly_expenses,
                bill,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            compensations.append((undo_monthly_expenses, [bill]))

            await workflow.execute_activity(
                update_income_expense_overview,
                bill,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            compensations.append((undo_income_expense_overview, [bill]))

        except Exception:
            for activity_fn, activity_args in reversed(compensations):
                await workflow.execute_activity(
                    activity_fn,
                    args=activity_args,
                    start_to_close_timeout=ACTIVITY_TIMEOUT,
                    retry_policy=DEFAULT_RETRY,
                )
            raise

        # ── Notification — best effort ───────────────────────────────────────
        try:
            draft_id: str = await workflow.execute_activity(
                draft_email_from_template,
                args=[bill, tenant],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            await workflow.execute_activity(
                attach_bill,
                args=[draft_id, bill],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            await workflow.execute_activity(
                send_email,
                draft_id,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
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
        except Exception:
            workflow.logger.warning("Archive failed — continuing")

        return "ok"
