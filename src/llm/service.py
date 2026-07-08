from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

from src.llm.base import BaseLLM
from src.llm.openai_client import OpenAICompatibleLLM, OpenAISettings


GOOGLE_AI_STUDIO_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GROQ_OPENAI_BASE_URL = "https://api.groq.com/openai/v1"


def create_llm(use_llm: Optional[bool] = None) -> BaseLLM | None:
    load_dotenv()
    mode = os.getenv("USE_LLM", "auto").strip().lower()
    provider = os.getenv("LLM_PROVIDER", "auto").strip().lower()
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
        enabled = mode in {"1", "true", "yes", "on"} or (mode == "auto" and bool(groq_key or openai_key or gemini_key))
    else:
        enabled = use_llm

    if not enabled:
        return None

    settings = _resolve_provider_settings(provider, groq_key=groq_key, openai_key=openai_key, gemini_key=gemini_key)
    if not settings:
        return None

    return OpenAICompatibleLLM(settings)


def _resolve_provider_settings(
    provider: str,
    *,
    groq_key: str,
    openai_key: str,
    gemini_key: str,
) -> OpenAISettings | None:
    if provider == "groq":
        if not groq_key:
            return None
        return _groq_settings(groq_key)

    if provider in {"google", "gemini", "google_ai_studio"}:
        if not gemini_key:
            return None
        return _gemini_settings(gemini_key)

    if provider == "openai":
        if not openai_key:
            return None
        return _openai_settings(openai_key)

    if provider == "auto":
        if groq_key:
            return _groq_settings(groq_key)
        if gemini_key:
            return _gemini_settings(gemini_key)
        if openai_key:
            return _openai_settings(openai_key)
        return None

    if groq_key:
        return _groq_settings(groq_key)
    if openai_key:
        return _openai_settings(openai_key)
    if gemini_key:
        return _gemini_settings(gemini_key)
    return None


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
