from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.schemas import LLMCallLog


@dataclass(frozen=True)
class LLMTokenUsageSummary:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    reported_calls: int = 0
    unreported_calls: int = 0


def summarize_llm_token_usage(logs: Iterable[LLMCallLog]) -> LLMTokenUsageSummary:
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    reported_calls = 0
    unreported_calls = 0

    for log in logs:
        has_input = log.input_tokens is not None
        has_output = log.output_tokens is not None
        has_total = log.total_tokens is not None
        if not (has_input or has_output or has_total):
            unreported_calls += 1
            continue

        reported_calls += 1
        input_tokens += log.input_tokens or 0
        output_tokens += log.output_tokens or 0
        if log.total_tokens is not None:
            total_tokens += log.total_tokens
        else:
            total_tokens += (log.input_tokens or 0) + (log.output_tokens or 0)

    return LLMTokenUsageSummary(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        reported_calls=reported_calls,
        unreported_calls=unreported_calls,
    )


def render_llm_token_usage_lines(logs: Iterable[LLMCallLog]) -> list[str]:
    summary = summarize_llm_token_usage(logs)
    return [
        f"- Input tokens: {summary.input_tokens}",
        f"- Output tokens: {summary.output_tokens}",
        f"- Total tokens: {summary.total_tokens}",
        f"- Calls with provider-reported usage: {summary.reported_calls}",
        f"- Calls without provider-reported usage: {summary.unreported_calls}",
    ]
