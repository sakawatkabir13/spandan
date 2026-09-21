"""Seed required medical specialization reference data.

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO specializations (id, name, description, is_active) VALUES
          ('250d44d4-8357-5214-be63-c96acfa31b49', 'General Medicine', 'Primary healthcare, diagnostics, and general medical checkups.', true),
          ('c4df3d61-c5a3-54e5-8622-a418d5530120', 'Cardiology', 'Heart diseases, blood pressure, and cardiovascular conditions.', true),
          ('934cf9d5-31cd-5697-a3c8-be1e7cbe4b7a', 'Pediatrics', 'Medical care for infants, children, and adolescents.', true),
          ('5bd7bf04-c97f-5a1b-a354-e649c74a2b16', 'Gynecology and Obstetrics', 'Women''s reproductive health, pregnancy, and childbirth.', true),
          ('b8de70f6-e1d9-5c9f-b9d2-8e865db2dc7e', 'Neurology', 'Brain, spinal cord, and nervous system disorders.', true),
          ('99c72419-dbfa-5887-a900-4f30f4478644', 'Orthopedics', 'Bone, joint, muscle, and ligament disorders.', true),
          ('f8ebada9-68f9-5ecb-bd89-f67c76756d93', 'Dermatology', 'Skin, hair, and nail disorders.', true),
          ('f474b21a-da10-58f4-9032-805680e72db2', 'Gastroenterology', 'Digestive system, stomach, liver, and bowel diseases.', true),
          ('68e18eda-aa30-5906-8cea-b8fc4420f194', 'Pulmonology / Respiratory Medicine', 'Lung and respiratory tract diseases, including asthma and COPD.', true),
          ('d2b14be0-fb4b-54f5-947c-421331cdf9e1', 'Nephrology', 'Kidney care, renal failure, and dialysis management.', true),
          ('d1ed3561-f8d2-5723-a83f-5dc3d2a4a653', 'Endocrinology', 'Hormone disorders, diabetes, and thyroid disorders.', true),
          ('5ec1593f-ee96-54dc-9a4c-e86ed70ce3ce', 'ENT', 'Ear, nose, and throat conditions and head and neck surgery.', true),
          ('9e83473e-a702-51cc-bce6-128a7b5a1291', 'Ophthalmology', 'Eye care, vision problems, and ocular surgery.', true),
          ('372a210e-8811-5605-8ad2-77b2e1065fcc', 'Psychiatry', 'Mental health disorders, assessment, and counseling.', true),
          ('6eac45b9-17fa-5505-b09d-7d9e2ef167b3', 'Emergency Medicine / ER', 'Immediate critical care for acute life-threatening conditions.', true)
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM specializations
        WHERE id IN (
          '250d44d4-8357-5214-be63-c96acfa31b49',
          'c4df3d61-c5a3-54e5-8622-a418d5530120',
          '934cf9d5-31cd-5697-a3c8-be1e7cbe4b7a',
          '5bd7bf04-c97f-5a1b-a354-e649c74a2b16',
          'b8de70f6-e1d9-5c9f-b9d2-8e865db2dc7e',
          '99c72419-dbfa-5887-a900-4f30f4478644',
          'f8ebada9-68f9-5ecb-bd89-f67c76756d93',
          'f474b21a-da10-58f4-9032-805680e72db2',
          '68e18eda-aa30-5906-8cea-b8fc4420f194',
          'd2b14be0-fb4b-54f5-947c-421331cdf9e1',
          'd1ed3561-f8d2-5723-a83f-5dc3d2a4a653',
          '5ec1593f-ee96-54dc-9a4c-e86ed70ce3ce',
          '9e83473e-a702-51cc-bce6-128a7b5a1291',
          '372a210e-8811-5605-8ad2-77b2e1065fcc',
          '6eac45b9-17fa-5505-b09d-7d9e2ef167b3'
        )
        """
    )
