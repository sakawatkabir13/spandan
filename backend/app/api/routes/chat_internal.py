"""Private service endpoints. No browser access or browser-token authentication."""

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy import update

from app.core.config import settings
from app.core.exceptions import SpandanException
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.chat import ChatAction
from app.schemas.chat import TokenExchange, ToolCall
from app.services.chat_actions import execute_action, prepare_action
from app.services.chat_contract import CONTRACT_VERSION, validate_tool
from app.services.chat_security import (
    actor_from_claims,
    decode_delegation,
    issue_token,
    require_chat,
)
from app.services.chat_tools import read_tool

router = APIRouter(prefix="/internal/chat-tools", include_in_schema=False)


def service_identity(x_mcp_service_token: str = Header(default="")):
    require_chat()
    if not settings.CHAT_MCP_SERVICE_TOKEN or not secrets.compare_digest(
        x_mcp_service_token, settings.CHAT_MCP_SERVICE_TOKEN
    ):
        raise SpandanException("INVALID_SERVICE", "Service authentication is required.", 401)


@router.post("/exchange", dependencies=[Depends(service_identity)])
async def exchange(request: TokenExchange, db=Depends(get_db)):
    if request.contract_version != CONTRACT_VERSION:
        raise SpandanException("MCP_CONTRACT_MISMATCH", "Unsupported tool API contract.", 409)
    claims = decode_delegation(request.subject_token, "spandan-mcp")
    await actor_from_claims(db, claims, request.tool_name)
    # Mint a distinct downstream audience; never reuse the MCP bearer token at the API.
    return {
        "access_token": issue_token(
            {k: v for k, v in claims.items() if k not in {"aud", "iat", "exp", "jti", "iss"}},
            "spandan-chat-api",
        ),
        "contract_version": CONTRACT_VERSION,
    }


@router.post("/call/{tool_name}", dependencies=[Depends(service_identity)])
async def call_tool(
    tool_name: str, request: ToolCall, authorization: str = Header(default=""), db=Depends(get_db)
):
    if request.contract_version != CONTRACT_VERSION:
        raise SpandanException("MCP_CONTRACT_MISMATCH", "Unsupported tool API contract.", 409)
    if not authorization.startswith("Bearer "):
        raise SpandanException("INVALID_DELEGATION", "Delegated access is required.", 401)
    claims = decode_delegation(authorization[7:], "spandan-chat-api")
    user, conversation = await actor_from_claims(db, claims, tool_name)
    actor_id = user.id
    try:
        executing = tool_name == "execute_confirmed_action"
        validate_tool(tool_name, request.arguments, user.role.value, execution=executing)
        if executing:
            if claims.get("action_id") != request.arguments["action_id"]:
                raise SpandanException(
                    "CONFIRMATION_REQUIRED", "An exact-action grant is required.", 403
                )
            data = await execute_action(db, user, UUID(request.arguments["action_id"]))
        elif tool_name.startswith("propose_"):
            data = await prepare_action(db, user, conversation, tool_name, request.arguments)
        else:
            data = await read_tool(db, user, tool_name, request.arguments)
    except SpandanException as exc:
        await db.rollback()
        target = claims.get("action_id")
        if target:
            await db.execute(
                update(ChatAction)
                .where(
                    ChatAction.id == UUID(target),
                    ChatAction.actor_user_id == actor_id,
                    ChatAction.status == "confirmed",
                )
                .values(error_code=exc.code)
            )
        db.add(
            AuditLog(
                actor_user_id=actor_id,
                action="chat.tool_denied" if exc.status_code in {401, 403} else "chat.tool_failed",
                entity_type="chat_action" if target else "chat_tool",
                entity_id=target or tool_name,
                metadata_json={"tool": tool_name, "code": exc.code},
            )
        )
        await db.commit()
        raise
    return {"contract_version": CONTRACT_VERSION, "success": True, "data": data}
