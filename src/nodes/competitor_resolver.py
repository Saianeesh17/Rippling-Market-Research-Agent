from __future__ import annotations

from src.data.dummy_sources import competitor_key, get_competitor_data
from src.schemas import CompetitorProfile
from src.state import AgentState
from src.tools.domain_utils import normalize_company_domain


def resolve_competitor(state: AgentState) -> AgentState:
    if state.real_sources_only:
        profile = _resolve_competitor_from_user_input(state.user_input)
        state.competitor = profile
        state.logs.append(f"Resolved competitor from user input: {profile.name} / {profile.domain or 'unknown domain'}")
        return state

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


def _resolve_competitor_from_user_input(user_input: str) -> CompetitorProfile:
    raw = user_input.strip() or "Unknown Competitor"
    domain = normalize_company_domain(raw) if "." in raw or "://" in raw else ""
    if domain:
        name = domain.split(".")[0].replace("-", " ").title()
        confidence = 0.68
    else:
        name = raw
        confidence = 0.5
    return CompetitorProfile(
        name=name,
        domain=domain or None,
        category="unknown",
        description="Competitor profile should be inferred from public sources gathered during this run.",
        confidence=confidence,
    )
