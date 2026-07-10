from __future__ import annotations

from src.schemas import ToolInput
from src.tools.exa_tools import ExaLinkedInCompanySearchTool, _normalize_linkedin_company_url


class FakeExaLinkedInTool(ExaLinkedInCompanySearchTool):
    def __init__(self):
        self.request = None
        self.calls = 0

    def _search(self, api_key, request):
        self.calls += 1
        self.request = request
        return [
            {
                "title": "Gusto | LinkedIn",
                "url": "https://www.linkedin.com/company/gustohq/",
                "highlights": ["Gusto company page"],
            }
        ]


def test_exa_linkedin_tool_resolves_company_posts_url(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    tool = FakeExaLinkedInTool()

    result = tool.run(ToolInput(competitor_name="Gusto", domain="gusto.com", category="social"))

    assert result.success
    assert result.metadata["linkedin_company_url"] == "https://www.linkedin.com/company/gustohq/posts/?feedView=all"
    assert result.metadata["api_request"]["contents"] == {"highlights": True}
    assert result.metadata["api_request"]["num_results"] == 5
    assert result.sources[0].url == "https://www.linkedin.com/company/gustohq/posts/?feedView=all"


def test_exa_linkedin_tool_uses_cache_on_second_run(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    tool = FakeExaLinkedInTool()

    first = tool.run(ToolInput(competitor_name="Gusto", domain="gusto.com", category="social"))
    monkeypatch.setenv("EXA_API_KEY", "")
    second = tool.run(ToolInput(competitor_name="Gusto", domain="gusto.com", category="social"))

    assert first.success
    assert second.success
    assert tool.calls == 1
    assert second.metadata["cache"]["hit"] is True
    assert second.metadata["linkedin_company_url"] == "https://www.linkedin.com/company/gustohq/posts/?feedView=all"


def test_exa_linkedin_tool_requires_api_key(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "")
    tool = ExaLinkedInCompanySearchTool()

    result = tool.run(ToolInput(competitor_name="Gusto", domain="gusto.com", category="social"))

    assert not result.success
    assert "EXA_API_KEY" in (result.error or "")


def test_normalize_linkedin_company_url_to_posts_url():
    assert (
        _normalize_linkedin_company_url("https://www.linkedin.com/company/gustohq/about/")
        == "https://www.linkedin.com/company/gustohq/posts/?feedView=all"
    )
