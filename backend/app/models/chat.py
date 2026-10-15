"""Encrypted transcripts and durable, independently auditable chat operations."""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, utcnow


class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    access_fingerprint = Column(String(64), nullable=False)
    title = Column(String(80), nullable=False, default="Support conversation")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    generation_until = Column(DateTime(timezone=True), nullable=True)
    generation_id = Column(UUID(as_uuid=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "client_message_id", name="uq_chat_client_message"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_message_id = Column(UUID(as_uuid=True), nullable=True)
    role = Column(String(12), nullable=False)
    ciphertext = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class ChatAction(Base):
    __tablename__ = "chat_actions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name = Column(String(60), nullable=False)
    arguments_ciphertext = Column(Text, nullable=False)
    summary_ciphertext = Column(Text, nullable=False)
    state_hash = Column(String(64), nullable=False)
    access_fingerprint = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, default="pending", index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    step_up_hash = Column(String(64), nullable=True)
    step_up_expires_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    result_ciphertext = Column(Text, nullable=True)
    error_code = Column(String(60), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class AIUsage(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (Index("ix_ai_usage_feature_created", "feature", "created_at"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("chat_conversations.id", ondelete="SET NULL"), nullable=True
    )
    model = Column(String(150), nullable=False)
    feature = Column(String(20), nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    estimated_cost = Column(Numeric(16, 10), nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class ChatTurn(Base):
    __tablename__ = "chat_turns"
    __table_args__ = (
        UniqueConstraint("user_id", "client_message_id", name="uq_chat_turn_request"),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_message_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
