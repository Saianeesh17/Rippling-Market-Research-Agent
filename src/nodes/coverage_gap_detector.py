from __future__ import annotations

from src.schemas import CoverageGap
from src.state import AgentState


NEXT_TOOL_BY_CATEGORY = {
    "website_positioning": "DummyWebSearchTool",
    "product_pages": "DummyProductPageTool",
    "pricing": "DummyThirdPartyPricingTool",
    "paid_ads": "DummyMetaAdLibraryTool",
    "social": "DummyLinkedInApiTool",
    "press_news": "DummyNewsSearchTool",
    "comparison_pages": "DummyComparisonPageTool",
}


def detect_coverage_gaps(state: AgentState) -> AgentState:
    gaps = []
    if not state.coverage_summary:
        state.coverage_gaps = gaps
        return state

    for summary in state.coverage_summary.categories:
        if summary.status in {"missing", "weak", "partial"}:
            gaps.append(
                CoverageGap(
                    category=summary.category,
                    severity="high" if summary.status == "missing" else "medium",
                    reason=summary.notes,
                    suggested_next_tool=NEXT_TOOL_BY_CATEGORY.get(summary.category),
                )
            )
    state.coverage_gaps = gaps
    state.logs.append(f"Detected {len(gaps)} coverage gaps or caveats.")
    return state

