from __future__ import annotations

import argparse
from collections import defaultdict

from src.graph import run_graph
from src.llm.base import BaseLLM
from src.llm.service import create_llm
from src.nodes.output_writer import refresh_json_report, refresh_run_log
from src.nodes.report_qa import answer_report_question, is_report_qa_termination
from src.state import AgentState


def _print_indented(text: str, prefix: str) -> None:
    for line in text.splitlines() or [""]:
        print(f"{prefix}{line}")


def _run_report_qa_loop(state: AgentState, llm: BaseLLM | None) -> None:
    if not llm:
        print()
        print("Interactive report Q&A requires an LLM. Re-run with --use-llm and a configured provider.")
        return

    print()
    print("Ask follow-up questions about the report. Type 'no' to exit.")
    while True:
        question = input("> ").strip()
        if is_report_qa_termination(question):
            print("Exiting report Q&A.")
            return
        if not question:
            continue
        qa_log = answer_report_question(state, question, llm)
        refresh_json_report(state)
        refresh_run_log(state)
        print()
        print(qa_log.answer)
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the competitive intelligence agent.")
    parser.add_argument("--competitor", required=True, help="Competitor name or domain.")
    parser.add_argument("--interactive", action="store_true", help="Start a post-report follow-up Q&A loop.")
    parser.add_argument("--output-dir", default="outputs", help="Directory for generated markdown and JSON files.")
    llm_group = parser.add_mutually_exclusive_group()
    llm_group.add_argument("--use-llm", action="store_true", help="Use the configured OpenAI-compatible LLM if possible.")
    llm_group.add_argument("--no-llm", action="store_true", help="Disable LLM calls and use deterministic fallback.")
    args = parser.parse_args()

    use_llm = True if args.use_llm else False if args.no_llm else None
    llm = create_llm(use_llm)
    state = run_graph(args.competitor, output_dir=args.output_dir, interactive=args.interactive, use_llm=use_llm, llm=llm)
    competitor = state.competitor
    assert competitor is not None

    print(f"Resolved competitor: {competitor.name} / {competitor.domain or 'unknown domain'}")
    print()
    print("Running source discovery using bounded tool registry...")
    print()
    print("Tool calls:")
    for log in state.tool_call_logs:
        arrow = "->"
        status = f"{log.sources_returned} source" if log.sources_returned == 1 else f"{log.sources_returned} sources"
        if not log.success:
            status = f"failed ({log.error})"
        print(f"- {log.tool_name} {arrow} {status}")

    print()
    print(f"Sources found for {competitor.name}:")
    grouped = defaultdict(list)
    for source in state.discovered_sources:
        grouped[source.source_type].append(source)
    for category, sources in grouped.items():
        print()
        print(category.replace("_", " ").title() + ":")
        for source in sources:
            marker = "third-party" if source.is_third_party else "official" if source.is_official else "public"
            print(f"- {source.title} ({marker})")
            if source.source_type == "pricing" and source.is_third_party:
                print("  Note: lower confidence because this is a third-party pricing source.")

    print()
    print("Coverage decision:")
    if state.planner_decision:
        print(state.planner_decision.reason)

    if state.llm_call_logs:
        print()
        print("LLM calls:")
        for log in state.llm_call_logs:
            status = "ok" if log.success else f"failed ({log.error})"
            print(f"- {log.stage} using {log.model}: {status}")
            print("  Response:")
            _print_indented(log.response_text or "<empty>", "    ")

    print()
    print("Generated:")
    print(f"- {state.final_markdown_path}")
    print(f"- {state.final_json_path}")
    print(f"- {state.final_log_path}")

    if state.eval_summary:
        print()
        print("Eval summary:")
        print(f"Overall quality score: {state.eval_summary.overall_quality_score}")
        print(f"Claim grounding score: {state.eval_summary.claim_grounding_score}")
        print(f"Third-party caveat score: {state.eval_summary.third_party_caveat_score}")
        print(f"Weak sections: {', '.join(state.eval_summary.weak_sections) or 'none'}")

    if args.interactive:
        _run_report_qa_loop(state, llm)


if __name__ == "__main__":
    main()
