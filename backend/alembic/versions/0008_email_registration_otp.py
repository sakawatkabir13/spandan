"""Email ownership challenges before registration and password reset."""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_otps",
        sa.Column("email", sa.String(320), primary_key=True),
        sa.Column("purpose", sa.String(20), primary_key=True),
        sa.Column("nonce", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requests_in_window", sa.Integer(), nullable=False),
    )
    op.create_index("ix_email_otps_expires_at", "email_otps", ["expires_at"])


def downgrade():
    op.drop_index("ix_email_otps_expires_at", "email_otps")
    op.drop_table("email_otps")
