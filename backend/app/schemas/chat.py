from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConversationCreate(ChatInput):
    provider_consent: bool


class MessageCreate(ChatInput):
    client_message_id: UUID
    text: str = Field(min_length=1, max_length=4000)


class StepUpRequest(ChatInput):
    action_id: UUID
    password: str = Field(min_length=1, max_length=128)
    code: str | None = Field(None, pattern=r"^[0-9]{6}$")


class ConfirmRequest(ChatInput):
    step_up_token: str | None = Field(None, max_length=200)


class ToolCall(ChatInput):
    arguments: dict = Field(default_factory=dict)
    contract_version: str


class TokenExchange(ChatInput):
    subject_token: str = Field(max_length=16000)
    tool_name: str = Field(max_length=80)
    contract_version: str
