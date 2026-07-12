from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMTokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class BaseLLM(ABC):
    def clear_last_token_usage(self) -> None:
        self._last_token_usage = None

    def set_last_token_usage(self, usage: LLMTokenUsage | None) -> None:
        self._last_token_usage = usage

    def last_token_usage(self) -> LLMTokenUsage | None:
        return getattr(self, "_last_token_usage", None)

    @abstractmethod
    def complete(self, prompt: str, *, system_prompt: str | None = None, json_mode: bool = False) -> str:
        raise NotImplementedError


def llm_token_usage_fields(llm: BaseLLM) -> dict[str, int | None]:
    usage = llm.last_token_usage()
    if not usage:
        return {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
    }
