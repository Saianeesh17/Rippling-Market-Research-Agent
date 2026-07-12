from __future__ import annotations

from src.schemas import ToolInput
from src.tools.exa_tools import ExaTwitterHandleSearchTool, _normalize_twitter_handle_from_url


class FakeExaTwitterTool(ExaTwitterHandleSearchTool):
    def __init__(self, results):
        self.results = results
        self.calls = 0
        self.request = None

    def _search(self, api_key, request):
        self.calls += 1
        self.request = request
        return self.results


def test_exa_twitter_tool_resolves_handle(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    tool = FakeExaTwitterTool(
        [
            {
                "title": "Gusto (@GustoHQ) / X",
                "url": "https://x.com/GustoHQ",
                "highlights": ["Official Gusto account"],
            }
        ]
    )

    result = tool.run(ToolInput(competitor_name="Gusto", domain="gusto.com", category="social"))

    assert result.success
    assert result.metadata["twitter_handle"] == "@GustoHQ"
    assert result.metadata["twitter_profile_url"] == "https://x.com/GustoHQ"
    assert "include_domains" not in result.metadata["api_request"]
    assert result.metadata["api_request"]["local_url_filter_domains"] == ["x.com", "twitter.com"]
    assert result.sources[0].url == "https://x.com/GustoHQ"


def test_exa_twitter_tool_rejects_non_profile_urls(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    tool = FakeExaTwitterTool(
        [
            {"title": "Search", "url": "https://x.com/search?q=gusto", "highlights": []},
            {"title": "Post", "url": "https://x.com/GustoHQ/status/123", "highlights": []},
        ]
    )

    result = tool.run(ToolInput(competitor_name="Gusto", category="social"))

    assert not result.success
    assert result.metadata["twitter_handle"] is None
    assert "proper Twitter/X handle" in (result.error or "")


def test_exa_twitter_tool_uses_cache_on_second_run(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    tool = FakeExaTwitterTool(
        [
            {
                "title": "Gusto (@GustoHQ) / X",
                "url": "https://twitter.com/GustoHQ",
                "highlights": ["Official Gusto account"],
            }
        ]
    )
    tool_input = ToolInput(competitor_name="Gusto", domain="gusto.com", category="social")

    first = tool.run(tool_input)
    monkeypatch.setenv("EXA_API_KEY", "")
    second = tool.run(tool_input)

    assert first.success
    assert second.success
    assert tool.calls == 1
    assert second.metadata["cache"]["hit"] is True
    assert second.metadata["twitter_handle"] == "@GustoHQ"


def test_normalize_twitter_profile_url_to_handle():
    assert _normalize_twitter_handle_from_url("https://twitter.com/GustoHQ") == "@GustoHQ"
    assert _normalize_twitter_handle_from_url("https://x.com/GustoHQ/status/123") is None
