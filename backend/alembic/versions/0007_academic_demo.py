"""Explicit academic demo identities and test payment provenance."""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "doctor_profiles",
        sa.Column("is_demo", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("doctor_profiles", sa.Column("source_url", sa.String(1000)))
    op.add_column("directory_doctors", sa.Column("demo_doctor_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_directory_demo_doctor",
        "directory_doctors",
        "doctor_profiles",
        ["demo_doctor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint("uq_directory_demo_doctor", "directory_doctors", ["demo_doctor_id"])
    op.add_column(
        "payments", sa.Column("provider", sa.String(20), server_default="cash", nullable=False)
    )
    op.add_column(
        "payments", sa.Column("is_test", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column(
        "payments", sa.Column("checkout_attempt", sa.Integer(), server_default="0", nullable=False)
    )
    op.execute("UPDATE payments SET provider = 'stripe' WHERE provider_reference IS NOT NULL")


def downgrade():
    for name in ("checkout_attempt", "is_test", "provider"):
        op.drop_column("payments", name)
    op.drop_constraint("uq_directory_demo_doctor", "directory_doctors", type_="unique")
    op.drop_constraint("fk_directory_demo_doctor", "directory_doctors", type_="foreignkey")
    op.drop_column("directory_doctors", "demo_doctor_id")
    op.drop_column("doctor_profiles", "source_url")
    op.drop_column("doctor_profiles", "is_demo")
