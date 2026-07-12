from __future__ import annotations

from src.config import utc_now_iso
from src.gui import format_state_summary, markdown_display_lines, read_report_markdown
from src.schemas import (
    CompetitorProfile,
    CoverageCategorySummary,
    CoverageSummary,
    EvalSummary,
    SourceInventory,
    ToolCallLog,
)
from src.state import AgentState


def test_markdown_display_lines_classifies_report_structure():
    markdown = (
        "# Competitive Brief: Gusto\n\n"
        "## Source Coverage\n"
        "- website_positioning: strong\n\n"
        "Sources\n"
        "[1] - Gusto homepage: https://gusto.com"
    )

    lines = markdown_display_lines(markdown)

    assert [line.tag for line in lines] == [
        "h1",
        "body",
        "h2",
        "bullet",
        "body",
        "sources_heading",
        "source",
    ]
    assert lines[0].text == "Competitive Brief: Gusto"
    assert lines[3].text == "- website_positioning: strong"


def test_format_state_summary_includes_run_outputs_and_scores():
    state = AgentState(
        user_input="Gusto",
        competitor=CompetitorProfile(
            name="Gusto",
            domain="gusto.com",
            category="payroll",
            description="Payroll and HR platform.",
            confidence=0.8,
        ),
        source_inventory=SourceInventory(
            total_sources=2,
            category_counts={"website_positioning": 1, "pricing": 1},
            source_ids_by_category={"website_positioning": ["src_1"], "pricing": ["src_2"]},
            official_source_count=1,
            third_party_source_count=1,
            tools_used=["TestTool"],
        ),
        coverage_summary=CoverageSummary(
            categories=[
                CoverageCategorySummary(
                    category="website_positioning",
                    status="strong",
                    source_count=1,
                    official_count=1,
                    third_party_count=0,
                    avg_reliability=0.88,
                    notes="Official source found.",
                )
            ],
            overall_status="usable",
            strong_categories=["website_positioning"],
            weak_categories=[],
        ),
        eval_summary=EvalSummary(
            source_coverage_score=0.8,
            claim_grounding_score=1.0,
            unsupported_claim_count=0,
            json_schema_valid=True,
            recommendation_specificity_score=1.0,
            third_party_caveat_score=0.9,
            public_source_compliance=True,
            weak_sections=[],
            overall_quality_score=0.94,
            explanation="Test eval.",
        ),
        tool_call_logs=[
            ToolCallLog(
                tool_name="TestTool",
                category="website_positioning",
                query="Gusto",
                success=True,
                sources_returned=1,
                timestamp=utc_now_iso(),
            )
        ],
    )
    state.final_markdown_path = "outputs/gusto_brief.md"
    state.final_json_path = "outputs/gusto_data.json"
    state.final_log_path = "outputs/gusto_run.log"

    summary = format_state_summary(state)

    assert "Name: Gusto" in summary
    assert "Markdown: outputs/gusto_brief.md" in summary
    assert "Total sources: 2" in summary
    assert "- website_positioning: strong" in summary
    assert "Overall quality score: 0.94" in summary
    assert "- website_positioning / TestTool: 1 sources" in summary


def test_read_report_markdown_returns_generated_report_text(tmp_path):
    report_path = tmp_path / "gusto_brief.md"
    report_path.write_text("# Competitive Brief: Gusto\n", encoding="utf-8")
    state = AgentState(user_input="Gusto", final_markdown_path=str(report_path))

    assert read_report_markdown(state) == "# Competitive Brief: Gusto\n"
