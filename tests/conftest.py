from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def disable_live_llm_for_tests(monkeypatch):
    monkeypatch.setenv("USE_LLM", "false")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_AI_STUDIO_API_KEY", raising=False)
