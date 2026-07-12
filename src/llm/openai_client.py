from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from openai import BadRequestError, OpenAI

from src.llm.base import BaseLLM, LLMTokenUsage


@dataclass
class OpenAISettings:
    api_key: str
    model: str
    base_url: Optional[str] = None
    provider: str = "openai-compatible"


class OpenAICompatibleLLM(BaseLLM):
    """Small wrapper around the OpenAI Chat Completions API.

    Chat Completions is used here because it is widely supported by OpenAI-compatible
    endpoints and is still supported by the official OpenAI SDK.
    """

    def __init__(self, settings: OpenAISettings):
        self.settings = settings
        kwargs = {
            "api_key": settings.api_key,
            "base_url": settings.base_url or "https://api.openai.com/v1",
        }
        self.client = OpenAI(**kwargs)

    @property
    def model(self) -> str:
        return self.settings.model

    @property
    def provider(self) -> str:
        return self.settings.provider

    def complete(self, prompt: str, *, system_prompt: str | None = None, json_mode: bool = False) -> str:
        self.clear_last_token_usage()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request = {
            "model": self.settings.model,
            "messages": messages,
        }
        if json_mode:
            request["response_format"] = {"type": "json_object"}

        try:
            completion = self.client.chat.completions.create(**request)
        except BadRequestError as exc:
            if not json_mode or "response_format" not in str(exc).lower():
                raise
            request.pop("response_format", None)
            request["messages"] = [
                *messages,
                {"role": "user", "content": "Return valid JSON only. Do not wrap it in markdown."},
            ]
            completion = self.client.chat.completions.create(**request)
        self.set_last_token_usage(_usage_from_completion(completion))
        return completion.choices[0].message.content or ""


def _usage_from_completion(completion: object) -> LLMTokenUsage | None:
    usage = getattr(completion, "usage", None)
    if usage is None:
        return None
    input_tokens = getattr(usage, "prompt_tokens", None)
    output_tokens = getattr(usage, "completion_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = int(input_tokens) + int(output_tokens)
    return LLMTokenUsage(
        input_tokens=_int_or_none(input_tokens),
        output_tokens=_int_or_none(output_tokens),
        total_tokens=_int_or_none(total_tokens),
    )


def _int_or_none(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
