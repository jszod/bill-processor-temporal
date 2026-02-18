# Bill Processor

## Running the app

Each step requires its own terminal.

**1. Start the Temporal server**
```bash
temporal server start-dev
```

**2. Start the worker**
```bash
uv run python -m app.run_worker
```

**3. Run the workflow**
```bash
uv run python -m app.run_workflow
```
