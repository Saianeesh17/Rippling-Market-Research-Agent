from __future__ import annotations

from typing import Iterable, List, Optional

from src.config import SOURCE_CATEGORIES, utc_now_iso
from src.schemas import SourceRecord, ToolCallLog, ToolInput
from src.state import AgentState
from src.tools.base import BaseSourceTool
from src.tools.registry import TOOL_REGISTRY, get_tools_for_category


def score_source_relevance(source: SourceRecord, expected_category: str) -> SourceRecord:
    score = 0.35
    if source.source_type == expected_category:
        score += 0.25
    if source.is_public:
        score += 0.1
    if source.is_official:
        score += 0.18
    if source.is_third_party:
        score -= 0.05
    if source.published_at:
        score += 0.05
    content = source.content.lower()
    if any(token in content for token in ["position", "pricing", "payroll", "hr", "compliance", "campaign", "product"]):
        score += 0.08
    source.relevance_score = round(max(0.0, min(1.0, score)), 2)
    return source


class ToolUsingSourceDiscoveryAgent:
    def __init__(self, category: str, tools: List[BaseSourceTool]):
        self.category = category
        self.tools = tools

    def discover(self, state: AgentState, specific_tool_name: Optional[str] = None) -> List[SourceRecord]:
        if not state.competitor:
            raise ValueError("Competitor must be resolved before discovery.")

        query = self._query_for(state.competitor.name)
        sources: List[SourceRecord] = []
        tool_context: dict[str, str] = {}
        for tool in self._selected_tools(specific_tool_name):
            if self.category not in tool.allowed_agents:
                log = ToolCallLog(
                    tool_name=tool.name,
                    category=self.category,
                    query=query,
                    success=False,
                    sources_returned=0,
                    error=f"Tool is not allowed for category {self.category}.",
                    timestamp=utc_now_iso(),
                )
                state.tool_call_logs.append(log)
                continue

            missing_context = [
                field
                for field in getattr(tool, "required_context_fields", [])
                if not tool_context.get(str(field))
            ]
            if missing_context:
                state.tool_call_logs.append(
                    ToolCallLog(
                        tool_name=tool.name,
                        category=self.category,
                        query=query,
                        success=False,
                        sources_returned=0,
                        error=f"Skipped because required context was not resolved: {', '.join(missing_context)}.",
                        timestamp=utc_now_iso(),
                    )
                )
                continue

            try:
                result = tool.run(
                    ToolInput(
                        competitor_name=state.competitor.name,
                        domain=state.competitor.domain,
                        query=query,
                        category=self.category,
                        linkedin_company_url=tool_context.get("linkedin_company_url"),
                        twitter_handle=tool_context.get("twitter_handle"),
                        resolved_company_domain=tool_context.get("resolved_company_domain"),
                        allow_third_party=self.category in {"pricing", "press_news", "comparison_pages"},
                    )
                )
                if result.metadata.get("linkedin_company_url"):
                    tool_context["linkedin_company_url"] = str(result.metadata["linkedin_company_url"])
                if result.metadata.get("twitter_handle"):
                    tool_context["twitter_handle"] = str(result.metadata["twitter_handle"])
                if result.metadata.get("resolved_company_domain"):
                    tool_context["resolved_company_domain"] = str(result.metadata["resolved_company_domain"])
                category_sources = [
                    score_source_relevance(source, self.category)
                    for source in result.sources
                    if source.is_public
                ]
                sources.extend(category_sources)
                state.tool_call_logs.append(
                    ToolCallLog(
                        tool_name=tool.name,
                        category=self.category,
                        query=query,
                        success=result.success,
                        sources_returned=len(category_sources),
                        api_request=result.metadata.get("api_request"),
                        api_response=result.metadata.get("api_response"),
                        error=result.error,
                        timestamp=utc_now_iso(),
                    )
                )
            except Exception as exc:
                state.tool_call_logs.append(
                    ToolCallLog(
                        tool_name=tool.name,
                        category=self.category,
                        query=query,
                        success=False,
                        sources_returned=0,
                        error=str(exc),
                        timestamp=utc_now_iso(),
                    )
                )
        return sources

    def _selected_tools(self, specific_tool_name: Optional[str]) -> Iterable[BaseSourceTool]:
        if not specific_tool_name:
            return self.tools
        return [tool for tool in self.tools if tool.name == specific_tool_name]

    def _query_for(self, competitor_name: str) -> str:
        terms = {
            "website_positioning": "homepage positioning product marketing personas",
            "product_pages": "public product pages use cases workflows",
            "pricing": "pricing packaging tiers public pricing",
            "paid_ads": "public ad library active campaigns",
            "social": "public social product posts campaigns",
            "press_news": "press release announcement launch public news",
            "comparison_pages": "comparison alternatives public buying criteria",
        }
        return f"{competitor_name} {terms.get(self.category, 'public sources')}"


def dedupe_sources(existing: List[SourceRecord], incoming: List[SourceRecord]) -> List[SourceRecord]:
    seen = {(source.source_id, source.url) for source in existing}
    unique = []
    for source in incoming:
        key = (source.source_id, source.url)
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique


def run_source_discovery(
    state: AgentState,
    *,
    category: Optional[str] = None,
    specific_tool_name: Optional[str] = None,
) -> AgentState:
    if not state.research_plan:
        raise ValueError("Research plan must exist before discovery.")

    categories = [category] if category else [task.category for task in state.research_plan.tasks]
    for task_category in categories:
        tools = get_tools_for_category(task_category, real_only=state.real_sources_only)
        agent = ToolUsingSourceDiscoveryAgent(task_category, tools)
        found = agent.discover(state, specific_tool_name=specific_tool_name)
        state.discovered_sources.extend(dedupe_sources(state.discovered_sources, found))

    if state.research_plan.max_sources and len(state.discovered_sources) > state.research_plan.max_sources:
        state.discovered_sources = limit_sources_preserving_categories(
            state.discovered_sources,
            state.research_plan.max_sources,
        )
    state.logs.append(f"Discovered {len(state.discovered_sources)} public sources using bounded tools.")
    return state


def limit_sources_preserving_categories(sources: List[SourceRecord], max_sources: int) -> List[SourceRecord]:
    if max_sources <= 0 or len(sources) <= max_sources:
        return sources

    grouped: dict[str, list[SourceRecord]] = {category: [] for category in SOURCE_CATEGORIES}
    grouped["__other__"] = []
    for source in sources:
        bucket = source.source_type if source.source_type in grouped else "__other__"
        grouped[bucket].append(source)

    selected: list[SourceRecord] = []
    categories = [*SOURCE_CATEGORIES, "__other__"]
    while len(selected) < max_sources:
        added_this_round = False
        for category in categories:
            category_sources = grouped.get(category, [])
            if not category_sources:
                continue
            selected.append(category_sources.pop(0))
            added_this_round = True
            if len(selected) >= max_sources:
                break
        if not added_this_round:
            break
    return selected
