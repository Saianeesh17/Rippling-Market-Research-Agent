from __future__ import annotations

import json

from src.graph import run_graph


def test_pipeline_runs_end_to_end_for_gusto(tmp_path):
    state = run_graph("Gusto", output_dir=tmp_path)

    assert state.competitor
    assert state.competitor.name == "Gusto"
    assert state.final_markdown_path
    assert state.final_json_path
    assert state.final_log_path
    assert state.eval_summary
    assert state.eval_summary.overall_quality_score > 0


def test_pipeline_creates_markdown_and_json_files(tmp_path):
    state = run_graph("Gusto", output_dir=tmp_path)

    markdown = tmp_path / "gusto_brief.md"
    data = tmp_path / "gusto_data.json"
    log = tmp_path / "gusto_run.log"
    assert markdown.exists()
    assert data.exists()
    assert log.exists()
    payload = json.loads(data.read_text(encoding="utf-8"))
    assert payload["competitor"]["name"] == "Gusto"
    assert payload["tool_call_logs"]
    assert "Tool Calls" in log.read_text(encoding="utf-8")


def test_every_claim_is_grounded(tmp_path):
    state = run_graph("Gusto", output_dir=tmp_path)

    assert state.extracted_claims
    assert all(claim.source_ids for claim in state.extracted_claims)
    assert all(claim.timestamp for claim in state.extracted_claims)


def test_opportunities_have_claims_and_pillars(tmp_path):
    state = run_graph("Gusto", output_dir=tmp_path)

    assert state.rippling_opportunities
    assert all(opp.supporting_claim_ids for opp in state.rippling_opportunities)
    assert all(opp.mapped_rippling_pillars for opp in state.rippling_opportunities)


def test_unknown_competitor_fallback_is_lower_confidence(tmp_path):
    state = run_graph("ACME Workforce Tool", output_dir=tmp_path)

    assert state.competitor
    assert state.competitor.confidence < 0.7
    assert state.eval_summary
    assert state.extracted_claims
    assert max(claim.confidence for claim in state.extracted_claims) <= 0.62
