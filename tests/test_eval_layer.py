from __future__ import annotations

from src.graph import run_graph


def test_eval_scores_are_between_zero_and_one(tmp_path):
    state = run_graph("Gusto", output_dir=tmp_path)
    summary = state.eval_summary
    assert summary

    scores = [
        summary.source_coverage_score,
        summary.claim_grounding_score,
        summary.recommendation_specificity_score,
        summary.third_party_caveat_score,
        summary.overall_quality_score,
    ]
    assert all(0 <= score <= 1 for score in scores)


def test_third_party_pricing_claims_get_lower_confidence(tmp_path):
    state = run_graph("Gusto", output_dir=tmp_path)
    pricing_claims = [claim for claim in state.extracted_claims if "pricing" in claim.theme]

    assert pricing_claims
    assert all(claim.confidence <= 0.68 for claim in pricing_claims)
    assert state.eval_summary
    assert state.eval_summary.third_party_caveat_score >= 0.9

