# Spandan Backend

FastAPI application for Spandan AI-Assisted Appointment Booking & Private Chamber Management System.

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
uvicorn app.main:app --reload
```
