from __future__ import annotations

from statistics import mean

from src.config import utc_now_iso
from src.data.dummy_sources import get_competitor_data
from src.schemas import ExtractedClaim
from src.state import AgentState


def extract_evidence_claims(state: AgentState) -> AgentState:
    if not state.competitor:
        return state
    data = get_competitor_data(state.competitor.name)
    sources_by_id = {source.source_id: source for source in state.discovered_sources}
    analyses_by_theme = {}
    for analysis in state.source_analyses:
        for theme in analysis.themes:
            analyses_by_theme.setdefault(theme, []).append(analysis)

    claims = []
    for index, theme_data in enumerate(data["themes"], start=1):
        theme = theme_data["theme"]
        matched = analyses_by_theme.get(theme, [])
        if not matched:
            continue
        source_ids = sorted({analysis.source_id for analysis in matched})
        source_types = sorted({sources_by_id[source_id].source_type for source_id in source_ids if source_id in sources_by_id})
        evidence = []
        confidences = []
        for analysis in matched[:4]:
            evidence.extend(analysis.observations[:1])
            confidences.append(analysis.confidence)
        source_diversity_bonus = min(0.1, 0.03 * len(source_types))
        confidence = round(min(0.98, mean(confidences) + source_diversity_bonus), 2) if confidences else 0.4
        if theme == "pricing packaging caveat" and any(
            sources_by_id[source_id].is_third_party for source_id in source_ids if source_id in sources_by_id
        ):
            confidence = min(confidence, 0.68)
        if state.competitor.confidence < 0.7:
            confidence = min(confidence, 0.62)
        claims.append(
            ExtractedClaim(
                claim_id=f"claim_{index:03d}",
                claim=str(theme_data["claim"]),
                theme=theme,
                source_ids=source_ids,
                evidence_snippets=evidence[:3],
                source_types=source_types,
                persona=str(theme_data.get("persona", "")),
                funnel_stage=str(theme_data.get("funnel_stage", "awareness")),
                confidence=confidence,
                timestamp=utc_now_iso(),
            )
        )
    state.extracted_claims = claims
    state.logs.append(f"Extracted {len(claims)} grounded claims.")
    return state

