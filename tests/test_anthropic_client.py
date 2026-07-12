from __future__ import annotations

import pytest

from src.llm.anthropic_client import AnthropicCompatibleLLM, AnthropicSettings


class FakeAnthropicResponse:
    status_code = 200
    text = ""

    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class FakeAnthropicHttpClient:
    def __init__(self, response_data):
        self.response_data = response_data
        self.posts = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, url, *, headers, json):
        self.posts.append({"url": url, "headers": headers, "json": json})
        return FakeAnthropicResponse(self.response_data)


def test_anthropic_client_disables_thinking_and_extracts_text(monkeypatch):
    fake_client = FakeAnthropicHttpClient(
        {
            "content": [
                {"type": "thinking", "thinking": "", "signature": "redacted-thinking-signature"},
                {"type": "text", "text": "# Report\n\nBody."},
            ],
            "stop_reason": "end_turn",
        }
    )
    monkeypatch.setattr("src.llm.anthropic_client.httpx.Client", lambda **kwargs: fake_client)
    llm = AnthropicCompatibleLLM(
        AnthropicSettings(
            auth_token="test-key",
            base_url="https://api.anthropic.com",
            verify_ssl=True,
            model="claude-sonnet-5",
            max_tokens=8000,
        )
    )

    response = llm.complete("Write a report.")

    assert response == "# Report\n\nBody."
    request = fake_client.posts[0]["json"]
    assert request["max_tokens"] == 8000
    assert request["thinking"] == {"type": "disabled"}


def test_anthropic_client_can_omit_thinking_when_configured(monkeypatch):
    fake_client = FakeAnthropicHttpClient({"content": [{"type": "text", "text": "ok"}]})
    monkeypatch.setattr("src.llm.anthropic_client.httpx.Client", lambda **kwargs: fake_client)
    llm = AnthropicCompatibleLLM(
        AnthropicSettings(
            auth_token="test-key",
            base_url="https://api.anthropic.com",
            verify_ssl=True,
            thinking_mode="auto",
        )
    )

    assert llm.complete("ping") == "ok"
    assert "thinking" not in fake_client.posts[0]["json"]


def test_anthropic_client_raises_sanitized_error_for_thinking_only_response(monkeypatch):
    fake_client = FakeAnthropicHttpClient(
        {
            "content": [
                {"type": "thinking", "thinking": "", "signature": "secret-signature-should-not-leak"},
            ],
            "stop_reason": "max_tokens",
            "usage": {
                "output_tokens": 2000,
                "output_tokens_details": {"thinking_tokens": 2000},
            },
        }
    )
    monkeypatch.setattr("src.llm.anthropic_client.httpx.Client", lambda **kwargs: fake_client)
    llm = AnthropicCompatibleLLM(
        AnthropicSettings(
            auth_token="test-key",
            base_url="https://api.anthropic.com",
            verify_ssl=True,
        )
    )

    with pytest.raises(RuntimeError) as exc_info:
        llm.complete("Write a report.")

    message = str(exc_info.value)
    assert "did not include a text block" in message
    assert "stop_reason=max_tokens" in message
    assert "thinking_tokens=2000" in message
    assert "secret-signature-should-not-leak" not in message
