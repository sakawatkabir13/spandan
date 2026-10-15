from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.chat_evaluation import BASELINE, CHEAPER, DEFAULT, select_model
from app.services.llm import ModelReply, bedrock_provider


async def test_stream_keeps_tool_pairs_usage_and_hides_reasoning(monkeypatch):
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AWS_USE_INSTANCE_ROLE", True)
    items = [
        {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"reasoningContent": {"text": "private reasoning"}},
            }
        },
        {"contentBlockDelta": {"contentBlockIndex": 1, "delta": {"text": "I will check."}}},
        {
            "contentBlockStart": {
                "contentBlockIndex": 2,
                "start": {"toolUse": {"toolUseId": "one", "name": "help"}},
            }
        },
        {
            "contentBlockDelta": {
                "contentBlockIndex": 2,
                "delta": {"toolUse": {"input": '{"topic":'}},
            }
        },
        {
            "contentBlockDelta": {
                "contentBlockIndex": 2,
                "delta": {"toolUse": {"input": '"booking"}'}},
            }
        },
        {"messageStop": {"stopReason": "tool_use"}},
        {"metadata": {"usage": {"inputTokens": 123, "outputTokens": 45}}},
    ]

    class Events:
        def __iter__(self):
            return iter(items)

        def close(self):
            pass

    client = SimpleNamespace(
        converse_stream=lambda **kwargs: {"stream": Events()}, close=lambda: None
    )
    monkeypatch.setattr(bedrock_provider, "_client", lambda: client)
    events = [
        event
        async for event in bedrock_provider.stream(model=DEFAULT, system="support", messages=[])
    ]
    reply = events[-1]["reply"]
    assert reply.input_tokens == 123 and reply.output_tokens == 45
    assert reply.tool_calls[0]["input"] == {"topic": "booking"}
    assert "private reasoning" not in str(reply.content)


async def test_invalid_triage_reply_preserves_usage_and_fallback(monkeypatch):
    from app.schemas.ai import SymptomCheckRequest
    from app.services.ai import triage_service

    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AWS_USE_INSTANCE_ROLE", True)

    async def invalid(**kwargs):
        assert kwargs["model"] == "openai.gpt-oss-120b-1:0"
        return ModelReply([{"text": "invalid JSON"}], "end_turn", 20, 30)

    monkeypatch.setattr(bedrock_provider, "complete", invalid)
    result = await triage_service._call_provider_or_fallback(
        SymptomCheckRequest(symptoms_text="A mild headache for two days", provider_consent=True),
        ["General Medicine"],
    )
    assert result["model_identifier"] == "fallback-general-medicine"
    assert result["_usage"]["input_tokens"] == 20


def test_release_selection_rejects_unsafe_or_unqualified_models():
    def report(successes, cost, latency=1):
        return {
            "results": [
                dict(
                    index=i + 1,
                    success=i < successes,
                    incorrect_mutation=False,
                    latency_seconds=latency,
                    input_tokens=100,
                    output_tokens=50,
                    tool_calls=1,
                    estimated_cost_usd=cost,
                )
                for i in range(100)
            ]
        }

    reports = {DEFAULT: report(98, 0.01), CHEAPER: report(97, 0.005), BASELINE: report(99, 0.02)}
    assert select_model(reports, security_passed=True)["selected_model"] == CHEAPER
    reports[CHEAPER]["results"][0]["incorrect_mutation"] = True
    assert select_model(reports, security_passed=True)["selected_model"] == DEFAULT
    assert not select_model(reports, security_passed=False)["qualified"]
    reports[DEFAULT] = report(94, 0.01)
    assert not select_model(reports, security_passed=True)["qualified"]
    reports[DEFAULT]["results"].pop()
    with pytest.raises(ValueError):
        select_model(reports, security_passed=True)
