from __future__ import annotations

import json

from src.graph import run_graph
from src.llm.base import BaseLLM


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
        return "# Competitive Marketing Brief: Gusto\n\n## 1. Executive Summary\n\nLLM generated from dummy evidence."


def test_llm_can_make_planner_decision_and_generate_report(tmp_path):
    state = run_graph("Gusto", output_dir=tmp_path, llm=PlannerAndReportLLM())

    assert state.planner_decision
    assert state.planner_decision.reason.startswith("LLM says")
    assert len(state.llm_call_logs) >= 2
    assert all(log.success for log in state.llm_call_logs)
    assert any("LLM says" in (log.response_text or "") for log in state.llm_call_logs)
    markdown = (tmp_path / "gusto_brief.md").read_text(encoding="utf-8")
    assert "LLM generated from dummy evidence" in markdown
    run_log = (tmp_path / "gusto_run.log").read_text(encoding="utf-8")
    assert "LLM Calls And Responses" in run_log
    assert "LLM generated from dummy evidence" in run_log
