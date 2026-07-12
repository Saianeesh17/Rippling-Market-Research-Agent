from __future__ import annotations

from src.data.dummy_sources import get_competitor_data
from src.schemas import RecentChange
from src.state import AgentState


def detect_recent_changes(state: AgentState) -> AgentState:
    if not state.competitor:
        return state
    if state.real_sources_only:
        return _detect_real_source_recent_changes(state)
    recent_source_ids = [
        source.source_id
        for source in state.discovered_sources
        if source.published_at and source.source_type in {"press_news", "paid_ads", "social"}
    ][:4]
    data = get_competitor_data(state.competitor.name)
    confidence = 0.76 if recent_source_ids else 0.45
    if state.competitor.confidence < 0.7:
        confidence = 0.5
    state.recent_changes = [
        RecentChange(
            change=str(data["recent_change"]),
            evidence_source_ids=recent_source_ids,
            interpretation="This is treated as a public messaging signal, not an internal roadmap claim.",
            confidence=confidence,
        )
    ]
    state.logs.append("Detected recent public messaging changes.")
    return state


def _detect_real_source_recent_changes(state: AgentState) -> AgentState:
    recent_sources = [
        source
        for source in state.discovered_sources
        if source.published_at and source.source_type in {"press_news", "paid_ads", "social"}
    ][:4]
    state.recent_changes = [
        RecentChange(
            change=f"Recent public source: {source.title}",
            evidence_source_ids=[source.source_id],
            interpretation="This is treated as a public messaging signal, not an internal roadmap claim.",
            confidence=round(source.reliability_weight * source.confidence_modifier, 2),
        )
        for source in recent_sources
    ]
    state.logs.append("Detected recent public messaging changes from real sources.")
    return state
