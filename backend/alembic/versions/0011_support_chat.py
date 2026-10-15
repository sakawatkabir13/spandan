"""Encrypted support conversations, confirmed actions and AI usage.

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=False,
            nullable=False,
        ),
        sa.Column("access_fingerprint", sa.String(64), primary_key=False, nullable=False),
        sa.Column("title", sa.String(80), primary_key=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column("generation_until", sa.DateTime(timezone=True), primary_key=False, nullable=True),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), primary_key=False, nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), primary_key=False, nullable=True),
    )
    op.create_index(
        "ix_chat_conversations_expires_at", "chat_conversations", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_chat_conversations_user_id", "chat_conversations", ["user_id"], unique=False
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"),
            primary_key=False,
            nullable=False,
        ),
        sa.Column(
            "client_message_id", postgresql.UUID(as_uuid=True), primary_key=False, nullable=True
        ),
        sa.Column("role", sa.String(12), primary_key=False, nullable=False),
        sa.Column("ciphertext", sa.Text(), primary_key=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.UniqueConstraint("conversation_id", "client_message_id", name="uq_chat_client_message"),
    )
    op.create_index(
        "ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"], unique=False
    )
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"], unique=False)
    op.create_table(
        "chat_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_conversations.id", ondelete="SET NULL"),
            primary_key=False,
            nullable=True,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            primary_key=False,
            nullable=True,
        ),
        sa.Column("name", sa.String(60), primary_key=False, nullable=False),
        sa.Column("arguments_ciphertext", sa.Text(), primary_key=False, nullable=False),
        sa.Column("summary_ciphertext", sa.Text(), primary_key=False, nullable=False),
        sa.Column("state_hash", sa.String(64), primary_key=False, nullable=False),
        sa.Column("access_fingerprint", sa.String(64), primary_key=False, nullable=False),
        sa.Column("status", sa.String(24), primary_key=False, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column("step_up_hash", sa.String(64), primary_key=False, nullable=True),
        sa.Column(
            "step_up_expires_at", sa.DateTime(timezone=True), primary_key=False, nullable=True
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), primary_key=False, nullable=True),
        sa.Column("result_ciphertext", sa.Text(), primary_key=False, nullable=True),
        sa.Column("error_code", sa.String(60), primary_key=False, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), primary_key=False, nullable=True),
    )
    op.create_index(
        "ix_chat_actions_actor_user_id", "chat_actions", ["actor_user_id"], unique=False
    )
    op.create_index(
        "ix_chat_actions_conversation_id", "chat_actions", ["conversation_id"], unique=False
    )
    op.create_index("ix_chat_actions_expires_at", "chat_actions", ["expires_at"], unique=False)
    op.create_index("ix_chat_actions_status", "chat_actions", ["status"], unique=False)
    op.create_table(
        "ai_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            primary_key=False,
            nullable=True,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_conversations.id", ondelete="SET NULL"),
            primary_key=False,
            nullable=True,
        ),
        sa.Column("model", sa.String(150), primary_key=False, nullable=False),
        sa.Column("feature", sa.String(20), primary_key=False, nullable=False),
        sa.Column("input_tokens", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("output_tokens", sa.Integer(), primary_key=False, nullable=False),
        sa.Column("estimated_cost", sa.Numeric(16, 10), primary_key=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    )
    op.create_index("ix_ai_usage_created_at", "ai_usage", ["created_at"], unique=False)
    op.create_index(
        "ix_ai_usage_feature_created", "ai_usage", ["feature", "created_at"], unique=False
    )
    op.create_index("ix_ai_usage_user_id", "ai_usage", ["user_id"], unique=False)
    op.create_table(
        "chat_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=False,
            nullable=False,
        ),
        sa.Column(
            "client_message_id", postgresql.UUID(as_uuid=True), primary_key=False, nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.UniqueConstraint("user_id", "client_message_id", name="uq_chat_turn_request"),
    )
    op.create_index("ix_chat_turns_created_at", "chat_turns", ["created_at"], unique=False)
    op.create_index("ix_chat_turns_user_id", "chat_turns", ["user_id"], unique=False)


def downgrade():
    op.drop_table("chat_turns")
    op.drop_table("ai_usage")
    op.drop_table("chat_actions")
    op.drop_table("chat_messages")
    op.drop_table("chat_conversations")
