from __future__ import annotations

from src.config import SOURCE_CATEGORIES
from src.nodes.coverage_gap_detector import detect_coverage_gaps
from src.nodes.planner_decision import decide_next_step
from src.nodes.research_planner import create_research_plan
from src.nodes.source_coverage_review import review_source_coverage
from src.nodes.source_discovery import run_source_discovery
from src.schemas import CoverageGap, ToolInput, ToolResult
from src.state import AgentState
from src.tools.base import BaseSourceTool
from src.tools.registry import TOOL_REGISTRY, get_tools_for_category
from src.nodes.competitor_resolver import resolve_competitor


def test_registry_only_gives_allowed_tools_to_category_agents():
    for category in SOURCE_CATEGORIES:
        tools = get_tools_for_category(category)
        assert tools
        assert all(category in tool.allowed_agents for tool in tools)


def test_coverage_review_groups_sources_by_category():
    state = AgentState(user_input="Gusto")
    state = resolve_competitor(state)
    state = create_research_plan(state)
    state = run_source_discovery(state)
    state = review_source_coverage(state)

    assert state.source_inventory
    assert state.source_inventory.category_counts["website_positioning"] > 0
    assert state.source_inventory.source_ids_by_category["pricing"]


class FailingTool(BaseSourceTool):
    name = "FailingTool"
    description = "Always fails in tests."
    source_category = "website"
    reliability_weight = 0.1
    allowed_agents = ["website_positioning"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        raise RuntimeError("intentional failure")


def test_tool_failures_are_logged_and_do_not_crash(monkeypatch):
    original = TOOL_REGISTRY["website_positioning"]
    monkeypatch.setitem(TOOL_REGISTRY, "website_positioning", [FailingTool(), *original])
    state = AgentState(user_input="Gusto")
    state = resolve_competitor(state)
    state = create_research_plan(state)
    state = run_source_discovery(state, category="website_positioning")

    assert any(log.tool_name == "FailingTool" and not log.success for log in state.tool_call_logs)
    assert state.discovered_sources


def test_planner_decision_can_choose_specific_next_tool():
    state = AgentState(user_input="Gusto")
    state = create_research_plan(state)
    state.coverage_gaps = [
        CoverageGap(
            category="social",
            severity="high",
            reason="No social sources found.",
            suggested_next_tool="DummyLinkedInApiTool",
        )
    ]
    state = decide_next_step(state)

    assert state.planner_decision
    assert state.planner_decision.action == "search_deeper"
    assert state.planner_decision.next_tool == "DummyLinkedInApiTool"
