"""Device sessions, refresh token rotation and single-use MFA recovery codes."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("account_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False), sa.Column("refresh_digest", sa.String(64), nullable=False),
        sa.Column("user_agent", sa.String(250), nullable=False), sa.Column("ip_address", sa.String(64)),
        *[sa.Column(name, sa.DateTime(timezone=True), nullable=False) for name in ("created_at", "last_seen_at", "expires_at")],
        sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_index("ix_account_sessions_user_id", "account_sessions", ["user_id"])
    op.create_table("mfa_recovery_codes",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("digest", sa.String(64), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("mfa_recovery_codes")
    op.drop_table("account_sessions")
