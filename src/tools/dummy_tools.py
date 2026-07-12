from __future__ import annotations

from typing import List

from src.data.dummy_sources import build_source, competitor_key, content_for, get_competitor_data
from src.schemas import SourceRecord, ToolInput, ToolResult
from src.tools.base import BaseSourceTool


class DummySourceTool(BaseSourceTool):
    description = "Dummy public-source adapter."
    source_category = "generic"
    reliability_weight = 0.6
    allowed_agents: List[str] = []
    is_dummy_tool = True

    def _result(self, tool_input: ToolInput, sources: List[SourceRecord]) -> ToolResult:
        return ToolResult(tool_name=self.name, success=True, sources=sources)


class DummyWebSearchTool(DummySourceTool):
    name = "DummyWebSearchTool"
    description = "Mock broad web search for public pages."
    source_category = "web_search"
    reliability_weight = 0.58
    allowed_agents = ["website_positioning", "product_pages", "pricing", "press_news", "comparison_pages"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        category = tool_input.category or "website_positioning"
        content = content_for(tool_input.competitor_name, "third_party_pricing" if category == "pricing" else "homepage")
        source = build_source(
            tool_input.competitor_name,
            self.name,
            category,
            f"Public search result for {category.replace('_', ' ')}",
            content,
            "search_result",
            self.reliability_weight,
            is_third_party=True,
            notes="Broad public search result; lower reliability than official pages.",
        )
        return self._result(tool_input, [source])


class DummyWebpageScraperTool(DummySourceTool):
    name = "DummyWebpageScraperTool"
    description = "Mock scraper for public webpage text."
    source_category = "webpage_scraper"
    reliability_weight = 0.72
    allowed_agents = ["website_positioning", "product_pages", "pricing", "press_news", "comparison_pages"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        purpose = "pricing" if tool_input.category == "pricing" else "product"
        source = build_source(
            tool_input.competitor_name,
            self.name,
            tool_input.category or "website_positioning",
            "Scraped public page",
            content_for(tool_input.competitor_name, purpose),
            "webpage",
            self.reliability_weight,
            url_path="/public-page",
            is_official=True,
            notes="Dummy scraped public page.",
        )
        return self._result(tool_input, [source])


class DummyHomepageTool(DummySourceTool):
    name = "DummyHomepageTool"
    description = "Mock official homepage fetcher."
    source_category = "website"
    reliability_weight = 0.95
    allowed_agents = ["website_positioning"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        source = build_source(
            tool_input.competitor_name,
            self.name,
            "website_positioning",
            "Official homepage",
            content_for(tool_input.competitor_name, "homepage"),
            "homepage",
            self.reliability_weight,
            url_path="/",
            is_official=True,
        )
        return self._result(tool_input, [source])


class DummyProductPageTool(DummySourceTool):
    name = "DummyProductPageTool"
    description = "Mock official product page discovery."
    source_category = "product_pages"
    reliability_weight = 0.92
    allowed_agents = ["website_positioning", "product_pages"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        data = get_competitor_data(tool_input.competitor_name)
        pages = [
            ("Core product page", "/product/core"),
            ("Workflow product page", "/product/workflows"),
        ]
        sources = [
            build_source(
                tool_input.competitor_name,
                self.name,
                tool_input.category or "product_pages",
                title,
                f"{content_for(tool_input.competitor_name, 'product')} Differentiators claimed: {', '.join(data['differentiators'])}.",
                "product_page",
                self.reliability_weight,
                url_path=path,
                is_official=True,
            )
            for title, path in pages
        ]
        return self._result(tool_input, sources)


class DummySitemapTool(DummySourceTool):
    name = "DummySitemapTool"
    description = "Mock sitemap parser for public pages."
    source_category = "sitemap"
    reliability_weight = 0.82
    allowed_agents = ["website_positioning", "product_pages"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        source = build_source(
            tool_input.competitor_name,
            self.name,
            tool_input.category or "product_pages",
            "Public sitemap product cluster",
            f"Sitemap-style dummy data lists public product and solution pages. {content_for(tool_input.competitor_name, 'product')}",
            "sitemap",
            self.reliability_weight,
            url_path="/sitemap.xml",
            is_official=True,
        )
        return self._result(tool_input, [source])


class DummyLandingPageFinderTool(DummySourceTool):
    name = "DummyLandingPageFinderTool"
    description = "Mock landing page finder for campaign pages."
    source_category = "landing_pages"
    reliability_weight = 0.86
    allowed_agents = ["website_positioning"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        source = build_source(
            tool_input.competitor_name,
            self.name,
            "website_positioning",
            "Campaign landing page",
            f"Campaign page uses conversion-oriented copy. {content_for(tool_input.competitor_name, 'homepage')}",
            "landing_page",
            self.reliability_weight,
            url_path="/campaign",
            is_official=True,
        )
        return self._result(tool_input, [source])


class DummyPricingPageTool(DummySourceTool):
    name = "DummyPricingPageTool"
    description = "Mock official pricing page adapter."
    source_category = "pricing"
    reliability_weight = 0.93
    allowed_agents = ["pricing"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        key = competitor_key(tool_input.competitor_name)
        if key in {"gusto", "generic"}:
            return self._result(tool_input, [])
        source = build_source(
            tool_input.competitor_name,
            self.name,
            "pricing",
            "Official pricing and packages page",
            content_for(tool_input.competitor_name, "pricing"),
            "pricing_page",
            self.reliability_weight,
            url_path="/pricing",
            is_official=True,
        )
        return self._result(tool_input, [source])


class DummyPricingFAQTool(DummySourceTool):
    name = "DummyPricingFAQTool"
    description = "Mock official pricing FAQ adapter."
    source_category = "pricing"
    reliability_weight = 0.84
    allowed_agents = ["pricing"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        source = build_source(
            tool_input.competitor_name,
            self.name,
            "pricing",
            "Official pricing FAQ",
            f"{content_for(tool_input.competitor_name, 'pricing')} Exact pricing may require demo or package selection in this dummy source.",
            "pricing_faq",
            self.reliability_weight,
            url_path="/pricing-faq",
            is_official=True,
            notes="Official but incomplete pricing evidence.",
        )
        return self._result(tool_input, [source])


class DummyThirdPartyPricingTool(DummySourceTool):
    name = "DummyThirdPartyPricingTool"
    description = "Mock third-party public pricing source."
    source_category = "pricing"
    reliability_weight = 0.55
    allowed_agents = ["pricing"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        source = build_source(
            tool_input.competitor_name,
            self.name,
            "pricing",
            "Third-party pricing estimate",
            content_for(tool_input.competitor_name, "third_party_pricing"),
            "third_party_pricing",
            self.reliability_weight,
            is_third_party=True,
            notes="Lower confidence applied because this is a third-party public source.",
        )
        return self._result(tool_input, [source])


class DummyMetaAdLibraryTool(DummySourceTool):
    name = "DummyMetaAdLibraryTool"
    description = "Mock Meta Ad Library adapter."
    source_category = "paid_ads"
    reliability_weight = 0.82
    allowed_agents = ["paid_ads"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        source = build_source(
            tool_input.competitor_name,
            self.name,
            "paid_ads",
            "Meta ad creative",
            content_for(tool_input.competitor_name, "ads"),
            "ad_library",
            self.reliability_weight,
            publisher="Meta Ad Library",
            is_official=True,
            published_at="2026-06-12T00:00:00Z",
        )
        return self._result(tool_input, [source])


class DummyGoogleAdsTransparencyTool(DummySourceTool):
    name = "DummyGoogleAdsTransparencyTool"
    description = "Mock Google Ads Transparency Center adapter."
    source_category = "paid_ads"
    reliability_weight = 0.8
    allowed_agents = ["paid_ads"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        source = build_source(
            tool_input.competitor_name,
            self.name,
            "paid_ads",
            "Google search ad",
            content_for(tool_input.competitor_name, "ads"),
            "ad_library",
            self.reliability_weight,
            publisher="Google Ads Transparency Center",
            is_official=True,
            published_at="2026-06-20T00:00:00Z",
        )
        return self._result(tool_input, [source])


class DummyTwitterApiTool(DummySourceTool):
    name = "DummyTwitterApiTool"
    description = "Mock Twitter/X public posts adapter."
    source_category = "social"
    reliability_weight = 0.74
    allowed_agents = ["social"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        source = build_source(
            tool_input.competitor_name,
            self.name,
            "social",
            "Twitter/X public post",
            content_for(tool_input.competitor_name, "social"),
            "social_post",
            self.reliability_weight,
            publisher="Twitter/X",
            is_official=True,
            published_at="2026-05-18T00:00:00Z",
        )
        return self._result(tool_input, [source])


class DummyLinkedInApiTool(DummySourceTool):
    name = "DummyLinkedInApiTool"
    description = "Mock LinkedIn public posts adapter."
    source_category = "social"
    reliability_weight = 0.78
    allowed_agents = ["social"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        source = build_source(
            tool_input.competitor_name,
            self.name,
            "social",
            "LinkedIn public post",
            content_for(tool_input.competitor_name, "social"),
            "social_post",
            self.reliability_weight,
            publisher="LinkedIn",
            is_official=True,
            published_at="2026-06-02T00:00:00Z",
        )
        return self._result(tool_input, [source])


class DummyPressReleaseTool(DummySourceTool):
    name = "DummyPressReleaseTool"
    description = "Mock official press release scraper."
    source_category = "press_news"
    reliability_weight = 0.86
    allowed_agents = ["press_news"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        source = build_source(
            tool_input.competitor_name,
            self.name,
            "press_news",
            "Product announcement",
            content_for(tool_input.competitor_name, "press"),
            "press_release",
            self.reliability_weight,
            url_path="/press/product-announcement",
            is_official=True,
            published_at="2026-04-10T00:00:00Z",
        )
        return self._result(tool_input, [source])


class DummyNewsSearchTool(DummySourceTool):
    name = "DummyNewsSearchTool"
    description = "Mock news search adapter."
    source_category = "press_news"
    reliability_weight = 0.66
    allowed_agents = ["press_news"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        source = build_source(
            tool_input.competitor_name,
            self.name,
            "press_news",
            "Third-party news mention",
            content_for(tool_input.competitor_name, "press"),
            "news_search",
            self.reliability_weight,
            is_third_party=True,
            published_at="2026-05-01T00:00:00Z",
        )
        return self._result(tool_input, [source])


class DummyComparisonPageTool(DummySourceTool):
    name = "DummyComparisonPageTool"
    description = "Mock comparison page adapter."
    source_category = "comparison_pages"
    reliability_weight = 0.76
    allowed_agents = ["comparison_pages"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        source = build_source(
            tool_input.competitor_name,
            self.name,
            "comparison_pages",
            "Public comparison page",
            content_for(tool_input.competitor_name, "comparison"),
            "comparison_page",
            self.reliability_weight,
            url_path="/compare",
            is_official=True,
        )
        return self._result(tool_input, [source])
