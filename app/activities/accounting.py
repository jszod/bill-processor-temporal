import asyncio

from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.shared.data import BillData


@activity.defn
async def update_monthly_expenses(bill: BillData) -> None:
    activity.logger.info(
        "Updating monthly expenses sheet: unit=%s amount=%s date_range=%s",
        bill.unit,
        bill.amount,
        bill.date_range,
    )
    await asyncio.sleep(3)


@activity.defn
async def update_income_expense_overview(bill: BillData) -> None:
    activity.logger.info(
        "Updating income/expense overview sheet: unit=%s amount=%s",
        bill.unit,
        bill.amount,
    )
    # Demo hooks — uncomment to simulate failures and trigger saga or best-effort paths
    # raise RuntimeError("Sheets API unavailable")  # retries 5x, then saga
    # raise ApplicationError("Quota exceeded", non_retryable=True)  # immediate saga failure AppError from Temporal
    await asyncio.sleep(3)


# Compensation activity — paired reversal for update_monthly_expenses
@activity.defn
async def undo_monthly_expenses(bill: BillData) -> None:
    activity.logger.info(
        "COMPENSATING: removing monthly expenses entry for unit=%s date_range=%s",
        bill.unit,
        bill.date_range,
    )
    await asyncio.sleep(3)


# Compensation activity — paired reversal for update_income_expense_overview
@activity.defn
async def undo_income_expense_overview(bill: BillData) -> None:
    activity.logger.info(
        "COMPENSATING: removing income/expense overview entry for unit=%s date_range=%s",
        bill.unit,
        bill.date_range,
    )
    await asyncio.sleep(3)
