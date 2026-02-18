# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the worker (requires Temporal server running)
python -m app.worker

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/path/to/test_file.py::test_name
```

Temporal server must be running locally at `localhost:7233` before starting the worker. Use [Temporal CLI](https://docs.temporal.io/cli) (`temporal server start-dev`) to run it locally.

## Architecture

This is a **Temporal workflow application** that processes PDF bills from `~/Documents/bills_to_process/`.

The execution flow is:
1. **Worker** (`app/worker.py`) connects to Temporal at `localhost:7233` on task queue `"bill-processor"` and registers workflows and activities
2. **Workflow** (`app/workflows.py`) — `ProcessBillWorkflow` orchestrates activity execution; workflows must not perform I/O directly
3. **Activities** (`app/activities.py`) — contain the actual I/O logic (`extract_bill_data`, `update_file_name`); decorated with `@activity.defn`
4. **Shared** (`app/shared/data.py`) — `Bill` dataclass and `BILL_DIR` path used across layers

Private helper functions in activity files use a `_` prefix (e.g., `_build_processed_file_name`) and are defined above the activity functions that call them.

The `Bill` dataclass fields (`input_file_name`, `processed_file_name`, `amount`, `unit`, `date_range`) are passed between activities via the workflow — Temporal serializes these automatically since `Bill` is a plain dataclass.

## Current state

The file processing activities in `app/activities/file_processing.py` are implemented:
- `extract_bill_data` — stubs bill data from `_BILL_DATA` (unit 104 hardcoded)
- `prefix_unit_name_to_file` — prepends unit number to filename
- `suffix_date_range_to_file` — appends date range to filename

## Next steps

The following activities referenced in `app/workflows.py` are not yet implemented:
- `get_tenant_data`
- `enter_bill_apartments_com` / `undo_apartments_com_entry`
- `update_monthly_expenses` / `undo_monthly_expenses`
- `update_income_expense_overview` / `undo_income_expense_overview`
- `draft_email_from_template`, `attach_bill`, `send_email`
- `move_file_to_gdrive`

There is also a name mismatch to fix: `run_workflow.py` references `ProcessBillWorkflow` but the class in `workflows.py` is `BillProcessorWorkflow`.
