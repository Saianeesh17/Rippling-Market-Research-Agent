from __future__ import annotations

import json

from src.graph import run_graph
from src.config import utc_now_iso
from src.nodes.evidence_extraction import extract_evidence_claims
from src.nodes.output_writer import _product_positioning_lines
from src.nodes.source_analysis import analyze_sources
from src.schemas import CompetitorProfile, ExtractedClaim, SourceRecord
from src.state import AgentState


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
    assert payload["category_report_sections"]
    log_text = log.read_text(encoding="utf-8")
    assert "Tool Calls" in log_text
    assert "Category Report Sections" in log_text


def test_category_report_sections_include_inline_citations(tmp_path):
    state = run_graph("Gusto", output_dir=tmp_path)

    assert state.category_report_sections
    assert any("[1]" in section.markdown and "Sources" in section.markdown for section in state.category_report_sections)


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


def test_generated_markdown_always_has_market_opportunities_for_rippling_section(tmp_path):
    run_graph("Gusto", output_dir=tmp_path)

    markdown = (tmp_path / "gusto_brief.md").read_text(encoding="utf-8")
    assert "## 7. Market Opportunities for Rippling" in markdown
    assert "Rippling positions itself as a unified workforce platform" in markdown
    assert "What Rippling should exploit:" in markdown


def test_unknown_competitor_fallback_is_lower_confidence(tmp_path):
    state = run_graph("ACME Workforce Tool", output_dir=tmp_path)

    assert state.competitor
    assert state.competitor.confidence < 0.7
    assert state.eval_summary
    assert state.extracted_claims
    assert max(claim.confidence for claim in state.extracted_claims) <= 0.62


def test_real_source_claims_are_derived_from_source_content():
    state = AgentState(
        user_input="Gusto",
        real_sources_only=True,
        competitor=CompetitorProfile(
            name="Gusto",
            domain="gusto.com",
            category="unknown",
            description="Real-source test profile.",
            confidence=0.7,
        ),
        discovered_sources=[
            SourceRecord(
                source_id="real_source_1",
                competitor_name="Gusto",
                source_type="website_positioning",
                title="Official homepage",
                content="Gusto public homepage says it helps small businesses manage payroll, HR, benefits, and compliance.",
                is_official=True,
                discovered_at=utc_now_iso(),
                discovery_tool="ExaWebsitePositioningTool",
                reliability_weight=0.88,
                relevance_score=0.5,
                confidence_modifier=0.84,
            )
        ],
    )

    state = analyze_sources(state)
    state = extract_evidence_claims(state)

    assert state.extracted_claims
    assert "public homepage says" in state.extracted_claims[0].claim


def test_real_source_website_pages_are_not_classified_as_pricing_from_nav_text():
    state = AgentState(
        user_input="Gusto",
        real_sources_only=True,
        competitor=CompetitorProfile(
            name="Gusto",
            domain="gusto.com",
            category="unknown",
            description="Real-source test profile.",
            confidence=0.7,
        ),
        discovered_sources=[
            SourceRecord(
                source_id="website_with_pricing_nav",
                competitor_name="Gusto",
                source_type="website_positioning",
                title="Official homepage",
                content="Navigation includes Pricing, but the page positions Gusto around payroll, HR, benefits, and compliance.",
                is_official=True,
                discovered_at=utc_now_iso(),
                discovery_tool="ExaWebsitePositioningTool",
                reliability_weight=0.88,
                relevance_score=0.5,
                confidence_modifier=0.84,
            )
        ],
    )

    state = analyze_sources(state)

    assert state.source_analyses[0].themes == ["website positioning"]


def test_product_positioning_lines_hide_raw_source_ids():
    state = AgentState(
        user_input="Gusto",
        discovered_sources=[
            SourceRecord(
                source_id="exa_website_positioning_gusto_123",
                competitor_name="Gusto",
                source_type="website_positioning",
                title="Official homepage",
                content="Gusto positions around payroll and HR.",
                is_official=True,
                discovered_at=utc_now_iso(),
                discovery_tool="ExaWebsitePositioningTool",
                reliability_weight=0.88,
                relevance_score=0.5,
                confidence_modifier=0.84,
            )
        ],
    )
    state.extracted_claims = [
        ExtractedClaim(
            claim_id="claim_001",
            claim="Gusto public sources show website positioning: Highlights: Gusto helps with payroll and HR.",
            theme="website positioning",
            source_ids=["exa_website_positioning_gusto_123"],
            evidence_snippets=["Highlights: Gusto helps with payroll and HR."],
            source_types=["website_positioning"],
            confidence=0.8,
            timestamp=utc_now_iso(),
        )
    ]

    lines = _product_positioning_lines(state)

    assert lines
    assert "exa_website_positioning_gusto_123" not in lines[0]
    assert "key sources: Official homepage" in lines[0]
