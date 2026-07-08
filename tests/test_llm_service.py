from __future__ import annotations

from src.llm.service import create_llm


def test_groq_provider_uses_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("USE_LLM", "true")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("GROQ_MODEL", "groq-test-model")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    llm = create_llm(use_llm=True)

    assert llm is not None
    assert llm.provider == "groq"
    assert llm.model == "groq-test-model"
    assert llm.settings.base_url == "https://api.groq.com/openai/v1"


def test_google_ai_studio_provider_uses_gemini_openai_endpoint(monkeypatch):
    monkeypatch.setenv("USE_LLM", "true")
    monkeypatch.setenv("LLM_PROVIDER", "google")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    llm = create_llm(use_llm=True)

    assert llm is not None
    assert llm.provider == "google-ai-studio"
    assert llm.model == "gemini-test-model"
    assert llm.settings.base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"


def test_auto_provider_prefers_groq_when_available(monkeypatch):
    monkeypatch.setenv("USE_LLM", "auto")
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    llm = create_llm()

    assert llm is not None
    assert llm.provider == "groq"
