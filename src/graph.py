from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.llm.base import BaseLLM
from src.llm.service import create_llm
from src.nodes.campaign_angle_generator import generate_campaign_angles
from src.nodes.competitor_resolver import resolve_competitor
from src.nodes.coverage_gap_detector import detect_coverage_gaps
from src.nodes.category_report_sections import generate_category_report_sections
from src.nodes.eval_layer import evaluate_output
from src.nodes.evidence_extraction import extract_evidence_claims
from src.nodes.messaging_positioning import summarize_messaging
from src.nodes.output_writer import write_outputs
from src.nodes.planner_decision import decide_next_step
from src.nodes.recent_change_detector import detect_recent_changes
from src.nodes.research_planner import create_research_plan
from src.nodes.rippling_opportunity_mapper import map_rippling_opportunities
from src.nodes.source_analysis import analyze_sources
from src.nodes.source_coverage_review import review_source_coverage
from src.nodes.source_discovery import run_source_discovery
from src.state import AgentState


def run_graph(
    competitor: str,
    *,
    output_dir: str | Path = "outputs",
    interactive: bool = False,
    use_llm: Optional[bool] = None,
    llm: BaseLLM | None = None,
) -> AgentState:
    llm = llm or create_llm(use_llm)
    state = AgentState(user_input=competitor)
    state.real_sources_only = llm is not None
    if state.real_sources_only:
        state.logs.append("Real-source mode enabled: dummy source tools are disabled for this run.")
    state = resolve_competitor(state)
    state = create_research_plan(state)
    state = run_source_discovery(state)
    state = review_source_coverage(state)
    state = detect_coverage_gaps(state)
    state = decide_next_step(state, llm=llm)

    if state.planner_decision and state.planner_decision.action == "search_deeper":
        state.replanning_cycles += 1
        state.logs.append(
            f"Replanning cycle {state.replanning_cycles}: using {state.planner_decision.next_tool} for {state.planner_decision.next_category}."
        )
        state = run_source_discovery(
            state,
            category=state.planner_decision.next_category,
            specific_tool_name=state.planner_decision.next_tool,
        )
        state = review_source_coverage(state)
        state = detect_coverage_gaps(state)
        state = decide_next_step(state, llm=llm)

    if interactive and state.planner_decision and state.planner_decision.action == "ask_user":
        state.logs.append("Interactive mode would ask the user; dummy CLI defaults to continuing.")

    state = analyze_sources(state)
    state = extract_evidence_claims(state)
    state = generate_category_report_sections(state, llm=llm)
    state = summarize_messaging(state)
    state = detect_recent_changes(state)
    state = map_rippling_opportunities(state)
    state = generate_campaign_angles(state)
    state = evaluate_output(state)
    state = write_outputs(state, output_dir=output_dir, llm=llm)
    return state
