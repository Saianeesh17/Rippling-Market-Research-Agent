from __future__ import annotations

from src.data.dummy_sources import get_competitor_data
from src.schemas import SourceAnalysis
from src.state import AgentState


def analyze_sources(state: AgentState) -> AgentState:
    analyses = []
    for index, source in enumerate(state.discovered_sources, start=1):
        themes = _themes_for(source.competitor_name, source.content)
        observations = _observations_for(source.content)
        analyses.append(
            SourceAnalysis(
                analysis_id=f"analysis_{index:03d}",
                source_id=source.source_id,
                category=source.source_type,
                observations=observations,
                themes=themes,
                confidence=round(source.reliability_weight * source.confidence_modifier * source.relevance_score, 2),
            )
        )
    state.source_analyses = analyses
    state.logs.append(f"Analyzed {len(analyses)} sources.")
    return state


def _themes_for(competitor_name: str, content: str) -> list[str]:
    content_lower = content.lower()
    themes = []
    for theme in get_competitor_data(competitor_name)["themes"]:
        if any(keyword.lower() in content_lower for keyword in theme["keywords"]):
            themes.append(theme["theme"])
    if not themes:
        themes.append("general positioning")
    return themes


def _observations_for(content: str) -> list[str]:
    parts = [part.strip() for part in content.split(".") if part.strip()]
    return parts[:3] or [content[:160]]

