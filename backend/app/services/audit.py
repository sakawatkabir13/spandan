from app.models.audit import AuditLog


def audit(db, user, action, entity, fields=None):
    """Record field names only, never passwords, tokens, or health text."""
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action=action,
            entity_type=entity.__tablename__,
            entity_id=str(entity.id),
            metadata_json={"changed_fields": sorted(fields or [])},
        )
    )
