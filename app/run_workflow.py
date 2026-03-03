import asyncio
import re
from pathlib import Path

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy

from app.workflows import BillProcessorWorkflow


def _workflow_id(file_path: str) -> str:
    name = Path(file_path).name
    sanitized = re.sub(r"[^a-zA-Z0-9_\-.]", "_", name)
    return f"bill-{sanitized}"


async def main():
    file_path = "bill.pdf"
    client = await Client.connect("localhost:7233")
    result = await client.execute_workflow(
        BillProcessorWorkflow.run,
        file_path,
        id=_workflow_id(file_path),
        task_queue="bill-processor",
        # id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
    )
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
