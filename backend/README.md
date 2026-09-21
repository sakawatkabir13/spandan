# Spandan backend

Python 3.11+ FastAPI API with PostgreSQL, SQLAlchemy and Alembic.

## Local development

From this directory, with a local PostgreSQL database available:

```bash
uv sync --frozen --extra dev
export DATABASE_URL=postgresql+asyncpg://spandan:spandan@localhost:5432/spandan
uv run alembic upgrade head
uv run python -m scripts.seed
uv run uvicorn app.main:app --reload
```

Alternatively, create a virtual environment, install `requirements.lock`, then install the project with `pip install --no-deps -e .`. The seed creates demo accounts and should only run in development.

## Checks

```bash
uv run pytest -q
uv run ruff check .
uv run alembic check
```

Pytest uses an isolated in-memory SQLite database. It does not test PostgreSQL row locks. To check real concurrent bookings, start a disposable PostgreSQL database whose name ends in `_test`, then run:

```bash
export DATABASE_URL=postgresql+asyncpg://postgres:YOUR_TEST_PASSWORD@localhost:55432/spandan_test
uv run alembic upgrade head
uv run python -m scripts.check_postgres
```

The concurrency script inserts test records. It verifies capacity limits, duplicate requests, cancellation, and serial allocation with independent transactions.

Use `uv lock` after changing dependencies, then regenerate the Docker/pip lock file:

```bash
uv export --frozen --extra dev --no-emit-project --format requirements-txt --output-file requirements.lock
```
