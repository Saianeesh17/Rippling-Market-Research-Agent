from __future__ import annotations

from src.tools.apify_linkedin_tool import ApifyLinkedInCompanyPostsTool
from src.schemas import ToolInput


class FakeApifyLinkedInTool(ApifyLinkedInCompanyPostsTool):
    def __init__(self):
        self.payload = None
        self.calls = 0

    def _fetch_items(self, token, payload):
        self.calls += 1
        self.payload = payload
        return [
            {
                "headline": f"Post {index}",
                "text": f"LinkedIn post body {index} about HR and payroll.",
                "date": "2026-07-01T00:00:00Z",
                "likeCount": index,
                "postUrl": f"https://www.linkedin.com/feed/update/{index}",
                "author": {"name": "Gusto"},
            }
            for index in range(1, 8)
        ]


def test_apify_linkedin_tool_requires_token(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "")
    tool = ApifyLinkedInCompanyPostsTool()

    result = tool.run(ToolInput(competitor_name="Gusto", domain="gusto.com", category="social"))

    assert not result.success
    assert "APIFY_TOKEN" in (result.error or "")


def test_apify_linkedin_tool_requires_resolved_linkedin_url(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "test-token")
    tool = ApifyLinkedInCompanyPostsTool()

    result = tool.run(ToolInput(competitor_name="Gusto", domain="gusto.com", category="social"))

    assert not result.success
    assert "No LinkedIn company URL" in (result.error or "")


def test_apify_linkedin_tool_limits_to_five_posts(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "test-token")
    monkeypatch.setenv("APIFY_LINKEDIN_MAX_POSTS_PER_COMPANY", "99")
    tool = FakeApifyLinkedInTool()

    result = tool.run(
        ToolInput(
            competitor_name="Gusto",
            domain="gusto.com",
            category="social",
            linkedin_company_url="https://www.linkedin.com/company/gustohq/posts/?feedView=all",
        )
    )

    assert result.success
    assert tool.payload == {
        "companyUrls": ["https://www.linkedin.com/company/gustohq/posts/?feedView=all"],
        "maxPostsPerCompany": 5,
        "maxCompanies": 1,
    }
    assert len(result.sources) == 5
    assert all(source.discovery_tool == "ApifyLinkedInCompanyPostsTool" for source in result.sources)
    assert result.sources[0].url == "https://www.linkedin.com/feed/update/1"
    assert result.metadata["api_request"]["json"]["maxPostsPerCompany"] == 5
    assert result.metadata["api_response"]["dataset_items_returned"] == 7
    assert len(result.metadata["api_response"]["logged_items"]) == 5


def test_apify_linkedin_tool_uses_cache_before_ttl_expiry(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "test-token")
    monkeypatch.setenv("APIFY_LINKEDIN_CACHE_TTL_HOURS", "5")
    tool = FakeApifyLinkedInTool()
    tool_input = ToolInput(
        competitor_name="Gusto",
        domain="gusto.com",
        category="social",
        linkedin_company_url="https://www.linkedin.com/company/gustohq/posts/?feedView=all",
    )

    first = tool.run(tool_input)
    second = tool.run(tool_input)

    assert first.success
    assert second.success
    assert tool.calls == 1
    assert second.metadata["cache"]["hit"] is True
    assert second.metadata["api_response"]["cache_hit"] is True
