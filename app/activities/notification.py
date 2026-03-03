import asyncio

from temporalio import activity

from app.shared.data import BillData, TenantData


@activity.defn
async def draft_email_from_template(bill: BillData, tenant: TenantData, idempotency_key: str) -> str:
    activity.logger.info(
        "Drafting bill email to %s for unit=%s amount=%s",
        tenant.email,
        bill.unit,
        bill.amount,
    )
    await asyncio.sleep(3)
    draft_id = idempotency_key  # stable across retries
    activity.logger.info("Created draft %s", draft_id)
    return draft_id


@activity.defn
async def attach_bill(draft_id: str, bill: BillData) -> None:
    activity.logger.info("Attaching %s to draft %s", bill.processed_file_name, draft_id)
    await asyncio.sleep(3)


@activity.defn
async def send_email(draft_id: str) -> None:
    activity.logger.info("Sending email draft %s", draft_id)
    await asyncio.sleep(3)
