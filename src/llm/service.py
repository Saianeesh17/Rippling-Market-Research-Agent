from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

from src.llm.base import BaseLLM
from src.llm.anthropic_client import AnthropicCompatibleLLM, AnthropicSettings
from src.llm.openai_client import OpenAICompatibleLLM, OpenAISettings


GOOGLE_AI_STUDIO_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GROQ_OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
ANTHROPIC_QGENIE_BASE_URL = "https://qgenie-api.qualcomm.com/"


def create_llm(use_llm: Optional[bool] = None) -> BaseLLM | None:
    load_dotenv()
    mode = os.getenv("USE_LLM", "auto").strip().lower()
    provider = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    anthropic_token = (
        os.getenv("ANTHROPIC_AUTH_TOKEN", "").strip()
        or os.getenv("ANTHROPIC_AUTH_TOJEN", "").strip()
    )
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    gemini_key = (
        os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("GOOGLE_API_KEY", "").strip()
        or os.getenv("GOOGLE_AI_STUDIO_API_KEY", "").strip()
    )

    if not os.getenv("OPENAI_BASE_URL", "").strip():
        os.environ.pop("OPENAI_BASE_URL", None)
    if not os.getenv("GROQ_OPENAI_BASE_URL", "").strip():
        os.environ.pop("GROQ_OPENAI_BASE_URL", None)

    if use_llm is False:
        return None
    if use_llm is None:
        enabled = mode in {"1", "true", "yes", "on"} or (
            mode == "auto" and bool(anthropic_token or groq_key or openai_key or gemini_key)
        )
    else:
        enabled = use_llm

    if not enabled:
        return None

    llm = _resolve_provider(
        provider,
        anthropic_token=anthropic_token,
        groq_key=groq_key,
        openai_key=openai_key,
        gemini_key=gemini_key,
    )
    if not llm:
        return None

    return llm


def _resolve_provider(
    provider: str,
    *,
    anthropic_token: str,
    groq_key: str,
    openai_key: str,
    gemini_key: str,
) -> BaseLLM | None:
    if provider in {"anthropic", "claude", "qgenie", "qualcomm"}:
        if not anthropic_token:
            return None
        return AnthropicCompatibleLLM(_anthropic_settings(anthropic_token))

    if provider == "groq":
        if not groq_key:
            return None
        return OpenAICompatibleLLM(_groq_settings(groq_key))

    if provider in {"google", "gemini", "google_ai_studio"}:
        if not gemini_key:
            return None
        return OpenAICompatibleLLM(_gemini_settings(gemini_key))

    if provider == "openai":
        if not openai_key:
            return None
        return OpenAICompatibleLLM(_openai_settings(openai_key))

    if provider == "auto":
        if anthropic_token:
            return AnthropicCompatibleLLM(_anthropic_settings(anthropic_token))
        if groq_key:
            return OpenAICompatibleLLM(_groq_settings(groq_key))
        if gemini_key:
            return OpenAICompatibleLLM(_gemini_settings(gemini_key))
        if openai_key:
            return OpenAICompatibleLLM(_openai_settings(openai_key))
        return None

    if anthropic_token:
        return AnthropicCompatibleLLM(_anthropic_settings(anthropic_token))
    if groq_key:
        return OpenAICompatibleLLM(_groq_settings(groq_key))
    if openai_key:
        return OpenAICompatibleLLM(_openai_settings(openai_key))
    if gemini_key:
        return OpenAICompatibleLLM(_gemini_settings(gemini_key))
    return None


def _anthropic_settings(auth_token: str) -> AnthropicSettings:
    return AnthropicSettings(
        auth_token=auth_token,
        base_url=os.getenv("ANTHROPIC_BASE_URL", "").strip() or ANTHROPIC_QGENIE_BASE_URL,
        verify_ssl=_env_bool("ANTHROPIC_VERIFY_SSL", default=True),
        model=os.getenv("ANTHROPIC_MODEL", "").strip() or "claude-opus-4-8",
        max_tokens=_env_int("ANTHROPIC_MAX_TOKENS", default=2000),
    )


def _groq_settings(api_key: str) -> OpenAISettings:
    return OpenAISettings(
        api_key=api_key,
        model=os.getenv("GROQ_MODEL", "").strip() or "llama-3.3-70b-versatile",
        base_url=os.getenv("GROQ_OPENAI_BASE_URL", "").strip() or GROQ_OPENAI_BASE_URL,
        provider="groq",
    )


def _gemini_settings(api_key: str) -> OpenAISettings:
    return OpenAISettings(
        api_key=api_key,
        model=os.getenv("GEMINI_MODEL", "").strip()
        or os.getenv("GOOGLE_MODEL", "").strip()
        or "gemini-3.5-flash",
        base_url=os.getenv("GEMINI_OPENAI_BASE_URL", "").strip() or GOOGLE_AI_STUDIO_OPENAI_BASE_URL,
        provider="google-ai-studio",
    )


def _openai_settings(api_key: str) -> OpenAISettings:
    return OpenAISettings(
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-5.5").strip() or "gpt-5.5",
        base_url=os.getenv("OPENAI_BASE_URL", "").strip() or None,
        provider="openai",
    )


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, *, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default
