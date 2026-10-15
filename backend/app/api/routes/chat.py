from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update

from app.api.dependencies.auth import get_current_active_user
from app.core.exceptions import SpandanException, create_success_response
from app.core.time import aware
from app.db.base import utcnow
from app.db.session import get_db
from app.models.chat import ChatAction, ChatConversation, ChatMessage
from app.schemas.chat import ConfirmRequest, ConversationCreate, MessageCreate, StepUpRequest
from app.services.chat_actions import action_view, confirm_action, owned_action, step_up
from app.services.chat_mcp import mcp_client
from app.services.chat_security import (
    conversation_for_user,
    execution_conversation,
    fingerprint,
    require_chat,
    unseal,
)
from app.services.chat_service import generate, reserve_turn

router = APIRouter(prefix="/chat", tags=["Spandan Assistant"], dependencies=[Depends(require_chat)])


@router.get("/conversations")
async def list_conversations(user=Depends(get_current_active_user), db=Depends(get_db)):
    access = await fingerprint(db, user)
    rows = await db.scalars(
        select(ChatConversation)
        .where(
            ChatConversation.user_id == user.id,
            ChatConversation.deleted_at.is_(None),
            ChatConversation.expires_at > utcnow(),
            ChatConversation.access_fingerprint == access,
        )
        .order_by(ChatConversation.created_at.desc())
        .limit(50)
    )
    return create_success_response(
        "Conversations.",
        [
            {"id": x.id, "title": x.title, "created_at": x.created_at, "expires_at": x.expires_at}
            for x in rows
        ],
    )


@router.post("/conversations", status_code=201)
async def create_conversation(
    request: ConversationCreate, user=Depends(get_current_active_user), db=Depends(get_db)
):
    if not request.provider_consent:
        raise SpandanException(
            "CONSENT_REQUIRED", "Agree to Amazon Bedrock processing before starting chat.", 400
        )
    row = ChatConversation(
        id=uuid4(),
        user_id=user.id,
        access_fingerprint=await fingerprint(db, user),
        expires_at=utcnow() + timedelta(days=30),
    )
    db.add(row)
    await db.commit()
    return create_success_response(
        "Conversation created.", {"id": row.id, "title": row.title, "expires_at": row.expires_at}
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)
):
    row = await conversation_for_user(db, user, conversation_id)
    messages = await db.scalars(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == row.id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )
    actions = list(
        await db.scalars(
            select(ChatAction).where(
                ChatAction.conversation_id == row.id, ChatAction.actor_user_id == user.id
            )
        )
    )
    action_map = {str(a.id): action_view(a) for a in actions}
    output = []
    for message in messages:
        payload = unseal(message.ciphertext)
        cards = payload.get("cards", [])
        for card in cards:
            proposal = card.get("data", {}).get("proposal")
            if proposal and proposal["id"] in action_map:
                card["data"]["proposal"] = action_map[proposal["id"]]
        output.append(
            {
                "id": message.id,
                "role": message.role,
                "text": payload.get("text", ""),
                "cards": cards,
                "created_at": message.created_at,
            }
        )
    return create_success_response(
        "Conversation.",
        {
            "id": row.id,
            "title": row.title,
            "messages": output,
            "expires_at": row.expires_at,
            "generating": bool(
                row.generation_id and row.generation_until
                and aware(row.generation_until) > utcnow()
            ),
        },
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)
):
    # Ownership permits deletion even after a role change invalidates conversation access.
    row = await db.scalar(
        select(ChatConversation)
        .where(ChatConversation.id == conversation_id, ChatConversation.user_id == user.id)
        .with_for_update()
    )
    if not row:
        raise SpandanException("NOT_FOUND", "Conversation not found.", 404)
    row.deleted_at = utcnow()
    row.generation_id = None
    row.generation_until = None
    await db.execute(
        update(ChatAction)
        .where(ChatAction.conversation_id == row.id, ChatAction.status == "pending")
        .values(status="cancelled")
    )
    # Physically remove transcript content immediately; durable action audits remain separate.
    from sqlalchemy import delete

    await db.execute(delete(ChatMessage).where(ChatMessage.conversation_id == row.id))
    await db.commit()
    return create_success_response("Conversation deleted.")


@router.post("/conversations/{conversation_id}/stop")
async def stop_conversation(
    conversation_id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)
):
    row = await conversation_for_user(db, user, conversation_id, lock=True)
    row.generation_id = None
    row.generation_until = None
    await db.commit()
    return create_success_response(
        "Generation stopped. Already confirmed actions retain their execution status."
    )


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID,
    request: MessageCreate,
    user=Depends(get_current_active_user),
    db=Depends(get_db),
):
    if not request.text.strip():
        raise SpandanException("VALIDATION_ERROR", "Enter a support request.", 422)
    row, generation_id = await reserve_turn(db, user, conversation_id, request)
    return StreamingResponse(
        generate(db, user, row, generation_id, request.text),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/step-up")
async def verify_action(
    request: StepUpRequest, user=Depends(get_current_active_user), db=Depends(get_db)
):
    token = await step_up(db, user, request.action_id, request.password, request.code)
    return create_success_response("Security check completed.", {"step_up_token": token})


@router.get("/actions/{action_id}")
async def get_action(action_id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)):
    row = await owned_action(db, user, action_id)
    return create_success_response("Action status.", action_view(row))


@router.post("/actions/{action_id}/cancel")
async def cancel_action(action_id: UUID, user=Depends(get_current_active_user), db=Depends(get_db)):
    row = await owned_action(db, user, action_id, lock=True)
    if row.status != "pending":
        raise SpandanException("CONFLICT", "Only an unconfirmed proposal can be cancelled.", 409)
    row.status = "cancelled"
    await db.commit()
    return create_success_response("Proposal cancelled.", action_view(row))


@router.post("/actions/{action_id}/confirm")
async def confirm(
    action_id: UUID,
    request: ConfirmRequest,
    user=Depends(get_current_active_user),
    db=Depends(get_db),
):
    row = await confirm_action(db, user, action_id, request.step_up_token)
    if row.status == "succeeded":
        return create_success_response("Action already completed.", action_view(row))
    conversation = await execution_conversation(db, user, row)
    outcome = await mcp_client.call(
        user, conversation, "execute_confirmed_action", {"action_id": str(row.id)}, action_id=row.id
    )
    return create_success_response("Confirmed action.", outcome["action"])
