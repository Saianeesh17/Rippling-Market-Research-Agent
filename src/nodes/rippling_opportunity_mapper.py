from __future__ import annotations

from collections import defaultdict

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
    pillars = [pillar.pillar for pillar in RIPPLING_POSITIONING_PILLARS]
    base_pillars = [
        pillar
        for pillar in [
            "Unified HR, IT, and Finance",
            "Employee lifecycle automation",
            "Identity, app, and device management",
            "Spend management",
        ]
        if pillar in pillars
    ]
    company = state.competitor.name if state.competitor else "the competitor"
    categories = {source.source_type for source in state.discovered_sources}
    categories.update(section.category for section in state.category_report_sections)
    opportunities = []

    if categories & {"website_positioning", "product_pages"}:
        opportunities.append(
            _real_source_opportunity(
                state,
                opportunity_id="opp_001",
                source_types=["website_positioning", "product_pages"],
                competitor_strategy=(
                    f"{company} leads with an all-in-one payroll, HR, benefits, compliance, and SMB simplicity story."
                ),
                competitor_gap=(
                    "The public story is broad inside HR, but it is not visibly anchored in a single employee data model "
                    "that also drives IT, identity, devices, spend, and finance workflows."
                ),
                why_gap_matters=(
                    "A buyer who is already outgrowing basic payroll likely feels pain across onboarding, app access, "
                    "device handoff, approvals, expenses, and finance controls, not only payroll."
                ),
                rippling_advantage=(
                    "Rippling can frame the category around one workforce operating layer where HR changes trigger IT, "
                    "finance, payroll, app, device, and spend actions automatically."
                ),
                campaign_angle="Expand the buying criteria from HR suite to workforce operating system.",
                example_copy=(
                    "Payroll and HR are only part of the employee lifecycle. Rippling connects HR, IT, finance, apps, "
                    "devices, payroll, and spend in one system."
                ),
                mapped_pillars=base_pillars,
            )
        )

    if categories & {"press_news", "social", "paid_ads"}:
        opportunities.append(
            _real_source_opportunity(
                state,
                opportunity_id="opp_002",
                source_types=["press_news", "social", "paid_ads"],
                competitor_strategy=(
                    f"{company} is pushing AI and automation through product launches, social posts, and paid creative."
                ),
                competitor_gap=(
                    "The AI narrative is mostly framed around payroll, HR administration, approvals, and small-business "
                    "busywork, leaving room to question whether the automation spans every system an employee touches."
                ),
                why_gap_matters=(
                    "AI messaging is more defensible when it is tied to a wider action surface and richer operational data."
                ),
                rippling_advantage=(
                    "Rippling can position AI as automation across employee data, apps, permissions, devices, spend, "
                    "payroll, and finance controls, not just a helper layered on top of HR workflows."
                ),
                campaign_angle="Counter the AI teammate story with cross-functional automation.",
                example_copy=(
                    "An AI assistant can suggest the next HR task. Rippling automates the employee changes across every "
                    "system your business runs on."
                ),
                mapped_pillars=[pillar for pillar in base_pillars if pillar != "Global workforce management"],
            )
        )

    if "pricing" in categories or "paid_ads" in categories:
        opportunities.append(
            _real_source_opportunity(
                state,
                opportunity_id="opp_003",
                source_types=["pricing", "paid_ads"],
                competitor_strategy=(
                    f"{company} emphasizes transparent SMB pricing, unlimited payroll runs, and concrete feature-level value."
                ),
                competitor_gap=(
                    "Transparent payroll pricing does not answer the total cost of running separate HR, IT, identity, "
                    "device, expense, and finance systems as the company scales."
                ),
                why_gap_matters=(
                    "The more a customer grows, the more tool sprawl and manual handoffs can outweigh a narrow per-person "
                    "payroll price comparison."
                ),
                rippling_advantage=(
                    "Rippling can compete on consolidation value, fewer systems, fewer manual changes, and fewer operational "
                    "handoffs across teams."
                ),
                campaign_angle="Shift price comparison from payroll cost to operating cost.",
                example_copy=(
                    "Do not just compare payroll fees. Compare the cost of every manual handoff between HR, IT, finance, "
                    "identity, devices, and spend."
                ),
                mapped_pillars=[
                    pillar
                    for pillar in base_pillars
                    if pillar in {"Unified HR, IT, and Finance", "Spend management", "Employee lifecycle automation"}
                ],
            )
        )

    if not opportunities and state.discovered_sources:
        opportunities.append(
            _real_source_opportunity(
                state,
                opportunity_id="opp_001",
                source_types=sorted(categories),
                competitor_strategy=f"{company}'s public sources establish a focused workforce-management narrative.",
                competitor_gap="The available public evidence does not show the same breadth across HR, IT, spend, and finance.",
                why_gap_matters="The gap lets Rippling broaden the buyer's problem definition beyond the competitor's strongest workflow.",
                rippling_advantage="Rippling can position around connected employee data and cross-functional workforce automation.",
                campaign_angle="Broaden the conversation from point workflow to connected workforce operations.",
                example_copy="Your current tool may solve one workflow. Rippling connects the employee data and actions around it.",
                mapped_pillars=base_pillars,
            )
        )

    state.rippling_opportunities = opportunities
    state.logs.append(f"Mapped {len(opportunities)} Rippling opportunities from real-source evidence.")
    return state


def _real_source_opportunity(
    state: AgentState,
    *,
    opportunity_id: str,
    source_types: list[str],
    competitor_strategy: str,
    competitor_gap: str,
    why_gap_matters: str,
    rippling_advantage: str,
    campaign_angle: str,
    example_copy: str,
    mapped_pillars: list[str],
) -> RipplingOpportunity:
    support_ids = _supporting_evidence_ids(state, source_types)
    confidence = _opportunity_confidence(state, support_ids)
    return RipplingOpportunity(
        opportunity_id=opportunity_id,
        competitor_strategy=competitor_strategy,
        competitor_gap=competitor_gap,
        why_gap_matters=why_gap_matters,
        rippling_advantage=rippling_advantage,
        campaign_angle=campaign_angle,
        example_copy=example_copy,
        supporting_claim_ids=support_ids,
        mapped_rippling_pillars=mapped_pillars,
        confidence=confidence,
    )


def _supporting_evidence_ids(state: AgentState, source_types: list[str]) -> list[str]:
    wanted = set(source_types)
    claim_ids = [
        claim.claim_id
        for claim in state.extracted_claims
        if wanted.intersection(set(claim.source_types))
    ]
    if claim_ids:
        return claim_ids[:4]

    section_ids = [
        section.section_id
        for section in state.category_report_sections
        if section.category in wanted
    ]
    if section_ids:
        return section_ids[:4]

    source_ids_by_type: dict[str, list[str]] = defaultdict(list)
    for source in state.discovered_sources:
        source_ids_by_type[source.source_type].append(source.source_id)
    support = []
    for source_type in source_types:
        support.extend(source_ids_by_type.get(source_type, [])[:2])
    return support[:4]


def _opportunity_confidence(state: AgentState, support_ids: list[str]) -> float:
    if state.extracted_claims:
        supported_claims = [claim for claim in state.extracted_claims if claim.claim_id in support_ids]
        if supported_claims:
            return round(max(claim.confidence for claim in supported_claims), 2)
    if state.category_report_sections:
        return round(max(section.confidence for section in state.category_report_sections), 2)
    return 0.62 if support_ids else 0.45
