"""Browser-test server: capture outbound mail locally, with no OTP verification bypass."""

import hashlib
import json
import os
from pathlib import Path

import uvicorn
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.services import mail


def main():
    if settings.APP_ENV.lower() == "production" or not (
        make_url(settings.DATABASE_URL).database or ""
    ).startswith("spandan_test"):
        raise RuntimeError(
            "Browser mail capture requires a spandan_test database outside production"
        )
    inbox = Path(os.environ.get("E2E_MAILBOX_DIR", "/tmp/spandan-e2e-mailbox"))
    inbox.mkdir(mode=0o700, parents=True, exist_ok=True)
    settings.SMTP_HOST = "test.invalid"
    settings.SMTP_USERNAME = ""
    settings.SMTP_PASSWORD = ""

    def capture(recipient, subject, body):
        destination = inbox / (hashlib.sha256(recipient.lower().encode()).hexdigest() + ".json")
        destination.write_text(json.dumps({"subject": subject, "body": body}))
        destination.chmod(0o600)

    mail.send_email = capture
    uvicorn.run("app.main:app", host="127.0.0.1", port=18000)


if __name__ == "__main__":
    main()
