from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def disable_live_llm_for_tests(monkeypatch, tmp_path):
    monkeypatch.setenv("USE_LLM", "false")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOJEN", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("APIFY_TOKEN", "")
    monkeypatch.setenv("APIFY_LINKEDIN_MAX_POSTS_PER_COMPANY", "5")
    monkeypatch.setenv("APIFY_LINKEDIN_CACHE_TTL_HOURS", "5")
    monkeypatch.setenv("EXA_API_KEY", "")
    monkeypatch.setenv("ADYNTEL_EMAIL", "")
    monkeypatch.setenv("ADYNTEL_API_KEY", "")
    monkeypatch.setenv("ADYNTEL_MAX_ADS_PER_PLATFORM", "5")
    monkeypatch.setenv("ADYNTEL_AD_CACHE_TTL_HOURS", "120")
    monkeypatch.setenv("AGENT_CACHE_DIR", str(tmp_path / "agent_cache"))
    monkeypatch.delenv("GROQ_OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
