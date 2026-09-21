"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-21 02:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('role', sa.Enum('PATIENT', 'DOCTOR', 'ASSISTANT', 'ADMINISTRATOR', name='userrole'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_phone_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_email_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('phone_number')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_phone_number'), 'users', ['phone_number'], unique=True)

    # Patient profiles table
    op.create_table(
        'patient_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('gender', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('emergency_contact', sa.String(), nullable=True),
        sa.Column('profile_photo_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_patient_profiles_id'), 'patient_profiles', ['id'], unique=False)

    # Doctor profiles table
    op.create_table(
        'doctor_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('profile_photo_url', sa.String(), nullable=True),
        sa.Column('medical_registration_number', sa.String(), nullable=False),
        sa.Column('biography', sa.Text(), nullable=True),
        sa.Column('current_workplace', sa.String(), nullable=True),
        sa.Column('years_of_experience', sa.Integer(), nullable=False, default=0),
        sa.Column('verification_status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', 'SUSPENDED', name='doctorverificationstatus'), nullable=False),
        sa.Column('verification_notes', sa.Text(), nullable=True),
        sa.Column('verified_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
        sa.UniqueConstraint('medical_registration_number')
    )
    op.create_index(op.f('ix_doctor_profiles_id'), 'doctor_profiles', ['id'], unique=False)
    op.create_index(op.f('ix_doctor_profiles_full_name'), 'doctor_profiles', ['full_name'], unique=False)
    op.create_index(op.f('ix_doctor_profiles_current_workplace'), 'doctor_profiles', ['current_workplace'], unique=False)
    op.create_index(op.f('ix_doctor_profiles_verification_status'), 'doctor_profiles', ['verification_status'], unique=False)

    # Qualifications table
    op.create_table(
        'qualifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('institution', sa.String(), nullable=False),
        sa.Column('country', sa.String(), nullable=True),
        sa.Column('completion_year', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctor_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_qualifications_id'), 'qualifications', ['id'], unique=False)
    op.create_index(op.f('ix_qualifications_doctor_id'), 'qualifications', ['doctor_id'], unique=False)

    # Specializations table
    op.create_table(
        'specializations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_specializations_id'), 'specializations', ['id'], unique=False)
    op.create_index(op.f('ix_specializations_name'), 'specializations', ['name'], unique=True)

    # Doctor specializations link table
    op.create_table(
        'doctor_specializations',
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('specialization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctor_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['specialization_id'], ['specializations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('doctor_id', 'specialization_id')
    )

    # Assistant assignments table
    op.create_table(
        'assistant_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assistant_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('can_manage_schedules', sa.Boolean(), nullable=False, default=True),
        sa.Column('can_manage_appointments', sa.Boolean(), nullable=False, default=True),
        sa.Column('can_update_queue', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctor_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assistant_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assistant_assignments_id'), 'assistant_assignments', ['id'], unique=False)
    op.create_index(op.f('ix_assistant_assignments_doctor_id'), 'assistant_assignments', ['doctor_id'], unique=False)
    op.create_index(op.f('ix_assistant_assignments_assistant_user_id'), 'assistant_assignments', ['assistant_user_id'], unique=False)

    # Chambers table
    op.create_table(
        'chambers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('address', sa.String(), nullable=False),
        sa.Column('district', sa.String(), nullable=False),
        sa.Column('area', sa.String(), nullable=False),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('consultation_fee', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('follow_up_fee', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('average_consultation_minutes', sa.Integer(), nullable=False, default=15),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctor_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chambers_id'), 'chambers', ['id'], unique=False)
    op.create_index(op.f('ix_chambers_doctor_id'), 'chambers', ['doctor_id'], unique=False)
    op.create_index(op.f('ix_chambers_district'), 'chambers', ['district'], unique=False)
    op.create_index(op.f('ix_chambers_area'), 'chambers', ['area'], unique=False)

    # Schedules table
    op.create_table(
        'schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chamber_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('schedule_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('maximum_patients', sa.Integer(), nullable=False),
        sa.Column('average_consultation_minutes', sa.Integer(), nullable=False, default=15),
        sa.Column('booking_open_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('booking_close_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum('DRAFT', 'OPEN', 'FULL', 'CLOSED', 'COMPLETED', 'CANCELLED', name='schedulestatus'), nullable=False),
        sa.Column('cancellation_reason', sa.String(), nullable=True),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctor_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['chamber_id'], ['chambers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_schedules_id'), 'schedules', ['id'], unique=False)
    op.create_index(op.f('ix_schedules_doctor_id'), 'schedules', ['doctor_id'], unique=False)
    op.create_index(op.f('ix_schedules_chamber_id'), 'schedules', ['chamber_id'], unique=False)
    op.create_index(op.f('ix_schedules_schedule_date'), 'schedules', ['schedule_date'], unique=False)
    op.create_index(op.f('ix_schedules_status'), 'schedules', ['status'], unique=False)

    # Queue states table
    op.create_table(
        'queue_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('schedule_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('current_serial', sa.Integer(), nullable=False, default=0),
        sa.Column('delay_minutes', sa.Integer(), nullable=False, default=0),
        sa.Column('status_message', sa.String(), nullable=True),
        sa.Column('updated_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['schedule_id'], ['schedules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('schedule_id')
    )
    op.create_index(op.f('ix_queue_states_id'), 'queue_states', ['id'], unique=False)

    # Appointments table
    op.create_table(
        'appointments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chamber_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('schedule_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('serial_number', sa.Integer(), nullable=False),
        sa.Column('booking_source', sa.Enum('ONLINE', 'ASSISTANT', 'PHONE', 'WALK_IN', 'DOCTOR', name='bookingsource'), nullable=False),
        sa.Column('appointment_status', sa.Enum('BOOKED', 'CONFIRMED', 'CHECKED_IN', 'WAITING', 'IN_CONSULTATION', 'COMPLETED', 'SKIPPED', 'ABSENT', 'CANCELLED', name='appointmentstatus'), nullable=False),
        sa.Column('estimated_consultation_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_consultation_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_consultation_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('patient_note', sa.Text(), nullable=True),
        sa.Column('cancellation_reason', sa.String(), nullable=True),
        sa.Column('booked_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patient_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctor_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['chamber_id'], ['chambers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['schedule_id'], ['schedules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['booked_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('schedule_id', 'serial_number', name='uq_schedule_serial')
    )
    op.create_index(op.f('ix_appointments_id'), 'appointments', ['id'], unique=False)
    op.create_index(op.f('ix_appointments_patient_id'), 'appointments', ['patient_id'], unique=False)
    op.create_index(op.f('ix_appointments_doctor_id'), 'appointments', ['doctor_id'], unique=False)
    op.create_index(op.f('ix_appointments_schedule_id'), 'appointments', ['schedule_id'], unique=False)
    op.create_index(op.f('ix_appointments_appointment_status'), 'appointments', ['appointment_status'], unique=False)

    # Specialist recommendations table
    op.create_table(
        'specialist_recommendations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('symptoms_text', sa.Text(), nullable=False),
        sa.Column('recommended_specialization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('recommended_specialization_name', sa.String(), nullable=False),
        sa.Column('alternative_specialization_name', sa.String(), nullable=True),
        sa.Column('urgency_level', sa.Enum('ROUTINE', 'SOON', 'URGENT', 'EMERGENCY', name='urgencylevel'), nullable=False),
        sa.Column('reasoning_summary', sa.Text(), nullable=True),
        sa.Column('safety_message', sa.Text(), nullable=True),
        sa.Column('emergency_warning', sa.Text(), nullable=True),
        sa.Column('disclaimer', sa.Text(), nullable=True),
        sa.Column('model_identifier', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['patient_profiles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recommended_specialization_id'], ['specializations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_specialist_recommendations_id'), 'specialist_recommendations', ['id'], unique=False)
    op.create_index(op.f('ix_specialist_recommendations_patient_id'), 'specialist_recommendations', ['patient_id'], unique=False)

    # Audit logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_user_id'), 'audit_logs', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_type'), 'audit_logs', ['entity_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('specialist_recommendations')
    op.drop_table('appointments')
    op.drop_table('queue_states')
    op.drop_table('schedules')
    op.drop_table('chambers')
    op.drop_table('assistant_assignments')
    op.drop_table('doctor_specializations')
    op.drop_table('specializations')
    op.drop_table('qualifications')
    op.drop_table('doctor_profiles')
    op.drop_table('patient_profiles')
    op.drop_table('users')

    sa.Enum(name='urgencylevel').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='appointmentstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='bookingsource').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='schedulestatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='doctorverificationstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='userrole').drop(op.get_bind(), checkfirst=True)
