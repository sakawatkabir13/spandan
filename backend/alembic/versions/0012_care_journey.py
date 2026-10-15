"""Patient charts, visit summaries, discovery and reserved waitlist offers."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("medical_reports", sa.Column("dependent_id", UUID(as_uuid=True), sa.ForeignKey("dependents.id", ondelete="CASCADE")))
    op.create_index("ix_medical_reports_dependent_id", "medical_reports", ["dependent_id"])
    op.add_column("medical_reports", sa.Column("share_with_doctors", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("dependent_medical_histories",
        sa.Column("dependent_id", UUID(as_uuid=True), sa.ForeignKey("dependents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("blood_group", sa.String(10)),
        *[sa.Column(name, sa.Text(), server_default="", nullable=False) for name in ("allergies", "medications", "conditions", "surgeries", "family_history")],
        sa.Column("history_reviewed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("share_with_doctors", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("appointment_sharing",
        sa.Column("appointment_id", UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("share_history", sa.Boolean(), nullable=False), sa.Column("report_ids", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("visit_summaries",
        sa.Column("appointment_id", UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("doctor_id", UUID(as_uuid=True), sa.ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False),
        *[sa.Column(name, sa.Text(), nullable=False) for name in ("summary", "prescription", "follow_up_instructions")],
        sa.Column("follow_up_date", sa.Date()), sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("favorite_doctors",
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("doctor_id", UUID(as_uuid=True), sa.ForeignKey("doctor_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("booking_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doctor_id", UUID(as_uuid=True), sa.ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    for column in ("patient_id", "doctor_id", "created_at"):
        op.create_index(f"ix_booking_events_{column}", "booking_events", [column])
    op.add_column("doctor_profiles", sa.Column("languages", sa.String(200), nullable=False, server_default=""))
    op.add_column("doctor_profiles", sa.Column("minimum_patient_age", sa.Integer()))
    op.add_column("doctor_profiles", sa.Column("maximum_patient_age", sa.Integer()))
    op.add_column("schedules", sa.Column("confirmed_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")))
    op.add_column("schedules", sa.Column("confirmed_at", sa.DateTime(timezone=True)))
    op.add_column("waitlist_entries", sa.Column("offered_at", sa.DateTime(timezone=True)))
    op.add_column("waitlist_entries", sa.Column("offer_expires_at", sa.DateTime(timezone=True)))
    op.add_column("waitlist_entries", sa.Column("appointment_id", UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="SET NULL")))


def downgrade():
    for column in ("appointment_id", "offer_expires_at", "offered_at"):
        op.drop_column("waitlist_entries", column)
    for column in ("confirmed_at", "confirmed_by_user_id"):
        op.drop_column("schedules", column)
    for column in ("maximum_patient_age", "minimum_patient_age", "languages"):
        op.drop_column("doctor_profiles", column)
    for table in ("booking_events", "favorite_doctors", "visit_summaries", "appointment_sharing", "dependent_medical_histories"):
        op.drop_table(table)
    op.drop_column("medical_reports", "share_with_doctors")
    op.drop_index("ix_medical_reports_dependent_id", table_name="medical_reports")
    op.drop_column("medical_reports", "dependent_id")
