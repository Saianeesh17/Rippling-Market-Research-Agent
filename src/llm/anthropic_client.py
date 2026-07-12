from __future__ import annotations

from dataclasses import dataclass

import httpx

from src.llm.base import BaseLLM


@dataclass
class AnthropicSettings:
    auth_token: str
    base_url: str
    verify_ssl: bool
    model: str = "claude-sonnet-5"
    max_tokens: int = 2000
    anthropic_version: str = "2023-06-01"
    provider: str = "anthropic"
    use_authorization_header: bool = False


class AnthropicCompatibleLLM(BaseLLM):
    """Anthropic Messages API client for the first-party API or compatible gateways."""

    def __init__(self, settings: AnthropicSettings):
        self.settings = settings

    @property
    def provider(self) -> str:
        return self.settings.provider

    @property
    def model(self) -> str:
        return self.settings.model

    def complete(self, prompt: str, *, system_prompt: str | None = None, json_mode: bool = False) -> str:
        user_prompt = prompt
        if json_mode:
            user_prompt = f"{prompt}\n\nReturn valid JSON only. Do not wrap it in markdown."

        payload = {
            "model": self.settings.model,
            "max_tokens": self.settings.max_tokens,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "content-type": "application/json",
            "anthropic-version": self.settings.anthropic_version,
            "x-api-key": self._raw_token(),
        }
        if self.settings.use_authorization_header:
            headers["authorization"] = self._authorization_header()

        url = self._messages_url()
        try:
            with httpx.Client(verify=self.settings.verify_ssl, timeout=120.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Could not connect to Anthropic-compatible endpoint at {url}. "
                "Verify ANTHROPIC_BASE_URL, network access, VPN, or corporate DNS."
            ) from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:1000] if exc.response is not None else ""
            raise RuntimeError(
                f"Anthropic-compatible endpoint returned HTTP {exc.response.status_code}: {body}"
            ) from exc
        return self._extract_text(data)

    def _messages_url(self) -> str:
        return f"{self.settings.base_url.rstrip('/')}/v1/messages"

    def _authorization_header(self) -> str:
        token = self.settings.auth_token.strip()
        if token.lower().startswith("bearer "):
            return token
        return f"Bearer {token}"

    def _raw_token(self) -> str:
        token = self.settings.auth_token.strip()
        if token.lower().startswith("bearer "):
            return token.split(" ", 1)[1].strip()
        return token

    def _extract_text(self, data: dict) -> str:
        content = data.get("content", [])
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(str(block.get("text", "")))
        if text_parts:
            return "".join(text_parts)
        if isinstance(data.get("completion"), str):
            return data["completion"]
        return str(data)
