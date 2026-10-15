"""Deterministic release selection; no model-reported confidence or automatic escalation."""

from math import ceil

DEFAULT = "openai.gpt-oss-20b-1:0"
CHEAPER = "amazon.nova-micro-v1:0"
BASELINE = "openai.gpt-oss-120b-1:0"


def metrics(report):
    rows = report["results"]
    if len(rows) != 100 or {x["index"] for x in rows} != set(range(1, 101)):
        raise ValueError("Each model requires the same complete 100-scenario suite")
    successes = sum(bool(row["success"]) for row in rows)
    latencies = sorted(row["latency_seconds"] for row in rows)
    return dict(
        successes=successes,
        incorrect_mutations=sum(bool(row["incorrect_mutation"]) for row in rows),
        p95_seconds=latencies[ceil(len(rows) * 0.95) - 1],
        input_tokens=sum(row["input_tokens"] for row in rows),
        output_tokens=sum(row["output_tokens"] for row in rows),
        tool_calls=sum(row["tool_calls"] for row in rows),
        estimated_cost_usd=sum(row["estimated_cost_usd"] for row in rows),
        cost_per_success=sum(row["estimated_cost_usd"] for row in rows) / max(successes, 1),
    )


def select_model(reports, *, security_passed, approved_model=None):
    scores = {model: metrics(reports[model]) for model in (DEFAULT, CHEAPER, BASELINE)}
    base, cheap = scores[DEFAULT], scores[CHEAPER]

    def eligible(value):
        return value["successes"] >= 95 and value["incorrect_mutations"] == 0

    selected = DEFAULT if security_passed and eligible(base) else None
    if (
        security_passed
        and eligible(cheap)
        and cheap["cost_per_success"] <= 0.8 * base["cost_per_success"]
        and cheap["p95_seconds"] <= 1.2 * base["p95_seconds"]
    ):
        selected = CHEAPER
    if approved_model is not None:
        if approved_model != BASELINE:
            raise ValueError(
                "Only the evaluated baseline can be explicitly selected outside the cheaper-model rule"
            )
        selected = BASELINE if security_passed and eligible(scores[BASELINE]) else None
    return dict(
        qualified=selected is not None,
        selected_model=selected,
        scenario_count=100,
        security_passed=security_passed,
        approved_model=approved_model,
        metrics=scores,
    )
