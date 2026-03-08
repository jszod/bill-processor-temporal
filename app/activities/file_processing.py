import asyncio
import dataclasses
from pathlib import Path
from typing import NamedTuple

from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.shared.data import BillData

BILL_DIR = Path("~/Documents/bills_to_process").expanduser()


class _BillStub(NamedTuple):
    amount: float
    date_range: str


# Stub registry — replaces real PDF extraction; keyed by unit number for demo purposes
_BILL_DATA: dict[int, _BillStub] = {
    104: _BillStub(amount=134.25, date_range="2026_01-03"),
}


def _add_prefix(file_name: str, unit: int) -> str:
    p = Path(file_name)
    return str(p.parent / f"{unit}_{p.name}")


def _add_suffix(file_name: str, date_range: str) -> str:
    p = Path(file_name)
    return str(p.parent / f"{p.stem}_{date_range}{p.suffix}")


@activity.defn
async def extract_bill_data(file_path: str) -> BillData:
    activity.logger.info("Extracting bill data from %s", file_path)
    await asyncio.sleep(3)
    unit = 104
    stub = _BILL_DATA.get(unit)
    if stub is None:
        # Non-retryable error — ApplicationError with non_retryable=True tells Temporal to skip retries and fail immediately
        raise ApplicationError(f"No bill data for unit {unit}", non_retryable=True)
    return BillData(
        input_file_name=file_path,
        processed_file_name=file_path,
        unit=unit,
        amount=stub.amount,
        date_range=stub.date_range,
    )


@activity.defn
async def add_unit_and_date_range_to_file(bill: BillData) -> BillData:
    activity.logger.info(
        "Renaming file for unit=%s date_range=%s: %s",
        bill.unit,
        bill.date_range,
        bill.processed_file_name,
    )
    await asyncio.sleep(3)
    new_name = _add_prefix(bill.processed_file_name, bill.unit)
    new_name = _add_suffix(new_name, bill.date_range)
    return dataclasses.replace(bill, processed_file_name=new_name)
