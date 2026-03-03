import asyncio

from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.shared.data import BillData, TenantData

# Stub tenant registry — replace with real apartments.com lookup
_TENANTS: dict[int, TenantData] = {
    104: TenantData(name="Jane Smith", email="jane.smith@example.com"),
}


@activity.defn
async def get_tenant_data(unit: int) -> TenantData:
    activity.logger.info("Fetching tenant data for unit %s", unit)
    # ── DEMO: fast-fail (no retries) ─────────────────────────────────────────
    # raise ApplicationError("Unknown unit — non-retryable fast fail", non_retryable=True)
    # ─────────────────────────────────────────────────────────────────────────
    await asyncio.sleep(3)
    tenant = _TENANTS.get(unit)
    if tenant is None:
        raise ApplicationError(f"No tenant found for unit {unit}", non_retryable=True)
    return tenant


@activity.defn
async def enter_bill_apartments_com(bill: BillData, tenant: TenantData) -> str:
    activity.logger.info(
        "Entering bill on apartments.com: unit=%s amount=%s tenant=%s",
        bill.unit,
        bill.amount,
        tenant.name,
    )
    await asyncio.sleep(3)
    confirmation = f"APT-{bill.unit}-{bill.date_range}"
    activity.logger.info("Apartments.com confirmation: %s", confirmation)
    return confirmation


@activity.defn
async def undo_apartments_com_entry(bill: BillData, tenant: TenantData) -> None:
    activity.logger.info(
        "COMPENSATING: removing apartments.com entry for unit=%s date_range=%s",
        bill.unit,
        bill.date_range,
    )
    await asyncio.sleep(3)
