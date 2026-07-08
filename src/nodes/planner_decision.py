from __future__ import annotations

from src.schemas import PlannerDecision
from src.state import AgentState


def decide_next_step(state: AgentState) -> AgentState:
    max_cycles = state.research_plan.max_replanning_cycles if state.research_plan else 0
    missing_or_high = [gap for gap in state.coverage_gaps if gap.severity == "high"]
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

