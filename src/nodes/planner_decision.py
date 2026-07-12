from __future__ import annotations

import json

from src.config import utc_now_iso
from src.llm.base import BaseLLM, llm_token_usage_fields
from src.schemas import LLMCallLog
from src.schemas import PlannerDecision
from src.state import AgentState
from src.tools.registry import TOOL_REGISTRY, get_tools_for_category


def decide_next_step(state: AgentState, llm: BaseLLM | None = None) -> AgentState:
    if llm:
        llm_decision = _try_llm_decision(state, llm)
        if llm_decision:
            state.planner_decision = llm_decision
            state.logs.append(f"LLM planner decision: {state.planner_decision.action}.")
            return state
    return _deterministic_decision(state)


def _deterministic_decision(state: AgentState) -> AgentState:
    max_cycles = state.research_plan.max_replanning_cycles if state.research_plan else 0
    missing_or_high = [gap for gap in state.coverage_gaps if gap.severity == "high" and gap.suggested_next_tool]
    if missing_or_high and state.replanning_cycles < max_cycles:
        gap = missing_or_high[0]
        state.planner_decision = PlannerDecision(
            action="search_deeper",
            reason=f"{gap.category} coverage is missing; retry with a specific allowed tool.",
            next_category=gap.category,
            next_tool=gap.suggested_next_tool,
        )
    elif state.coverage_gaps:
        caveats = ", ".join(gap.category for gap in state.coverage_gaps)
        state.planner_decision = PlannerDecision(
            action="continue",
            reason=f"Core coverage is usable; continuing with caveats for {caveats}.",
        )
    else:
        state.planner_decision = PlannerDecision(
            action="continue",
            reason="Coverage is strong enough to continue to analysis.",
        )
    state.logs.append(f"Planner decision: {state.planner_decision.action}.")
    return state


def _try_llm_decision(state: AgentState, llm: BaseLLM) -> PlannerDecision | None:
    model = getattr(llm, "model", "unknown")
    provider = getattr(llm, "provider", "llm")
    content = ""
    try:
        prompt = _planner_prompt(state)
        content = llm.complete(
            prompt,
            system_prompt=(
                "You are a bounded research planner. Return only valid JSON matching the requested schema. "
                "You may choose only tools listed in the provided registry."
            ),
            json_mode=True,
        )
        payload = _json_from_text(content)
        decision = PlannerDecision.model_validate(payload)
        if not _decision_is_allowed(decision, state):
            raise ValueError("LLM returned a tool or category outside the allowed registry.")
        state.llm_call_logs.append(
            LLMCallLog(
                stage="planner_decision",
                provider=provider,
                model=model,
                success=True,
                **llm_token_usage_fields(llm),
                response_text=content.strip(),
                timestamp=utc_now_iso(),
            )
        )
        return decision
    except Exception as exc:
        state.llm_call_logs.append(
            LLMCallLog(
                stage="planner_decision",
                provider=provider,
                model=model,
                success=False,
                **llm_token_usage_fields(llm),
                response_text=content.strip() or None,
                error=str(exc),
                timestamp=utc_now_iso(),
            )
        )
        state.logs.append(f"LLM planner failed; using deterministic fallback: {exc}")
        return None


def _planner_prompt(state: AgentState) -> str:
    registry_summary = {
        category: [
            {
                "name": tool.name,
                "description": tool.description,
                "allowed_agents": tool.allowed_agents,
                "reliability_weight": tool.reliability_weight,
            }
            for tool in get_tools_for_category(category, real_only=state.real_sources_only)
        ]
        for category in TOOL_REGISTRY
    }
    return json.dumps(
        {
            "task": (
                "Choose the next planner decision for a competitive intelligence agent. "
                "Use only the bounded tools provided. Prefer continue when core coverage is usable."
            ),
            "output_schema": {
                "action": "continue | search_deeper | ask_user | skip_category | stop",
                "reason": "short rationale",
                "next_category": "category name or null",
                "next_tool": "allowed tool name or null",
            },
            "coverage_summary": state.coverage_summary.model_dump(mode="json") if state.coverage_summary else None,
            "coverage_gaps": [gap.model_dump(mode="json") for gap in state.coverage_gaps],
            "replanning_cycles": state.replanning_cycles,
            "max_replanning_cycles": state.research_plan.max_replanning_cycles if state.research_plan else 0,
            "available_tools_by_category": registry_summary,
        },
        indent=2,
    )


def _decision_is_allowed(decision: PlannerDecision, state: AgentState) -> bool:
    if decision.action != "search_deeper":
        return True
    if not decision.next_category or not decision.next_tool:
        return False
    allowed_tools = get_tools_for_category(decision.next_category, real_only=state.real_sources_only)
    return any(tool.name == decision.next_tool and decision.next_category in tool.allowed_agents for tool in allowed_tools)


def _json_from_text(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(content[start : end + 1])
