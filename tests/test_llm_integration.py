from __future__ import annotations

import json

from src.config import utc_now_iso
from src.graph import run_graph
from src.llm.base import BaseLLM
from src.nodes.output_writer import write_outputs
from src.schemas import CategoryReportSection, CompetitorProfile, ReportCitation, SourceRecord, ToolCallLog
from src.state import AgentState


class PlannerAndReportLLM(BaseLLM):
    provider = "test"
    model = "test-model"

    def complete(self, prompt: str, *, system_prompt: str | None = None, json_mode: bool = False) -> str:
        if json_mode:
            return json.dumps(
                {
                    "action": "continue",
                    "reason": "LLM says core coverage is usable with pricing caveats.",
                    "next_category": None,
                    "next_tool": None,
                }
            )
        return "# Competitive Marketing Brief: Gusto\n\n## 1. Executive Summary\n\nLLM generated from real-source evidence."


def test_llm_can_make_planner_decision_and_generate_report(tmp_path):
    state = run_graph("Gusto", output_dir=tmp_path, llm=PlannerAndReportLLM())

    assert state.planner_decision
    assert state.planner_decision.reason.startswith("LLM says")
    assert len(state.llm_call_logs) >= 2
    assert all(log.success for log in state.llm_call_logs)
    assert any("LLM says" in (log.response_text or "") for log in state.llm_call_logs)
    markdown = (tmp_path / "gusto_brief.md").read_text(encoding="utf-8")
    assert "LLM generated from real-source evidence" in markdown
    assert all(not log.tool_name.startswith("Dummy") for log in state.tool_call_logs)
    run_log = (tmp_path / "gusto_run.log").read_text(encoding="utf-8")
    assert "LLM Calls And Responses" in run_log
    assert "LLM generated from real-source evidence" in run_log


class CapturingReportLLM(BaseLLM):
    provider = "test"
    model = "test-model"

    def __init__(self):
        self.prompts = []

    def complete(self, prompt: str, *, system_prompt: str | None = None, json_mode: bool = False) -> str:
        self.prompts.append(prompt)
        return "# Competitive Marketing Brief: Gusto\n\n## 1. Executive Summary\n\nCompact prompt."


def test_final_report_llm_prompt_and_data_json_exclude_raw_api_payloads(tmp_path):
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
                source_id="src_1",
                competitor_name="Gusto",
                source_type="website_positioning",
                title="Official homepage",
                url="https://gusto.com",
                content="Gusto helps with payroll and HR.",
                is_official=True,
                discovered_at=utc_now_iso(),
                discovery_tool="ExaWebsitePositioningTool",
                reliability_weight=0.88,
                relevance_score=0.5,
                confidence_modifier=0.84,
            )
        ],
        category_report_sections=[
            CategoryReportSection(
                section_id="section_website_positioning",
                category="website_positioning",
                title="Website Positioning",
                markdown="### Website Positioning\n\nGusto positions around payroll and HR [1].\n\nSources\n[1] - Official homepage: https://gusto.com",
                source_ids=["src_1"],
                citations=[ReportCitation(source_id="src_1", title="Official homepage", url="https://gusto.com")],
                generated_by="test",
                confidence=0.8,
            )
        ],
        tool_call_logs=[
            ToolCallLog(
                tool_name="RawApiTool",
                category="website_positioning",
                query="Gusto",
                success=True,
                sources_returned=1,
                api_request={"json": {"raw_request_marker": "DO_NOT_SEND_TO_FINAL_LLM"}},
                api_response={"raw_response_marker": "DO_NOT_SEND_TO_FINAL_LLM", "items": [{"body": "x" * 1000}]},
                timestamp=utc_now_iso(),
            )
        ],
    )
    llm = CapturingReportLLM()

    state = write_outputs(state, output_dir=tmp_path, llm=llm)

    assert llm.prompts
    final_prompt = llm.prompts[-1]
    assert "DO_NOT_SEND_TO_FINAL_LLM" not in final_prompt
    assert "tool_call_logs" not in final_prompt
    assert "api_response" not in final_prompt
    payload = json.loads((tmp_path / "gusto_data.json").read_text(encoding="utf-8"))
    payload_text = json.dumps(payload)
    assert "DO_NOT_SEND_TO_FINAL_LLM" not in payload_text
    assert payload["tool_call_logs"][0]["api_request"]["omitted_raw_payload"] is True
    assert "json" not in payload["tool_call_logs"][0]["api_request"]
    assert payload["tool_call_logs"][0]["api_response"]["omitted_raw_payload"] is True
    assert payload["tool_call_logs"][0]["api_response"]["approx_size_chars"] > 1000
    run_log = (tmp_path / "gusto_run.log").read_text(encoding="utf-8")
    assert "DO_NOT_SEND_TO_FINAL_LLM" in run_log
    assert "reproduce each category_report_sections[].markdown block verbatim" in final_prompt


class SummaryOnlyReportLLM(BaseLLM):
    provider = "test"
    model = "test-model"

    def complete(self, prompt: str, *, system_prompt: str | None = None, json_mode: bool = False) -> str:
        return "# Competitive Marketing Brief: Gusto\n\n## Executive Summary\n\nShort synthesis only."


class PartialDetailedReportLLM(BaseLLM):
    provider = "test"
    model = "test-model"

    def complete(self, prompt: str, *, system_prompt: str | None = None, json_mode: bool = False) -> str:
        return (
            "# Competitive Marketing Brief: Gusto\n\n"
            "## Executive Summary\n\n"
            "High-level synthesis.\n\n"
            "## Detailed Category Research\n\n"
            "### Website Positioning\n\n"
            "Short category summary.\n\n"
            "Sources\n"
            "[1] - Short source: https://example.com\n\n"
            "## Evaluation Summary\n\n"
            "Keep this section after the model-generated detail block."
        )


def test_final_report_preserves_detailed_category_sections_when_llm_summarizes(tmp_path):
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
        category_report_sections=[
            CategoryReportSection(
                section_id="section_website_positioning",
                category="website_positioning",
                title="Website Positioning",
                markdown="### Website Positioning\n\nGusto positions around payroll and HR [1].\n\nSources\n[1] - Official homepage: https://gusto.com",
                source_ids=["src_1"],
                citations=[ReportCitation(source_id="src_1", title="Official homepage", url="https://gusto.com")],
                generated_by="test",
                confidence=0.8,
            )
        ],
    )

    write_outputs(state, output_dir=tmp_path, llm=SummaryOnlyReportLLM())

    markdown = (tmp_path / "gusto_brief.md").read_text(encoding="utf-8")
    assert "## Detailed Category Research" in markdown
    assert "### Website Positioning" in markdown
    assert "[1] - Official homepage: https://gusto.com" in markdown


def test_final_report_replaces_short_llm_detail_block_with_full_subagent_sections(tmp_path):
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
        category_report_sections=[
            CategoryReportSection(
                section_id="section_website_positioning",
                category="website_positioning",
                title="Website Positioning",
                markdown=(
                    "### Website Positioning\n\n"
                    "Gusto positions around payroll, HR, and benefits workflows for small businesses [1].\n\n"
                    "Sources\n"
                    "[1] - Official homepage: https://gusto.com"
                ),
                source_ids=["src_1"],
                citations=[ReportCitation(source_id="src_1", title="Official homepage", url="https://gusto.com")],
                generated_by="test",
                confidence=0.8,
            ),
            CategoryReportSection(
                section_id="section_pricing",
                category="pricing",
                title="Pricing",
                markdown=(
                    "### Pricing\n\n"
                    "Gusto's pricing evidence should keep the full caveat and sourced detail [1].\n\n"
                    "Sources\n"
                    "[1] - Pricing page: https://gusto.com/pricing"
                ),
                source_ids=["src_2"],
                citations=[ReportCitation(source_id="src_2", title="Pricing page", url="https://gusto.com/pricing")],
                generated_by="test",
                confidence=0.7,
            ),
        ],
    )

    write_outputs(state, output_dir=tmp_path, llm=PartialDetailedReportLLM())

    markdown = (tmp_path / "gusto_brief.md").read_text(encoding="utf-8")
    assert markdown.count("## Detailed Category Research") == 1
    assert markdown.index("## Detailed Category Research") < markdown.index("## Evaluation Summary")
    assert "Short category summary." not in markdown
    assert "Keep this section after the model-generated detail block." in markdown
    assert "Gusto positions around payroll, HR, and benefits workflows for small businesses [1]." in markdown
    assert "Gusto's pricing evidence should keep the full caveat and sourced detail [1]." in markdown
    assert "[1] - Pricing page: https://gusto.com/pricing" in markdown
