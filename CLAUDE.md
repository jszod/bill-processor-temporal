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

A Temporal workflow application that processes PDF bills from `~/Documents/bills_to_process/`. See `docs/workflow-design.md` for the full architecture, activity sequence, data models, and retry policy.

Private helper functions in activity files use a `_` prefix (e.g., `_build_processed_file_name`) and are defined above the activity functions that call them.
