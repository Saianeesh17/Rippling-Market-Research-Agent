from __future__ import annotations

from src.schemas import ToolInput
from src.tools.domain_utils import normalize_company_domain
from src.tools.exa_tools import ExaCompanyDomainSearchTool


class FakeExaDomainTool(ExaCompanyDomainSearchTool):
    def __init__(self):
        self.calls = 0
        self.request = None

    def _search(self, api_key, request):
        self.calls += 1
        self.request = request
        return [
            {
                "title": "Gusto LinkedIn",
                "url": "https://www.linkedin.com/company/gustohq/",
                "highlights": ["Social profile"],
            },
            {
                "title": "Gusto | Payroll and HR",
                "url": "https://www.gusto.com/product/payroll",
                "highlights": ["Official Gusto website"],
            },
        ]


def test_exa_company_domain_uses_existing_profile_domain_without_api_key(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "")
    tool = ExaCompanyDomainSearchTool()

    result = tool.run(
        ToolInput(
            competitor_name="Gusto",
            domain="https://www.gusto.com/product/payroll?utm=test",
            category="paid_ads",
        )
    )

    assert result.success
    assert result.metadata["resolved_company_domain"] == "gusto.com"
    assert result.metadata["api_request"]["skipped"] == "domain_already_available"


def test_exa_company_domain_search_skips_social_domains(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    tool = FakeExaDomainTool()

    result = tool.run(ToolInput(competitor_name="Gusto", category="paid_ads"))

    assert result.success
    assert result.metadata["resolved_company_domain"] == "gusto.com"
    assert tool.request["num_results"] == 5
    assert tool.request["contents"] == {"highlights": True}


def test_exa_company_domain_cache_avoids_second_search(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    tool = FakeExaDomainTool()
    tool_input = ToolInput(competitor_name="Gusto", category="paid_ads")

    first = tool.run(tool_input)
    monkeypatch.setenv("EXA_API_KEY", "")
    second = tool.run(tool_input)

    assert first.success
    assert second.success
    assert tool.calls == 1
    assert second.metadata["cache"]["hit"] is True
    assert second.metadata["resolved_company_domain"] == "gusto.com"


def test_normalize_company_domain_removes_scheme_www_and_path():
    assert normalize_company_domain("https://www.gusto.com/products/payroll") == "gusto.com"
