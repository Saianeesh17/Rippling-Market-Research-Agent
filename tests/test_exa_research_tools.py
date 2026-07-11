from __future__ import annotations

from src.schemas import ToolInput
from src.tools.exa_research_tools import (
    ExaPressNewsResearchTool,
    ExaPricingResearchTool,
    ExaProductPagesTool,
    ExaWebsitePositioningTool,
)


class FakeExaWebsiteTool(ExaWebsitePositioningTool):
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def _search(self, api_key, request):
        self.calls.append(request)
        return self.responses[len(self.calls) - 1]


class FakeExaProductTool(ExaProductPagesTool):
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def _search(self, api_key, request):
        self.calls.append(request)
        return self.responses[len(self.calls) - 1]


class FakeExaPricingTool(ExaPricingResearchTool):
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def _search(self, api_key, request):
        self.calls.append(request)
        return self.responses[len(self.calls) - 1]


class FakeExaPressTool(ExaPressNewsResearchTool):
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def _search(self, api_key, request):
        self.calls.append(request)
        return self.responses[len(self.calls) - 1]


def test_exa_website_positioning_prefers_official_domain(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    tool = FakeExaWebsiteTool(
        [
            [
                {
                    "title": "Gusto | Payroll and HR",
                    "url": "https://www.gusto.com/",
                    "highlights": ["Gusto positions itself around payroll, HR, benefits, and compliance for small businesses."],
                    "text": "Gusto helps small businesses run payroll, manage HR, administer benefits, and stay compliant.",
                }
            ]
        ]
    )

    result = tool.run(ToolInput(competitor_name="Gusto", domain="gusto.com", category="website_positioning"))

    assert result.success
    assert len(tool.calls) == 1
    assert tool.calls[0]["include_domains"] == ["gusto.com"]
    assert result.sources[0].source_type == "website_positioning"
    assert result.sources[0].is_official
    assert not result.sources[0].is_third_party
    assert result.metadata["api_response"]["sources_accepted"] == 1


def test_exa_pricing_falls_back_to_external_sources_with_lower_confidence(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    tool = FakeExaPricingTool(
        [
            [],
            [
                {
                    "title": "Gusto Pricing Review",
                    "url": "https://www.g2.com/products/gusto/pricing",
                    "highlights": ["Public marketplace pricing context says Gusto has plan tiers and add-ons."],
                    "text": "Gusto pricing is discussed by a third-party marketplace with plan tier context.",
                }
            ],
        ]
    )

    result = tool.run(ToolInput(competitor_name="Gusto", domain="gusto.com", category="pricing"))

    assert result.success
    assert len(tool.calls) == 2
    assert tool.calls[1]["exclude_domains"] == ["gusto.com"]
    assert result.sources[0].source_type == "pricing"
    assert result.sources[0].is_third_party
    assert result.sources[0].reliability_weight == 0.52
    assert result.sources[0].confidence_modifier == 0.55


def test_exa_product_tool_drops_low_quality_social_results(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    tool = FakeExaProductTool(
        [
            [
                {
                    "title": "Gusto LinkedIn",
                    "url": "https://www.linkedin.com/company/gustohq/",
                    "highlights": ["Social page"],
                    "text": "Social profile content that should not be used for product page research.",
                }
            ]
        ]
    )

    result = tool.run(ToolInput(competitor_name="Gusto", category="product_pages"))

    assert not result.success
    assert result.sources == []
    assert "no usable sources" in (result.error or "")


def test_exa_press_news_uses_news_category_and_recent_window(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    monkeypatch.setenv("EXA_PRESS_RECENCY_MONTHS", "6")
    tool = FakeExaPressTool(
        [
            [],
            [
                {
                    "title": "Gusto announces new payroll product",
                    "url": "https://example-news.com/gusto-product-launch",
                    "published_date": "2026-05-01T00:00:00Z",
                    "highlights": ["Gusto announced a new payroll product for small businesses."],
                    "text": "A news article reports that Gusto announced a new payroll product for small businesses.",
                }
            ],
        ]
    )

    result = tool.run(ToolInput(competitor_name="Gusto", domain="gusto.com", category="press_news"))

    assert result.success
    assert len(tool.calls) == 2
    assert tool.calls[1]["category"] == "news"
    assert tool.calls[1]["start_published_date"]
    assert result.sources[0].published_at == "2026-05-01T00:00:00Z"
    assert result.sources[0].is_third_party


def test_exa_research_tool_uses_cache_before_ttl_expiry(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    monkeypatch.setenv("EXA_RESEARCH_CACHE_TTL_HOURS", "24")
    tool = FakeExaWebsiteTool(
        [
            [
                {
                    "title": "Gusto | Payroll and HR",
                    "url": "https://gusto.com/",
                    "highlights": ["Gusto positions around payroll and HR."],
                    "text": "Gusto helps companies manage payroll and HR with a public website value proposition.",
                }
            ]
        ]
    )
    tool_input = ToolInput(competitor_name="Gusto", domain="gusto.com", category="website_positioning")

    first = tool.run(tool_input)
    monkeypatch.setenv("EXA_API_KEY", "")
    second = tool.run(tool_input)

    assert first.success
    assert second.success
    assert len(tool.calls) == 1
    assert second.metadata["cache"]["hit"] is True
    assert second.metadata["api_response"]["cache_hit"] is True
