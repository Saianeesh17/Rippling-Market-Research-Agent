from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from src.config import utc_now_iso
from src.data.dummy_rippling_positioning import RIPPLING_CURRENT_POSITION, RIPPLING_POSITIONING_PILLARS
from src.data.dummy_sources import get_competitor_data
from src.llm.base import BaseLLM, llm_token_usage_fields
from src.schemas import LLMCallLog, RipplingOpportunity
from src.state import AgentState


MAX_LLM_OPPORTUNITIES = 3
MAX_LLM_CLAIMS = 16
MAX_LLM_SOURCES = 18
MAX_LLM_SECTION_CHARS = 1800
MAX_LLM_SOURCE_CONTENT_CHARS = 700


def map_rippling_opportunities(state: AgentState, llm: BaseLLM | None = None) -> AgentState:
    if not state.competitor:
        return state
    if state.real_sources_only:
        if llm and _has_opportunity_evidence(state):
            opportunities = _try_llm_rippling_opportunities(state, llm)
            if opportunities:
                state.rippling_opportunities = opportunities
                state.logs.append(
                    f"Mapped {len(opportunities)} Rippling opportunities with LLM from grounded evidence."
                )
                return state
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


def _has_opportunity_evidence(state: AgentState) -> bool:
    return bool(state.extracted_claims or state.category_report_sections or state.discovered_sources)


def _try_llm_rippling_opportunities(state: AgentState, llm: BaseLLM) -> list[RipplingOpportunity] | None:
    model = getattr(llm, "model", "unknown")
    provider = getattr(llm, "provider", "llm")
    response = ""
    try:
        response = llm.complete(
            _llm_opportunity_prompt(state),
            system_prompt=(
                "You are a competitive positioning strategist. Return valid JSON only. "
                "Use the provided target-company evidence and Rippling positioning; do not invent facts."
            ),
            json_mode=True,
        ).strip()
        payload = _json_from_text(response)
        opportunities = _opportunities_from_llm_payload(state, payload)
        if not opportunities:
            raise ValueError("LLM returned no valid grounded opportunities.")
        state.llm_call_logs.append(
            LLMCallLog(
                stage="rippling_opportunity_mapper",
                provider=provider,
                model=model,
                success=True,
                **llm_token_usage_fields(llm),
                response_text=response,
                timestamp=utc_now_iso(),
            )
        )
        return opportunities
    except Exception as exc:
        state.llm_call_logs.append(
            LLMCallLog(
                stage="rippling_opportunity_mapper",
                provider=provider,
                model=model,
                success=False,
                **llm_token_usage_fields(llm),
                response_text=response or None,
                error=str(exc),
                timestamp=utc_now_iso(),
            )
        )
        state.logs.append(f"LLM Rippling opportunity mapper failed; using deterministic fallback: {exc}")
        return None


def _llm_opportunity_prompt(state: AgentState) -> str:
    assert state.competitor is not None
    allowed_evidence_ids = _known_evidence_ids(state)
    return json.dumps(
        {
            "task": (
                "Generate 1 to 3 Market Opportunities for Rippling. Compare the target company's grounded public "
                "positioning against Rippling's current positioning and pillars. The static Rippling positioning is "
                "allowed as strategic context, but target-company strategy and gaps must come only from the supplied "
                "claims, category sections, and public sources."
            ),
            "rules": [
                "Return JSON only.",
                "Do not write markdown.",
                "Do not invent private strategy, customer claims, roadmap claims, or unsupported competitor facts.",
                "Each opportunity must cite at least one ID from allowed_evidence_ids.",
                "mapped_rippling_pillars must use exact pillar names from rippling_positioning_pillars.",
                "Make the gap specific to the target company's public evidence, not a generic Rippling sales pitch.",
            ],
            "output_schema": {
                "opportunities": [
                    {
                        "competitor_strategy": "evidence-grounded summary of the target company's public strategy",
                        "competitor_gap": "specific positioning gap Rippling can exploit",
                        "why_gap_matters": "buyer-relevant reason this gap matters",
                        "rippling_advantage": "how Rippling's current position addresses the gap",
                        "campaign_angle": "short actionable angle",
                        "example_copy": "one concise campaign copy example",
                        "supporting_evidence_ids": ["claim_001"],
                        "mapped_rippling_pillars": ["Unified HR, IT, and Finance"],
                        "confidence": 0.75,
                    }
                ]
            },
            "competitor": state.competitor.model_dump(mode="json"),
            "rippling_current_position": RIPPLING_CURRENT_POSITION,
            "rippling_positioning_pillars": [
                pillar.model_dump(mode="json") for pillar in RIPPLING_POSITIONING_PILLARS
            ],
            "allowed_evidence_ids": allowed_evidence_ids,
            "grounded_claims": [
                {
                    "claim_id": claim.claim_id,
                    "claim": _compact_text(claim.claim, limit=420),
                    "theme": claim.theme,
                    "source_ids": claim.source_ids,
                    "source_types": claim.source_types,
                    "confidence": claim.confidence,
                    "evidence_snippets": [
                        _compact_text(snippet, limit=240) for snippet in claim.evidence_snippets[:2]
                    ],
                }
                for claim in state.extracted_claims[:MAX_LLM_CLAIMS]
            ],
            "category_report_sections": [
                {
                    "section_id": section.section_id,
                    "category": section.category,
                    "title": section.title,
                    "markdown": _compact_text(section.markdown, limit=MAX_LLM_SECTION_CHARS),
                    "source_ids": section.source_ids,
                    "confidence": section.confidence,
                }
                for section in state.category_report_sections
            ],
            "public_sources": [
                {
                    "source_id": source.source_id,
                    "source_type": source.source_type,
                    "title": source.title,
                    "url": source.url,
                    "is_official": source.is_official,
                    "is_third_party": source.is_third_party,
                    "published_at": source.published_at,
                    "content": _compact_text(source.content, limit=MAX_LLM_SOURCE_CONTENT_CHARS),
                }
                for source in state.discovered_sources[:MAX_LLM_SOURCES]
            ],
            "coverage_gaps": [gap.model_dump(mode="json") for gap in state.coverage_gaps],
        },
        indent=2,
    )


def _opportunities_from_llm_payload(state: AgentState, payload: Any) -> list[RipplingOpportunity]:
    items = payload.get("opportunities") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("Expected an opportunities list.")

    known_ids = set(_known_evidence_ids(state))
    opportunities = []
    for index, item in enumerate(items[:MAX_LLM_OPPORTUNITIES], start=1):
        if not isinstance(item, dict):
            continue

        competitor_strategy = _required_text(item, "competitor_strategy")
        competitor_gap = _required_text(item, "competitor_gap")
        why_gap_matters = _required_text(item, "why_gap_matters")
        rippling_advantage = _required_text(item, "rippling_advantage")
        campaign_angle = _required_text(item, "campaign_angle")
        example_copy = _required_text(item, "example_copy")
        if not all(
            [
                competitor_strategy,
                competitor_gap,
                why_gap_matters,
                rippling_advantage,
                campaign_angle,
                example_copy,
            ]
        ):
            continue

        support_ids = _valid_supporting_ids(
            item.get("supporting_evidence_ids") or item.get("supporting_claim_ids") or item.get("source_ids"),
            known_ids,
        )
        if not support_ids:
            support_ids = _fallback_support_ids(state)
        if not support_ids:
            continue

        mapped_pillars = _valid_mapped_pillars(item.get("mapped_rippling_pillars"))
        if not mapped_pillars:
            mapped_pillars = _fallback_pillars()

        opportunities.append(
            RipplingOpportunity(
                opportunity_id=f"opp_{index:03d}",
                competitor_strategy=competitor_strategy,
                competitor_gap=competitor_gap,
                why_gap_matters=why_gap_matters,
                rippling_advantage=rippling_advantage,
                campaign_angle=campaign_angle,
                example_copy=example_copy,
                supporting_claim_ids=support_ids,
                mapped_rippling_pillars=mapped_pillars,
                confidence=_confidence_from_llm(item.get("confidence")),
            )
        )
    return opportunities


def _required_text(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str):
        return ""
    return _compact_text(value.strip(), limit=700)


def _valid_supporting_ids(raw_value: Any, known_ids: set[str]) -> list[str]:
    if isinstance(raw_value, str):
        values = [part.strip() for part in raw_value.split(",")]
    elif isinstance(raw_value, list):
        values = [str(value).strip() for value in raw_value]
    else:
        values = []

    support_ids = []
    for value in values:
        if value in known_ids and value not in support_ids:
            support_ids.append(value)
        if len(support_ids) >= 4:
            break
    return support_ids


def _valid_mapped_pillars(raw_value: Any) -> list[str]:
    if isinstance(raw_value, str):
        values = [raw_value]
    elif isinstance(raw_value, list):
        values = [str(value).strip() for value in raw_value]
    else:
        values = []

    pillar_by_lower = {pillar.pillar.lower(): pillar.pillar for pillar in RIPPLING_POSITIONING_PILLARS}
    mapped = []
    for value in values:
        pillar = pillar_by_lower.get(value.lower())
        if pillar and pillar not in mapped:
            mapped.append(pillar)
        if len(mapped) >= 4:
            break
    return mapped


def _fallback_support_ids(state: AgentState) -> list[str]:
    if state.extracted_claims:
        return [claim.claim_id for claim in state.extracted_claims[:4]]
    if state.category_report_sections:
        return [section.section_id for section in state.category_report_sections[:4]]
    return [source.source_id for source in state.discovered_sources[:4]]


def _fallback_pillars() -> list[str]:
    preferred = {
        "Unified HR, IT, and Finance",
        "Employee lifecycle automation",
        "Identity, app, and device management",
        "Spend management",
    }
    return [pillar.pillar for pillar in RIPPLING_POSITIONING_PILLARS if pillar.pillar in preferred]


def _confidence_from_llm(raw_value: Any) -> float:
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        value = 0.65
    if value > 1:
        value = value / 100
    return round(max(0.0, min(0.95, value)), 2)


def _known_evidence_ids(state: AgentState) -> list[str]:
    ids = []
    ids.extend(claim.claim_id for claim in state.extracted_claims)
    ids.extend(section.section_id for section in state.category_report_sections)
    ids.extend(source.source_id for source in state.discovered_sources)
    return ids


def _json_from_text(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(content[start : end + 1])


def _compact_text(text: str, *, limit: int) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _map_real_source_rippling_opportunities(state: AgentState) -> AgentState:
    # Deterministic fallback for no-LLM runs and failed opportunity-generation calls.
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
