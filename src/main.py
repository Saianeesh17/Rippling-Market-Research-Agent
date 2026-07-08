from __future__ import annotations

import argparse
from collections import defaultdict

from src.graph import run_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the competitive intelligence agent.")
    parser.add_argument("--competitor", required=True, help="Competitor name or domain.")
    parser.add_argument("--interactive", action="store_true", help="Reserved for future interactive replanning.")
    parser.add_argument("--output-dir", default="outputs", help="Directory for generated markdown and JSON files.")
    args = parser.parse_args()

    state = run_graph(args.competitor, output_dir=args.output_dir, interactive=args.interactive)
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

    print()
    print("Generated:")
    print(f"- {state.final_markdown_path}")
    print(f"- {state.final_json_path}")

    if state.eval_summary:
        print()
        print("Eval summary:")
        print(f"Overall quality score: {state.eval_summary.overall_quality_score}")
        print(f"Claim grounding score: {state.eval_summary.claim_grounding_score}")
        print(f"Third-party caveat score: {state.eval_summary.third_party_caveat_score}")
        print(f"Weak sections: {', '.join(state.eval_summary.weak_sections) or 'none'}")


if __name__ == "__main__":
    main()

