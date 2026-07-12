from __future__ import annotations

import json

from src.config import utc_now_iso
from src.llm.base import BaseLLM
from src.nodes.output_writer import refresh_json_report, refresh_run_log, write_outputs
from src.nodes.report_qa import answer_report_question, is_report_qa_termination
from src.schemas import CompetitorProfile, SourceRecord, ToolInput, ToolResult
from src.state import AgentState


class ReportAnswerLLM(BaseLLM):
    provider = "test"
    model = "test-model"

    def __init__(self, route: str):
        self.route = route
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, system_prompt: str | None = None, json_mode: bool = False) -> str:
        self.prompts.append(prompt)
        if json_mode:
            return json.dumps(
                {
                    "route": self.route,
                    "reason": "The report contains enough context." if self.route == "answer_from_report" else "Needs fresh public research.",
                    "search_query": "Gusto newest payroll product announcement" if self.route == "search_web" else None,
                }
            )
        if self.route == "answer_from_report":
            return "From the report: Gusto emphasizes payroll and HR workflows in its positioning."
        return "Fresh research says Gusto announced an update [1]."


class FakeFollowUpSearchTool:
    name = "ExaFollowUpResearchTool"

    def __init__(self):
        self.inputs: list[ToolInput] = []

    def run(self, tool_input: ToolInput) -> ToolResult:
        self.inputs.append(tool_input)
        return ToolResult(
            tool_name=self.name,
            success=True,
            sources=[
                SourceRecord(
                    source_id="exa_follow_up_gusto_1",
                    competitor_name="Gusto",
                    source_type="follow_up_research",
                    title="Gusto product announcement",
                    url="https://gusto.com/news/product-announcement",
                    content="Gusto announced a new payroll product update for small businesses.",
                    publisher="Official website",
                    is_official=True,
                    is_public=True,
                    discovered_at=utc_now_iso(),
                    discovery_tool=self.name,
                    reliability_weight=0.74,
                    relevance_score=0.7,
                    confidence_modifier=0.84,
                )
            ],
            metadata={
                "api_request": {"calls": [{"query": tool_input.query}], "cache_hit": False},
                "api_response": {"sources_accepted": 1},
            },
        )


def _state(tmp_path) -> AgentState:
    markdown_path = tmp_path / "gusto_brief.md"
    markdown_path.write_text(
        "# Competitive Marketing Brief: Gusto\n\n"
        "## Product Positioning\n\n"
        "Gusto emphasizes payroll and HR workflows for small businesses.\n",
        encoding="utf-8",
    )
    return AgentState(
        user_input="Gusto",
        competitor=CompetitorProfile(
            name="Gusto",
            domain="gusto.com",
            category="unknown",
            description="Test competitor.",
            confidence=0.8,
        ),
        final_markdown_path=str(markdown_path),
    )


def test_report_qa_exit_keyword_terminates_loop():
    assert is_report_qa_termination("no")
    assert is_report_qa_termination("NO")
    assert is_report_qa_termination(" exit ")
    assert not is_report_qa_termination("no, research this")


def test_report_qa_answers_from_existing_report_without_exa(tmp_path):
    state = _state(tmp_path)
    llm = ReportAnswerLLM(route="answer_from_report")
    search_tool = FakeFollowUpSearchTool()

    qa_log = answer_report_question(state, "How does Gusto position itself?", llm, search_tool=search_tool)

    assert qa_log.route == "answer_from_report"
    assert "payroll and HR workflows" in qa_log.answer
    assert not search_tool.inputs
    assert not state.tool_call_logs
    assert [log.stage for log in state.llm_call_logs] == ["report_qa_route", "report_qa_answer_from_report"]


def test_report_qa_uses_exa_for_missing_follow_up_research(tmp_path):
    state = _state(tmp_path)
    llm = ReportAnswerLLM(route="search_web")
    search_tool = FakeFollowUpSearchTool()

    qa_log = answer_report_question(state, "What did Gusto launch most recently?", llm, search_tool=search_tool)

    assert qa_log.route == "search_web"
    assert qa_log.search_query == "Gusto newest payroll product announcement"
    assert qa_log.source_ids == ["exa_follow_up_gusto_1"]
    assert search_tool.inputs[0].category == "report_qa"
    assert state.tool_call_logs[0].tool_name == "ExaFollowUpResearchTool"
    assert state.tool_call_logs[0].category == "report_qa"
    assert "Sources" in qa_log.answer
    assert "[1] - Gusto product announcement: https://gusto.com/news/product-announcement" in qa_log.answer


def test_report_qa_is_written_to_refreshed_run_log(tmp_path):
    state = _state(tmp_path)
    write_outputs(state, output_dir=tmp_path)
    llm = ReportAnswerLLM(route="answer_from_report")

    answer_report_question(state, "How does Gusto position itself?", llm, search_tool=FakeFollowUpSearchTool())
    refresh_json_report(state)
    refresh_run_log(state)

    run_log = (tmp_path / "gusto_run.log").read_text(encoding="utf-8")
    assert "Report Q&A" in run_log
    assert "Question: How does Gusto position itself?" in run_log
    assert "From the report:" in run_log
    data = json.loads((tmp_path / "gusto_data.json").read_text(encoding="utf-8"))
    assert data["report_question_logs"][0]["question"] == "How does Gusto position itself?"
    assert data["report_question_logs"][0]["route"] == "answer_from_report"
