from __future__ import annotations

from src.data.dummy_sources import competitor_key, get_competitor_data
from src.schemas import CompetitorProfile
from src.state import AgentState


def resolve_competitor(state: AgentState) -> AgentState:
    key = competitor_key(state.user_input)
    data = get_competitor_data(key)
    if key == "generic":
        display_name = state.user_input.strip() or "Unknown Competitor"
        profile = CompetitorProfile(
            name=display_name,
            domain=None,
            category=str(data["category"]),
            description=str(data["description"]),
            confidence=float(data["confidence"]),
        )
    else:
        profile = CompetitorProfile(
            name=str(data["name"]),
            domain=str(data["domain"]),
            category=str(data["category"]),
            description=str(data["description"]),
            confidence=float(data["confidence"]),
        )
    state.competitor = profile
    state.logs.append(f"Resolved competitor: {profile.name} / {profile.domain or 'unknown domain'}")
    return state

