import asyncio
import dataclasses
from pathlib import Path
from typing import NamedTuple

from temporalio import activity

from app.shared.data import BillData

BILL_DIR = Path("~/Documents/bills_to_process").expanduser()


class _BillStub(NamedTuple):
    amount: float
    date_range: str


# Stub bill registry — replace with real apartments.com lookup
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
    await asyncio.sleep(1)
    unit = 104
    stub = _BILL_DATA[unit]
    return BillData(
        input_file_name=file_path,
        processed_file_name=file_path,
        unit=unit,
        amount=stub.amount,
        date_range=stub.date_range,
    )


@activity.defn
async def prefix_unit_name_to_file(bill: BillData) -> BillData:
    activity.logger.info(
        "Prefixing unit %s to file %s", bill.unit, bill.processed_file_name
    )
    await asyncio.sleep(0.5)
    new_name = _add_prefix(bill.processed_file_name, bill.unit)
    return dataclasses.replace(bill, processed_file_name=new_name)


@activity.defn
async def suffix_date_range_to_file(bill: BillData) -> BillData:
    activity.logger.info(
        "Suffixing date range %s to file %s", bill.date_range, bill.processed_file_name
    )
    await asyncio.sleep(0.5)
    new_name = _add_suffix(bill.processed_file_name, bill.date_range)
    return dataclasses.replace(bill, processed_file_name=new_name)
