from __future__ import annotations

from src.data.dummy_sources import get_competitor_data
from src.schemas import SourceAnalysis
from src.state import AgentState


def analyze_sources(state: AgentState) -> AgentState:
    analyses = []
    for index, source in enumerate(state.discovered_sources, start=1):
        themes = _themes_for(source.competitor_name, source.content, source.source_type, state.real_sources_only)
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


def _themes_for(competitor_name: str, content: str, source_type: str, real_sources_only: bool = False) -> list[str]:
    if real_sources_only:
        return [_real_theme_for(source_type, content)]

    content_lower = content.lower()
    themes = []
    for theme in get_competitor_data(competitor_name)["themes"]:
        if any(keyword.lower() in content_lower for keyword in theme["keywords"]):
            themes.append(theme["theme"])
    if not themes:
        themes.append("general positioning")
    return themes


def _real_theme_for(source_type: str, content: str) -> str:
    if source_type == "pricing":
        return "pricing packaging caveat"
    themes = {
        "website_positioning": "website positioning",
        "product_pages": "product and use cases",
        "paid_ads": "paid ads messaging",
        "social": "social messaging",
        "press_news": "recent launches and announcements",
        "comparison_pages": "comparison positioning",
    }
    if source_type in themes:
        return themes[source_type]
    content_lower = content.lower()
    if any(token in content_lower for token in ["pricing", "price", "plan", "tier"]):
        return "pricing packaging caveat"
    return "general positioning"


def _observations_for(content: str) -> list[str]:
    parts = [part.strip() for part in content.split(".") if part.strip()]
    return parts[:3] or [content[:160]]
