from __future__ import annotations

from collections import defaultdict
from statistics import mean

from src.config import SOURCE_CATEGORIES
from src.schemas import CoverageCategorySummary, CoverageSummary, SourceInventory
from src.state import AgentState


def review_source_coverage(state: AgentState) -> AgentState:
    grouped = defaultdict(list)
    for source in state.discovered_sources:
        grouped[source.source_type].append(source)

    summaries = []
    strong = []
    weak = []
    source_ids_by_category = {}
    category_counts = {}

    for category in SOURCE_CATEGORIES:
        sources = grouped.get(category, [])
        source_ids_by_category[category] = [source.source_id for source in sources]
        category_counts[category] = len(sources)
        official_count = sum(1 for source in sources if source.is_official)
        third_party_count = sum(1 for source in sources if source.is_third_party)
        avg_reliability = round(mean([source.reliability_weight for source in sources]), 2) if sources else 0.0
        status = _status_for(category, len(sources), official_count, third_party_count, avg_reliability)
        if status == "strong":
            strong.append(category)
        if status in {"missing", "weak", "partial"}:
            weak.append(category)
        summaries.append(
            CoverageCategorySummary(
                category=category,
                status=status,
                source_count=len(sources),
                official_count=official_count,
                third_party_count=third_party_count,
                avg_reliability=avg_reliability,
                notes=_notes_for(category, status, third_party_count),
            )
        )

    state.source_inventory = SourceInventory(
        total_sources=len(state.discovered_sources),
        category_counts=category_counts,
        source_ids_by_category=source_ids_by_category,
        official_source_count=sum(1 for source in state.discovered_sources if source.is_official),
        third_party_source_count=sum(1 for source in state.discovered_sources if source.is_third_party),
        tools_used=sorted({log.tool_name for log in state.tool_call_logs if log.success}),
    )
    overall = "usable" if len(strong) >= 3 and "website_positioning" in strong else "partial"
    state.coverage_summary = CoverageSummary(
        categories=summaries,
        overall_status=overall,
        strong_categories=strong,
        weak_categories=weak,
    )
    state.logs.append(f"Reviewed source coverage: {overall}.")
    return state


def _status_for(category: str, count: int, official_count: int, third_party_count: int, avg_reliability: float) -> str:
    if count == 0:
        return "missing"
    if category == "pricing" and third_party_count > 0:
        return "partial"
    if official_count == 0 and avg_reliability < 0.7:
        return "partial"
    if count >= 3 and official_count >= 1 and avg_reliability >= 0.75:
        return "strong"
    if count >= 2 and avg_reliability >= 0.65:
        return "medium"
    return "weak"


def _notes_for(category: str, status: str, third_party_count: int) -> str:
    if category == "pricing" and third_party_count:
        return "Pricing is caveated because at least one pricing source is third-party public evidence."
    if status == "missing":
        return "No useful public dummy sources found."
    if status == "partial":
        return "Coverage is usable but should be caveated."
    if status == "strong":
        return "Coverage has multiple public sources and official evidence."
    return "Coverage is useful but not deep."

