import asyncio
import logging

import temporalio.activity
import temporalio.workflow
from temporalio.client import Client
from temporalio.worker import Worker

from app.activities import (
    add_unit_and_date_range_to_file,
    attach_bill,
    draft_email_from_template,
    enter_bill_apartments_com,
    extract_bill_data,
    get_tenant_data,
    move_file_to_gdrive,
    send_email,
    undo_apartments_com_entry,
    undo_income_expense_overview,
    undo_monthly_expenses,
    update_income_expense_overview,
    update_monthly_expenses,
)
from app.workflows import BillProcessorWorkflow


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    temporalio.activity.logger.activity_info_on_message = False
    temporalio.workflow.logger.workflow_info_on_message = False

    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="bill-processor",
        workflows=[BillProcessorWorkflow],
        activities=[
            extract_bill_data,
            add_unit_and_date_range_to_file,
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
        ],
    )
    print("Worker started, press ctrl-c to exit")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
