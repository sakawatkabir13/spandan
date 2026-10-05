"""Public directory listings without doctor accounts or booking inventory."""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "directory_doctors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listing_key", sa.String(160), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("native_name", sa.String(200)),
        sa.Column("specialty", sa.String(100), nullable=False),
        sa.Column("qualifications", sa.String(500)),
        sa.Column("institution", sa.String(200), nullable=False),
        sa.Column("division", sa.String(50), nullable=False),
        sa.Column("district", sa.String(80), nullable=False),
        sa.Column("address", sa.Text()),
        sa.Column("appointment_phone", sa.String(40)),
        sa.Column("published_hours", sa.String(300)),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("contact_source_url", sa.String(1000)),
        sa.Column("source_checked_on", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_key"),
    )
    for field in ("full_name", "specialty", "division", "district"):
        op.create_index(f"ix_directory_doctors_{field}", "directory_doctors", [field])


def downgrade():
    op.drop_table("directory_doctors")
