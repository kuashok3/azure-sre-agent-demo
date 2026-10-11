# Contributing

## Workflow
1. Branch from `main`: `feature/<short-name>` or `fix/<short-name>`.
2. Make the change **and** update the matching docs/runbooks (code, docs and telemetry must agree).
3. Run locally before pushing:
   ```bash
   ruff check . && ruff format --check .
   pytest -m "not integration"
   docker compose up -d --build
   pytest -m integration
   python scripts/smoke_test.py
   ```
4. Open a pull request. CI must be green and one teammate must review.

## Conventions
- Python 3.12+, FastAPI, formatted with `ruff format` (line length 100).
- Expected failures raise an `AppError` subclass with a stable `error_code`.
- Log with `logger.info("message", extra={"event": "snake_case_event", ...})`.
  Never log secrets, tokens or full request bodies.
- New failure scenarios: add a `FaultSpec`, a unit test, a check in
  `scripts/validate_faults.py`, and a runbook entry.
