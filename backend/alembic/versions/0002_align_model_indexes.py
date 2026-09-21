"""Align model indexes with the initial PostgreSQL schema.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

INDEXED_COLUMNS = [
    ("doctor_profiles", "medical_registration_number"),
    ("doctor_profiles", "user_id"),
    ("patient_profiles", "user_id"),
    ("queue_states", "schedule_id"),
]
REDUNDANT_CONSTRAINTS = [("users", "email"), ("users", "phone_number"), ("specializations", "name")]


def upgrade():
    # Build equivalent unique indexes before removing the old constraints.
    for table, column in INDEXED_COLUMNS:
        op.create_index(f"ix_{table}_{column}", table, [column], unique=True)
        op.drop_constraint(f"{table}_{column}_key", table, type_="unique")
    for table, column in REDUNDANT_CONSTRAINTS:
        # These columns already have a unique index from revision 0001.
        op.drop_constraint(f"{table}_{column}_key", table, type_="unique")
    op.create_index("ix_appointments_chamber_id", "appointments", ["chamber_id"])


def downgrade():
    op.drop_index("ix_appointments_chamber_id", table_name="appointments")
    for table, column in REDUNDANT_CONSTRAINTS:
        op.create_unique_constraint(f"{table}_{column}_key", table, [column])
    for table, column in INDEXED_COLUMNS:
        op.create_unique_constraint(f"{table}_{column}_key", table, [column])
        op.drop_index(f"ix_{table}_{column}", table_name=table)
