import asyncio

from temporalio import activity

from app.shared.data import BillData


@activity.defn
async def move_file_to_gdrive(bill: BillData) -> None:
    activity.logger.info("Moving %s to Google Drive", bill.processed_file_name)
    # ── DEMO: best-effort failure (workflow still completes) ──────────────────
    # raise RuntimeError("Google Drive API unavailable")
    # ─────────────────────────────────────────────────────────────────────────
    await asyncio.sleep(3)
    activity.logger.info("File archived successfully")
