import asyncio
import re
from pathlib import Path

from temporalio.client import Client
from temporalio.client import WorkflowFailureError

from app.shared.data import WorkflowResult
from app.workflows import BillProcessorWorkflow

_BAR = "━" * 38


def _print_result(result: WorkflowResult) -> None:
    b = result.bill
    print(_BAR)
    print("  BILL PROCESSED")
    print(_BAR)
    print(f"  File:    {b.processed_file_name}")
    print(f"  Unit:    {b.unit}")
    print(f"  Amount:  ${b.amount:.2f}")
    print(f"  Period:  {b.date_range}")
    print(f"  Email:   {result.email_status}")
    print(f"  Archive: {result.archive_status}")
    print(_BAR)


def _print_failure(message: str) -> None:
    print(_BAR)
    print("  WORKFLOW FAILED")
    print(_BAR)
    print(f"  Error: {message}")
    print(_BAR)


# Deterministic workflow ID — derived from the filename so re-running the same file deduplicates via Temporal's ID reuse policy
def _workflow_id(file_path: str) -> str:
    name = Path(file_path).name
    sanitized = re.sub(r"[^a-zA-Z0-9_\-.]", "_", name)
    return f"bill-{sanitized}"


async def main():
    file_path = "bill.pdf"
    client = await Client.connect("localhost:7233")
    try:
        # Trigger workflow — submits to the task queue and blocks until the workflow returns a result
        result: WorkflowResult = await client.execute_workflow(
            BillProcessorWorkflow.run,
            file_path,
            id=_workflow_id(file_path),
            task_queue="bill-processor",
            # id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
        )
        _print_result(result)
    # Workflow failure handling — unwraps the cause chain to surface the original root error message
    except WorkflowFailureError as e:
        cause: BaseException = e.cause
        while cause.__cause__ is not None:
            cause = cause.__cause__
        _print_failure(str(cause))


if __name__ == "__main__":
    asyncio.run(main())
