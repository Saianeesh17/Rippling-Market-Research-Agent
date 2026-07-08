from __future__ import annotations

from src.llm.base import BaseLLM


class FakeLLM(BaseLLM):
    """Deterministic placeholder for future LangChain-compatible LLM calls."""

    def complete(self, prompt: str) -> str:
        return f"FAKE_LLM_RESPONSE: {prompt[:120]}"

