# Bill Processor

A Temporal workflow that processes tenant utility bills. Data is extracted from a PDF bill, a bill is created in the tenant facing system, internal accounting is updated, tenant notification email is sent, and bill file is archived.

## Prerequisites

- [Python 3.12+](https://python.org)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Temporal CLI](https://docs.temporal.io/cli)

## Setup

```bash
uv sync
```

## Running

**1. Start the Temporal server**
```bash
temporal server start-dev
```

**2. Start the worker** (new terminal)
```bash
uv run python -m app.worker
```

**3. Trigger the workflow** (new terminal)
```bash
uv run python -m app.run_workflow
```

The Temporal UI is available at http://localhost:8233.

## Email Approval

The workflow pauses for a human review signal before sending the tenant email.
From the Temporal UI, open the running workflow and send one of these signals:

- `approve_email` — sends the email
- `reject_email` — skips sending

The review gate times out after **35 seconds** if no signal is received.

## Simulating Errors

Each scenario is a one-line uncomment in the relevant activity file. After editing, restart the worker to pick up the change.

| Scenario | File | Line to uncomment |
|---|---|---|
| Fast-fail — no retries | `app/activities/property_management.py` | `raise ApplicationError(...)` in `get_tenant_data` |
| Saga: retry 5× then compensate | `app/activities/accounting.py` | `raise RuntimeError(...)` in `update_income_expense_overview` |
| Saga: immediate compensate | `app/activities/accounting.py` | `raise ApplicationError(...)` in `update_income_expense_overview` |
| Best-effort email failure | `app/activities/notification.py` | `raise RuntimeError(...)` in `draft_email_from_template` |
| Best-effort archive failure | `app/activities/archive.py` | `raise RuntimeError(...)` in `move_file_to_gdrive` |

Look for the `# ── DEMO:` comment block in each file to find the exact line.

## Design

See [docs/workflow-design.md](docs/workflow-design.md) for a detailed breakdown
of the workflow architecture.
