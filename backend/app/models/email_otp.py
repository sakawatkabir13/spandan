from sqlalchemy import Column, DateTime, Integer, String

from app.db.base import Base


class EmailOTP(Base):
    """No account or plaintext code is stored before mailbox ownership is proven."""

    __tablename__ = "email_otps"
    email = Column(String(320), primary_key=True)
    purpose = Column(String(20), primary_key=True)
    nonce = Column(String(36), nullable=False)
    token_hash = Column(String(64), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    window_started_at = Column(DateTime(timezone=True), nullable=False)
    requests_in_window = Column(Integer, nullable=False, default=1)
