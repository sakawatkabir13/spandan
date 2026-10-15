"""Provider adapters. Neither provider executes tools or receives credentials in prompts."""

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.exceptions import SpandanException

logger = logging.getLogger(__name__)


@dataclass
class ModelReply:
    content: list[dict[str, Any]]
    stop_reason: str
    input_tokens: int = 0
    output_tokens: int = 0
    raw_usage: dict = field(default_factory=dict)

    @property
    def text(self):
        return "".join(block.get("text", "") for block in self.content)

    @property
    def tool_calls(self):
        return [block["toolUse"] for block in self.content if "toolUse" in block]


class ModelProvider(Protocol):
    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list,
        tools: list | None = None,
        max_tokens: int = 1500,
    ) -> ModelReply: ...

    def stream(self, **kwargs): ...


class BedrockProvider:
    def _client(self):
        # Boto3 consumes the bearer token from its standard environment setting.
        # Profile/instance-role credentials stay in the AWS credential chain.
        import os

        if settings.AWS_BEARER_TOKEN_BEDROCK:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.AWS_BEARER_TOKEN_BEDROCK
        session = boto3.Session(profile_name=settings.AWS_PROFILE or None)
        return session.client(
            "bedrock-runtime",
            region_name=settings.AWS_REGION,
            config=Config(
                connect_timeout=5,
                read_timeout=settings.AI_TIMEOUT_SECONDS,
                retries={"total_max_attempts": 1},
            ),
        )

    def _request(self, *, model, system, messages, tools=None, max_tokens=1500):
        if not settings.ai_configured:
            raise SpandanException(
                "AI_UNAVAILABLE",
                "AI support is temporarily unavailable. Please use the website controls.",
                503,
            )
        request = dict(
            modelId=model,
            system=[{"text": system}],
            messages=messages,
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0.1},
        )
        if tools:
            request["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": t["name"],
                            "description": t["description"],
                            "inputSchema": {"json": t["inputSchema"]},
                        }
                    }
                    for t in tools
                ],
                "toolChoice": {"auto": {}},
            }

        return request

    async def complete(self, **kwargs):
        request = self._request(**kwargs)

        def invoke():
            client = self._client()
            try:
                return client.converse(**request)
            finally:
                client.close()

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(invoke), settings.AI_TIMEOUT_SECONDS + 5
            )
            usage = response.get("usage", {})
            return ModelReply(
                content=response["output"]["message"]["content"],
                stop_reason=response.get("stopReason", "end_turn"),
                input_tokens=usage.get("inputTokens", 0),
                output_tokens=usage.get("outputTokens", 0),
                raw_usage=usage,
            )
        except SpandanException:
            raise
        except Exception:
            # Provider exceptions may contain request content or credential information.
            raise SpandanException(
                "AI_UNAVAILABLE",
                "The AI provider could not respond. Please retry or use the website controls.",
                503,
            ) from None

    async def stream(self, **kwargs):
        """Bridge blocking AWS event streams without blocking the ASGI loop.

        Only visible text and validated tool blocks leave the adapter. Reasoning
        blocks and provider exception bodies are never sent to the browser.
        """
        request = self._request(**kwargs)
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()
        stopped = threading.Event()
        resources = {}

        def publish(item):
            if not stopped.is_set():
                loop.call_soon_threadsafe(queue.put_nowait, item)

        def invoke():
            client = self._client()
            resources["client"] = client
            blocks, usage, reason = {}, {}, "end_turn"
            try:
                response = client.converse_stream(**request)
                resources["stream"] = response["stream"]
                for item in response["stream"]:
                    if stopped.is_set():
                        break
                    if "contentBlockStart" in item:
                        start = item["contentBlockStart"]
                        tool = start.get("start", {}).get("toolUse")
                        if tool:
                            blocks[start["contentBlockIndex"]] = {"toolUse": {**tool, "input": ""}}
                    elif "contentBlockDelta" in item:
                        delta = item["contentBlockDelta"]
                        index, value = delta["contentBlockIndex"], delta["delta"]
                        if "text" in value:
                            block = blocks.setdefault(index, {"text": ""})
                            block["text"] += value["text"]
                            publish({"type": "text_delta", "text": value["text"]})
                        elif "toolUse" in value:
                            blocks[index]["toolUse"]["input"] += value["toolUse"]["input"]
                    elif "messageStop" in item:
                        reason = item["messageStop"]["stopReason"]
                    elif "metadata" in item:
                        usage = item["metadata"].get("usage", {})
                    elif any(key.endswith("Exception") for key in item):
                        raise ValueError("Provider stream interrupted")
                for block in blocks.values():
                    if "toolUse" in block:
                        try:
                            block["toolUse"]["input"] = json.loads(
                                block["toolUse"]["input"] or "{}"
                            )
                        except (ValueError, TypeError):
                            # Keep billed usage and let the single schema-validation retry
                            # handle a malformed model call; never execute partial arguments.
                            block["toolUse"]["input"] = {"__invalid_json": True}
                publish(
                    {
                        "type": "reply",
                        "reply": ModelReply(
                            [blocks[k] for k in sorted(blocks)],
                            reason,
                            usage.get("inputTokens", 0),
                            usage.get("outputTokens", 0),
                            usage,
                        ),
                    }
                )
            except Exception as exc:
                provider_code = (
                    exc.response.get("Error", {}).get("Code", "unknown")
                    if isinstance(exc, ClientError)
                    else "unknown"
                )
                logger.warning(
                    "bedrock_stream_failed type=%s code=%s", type(exc).__name__, provider_code
                )
                publish({"type": "error"})
            finally:
                if "stream" in resources:
                    resources["stream"].close()
                client.close()

        task = asyncio.create_task(asyncio.to_thread(invoke))
        try:
            async with asyncio.timeout(settings.AI_TIMEOUT_SECONDS + 5):
                while True:
                    item = await queue.get()
                    if item["type"] == "error":
                        raise SpandanException(
                            "AI_UNAVAILABLE", "The AI reply was interrupted. Please retry.", 503
                        )
                    yield item
                    if item["type"] == "reply":
                        break
        except TimeoutError:
            raise SpandanException(
                "AI_TIMEOUT", "The AI reply timed out. Please retry.", 503
            ) from None
        finally:
            stopped.set()
            if "stream" in resources:
                # Closing the socket ends the blocking reader when generation is stopped.
                await asyncio.to_thread(resources["stream"].close)
            task.add_done_callback(
                lambda finished: finished.exception() if not finished.cancelled() else None
            )


bedrock_provider = BedrockProvider()


def extract_json(text: str) -> str:
    """Allow fenced JSON, but never silently accept a truncated or invalid response."""
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    json.loads(value)
    return value
