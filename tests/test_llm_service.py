from __future__ import annotations

from src.llm.service import create_llm


def test_anthropic_provider_uses_first_party_api_by_default(monkeypatch):
    monkeypatch.setenv("USE_LLM", "true")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    llm = create_llm(use_llm=True)

    assert llm is not None
    assert llm.provider == "anthropic"
    assert llm.model == "claude-sonnet-5"
    assert llm.settings.base_url == "https://api.anthropic.com"
    assert llm.settings.auth_token == "test-anthropic-key"
    assert llm.settings.verify_ssl is True
    assert llm.settings.use_authorization_header is False


def test_anthropic_qgenie_provider_uses_requested_gateway_fields(monkeypatch):
    monkeypatch.setenv("USE_LLM", "true")
    monkeypatch.setenv("LLM_PROVIDER", "qgenie")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-qgenie-token")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://qgenie-api.qualcomm.com/")
    monkeypatch.setenv("ANTHROPIC_VERIFY_SSL", "false")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    llm = create_llm(use_llm=True)

    assert llm is not None
    assert llm.provider == "anthropic-qgenie"
    assert llm.model == "claude-opus-4-8"
    assert llm.settings.base_url == "https://qgenie-api.qualcomm.com/"
    assert llm.settings.auth_token == "test-qgenie-token"
    assert llm.settings.verify_ssl is False
    assert llm.settings.use_authorization_header is True


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


def test_auto_provider_prefers_anthropic_when_available(monkeypatch):
    monkeypatch.setenv("USE_LLM", "auto")
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    llm = create_llm()

    assert llm is not None
    assert llm.provider == "anthropic"
