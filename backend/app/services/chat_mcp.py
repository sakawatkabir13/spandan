"""First-party MCP client; model requests never control the server URL or auth headers."""

import ssl
from urllib.parse import urlparse

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from app.core.config import settings
from app.core.exceptions import SpandanException
from app.services.chat_contract import (
    CONTRACT_VERSION,
    PROTOCOL_VERSION,
    TOOL_CATALOG,
    tools_for_role,
    validate_tool,
)
from app.services.chat_security import digest, issue_token


def delegation(user, conversation, tools, action_id=None):
    claims = {
        "sub": str(user.id),
        "ver": user.token_version,
        "role": user.role.value,
        "conversation_id": str(conversation.id),
        "fingerprint": conversation.access_fingerprint,
        "tools": tools,
    }
    if action_id:
        claims["action_id"] = str(action_id)
    elif conversation.generation_id:
        claims["generation_id"] = str(conversation.generation_id)
    return issue_token(claims, "spandan-mcp")


class SpandanMCPClient:
    async def discover(self, user, conversation):
        expected = {t["name"]: t for t in tools_for_role(user.role.value)}
        token = delegation(user, conversation, list(expected))
        try:
            async with self._http_client(token) as http:
                async with Client(
                    streamable_http_client(
                        settings.CHAT_MCP_URL, http_client=http, terminate_on_close=False
                    ),
                    mode=PROTOCOL_VERSION,
                    cache=None,
                    read_timeout_seconds=30,
                ) as client:
                    listing = await client.list_tools()
                    observed = []
                    for item in listing.tools:
                        source = expected.get(item.name)
                        if (
                            not source
                            or item.input_schema != source["inputSchema"]
                            or item.description != source["description"]
                            or (item.meta or {}).get("contract_sha256") != digest(TOOL_CATALOG)
                        ):
                            raise SpandanException(
                                "MCP_CONTRACT_MISMATCH",
                                "Support tool definitions do not match the application release.",
                                503,
                            )
                        observed.append(
                            {
                                "name": item.name,
                                "description": item.description,
                                "inputSchema": item.input_schema,
                            }
                        )
                    if {t["name"] for t in observed} != set(expected):
                        raise SpandanException(
                            "MCP_CONTRACT_MISMATCH", "Required support tools are missing.", 503
                        )
                    return observed
        except SpandanException:
            raise
        except Exception:
            raise SpandanException(
                "MCP_UNAVAILABLE",
                "Support tools could not be discovered. Please use the website controls.",
                503,
            ) from None

    def _http_client(self, token):
        url = urlparse(settings.CHAT_MCP_URL)
        if not url.hostname or url.username or url.password or url.query or url.fragment:
            raise SpandanException(
                "MCP_UNAVAILABLE", "The support tool connection is not configured.", 503
            )
        if settings.APP_ENV == "production" and url.scheme != "https":
            raise SpandanException(
                "MCP_UNAVAILABLE", "A secure support connection is required.", 503
            )
        context = ssl.create_default_context(cafile=settings.CHAT_TLS_CA or None)
        if settings.CHAT_TLS_CERT and settings.CHAT_TLS_KEY:
            context.load_cert_chain(settings.CHAT_TLS_CERT, settings.CHAT_TLS_KEY)
        return httpx2.AsyncClient(
            headers={"Authorization": "Bearer " + token},
            verify=context,
            follow_redirects=False,
            timeout=25,
            trust_env=False,
        )

    async def call(self, user, conversation, name, arguments, *, action_id=None):
        validate_tool(name, arguments, user.role.value, execution=bool(action_id))
        token = delegation(user, conversation, [name], action_id)
        try:
            async with self._http_client(token) as http:
                async with Client(
                    streamable_http_client(
                        settings.CHAT_MCP_URL, http_client=http, terminate_on_close=False
                    ),
                    mode=PROTOCOL_VERSION,
                    cache=None,
                    read_timeout_seconds=30,
                ) as client:
                    result = await client.call_tool(name, arguments)
                    content = result.structured_content
                    if (
                        not isinstance(content, dict)
                        or content.get("contract_version") != CONTRACT_VERSION
                    ):
                        raise SpandanException(
                            "MCP_CONTRACT_MISMATCH",
                            "Support tools need a compatible deployment.",
                            503,
                        )
                    if result.is_error or not content.get("success"):
                        error = content.get("error", {})
                        raise SpandanException(
                            error.get("code", "TOOL_FAILED"),
                            error.get("message", "The tool could not complete."),
                            error.get("status_code", 409),
                        )
                    return content["data"]
        except SpandanException:
            raise
        except Exception:
            raise SpandanException(
                "MCP_UNAVAILABLE",
                "Support tools could not be reached. Confirmed actions remain available for status checks and retry.",
                503,
            ) from None


mcp_client = SpandanMCPClient()
