from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from openai import BadRequestError, OpenAI

from src.llm.base import BaseLLM


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
        return completion.choices[0].message.content or ""
