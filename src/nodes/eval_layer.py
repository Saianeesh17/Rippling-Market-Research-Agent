from __future__ import annotations

from statistics import mean

from src.schemas import EvalSummary
from src.state import AgentState


def evaluate_output(state: AgentState) -> AgentState:
    coverage_score = _coverage_score(state)
    grounded = [claim for claim in state.extracted_claims if claim.source_ids and claim.timestamp]
    unsupported_count = len(state.extracted_claims) - len(grounded)
    claim_grounding_score = round(len(grounded) / len(state.extracted_claims), 2) if state.extracted_claims else 0.0
    public_source_compliance = all(source.is_public for source in state.discovered_sources)
    rec_specificity = _recommendation_score(state)
    third_party_caveat = _third_party_caveat_score(state)
    weak_sections = []
    if state.coverage_summary:
        weak_sections = [
            f"{summary.category} coverage {summary.status}"
            for summary in state.coverage_summary.categories
            if summary.status in {"partial", "weak", "missing"}
        ]
    component_scores = [
        coverage_score,
        claim_grounding_score,
        rec_specificity,
        third_party_caveat,
        1.0 if public_source_compliance else 0.0,
    ]
    overall = round(mean(component_scores), 2)
    state.eval_summary = EvalSummary(
        source_coverage_score=coverage_score,
        claim_grounding_score=claim_grounding_score,
        unsupported_claim_count=unsupported_count,
        json_schema_valid=True,
        recommendation_specificity_score=rec_specificity,
        third_party_caveat_score=third_party_caveat,
        public_source_compliance=public_source_compliance,
        weak_sections=weak_sections,
        overall_quality_score=overall,
        explanation="Evaluation checks grounding, bounded sources, caveats, and recommendation specificity.",
    )
    state.logs.append(f"Eval complete: overall quality score {overall}.")
    return state


def _coverage_score(state: AgentState) -> float:
    if not state.coverage_summary:
        return 0.0
    values = {"strong": 1.0, "medium": 0.78, "partial": 0.58, "weak": 0.4, "missing": 0.0}
    return round(mean(values.get(summary.status, 0.0) for summary in state.coverage_summary.categories), 2)


def _recommendation_score(state: AgentState) -> float:
    if not state.rippling_opportunities:
        return 0.0
    valid = [
        opportunity
        for opportunity in state.rippling_opportunities
        if opportunity.supporting_claim_ids and opportunity.mapped_rippling_pillars and opportunity.example_copy
    ]
    return round(len(valid) / len(state.rippling_opportunities), 2)


def _third_party_caveat_score(state: AgentState) -> float:
    has_third_party_pricing = any(
        source.source_type == "pricing" and source.is_third_party for source in state.discovered_sources
    )
    if not has_third_party_pricing:
        return 1.0
    caveated = any(
        "third-party" in claim.claim.lower() or "lower-confidence" in claim.claim.lower()
        for claim in state.extracted_claims
    )
    return 0.9 if caveated else 0.35
