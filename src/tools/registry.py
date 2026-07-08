from __future__ import annotations

from typing import Dict, List

from src.tools.base import BaseSourceTool
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
        DummyWebSearchTool(),
        DummyWebpageScraperTool(),
        DummyHomepageTool(),
        DummyProductPageTool(),
        DummySitemapTool(),
        DummyLandingPageFinderTool(),
    ],
    "product_pages": [
        DummyWebSearchTool(),
        DummyWebpageScraperTool(),
        DummyProductPageTool(),
        DummySitemapTool(),
    ],
    "pricing": [
        DummyWebSearchTool(),
        DummyWebpageScraperTool(),
        DummyPricingPageTool(),
        DummyPricingFAQTool(),
        DummyThirdPartyPricingTool(),
    ],
    "paid_ads": [
        DummyMetaAdLibraryTool(),
        DummyGoogleAdsTransparencyTool(),
    ],
    "social": [
        DummyTwitterApiTool(),
        DummyLinkedInApiTool(),
    ],
    "press_news": [
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


def get_tools_for_category(category: str) -> List[BaseSourceTool]:
    return TOOL_REGISTRY.get(category, [])

