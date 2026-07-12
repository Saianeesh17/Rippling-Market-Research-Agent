from __future__ import annotations

from src.data.dummy_rippling_positioning import RIPPLING_POSITIONING_PILLARS
from src.data.dummy_sources import get_competitor_data
from src.schemas import RipplingOpportunity
from src.state import AgentState


def map_rippling_opportunities(state: AgentState) -> AgentState:
    if not state.competitor:
        return state
    if state.real_sources_only:
        return _map_real_source_rippling_opportunities(state)
    data = get_competitor_data(state.competitor.name)
    claim_ids = [claim.claim_id for claim in state.extracted_claims[:3]]
    pillars = [pillar.pillar for pillar in RIPPLING_POSITIONING_PILLARS]
    if "deel" in state.competitor.name.lower():
        mapped = [
            "Unified HR, IT, and Finance",
            "Identity, app, and device management",
            "Spend management",
        ]
        angle = "Global workforce operations should connect to every employee workflow."
        copy = "Hiring globally is only the start. Rippling connects the employee data to apps, devices, payroll, and spend."
    elif "bamboo" in state.competitor.name.lower():
        mapped = [
            "Unified HR, IT, and Finance",
            "Employee lifecycle automation",
            "Identity, app, and device management",
        ]
        angle = "HRIS is the record. Rippling is the action layer."
        copy = "When an employee changes roles, Rippling updates HR, apps, devices, payroll, and approvals in one workflow."
    else:
        mapped = [
            "Unified HR, IT, and Finance",
            "Employee lifecycle automation",
            "Identity, app, and device management",
            "Spend management",
        ]
        angle = "Payroll is only one part of the employee lifecycle."
        copy = "Your payroll tool handles payday. Rippling handles everything before and after it."

    mapped = [pillar for pillar in mapped if pillar in pillars]
    confidence = 0.86 if state.competitor.confidence >= 0.7 else 0.58
    state.rippling_opportunities = [
        RipplingOpportunity(
            opportunity_id="opp_001",
            competitor_strategy=str(data["primary_positioning"]),
            competitor_gap=str(data["gap"]),
            why_gap_matters=(
                "The gap gives Rippling room to frame the buying problem as broader than a single HR or payroll workflow."
            ),
            rippling_advantage=str(data["opportunity"]),
            campaign_angle=angle,
            example_copy=copy,
            supporting_claim_ids=claim_ids,
            mapped_rippling_pillars=mapped,
            confidence=confidence,
        )
    ]
    state.logs.append("Mapped Rippling opportunities.")
    return state


def _map_real_source_rippling_opportunities(state: AgentState) -> AgentState:
    claim_ids = [claim.claim_id for claim in state.extracted_claims[:3]]
    if not claim_ids:
        state.rippling_opportunities = []
        state.logs.append("Skipped Rippling opportunity mapping because no real-source claims were extracted.")
        return state

    pillars = [pillar.pillar for pillar in RIPPLING_POSITIONING_PILLARS]
    mapped = [
        pillar
        for pillar in [
            "Unified HR, IT, and Finance",
            "Employee lifecycle automation",
            "Identity, app, and device management",
            "Spend management",
        ]
        if pillar in pillars
    ]
    top_claim = state.extracted_claims[0]
    state.rippling_opportunities = [
        RipplingOpportunity(
            opportunity_id="opp_001",
            competitor_strategy=top_claim.claim,
            competitor_gap="Public-source evidence should be compared against Rippling's broader unified workflow narrative.",
            why_gap_matters="The gap gives Rippling room to frame the buying problem as broader than a single HR or payroll workflow.",
            rippling_advantage="Rippling can position around connected employee data across HR, IT, finance, apps, devices, payroll, and spend.",
            campaign_angle="Unify the employee lifecycle beyond the competitor's strongest public message.",
            example_copy="Your point solution may cover the visible workflow. Rippling connects the data, systems, and actions around it.",
            supporting_claim_ids=claim_ids,
            mapped_rippling_pillars=mapped,
            confidence=round(max(claim.confidence for claim in state.extracted_claims[:3]), 2),
        )
    ]
    state.logs.append("Mapped Rippling opportunities from real-source claims.")
    return state
