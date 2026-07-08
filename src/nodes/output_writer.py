from __future__ import annotations

import json
from pathlib import Path

from src.config import utc_now_iso
from src.data.dummy_sources import slugify
from src.llm.base import BaseLLM
from src.schemas import LLMCallLog
from src.schemas import FinalReport
from src.state import AgentState


def write_outputs(state: AgentState, output_dir: str | Path = "outputs", llm: BaseLLM | None = None) -> AgentState:
    if not state.competitor:
        raise ValueError("Cannot write outputs without a competitor.")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(state.competitor.name) or "competitor"
    markdown_path = out_dir / f"{slug}_brief.md"
    json_path = out_dir / f"{slug}_data.json"
    log_path = out_dir / f"{slug}_run.log"

    report = FinalReport(
        competitor=state.competitor,
        research_plan=state.research_plan,
        source_inventory=state.source_inventory,
        coverage_summary=state.coverage_summary,
        coverage_gaps=state.coverage_gaps,
        tool_call_logs=state.tool_call_logs,
        llm_call_logs=state.llm_call_logs,
        extracted_claims=state.extracted_claims,
        messaging_summary=state.messaging_summary,
        recent_changes=state.recent_changes,
        rippling_opportunities=state.rippling_opportunities,
        campaign_recommendations=state.campaign_recommendations,
        eval_summary=state.eval_summary,
    )
    markdown = _try_render_markdown_with_llm(state, report, llm) if llm else None
    markdown_path.write_text(markdown or _render_markdown(state), encoding="utf-8")
    report.llm_call_logs = state.llm_call_logs
    json_path.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
    state.final_markdown_path = str(markdown_path)
    state.final_json_path = str(json_path)
    state.final_log_path = str(log_path)
    state.logs.append(f"Generated outputs: {markdown_path}, {json_path}, {log_path}.")
    log_path.write_text(_render_run_log(state), encoding="utf-8")
    return state


def _try_render_markdown_with_llm(state: AgentState, report: FinalReport, llm: BaseLLM) -> str | None:
    model = getattr(llm, "model", "unknown")
    provider = getattr(llm, "provider", "llm")
    markdown = ""
    try:
        prompt = "\n".join(
            [
                "Generate the final markdown competitive brief from the structured dummy data below.",
                "Rules:",
                "- Return only markdown.",
                "- Keep every substantive claim grounded in the provided sources, claims, opportunities, and eval summary.",
                "- Do not invent real-world facts or private strategy.",
                "- Preserve the required sections 1 through 10.",
                "- Clearly caveat third-party pricing evidence as lower confidence.",
                "",
                json.dumps(report.model_dump(mode="json"), indent=2),
            ]
        )
        markdown = llm.complete(
            prompt,
            system_prompt="You are an evidence-first competitive marketing brief writer for Rippling.",
        ).strip()
        if not markdown.startswith("#"):
            raise ValueError("LLM report did not look like markdown with a top-level heading.")
        state.llm_call_logs.append(
            LLMCallLog(
                stage="final_markdown_report",
                provider=provider,
                model=model,
                success=True,
                response_text=markdown,
                timestamp=utc_now_iso(),
            )
        )
        return markdown
    except Exception as exc:
        state.llm_call_logs.append(
            LLMCallLog(
                stage="final_markdown_report",
                provider=provider,
                model=model,
                success=False,
                response_text=markdown or None,
                error=str(exc),
                timestamp=utc_now_iso(),
            )
        )
        state.logs.append(f"LLM report writer failed; using deterministic fallback: {exc}")
        return None


def _render_markdown(state: AgentState) -> str:
    competitor = state.competitor
    assert competitor is not None
    coverage_lines = []
    if state.coverage_summary:
        for summary in state.coverage_summary.categories:
            coverage_lines.append(
                f"- {summary.category}: {summary.status} ({summary.source_count} sources, "
                f"{summary.official_count} official, {summary.third_party_count} third-party). {summary.notes}"
            )
    theme_lines = []
    if state.messaging_summary:
        for theme in state.messaging_summary.top_messaging_themes:
            theme_lines.append(f"- {theme.theme}: confidence {theme.confidence}, claims {', '.join(theme.supporting_claim_ids)}")
    claim_lines = [f"- {claim.claim} (confidence {claim.confidence}; sources: {', '.join(claim.source_ids)})" for claim in state.extracted_claims]
    pricing_sources = [source for source in state.discovered_sources if source.source_type == "pricing"]
    pricing_lines = []
    for source in pricing_sources:
        source_kind = "official competitor page" if source.is_official else "third-party pricing source"
        pricing_lines.append(f"- {source.title}: {source_kind}. {source.notes or 'Public dummy pricing evidence.'}")
    if not pricing_lines:
        pricing_lines.append("- No useful public pricing source found.")

    recent_lines = [
        f"- {change.change} Confidence {change.confidence}. Evidence: {', '.join(change.evidence_source_ids) or 'none'}"
        for change in state.recent_changes
    ]
    opportunity_lines = []
    for opportunity in state.rippling_opportunities:
        opportunity_lines.extend(
            [
                f"### {opportunity.opportunity_id}",
                f"Competitor strategy: {opportunity.competitor_strategy}",
                f"Gap: {opportunity.competitor_gap}",
                f"Rippling opportunity: {opportunity.rippling_advantage}",
                f"Campaign angle: {opportunity.campaign_angle}",
                f"Example copy: {opportunity.example_copy}",
                f"Supporting claims: {', '.join(opportunity.supporting_claim_ids)}",
            ]
        )
    campaign_lines = [
        f"- {rec.angle}: {rec.message} Channels: {', '.join(rec.recommended_channels)}. Example: {rec.example_copy}"
        for rec in state.campaign_recommendations
    ]
    eval_lines = []
    if state.eval_summary:
        eval_lines = [
            f"- Overall quality score: {state.eval_summary.overall_quality_score}",
            f"- Claim grounding score: {state.eval_summary.claim_grounding_score}",
            f"- Third-party caveat score: {state.eval_summary.third_party_caveat_score}",
            f"- Weak sections: {', '.join(state.eval_summary.weak_sections) or 'none'}",
        ]

    return "\n".join(
        [
            f"# Competitive Marketing Brief: {competitor.name}",
            "",
            "## 1. Executive Summary",
            f"{competitor.name} was resolved as {competitor.domain or 'an unknown domain'} with confidence {competitor.confidence}. This dummy prototype uses bounded public-source-style tools only.",
            "",
            "## 2. Source Coverage Summary",
            *coverage_lines,
            "",
            "## 3. Messaging Angles and Themes",
            *theme_lines,
            "",
            "## 4. Product Positioning",
            *(claim_lines or ["- No grounded claims extracted."]),
            "",
            "## 5. Pricing and Packaging Observations",
            *pricing_lines,
            "",
            "## 6. Recent Changes in Public Messaging",
            *(recent_lines or ["- No recent public messaging changes detected."]),
            "",
            "## 7. Rippling Opportunities",
            *opportunity_lines,
            "",
            "## 8. Campaign Angles Rippling Could Exploit",
            *campaign_lines,
            "",
            "## 9. Confidence, Gaps, and Limitations",
            "All data is dummy public-source-style evidence. Third-party pricing and comparison evidence is deliberately lower confidence than official sources.",
            "",
            "## 10. Eval Summary",
            *eval_lines,
            "",
        ]
    )


def _render_run_log(state: AgentState) -> str:
    lines = [
        "Competitive Intel Agent Run Log",
        "===============================",
        "",
    ]
    if state.competitor:
        lines.extend(
            [
                f"Competitor: {state.competitor.name}",
                f"Domain: {state.competitor.domain or 'unknown'}",
                f"Resolved confidence: {state.competitor.confidence}",
                "",
            ]
        )

    lines.extend(["Pipeline Logs", "-------------"])
    lines.extend(f"- {entry}" for entry in state.logs)
    lines.append("")

    lines.extend(["Tool Calls", "----------"])
    for log in state.tool_call_logs:
        status = "ok" if log.success else f"failed: {log.error}"
        lines.append(
            f"- {log.timestamp} {log.category} {log.tool_name}: {status}, "
            f"sources_returned={log.sources_returned}, query={log.query or ''}"
        )
    lines.append("")

    if state.planner_decision:
        lines.extend(
            [
                "Planner Decision",
                "----------------",
                f"Action: {state.planner_decision.action}",
                f"Reason: {state.planner_decision.reason}",
                f"Next category: {state.planner_decision.next_category or ''}",
                f"Next tool: {state.planner_decision.next_tool or ''}",
                "",
            ]
        )

    lines.extend(["LLM Calls And Responses", "-----------------------"])
    if not state.llm_call_logs:
        lines.append("- No LLM calls were made.")
    for log in state.llm_call_logs:
        status = "ok" if log.success else f"failed: {log.error}"
        lines.extend(
            [
                f"Stage: {log.stage}",
                f"Provider: {log.provider}",
                f"Model: {log.model}",
                f"Timestamp: {log.timestamp}",
                f"Status: {status}",
                "Response:",
                log.response_text or "<empty>",
                "",
            ]
        )
    lines.append("")

    if state.eval_summary:
        lines.extend(
            [
                "Eval Summary",
                "------------",
                f"Overall quality score: {state.eval_summary.overall_quality_score}",
                f"Claim grounding score: {state.eval_summary.claim_grounding_score}",
                f"Third-party caveat score: {state.eval_summary.third_party_caveat_score}",
                f"Weak sections: {', '.join(state.eval_summary.weak_sections) or 'none'}",
                "",
            ]
        )

    lines.extend(
        [
            "Generated Files",
            "---------------",
            f"Markdown: {state.final_markdown_path or ''}",
            f"JSON: {state.final_json_path or ''}",
            f"Log: {state.final_log_path or ''}",
            "",
        ]
    )
    return "\n".join(lines)
