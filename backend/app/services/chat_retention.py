"""Remove transcript content on expiry independently of the feature flag."""

from datetime import timedelta

from sqlalchemy import delete, select, update

from app.models.chat import ChatAction, ChatConversation, ChatMessage, ChatTurn


async def cleanup_chat(db, now):
    await db.execute(
        update(ChatAction)
        .where(ChatAction.status == "pending", ChatAction.expires_at <= now)
        .values(status="expired", step_up_hash=None, step_up_expires_at=None)
    )
    expired = select(ChatConversation.id).where(
        (ChatConversation.expires_at <= now) | ChatConversation.deleted_at.is_not(None)
    )
    await db.execute(
        update(ChatAction)
        .where(ChatAction.conversation_id.in_(expired), ChatAction.status == "pending")
        .values(status="cancelled", step_up_hash=None, step_up_expires_at=None)
    )
    await db.execute(delete(ChatMessage).where(ChatMessage.conversation_id.in_(expired)))
    await db.execute(
        update(ChatConversation)
        .where(ChatConversation.id.in_(expired))
        .values(deleted_at=now, generation_id=None, generation_until=None)
    )
    await db.execute(delete(ChatTurn).where(ChatTurn.created_at < now - timedelta(days=2)))
