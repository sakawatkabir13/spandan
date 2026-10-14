"""Patient medical history and private report metadata.

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "medical_histories",
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("blood_group", sa.String(10), nullable=True),
        *[sa.Column(name, sa.Text(), server_default="", nullable=False) for name in ("allergies", "medications", "conditions", "surgeries", "family_history")],
        sa.Column("history_reviewed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("share_with_doctors", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "medical_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("report_type", sa.String(30), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("original_filename", sa.String(180), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_medical_reports_patient_id", "medical_reports", ["patient_id"])


def downgrade():
    op.drop_table("medical_reports")
    op.drop_table("medical_histories")
