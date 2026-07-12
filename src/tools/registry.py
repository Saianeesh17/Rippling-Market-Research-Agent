from __future__ import annotations

from typing import Dict, List

from src.tools.base import BaseSourceTool
from src.tools.adyntel_ads_tool import AdyntelGoogleAdsTool, AdyntelLinkedInAdsTool, AdyntelMetaAdsTool
from src.tools.apify_linkedin_tool import ApifyLinkedInCompanyPostsTool
from src.tools.apify_x_twitter_tool import ApifyXTwitterPostsSearchTool
from src.tools.exa_research_tools import (
    ExaPressNewsResearchTool,
    ExaPricingResearchTool,
    ExaProductPagesTool,
    ExaWebsitePositioningTool,
)
from src.tools.exa_tools import ExaCompanyDomainSearchTool, ExaLinkedInCompanySearchTool, ExaTwitterHandleSearchTool
from src.tools.dummy_tools import (
    DummyComparisonPageTool,
    DummyGoogleAdsTransparencyTool,
    DummyHomepageTool,
    DummyLandingPageFinderTool,
    DummyLinkedInApiTool,
    DummyMetaAdLibraryTool,
    DummyNewsSearchTool,
    DummyPressReleaseTool,
    DummyPricingFAQTool,
    DummyPricingPageTool,
    DummyProductPageTool,
    DummySitemapTool,
    DummyThirdPartyPricingTool,
    DummyTwitterApiTool,
    DummyWebSearchTool,
    DummyWebpageScraperTool,
)


TOOL_REGISTRY: Dict[str, List[BaseSourceTool]] = {
    "website_positioning": [
        ExaCompanyDomainSearchTool(),
        ExaWebsitePositioningTool(),
        DummyWebSearchTool(),
        DummyWebpageScraperTool(),
        DummyHomepageTool(),
        DummyProductPageTool(),
        DummySitemapTool(),
        DummyLandingPageFinderTool(),
    ],
    "product_pages": [
        ExaCompanyDomainSearchTool(),
        ExaProductPagesTool(),
        DummyWebSearchTool(),
        DummyWebpageScraperTool(),
        DummyProductPageTool(),
        DummySitemapTool(),
    ],
    "pricing": [
        ExaCompanyDomainSearchTool(),
        ExaPricingResearchTool(),
        DummyWebSearchTool(),
        DummyWebpageScraperTool(),
        DummyPricingPageTool(),
        DummyPricingFAQTool(),
        DummyThirdPartyPricingTool(),
    ],
    "paid_ads": [
        ExaCompanyDomainSearchTool(),
        AdyntelMetaAdsTool(),
        AdyntelLinkedInAdsTool(),
        AdyntelGoogleAdsTool(),
        DummyMetaAdLibraryTool(),
        DummyGoogleAdsTransparencyTool(),
    ],
    "social": [
        ExaLinkedInCompanySearchTool(),
        ApifyLinkedInCompanyPostsTool(),
        ExaTwitterHandleSearchTool(),
        ApifyXTwitterPostsSearchTool(),
        DummyTwitterApiTool(),
        DummyLinkedInApiTool(),
    ],
    "press_news": [
        ExaCompanyDomainSearchTool(),
        ExaPressNewsResearchTool(),
        DummyWebSearchTool(),
        DummyNewsSearchTool(),
        DummyPressReleaseTool(),
    ],
    "comparison_pages": [
        DummyWebSearchTool(),
        DummyWebpageScraperTool(),
        DummyComparisonPageTool(),
    ],
}


def get_tools_for_category(category: str, *, real_only: bool = False) -> List[BaseSourceTool]:
    tools = TOOL_REGISTRY.get(category, [])
    if real_only:
        return [tool for tool in tools if not getattr(tool, "is_dummy_tool", False)]
    return tools
