"""Add account security and chamber operations records."""
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    # SQL is frozen with this revision, independent of future application models.
    schema = Path(__file__).resolve().parents[1] / "operations_0005.sql"
    for statement in schema.read_text().split(";"):
        if statement.strip():
            op.execute(statement)
    op.add_column("users", sa.Column("mfa_secret", sa.String(), nullable=True))
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("mfa_last_counter", sa.Integer(), nullable=False, server_default="-1"))
    op.add_column("appointments", sa.Column("dependent_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_appointment_dependent", "appointments", "dependents", ["dependent_id"], ["id"])
    op.add_column("appointments", sa.Column("consultation_mode", sa.String(20), nullable=False, server_default="in_person"))
    op.add_column("appointments", sa.Column("video_room", sa.String(100), nullable=True))
    op.add_column("schedules", sa.Column("series_id", sa.Uuid(), nullable=True))
    op.create_index("ix_schedules_series_id", "schedules", ["series_id"])


def downgrade():
    op.drop_index("ix_schedules_series_id", "schedules")
    op.drop_column("schedules", "series_id")
    op.drop_column("appointments", "video_room")
    op.drop_column("appointments", "consultation_mode")
    op.drop_constraint("fk_appointment_dependent", "appointments", type_="foreignkey")
    op.drop_column("appointments", "dependent_id")
    for name in ("mfa_last_counter", "mfa_enabled", "mfa_secret"):
        op.drop_column("users", name)
    for name in ("availability_exceptions", "payments", "privacy_requests", "account_actions", "notifications", "waitlist_entries", "dependents"):
        op.drop_table(name)
