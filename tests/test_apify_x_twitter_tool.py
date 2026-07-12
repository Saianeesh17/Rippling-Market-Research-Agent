from __future__ import annotations

from src.schemas import ToolInput
from src.tools.apify_x_twitter_tool import ApifyXTwitterPostsSearchTool


class FakeApifyXTwitterTool(ApifyXTwitterPostsSearchTool):
    def __init__(self):
        self.payload = None
        self.calls = 0

    def _fetch_items(self, token, payload):
        self.calls += 1
        self.payload = payload
        return [
            {
                "text": f"Twitter/X post body {index} about payroll and HR.",
                "createdAt": "2026-07-01T00:00:00Z",
                "likeCount": index,
                "url": f"https://x.com/GustoHQ/status/{index}",
                "author": {"username": "GustoHQ"},
            }
            for index in range(1, 8)
        ]


def test_apify_x_twitter_tool_requires_token(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "")
    tool = ApifyXTwitterPostsSearchTool()

    result = tool.run(ToolInput(competitor_name="Gusto", category="social", twitter_handle="@GustoHQ"))

    assert not result.success
    assert "APIFY_TOKEN" in (result.error or "")


def test_apify_x_twitter_tool_requires_resolved_handle(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "test-token")
    tool = ApifyXTwitterPostsSearchTool()

    result = tool.run(ToolInput(competitor_name="Gusto", category="social"))

    assert not result.success
    assert "No Twitter/X handle" in (result.error or "")


def test_apify_x_twitter_tool_limits_to_five_posts(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "test-token")
    monkeypatch.setenv("APIFY_X_TWITTER_MAX_POSTS", "99")
    tool = FakeApifyXTwitterTool()

    result = tool.run(ToolInput(competitor_name="Gusto", category="social", twitter_handle="@GustoHQ"))

    assert result.success
    assert tool.payload == {
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"],
        },
        "startUrls": ["@GustoHQ"],
    }
    assert len(result.sources) == 5
    assert all(source.discovery_tool == "ApifyXTwitterPostsSearchTool" for source in result.sources)
    assert result.sources[0].url == "https://x.com/GustoHQ/status/1"
    assert result.metadata["api_request"]["query_params"] == {"token": "<redacted>"}
    assert result.metadata["api_response"]["dataset_items_returned"] == 7
    assert len(result.metadata["api_response"]["logged_items"]) == 5


def test_apify_x_twitter_tool_uses_cache_before_ttl_expiry(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "test-token")
    monkeypatch.setenv("APIFY_X_TWITTER_CACHE_TTL_HOURS", "5")
    tool = FakeApifyXTwitterTool()
    tool_input = ToolInput(competitor_name="Gusto", category="social", twitter_handle="@GustoHQ")

    first = tool.run(tool_input)
    second = tool.run(tool_input)

    assert first.success
    assert second.success
    assert tool.calls == 1
    assert second.metadata["cache"]["hit"] is True
    assert second.metadata["api_response"]["cache_hit"] is True
