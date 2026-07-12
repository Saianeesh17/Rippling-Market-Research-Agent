from __future__ import annotations

import json
from pathlib import Path

from src.config import utc_now_iso
from src.data.dummy_sources import slugify
from src.llm.base import BaseLLM
from src.schemas import LLMCallLog
from src.schemas import FinalReport
from src.state import AgentState


MAX_SECTION_CHARS_FOR_FINAL_LLM = 4000
MAX_CLAIMS_FOR_FINAL_LLM = 24
MAX_RECENT_CHANGES_FOR_FINAL_LLM = 8
MAX_OPPORTUNITIES_FOR_FINAL_LLM = 6
MAX_CAMPAIGN_RECOMMENDATIONS_FOR_FINAL_LLM = 8
MAX_CITATIONS_PER_SECTION_FOR_FINAL_LLM = 8
MAX_TOOL_FAILURES_FOR_FINAL_LLM = 20
MAX_OUTPUT_JSON_REQUEST_FIELD_CHARS = 500
DETAILED_CATEGORY_HEADING = "## Detailed Category Research"
API_PAYLOAD_SUMMARY_KEYS = {
    "cache_hit",
    "cached",
    "dataset_items_returned",
    "sources_accepted",
    "sources_rejected",
    "ads_returned_by_api",
    "selected_linkedin_url",
    "selected_twitter_handle",
    "selected_company_domain",
    "source",
    "skipped",
}
SAFE_API_REQUEST_BODY_KEYS = {
    "companyUrls",
    "maxPostsPerCompany",
    "maxCompanies",
    "startUrls",
    "proxyConfiguration",
    "company_domain",
    "limit",
    "max_results",
    "num_results",
    "type",
    "query",
    "contents",
}


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
        category_report_sections=state.category_report_sections,
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
    json_path.write_text(json.dumps(_build_output_json_payload(report), indent=2), encoding="utf-8")
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
                "Generate the final markdown competitive brief from the structured data below.",
                "Rules:",
                "- Return only markdown.",
                "- Category-specific research sections are already written by specialist subagents.",
                "- Include a section named 'Detailed Category Research' and reproduce each category_report_sections[].markdown block verbatim, including inline citations and Sources lists.",
                "- Do not replace the category_report_sections with a short bullet summary.",
                "- Your job is final synthesis: executive summary, confidence/gaps, market gaps, Rippling opportunities, and campaign implications.",
                "- Keep every substantive claim grounded in provided sources, claims, category sections, opportunities, and eval summary.",
                "- Do not invent real-world facts or private strategy.",
                "- Preserve the required sections 1 through 10.",
                "- Clearly caveat third-party pricing evidence as lower confidence.",
                "",
                json.dumps(_build_final_llm_payload(state, report), indent=2),
            ]
        )
        markdown = llm.complete(
            prompt,
            system_prompt="You are an evidence-first competitive marketing brief writer for Rippling.",
        ).strip()
        if not markdown.startswith("#"):
            raise ValueError("LLM report did not look like markdown with a top-level heading.")
        markdown = _ensure_detailed_category_sections(markdown, state)
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


def _ensure_detailed_category_sections(markdown: str, state: AgentState) -> str:
    if not state.category_report_sections:
        return markdown
    detailed_section = _render_detailed_category_sections(state)
    if _has_generated_detailed_category_section(markdown):
        return _replace_generated_detailed_category_section(markdown, detailed_section)
    return "\n".join(
        [
            markdown.rstrip(),
            "",
            detailed_section,
            "",
        ]
    )


def _render_detailed_category_sections(state: AgentState) -> str:
    return "\n".join(
        [
            DETAILED_CATEGORY_HEADING,
            "",
            "The following sections preserve the full category subagent findings, inline citations, and source lists.",
            "",
            *[section.markdown.strip() for section in state.category_report_sections],
        ]
    )


def _has_generated_detailed_category_section(markdown: str) -> bool:
    return _detailed_category_section_bounds(markdown) is not None


def _replace_generated_detailed_category_section(markdown: str, replacement: str) -> str:
    bounds = _detailed_category_section_bounds(markdown)
    if bounds is None:
        return markdown
    start_index, end_index = bounds
    lines = markdown.splitlines()
    replacement_lines = replacement.splitlines()
    return "\n".join(lines[:start_index] + replacement_lines + [""] + lines[end_index:]).rstrip()


def _detailed_category_section_bounds(markdown: str) -> tuple[int, int] | None:
    lines = markdown.splitlines()
    start_index = None
    for index, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped.startswith("## ") and "detailed category research" in stripped:
            start_index = index
            break
    if start_index is None:
        return None

    end_index = len(lines)
    for index in range(start_index + 1, len(lines)):
        if lines[index].strip().startswith("## "):
            end_index = index
            break

    return start_index, end_index


def _build_output_json_payload(report: FinalReport) -> dict:
    payload = report.model_dump(mode="json")
    payload["tool_call_logs"] = [_compact_tool_call_log_for_json(log) for log in payload.get("tool_call_logs", [])]
    return payload


def _compact_tool_call_log_for_json(log: dict) -> dict:
    compacted = dict(log)
    if compacted.get("api_request") is not None:
        compacted["api_request"] = _summarize_api_payload_for_json(compacted["api_request"], include_safe_request_body=True)
    if compacted.get("api_response") is not None:
        compacted["api_response"] = _summarize_api_payload_for_json(compacted["api_response"], include_safe_request_body=False)
    return compacted


def _summarize_api_payload_for_json(payload: object, *, include_safe_request_body: bool) -> dict:
    summary = {
        "omitted_raw_payload": True,
        "payload_type": type(payload).__name__,
        "approx_size_chars": _approx_json_size(payload),
    }
    if isinstance(payload, list):
        summary["item_count"] = len(payload)
        return summary
    if not isinstance(payload, dict):
        summary["value_preview"] = _compact_text(str(payload), limit=MAX_OUTPUT_JSON_REQUEST_FIELD_CHARS)
        return summary

    summary["top_level_key_count"] = len(payload)
    for key in API_PAYLOAD_SUMMARY_KEYS:
        if key in payload and _is_safe_json_scalar(payload[key]):
            summary[key] = payload[key]

    for key, value in payload.items():
        if isinstance(value, list):
            summary[f"{key}_count"] = len(value)
        elif isinstance(value, dict) and key != "json":
            summary[f"{key}_key_count"] = len(value)

    if include_safe_request_body and isinstance(payload.get("json"), dict):
        safe_json = _safe_request_json(payload["json"])
        if safe_json:
            summary["json"] = safe_json
    if include_safe_request_body and isinstance(payload.get("query_params"), dict):
        summary["query_params"] = _safe_query_params(payload["query_params"])

    return summary


def _safe_request_json(request_json: dict) -> dict:
    safe = {}
    for key, value in request_json.items():
        if key in SAFE_API_REQUEST_BODY_KEYS:
            safe[key] = _compact_json_value(value)
    return safe


def _safe_query_params(query_params: dict) -> dict:
    safe = {}
    for key, value in query_params.items():
        key_lower = str(key).lower()
        if any(secret_marker in key_lower for secret_marker in ["token", "key", "auth", "secret"]):
            safe[key] = "<redacted>"
        elif _is_safe_json_scalar(value):
            safe[key] = _compact_text(str(value), limit=MAX_OUTPUT_JSON_REQUEST_FIELD_CHARS)
    return safe


def _compact_json_value(value: object, *, depth: int = 0) -> object:
    if depth >= 3:
        return "<nested value omitted>"
    if _is_safe_json_scalar(value):
        if isinstance(value, str):
            return _compact_text(value, limit=MAX_OUTPUT_JSON_REQUEST_FIELD_CHARS)
        return value
    if isinstance(value, list):
        compacted = [_compact_json_value(item, depth=depth + 1) for item in value[:5]]
        if len(value) > 5:
            compacted.append({"omitted_items": len(value) - 5})
        return compacted
    if isinstance(value, dict):
        return {str(key): _compact_json_value(item, depth=depth + 1) for key, item in list(value.items())[:20]}
    return _compact_text(str(value), limit=MAX_OUTPUT_JSON_REQUEST_FIELD_CHARS)


def _is_safe_json_scalar(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _approx_json_size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=True, default=str))


def _build_final_llm_payload(state: AgentState, report: FinalReport) -> dict:
    source_by_id = {source.source_id: source for source in state.discovered_sources}
    tools_used = sorted({log.tool_name for log in state.tool_call_logs if log.success})
    failed_tools = [
        {
            "tool_name": log.tool_name,
            "category": log.category,
            "error": _compact_text(log.error or "", limit=240),
        }
        for log in state.tool_call_logs
        if not log.success
    ][:MAX_TOOL_FAILURES_FOR_FINAL_LLM]

    return {
        "competitor": report.competitor.model_dump(mode="json") if report.competitor else None,
        "real_sources_only": state.real_sources_only,
        "source_inventory": _compact_source_inventory(report.source_inventory),
        "coverage_summary": report.coverage_summary.model_dump(mode="json") if report.coverage_summary else None,
        "coverage_gaps": [gap.model_dump(mode="json") for gap in report.coverage_gaps],
        "tool_summary": {
            "tools_used": tools_used,
            "failed_tools": failed_tools,
        },
        "category_report_sections": [
            {
                "category": section.category,
                "title": section.title,
                "confidence": section.confidence,
                "markdown": _compact_text(section.markdown, limit=MAX_SECTION_CHARS_FOR_FINAL_LLM),
                "citations": [
                    {
                        "title": citation.title,
                        "url": citation.url,
                    }
                    for citation in section.citations[:MAX_CITATIONS_PER_SECTION_FOR_FINAL_LLM]
                ],
            }
            for section in report.category_report_sections
        ],
        "top_grounded_claims": [
            {
                "claim": _compact_text(claim.claim, limit=320),
                "theme": claim.theme,
                "source_types": claim.source_types,
                "confidence": claim.confidence,
                "evidence_snippets": [_compact_text(snippet, limit=220) for snippet in claim.evidence_snippets[:2]],
                "source_titles": _source_titles_for_claim(claim.source_ids, source_by_id),
            }
            for claim in _select_final_claims(report.extracted_claims)
        ],
        "messaging_summary": report.messaging_summary.model_dump(mode="json") if report.messaging_summary else None,
        "recent_changes": [
            {
                "change": _compact_text(change.change, limit=260),
                "interpretation": _compact_text(change.interpretation, limit=220),
                "confidence": change.confidence,
                "source_titles": _source_titles_for_claim(change.evidence_source_ids, source_by_id),
            }
            for change in report.recent_changes[:MAX_RECENT_CHANGES_FOR_FINAL_LLM]
        ],
        "rippling_opportunities": [
            {
                "competitor_strategy": _compact_text(opportunity.competitor_strategy, limit=300),
                "competitor_gap": _compact_text(opportunity.competitor_gap, limit=300),
                "why_gap_matters": _compact_text(opportunity.why_gap_matters, limit=300),
                "rippling_advantage": _compact_text(opportunity.rippling_advantage, limit=300),
                "campaign_angle": _compact_text(opportunity.campaign_angle, limit=220),
                "example_copy": _compact_text(opportunity.example_copy, limit=220),
                "mapped_rippling_pillars": opportunity.mapped_rippling_pillars,
                "confidence": opportunity.confidence,
            }
            for opportunity in report.rippling_opportunities[:MAX_OPPORTUNITIES_FOR_FINAL_LLM]
        ],
        "campaign_recommendations": [
            {
                "angle": _compact_text(recommendation.angle, limit=180),
                "target_segment": _compact_text(recommendation.target_segment, limit=120),
                "message": _compact_text(recommendation.message, limit=240),
                "recommended_channels": recommendation.recommended_channels,
                "example_copy": _compact_text(recommendation.example_copy, limit=220),
                "why_it_works": _compact_text(recommendation.why_it_works, limit=260),
                "confidence": recommendation.confidence,
            }
            for recommendation in report.campaign_recommendations[:MAX_CAMPAIGN_RECOMMENDATIONS_FOR_FINAL_LLM]
        ],
        "eval_summary": report.eval_summary.model_dump(mode="json") if report.eval_summary else None,
    }


def _select_final_claims(claims: list) -> list:
    sorted_claims = sorted(claims, key=lambda claim: claim.confidence, reverse=True)
    selected = []
    seen_themes = set()
    for claim in sorted_claims:
        if claim.theme in seen_themes:
            continue
        selected.append(claim)
        seen_themes.add(claim.theme)
        if len(selected) >= MAX_CLAIMS_FOR_FINAL_LLM:
            return selected
    for claim in sorted_claims:
        if claim in selected:
            continue
        selected.append(claim)
        if len(selected) >= MAX_CLAIMS_FOR_FINAL_LLM:
            break
    return selected


def _compact_source_inventory(source_inventory: object) -> dict | None:
    if not source_inventory:
        return None
    return {
        "total_sources": source_inventory.total_sources,
        "category_counts": source_inventory.category_counts,
        "official_source_count": source_inventory.official_source_count,
        "third_party_source_count": source_inventory.third_party_source_count,
        "tools_used": source_inventory.tools_used,
    }


def _source_titles_for_claim(source_ids: list[str], source_by_id: dict) -> list[str]:
    titles = []
    for source_id in source_ids:
        source = source_by_id.get(source_id)
        if not source:
            continue
        title = _compact_text(source.title, limit=90)
        if title and title not in titles:
            titles.append(title)
        if len(titles) >= 4:
            break
    return titles


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
    product_positioning_lines = _product_positioning_lines(state)
    pricing_sources = [source for source in state.discovered_sources if source.source_type == "pricing"]
    pricing_lines = []
    for source in pricing_sources:
        source_kind = "official competitor page" if source.is_official else "third-party pricing source"
        pricing_lines.append(f"- {source.title}: {source_kind}. {source.notes or 'Public pricing evidence.'}")
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
            f"{competitor.name} was resolved as {competitor.domain or 'an unknown domain'} with confidence {competitor.confidence}. This prototype uses bounded public-source tools only.",
            "",
            "## 2. Source Coverage Summary",
            *coverage_lines,
            "",
            "## 3. Messaging Angles and Themes",
            *theme_lines,
            "",
            "## Category Research Sections",
            *[section.markdown for section in state.category_report_sections],
            "",
            "## 4. Product Positioning",
            *(product_positioning_lines or ["- No product positioning claims extracted from website or product-page sources."]),
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
            "All data is public-source evidence. Third-party pricing and comparison evidence is deliberately lower confidence than official sources.",
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
        if log.api_request is not None:
            lines.extend(["  API Request:", _json_block(log.api_request, indent=4)])
        if log.api_response is not None:
            lines.extend(["  API Response:", _json_block(log.api_response, indent=4)])
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

    lines.extend(["Category Report Sections", "------------------------"])
    if not state.category_report_sections:
        lines.append("- No category report sections were generated.")
    for section in state.category_report_sections:
        lines.extend(
            [
                f"Section: {section.title}",
                f"Category: {section.category}",
                f"Generated by: {section.generated_by}",
                f"Confidence: {section.confidence}",
                "Markdown:",
                section.markdown,
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


def _product_positioning_lines(state: AgentState) -> list[str]:
    source_by_id = {source.source_id: source for source in state.discovered_sources}
    preferred_source_types = {"website_positioning", "product_pages"}
    preferred_themes = {"website positioning", "product and use cases"}

    selected_claims = [
        claim
        for claim in state.extracted_claims
        if claim.theme in preferred_themes
        or any(source_by_id.get(source_id) and source_by_id[source_id].source_type in preferred_source_types for source_id in claim.source_ids)
    ]
    if not selected_claims:
        selected_claims = state.extracted_claims[:4]

    lines = []
    for claim in selected_claims[:6]:
        source_titles = []
        for source_id in claim.source_ids:
            source = source_by_id.get(source_id)
            if not source:
                continue
            title = _compact_text(source.title, limit=72)
            if title and title not in source_titles:
                source_titles.append(title)
            if len(source_titles) >= 3:
                break
        source_note = f"; key sources: {'; '.join(source_titles)}" if source_titles else ""
        theme = claim.theme.replace("_", " ").title()
        lines.append(f"- {theme}: {_clean_claim_text(claim.claim)} (confidence {claim.confidence}{source_note})")
    return lines


def _clean_claim_text(text: str) -> str:
    cleaned = text.strip()
    marker = " public sources show "
    if marker in cleaned:
        cleaned = cleaned.split(marker, 1)[1]
        if ": " in cleaned:
            cleaned = cleaned.split(": ", 1)[1]
    for prefix in ["Highlights:", "Page text excerpt:", "Summary:", "Body:", "Post:"]:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    cleaned = " ".join(cleaned.split())
    return _compact_text(cleaned, limit=220)


def _compact_text(text: str, *, limit: int) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _json_block(value: object, *, indent: int) -> str:
    prefix = " " * indent
    rendered = json.dumps(value, indent=2, ensure_ascii=True, default=str)
    return "\n".join(f"{prefix}{line}" for line in rendered.splitlines())
