from __future__ import annotations

from src.config import SOURCE_CATEGORIES
from src.nodes.coverage_gap_detector import detect_coverage_gaps
from src.nodes.planner_decision import decide_next_step
from src.nodes.research_planner import create_research_plan
from src.nodes.source_coverage_review import review_source_coverage
from src.nodes.source_discovery import run_source_discovery
from src.schemas import CoverageGap, ToolInput, ToolResult
from src.schemas import SourceRecord
from src.config import utc_now_iso
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


class ApiOutputTool(BaseSourceTool):
    name = "ApiOutputTool"
    description = "Returns API metadata for logging tests."
    source_category = "social"
    reliability_weight = 0.8
    allowed_agents = ["social"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            success=True,
            sources=[
                SourceRecord(
                    source_id="api_output_source",
                    competitor_name=tool_input.competitor_name,
                    source_type="social",
                    title="API output source",
                    content="Real API output test source.",
                    is_official=True,
                    discovered_at=utc_now_iso(),
                    discovery_tool=self.name,
                    reliability_weight=0.8,
                    relevance_score=0.5,
                    confidence_modifier=0.8,
                )
            ],
            metadata={
                "api_request": {"json": {"companyUrls": ["test"], "maxPostsPerCompany": 5}},
                "api_response": {"items": [{"text": "hello"}]},
            },
        )


def test_api_outputs_are_captured_in_tool_call_logs(monkeypatch):
    monkeypatch.setitem(TOOL_REGISTRY, "social", [ApiOutputTool()])
    state = AgentState(user_input="Gusto")
    state = resolve_competitor(state)
    state = create_research_plan(state)
    state = run_source_discovery(state, category="social")

    log = state.tool_call_logs[0]
    assert log.api_request == {"json": {"companyUrls": ["test"], "maxPostsPerCompany": 5}}
    assert log.api_response == {"items": [{"text": "hello"}]}


class LinkedinResolverTool(BaseSourceTool):
    name = "LinkedinResolverTool"
    description = "Resolves LinkedIn URL for handoff test."
    source_category = "social"
    reliability_weight = 0.7
    allowed_agents = ["social"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            success=True,
            metadata={"linkedin_company_url": "https://www.linkedin.com/company/gustohq/posts/?feedView=all"},
        )


class LinkedinConsumerTool(BaseSourceTool):
    name = "LinkedinConsumerTool"
    description = "Consumes LinkedIn URL for handoff test."
    source_category = "social"
    reliability_weight = 0.7
    allowed_agents = ["social"]
    received_url = None

    def run(self, tool_input: ToolInput) -> ToolResult:
        LinkedinConsumerTool.received_url = tool_input.linkedin_company_url
        return ToolResult(tool_name=self.name, success=True)


def test_exa_resolved_linkedin_url_is_available_to_later_social_tools(monkeypatch):
    LinkedinConsumerTool.received_url = None
    monkeypatch.setitem(TOOL_REGISTRY, "social", [LinkedinResolverTool(), LinkedinConsumerTool()])
    state = AgentState(user_input="Gusto")
    state = resolve_competitor(state)
    state = create_research_plan(state)
    state = run_source_discovery(state, category="social")

    assert LinkedinConsumerTool.received_url == "https://www.linkedin.com/company/gustohq/posts/?feedView=all"


class DomainResolverTool(BaseSourceTool):
    name = "DomainResolverTool"
    description = "Resolves company domain for handoff test."
    source_category = "paid_ads"
    reliability_weight = 0.7
    allowed_agents = ["paid_ads"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            success=True,
            metadata={"resolved_company_domain": "gusto.com"},
        )


class DomainConsumerTool(BaseSourceTool):
    name = "DomainConsumerTool"
    description = "Consumes company domain for handoff test."
    source_category = "paid_ads"
    reliability_weight = 0.7
    allowed_agents = ["paid_ads"]
    received_domain = None

    def run(self, tool_input: ToolInput) -> ToolResult:
        DomainConsumerTool.received_domain = tool_input.resolved_company_domain
        return ToolResult(tool_name=self.name, success=True)


def test_exa_resolved_company_domain_is_available_to_later_paid_ad_tools(monkeypatch):
    DomainConsumerTool.received_domain = None
    monkeypatch.setitem(TOOL_REGISTRY, "paid_ads", [DomainResolverTool(), DomainConsumerTool()])
    state = AgentState(user_input="Gusto")
    state = resolve_competitor(state)
    state = create_research_plan(state)
    state = run_source_discovery(state, category="paid_ads")

    assert DomainConsumerTool.received_domain == "gusto.com"
