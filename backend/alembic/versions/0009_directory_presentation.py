"""Refresh generated directory presentation without changing source facts or provenance."""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


OLD_BIO = "Academic demo account. Fees, schedules, queues and appointments on Spandan are simulated; contact the hospital for real services."
NEW_BIO = "Contact the hospital directly to confirm fees and arrange a consultation. Spandan schedules do not reserve a hospital visit."


def upgrade():
    op.execute(
        sa.text(
            "UPDATE doctor_profiles SET biography = replace(biography, :old, :new) WHERE is_demo = true"
        ).bindparams(old=OLD_BIO, new=NEW_BIO)
    )
    op.execute(
        "UPDATE chambers SET name = 'Spandan chamber' WHERE name = 'Academic demo chamber' AND doctor_id IN (SELECT id FROM doctor_profiles WHERE is_demo = true)"
    )
    op.execute(
        "UPDATE chambers SET area = district WHERE area = 'Academic demonstration' AND doctor_id IN (SELECT id FROM doctor_profiles WHERE is_demo = true)"
    )
    op.execute(
        "UPDATE chambers SET address = replace(address, 'Simulated appointment only. Public hospital address:', 'Hospital reference address:') WHERE doctor_id IN (SELECT id FROM doctor_profiles WHERE is_demo = true)"
    )
    op.execute(
        "UPDATE queue_states SET status_message = 'Contact the hospital directly to arrange a consultation.' WHERE status_message = 'Academic demo queue; no real consultation.'"
    )
    op.execute(
        "UPDATE notifications SET subject = replace(subject, 'Demo appointment', 'Appointment') WHERE subject IN ('Demo appointment booked', 'Demo appointment reminder')"
    )
    op.execute(
        "UPDATE notifications SET message = replace(replace(message, 'academic demo booking', 'Spandan booking'), 'Academic demo session:', 'Spandan session:') WHERE message LIKE '%academic demo booking%' OR message LIKE '%Academic demo session:%'"
    )


def downgrade():
    # Presentation edits are retained; restoring a database snapshot can recover original wording.
    pass
