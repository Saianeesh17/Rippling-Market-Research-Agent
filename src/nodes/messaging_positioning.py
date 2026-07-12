from __future__ import annotations

from collections import Counter

from src.data.dummy_sources import get_competitor_data
from src.schemas import MessagingSummary, MessagingTheme, PositioningSummary
from src.state import AgentState


def summarize_messaging(state: AgentState) -> AgentState:
    if not state.competitor:
        return state
    if state.real_sources_only:
        return _summarize_real_source_messaging(state)
    data = get_competitor_data(state.competitor.name)
    counts = Counter(claim.theme for claim in state.extracted_claims)
    themes = []
    for theme, frequency in counts.most_common():
        matching = [claim for claim in state.extracted_claims if claim.theme == theme]
        avg_conf = round(sum(claim.confidence for claim in matching) / len(matching), 2)
        themes.append(
            MessagingTheme(
                theme=theme,
                frequency=frequency,
                confidence=avg_conf,
                supporting_claim_ids=[claim.claim_id for claim in matching],
            )
        )

    state.messaging_summary = MessagingSummary(
        top_messaging_themes=themes,
        positioning_summary=PositioningSummary(
            primary_positioning=str(data["primary_positioning"]),
            target_personas=list(data["personas"]),
            target_segments=list(data["segments"]),
            main_differentiators_claimed=list(data["differentiators"]),
            confidence=round(max([claim.confidence for claim in state.extracted_claims] or [0.55]), 2),
        ),
    )
    state.logs.append("Summarized messaging and positioning.")
    return state


def _summarize_real_source_messaging(state: AgentState) -> AgentState:
    counts = Counter(claim.theme for claim in state.extracted_claims)
    themes = []
    for theme, frequency in counts.most_common():
        matching = [claim for claim in state.extracted_claims if claim.theme == theme]
        avg_conf = round(sum(claim.confidence for claim in matching) / len(matching), 2)
        themes.append(
            MessagingTheme(
                theme=theme,
                frequency=frequency,
                confidence=avg_conf,
                supporting_claim_ids=[claim.claim_id for claim in matching],
            )
        )

    top_claim = max(state.extracted_claims, key=lambda claim: claim.confidence, default=None)
    state.messaging_summary = MessagingSummary(
        top_messaging_themes=themes,
        positioning_summary=PositioningSummary(
            primary_positioning=top_claim.claim if top_claim else "Insufficient real-source evidence to summarize positioning.",
            target_personas=[],
            target_segments=[],
            main_differentiators_claimed=[theme.theme for theme in themes[:4]],
            confidence=round(max([claim.confidence for claim in state.extracted_claims] or [0.0]), 2),
        ),
    )
    state.logs.append("Summarized messaging and positioning from real sources.")
    return state
