from __future__ import annotations

from types import SimpleNamespace

from src.config import utc_now_iso
from src.gui import format_state_summary
from src.llm.anthropic_client import _usage_from_response
from src.llm.openai_client import _usage_from_completion
from src.llm.token_usage import summarize_llm_token_usage
from src.nodes.output_writer import write_outputs
from src.schemas import CompetitorProfile, LLMCallLog
from src.state import AgentState


def test_openai_usage_is_normalized_to_input_output_and_total_tokens():
    completion = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=120,
            completion_tokens=45,
            total_tokens=165,
        )
    )

    usage = _usage_from_completion(completion)

    assert usage is not None
    assert usage.input_tokens == 120
    assert usage.output_tokens == 45
    assert usage.total_tokens == 165


def test_anthropic_usage_is_normalized_to_input_output_and_total_tokens():
    usage = _usage_from_response({"usage": {"input_tokens": 300, "output_tokens": 75}})

    assert usage is not None
    assert usage.input_tokens == 300
    assert usage.output_tokens == 75
    assert usage.total_tokens == 375


def test_token_usage_summary_counts_reported_and_unreported_calls():
    logs = [
        LLMCallLog(
            stage="planner_decision",
            provider="test",
            model="test-model",
            success=True,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            timestamp=utc_now_iso(),
        ),
        LLMCallLog(
            stage="final_markdown_report",
            provider="test",
            model="test-model",
            success=True,
            timestamp=utc_now_iso(),
        ),
    ]

    summary = summarize_llm_token_usage(logs)

    assert summary.input_tokens == 10
    assert summary.output_tokens == 5
    assert summary.total_tokens == 15
    assert summary.reported_calls == 1
    assert summary.unreported_calls == 1


def test_report_footer_includes_llm_token_usage_totals(tmp_path):
    state = AgentState(
        user_input="Gusto",
        competitor=CompetitorProfile(
            name="Gusto",
            domain="gusto.com",
            category="unknown",
            description="Test competitor.",
            confidence=0.8,
        ),
        llm_call_logs=[
            LLMCallLog(
                stage="planner_decision",
                provider="test",
                model="test-model",
                success=True,
                input_tokens=20,
                output_tokens=10,
                total_tokens=30,
                timestamp=utc_now_iso(),
            )
        ],
    )

    write_outputs(state, output_dir=tmp_path)

    markdown = (tmp_path / "gusto_brief.md").read_text(encoding="utf-8")
    assert markdown.rstrip().endswith("- Calls without provider-reported usage: 0")
    assert "## LLM Token Usage" in markdown
    assert "- Input tokens: 20" in markdown
    assert "- Output tokens: 10" in markdown
    assert "- Total tokens: 30" in markdown


def test_gui_summary_includes_llm_token_usage_totals():
    state = AgentState(
        user_input="Gusto",
        llm_call_logs=[
            LLMCallLog(
                stage="final_markdown_report",
                provider="test",
                model="test-model",
                success=True,
                input_tokens=50,
                output_tokens=25,
                total_tokens=75,
                timestamp=utc_now_iso(),
            )
        ],
    )

    summary = format_state_summary(state)

    assert "LLM Token Usage" in summary
    assert "- Input tokens: 50" in summary
    assert "- Output tokens: 25" in summary
    assert "- Total tokens: 75" in summary
