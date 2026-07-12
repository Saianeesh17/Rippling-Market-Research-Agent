from __future__ import annotations

from src.schemas import CoverageGap
from src.state import AgentState


NEXT_TOOL_BY_CATEGORY = {
    "website_positioning": "ExaWebsitePositioningTool",
    "product_pages": "ExaProductPagesTool",
    "pricing": "ExaPricingResearchTool",
    "paid_ads": "DummyMetaAdLibraryTool",
    "social": "DummyLinkedInApiTool",
    "press_news": "ExaPressNewsResearchTool",
    "comparison_pages": "DummyComparisonPageTool",
}

REAL_NEXT_TOOL_BY_CATEGORY = {
    "website_positioning": "ExaWebsitePositioningTool",
    "product_pages": "ExaProductPagesTool",
    "pricing": "ExaPricingResearchTool",
    "paid_ads": "AdyntelMetaAdsTool",
    "social": "ExaTwitterHandleSearchTool",
    "press_news": "ExaPressNewsResearchTool",
    "comparison_pages": None,
}


def detect_coverage_gaps(state: AgentState) -> AgentState:
    gaps = []
    if not state.coverage_summary:
        state.coverage_gaps = gaps
        return state

    for summary in state.coverage_summary.categories:
        if summary.status in {"missing", "weak", "partial"}:
            next_tool_by_category = REAL_NEXT_TOOL_BY_CATEGORY if state.real_sources_only else NEXT_TOOL_BY_CATEGORY
            gaps.append(
                CoverageGap(
                    category=summary.category,
                    severity="high" if summary.status == "missing" else "medium",
                    reason=summary.notes,
                    suggested_next_tool=next_tool_by_category.get(summary.category),
                )
            )
    state.coverage_gaps = gaps
    state.logs.append(f"Detected {len(gaps)} coverage gaps or caveats.")
    return state
