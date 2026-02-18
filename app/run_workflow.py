import asyncio

from temporalio.client import Client

from app.workflows import BillProcessorWorkflow


async def main():
    print("Workflow started")
    client = await Client.connect("localhost:7233")
    result = await client.execute_workflow(
        BillProcessorWorkflow.run,
        "bill.pdf",
        id="bill-processor-workflow",
        task_queue="bill-processor",
    )
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
