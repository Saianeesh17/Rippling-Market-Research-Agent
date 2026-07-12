from __future__ import annotations

import json
from pathlib import Path

from src.config import utc_now_iso
from src.llm.base import BaseLLM, llm_token_usage_fields
from src.schemas import LLMCallLog, ReportQuestionLog, SourceRecord, ToolCallLog, ToolInput
from src.state import AgentState
from src.tools.exa_follow_up_tool import ExaFollowUpResearchTool


REPORT_QA_EXIT_KEYWORDS = {"no", "n", "quit", "exit", "stop"}
MAX_REPORT_CONTEXT_CHARS = 40000
MAX_FOLLOW_UP_SOURCE_CHARS = 1600


def is_report_qa_termination(text: str) -> bool:
    return text.strip().lower() in REPORT_QA_EXIT_KEYWORDS


def answer_report_question(
    state: AgentState,
    question: str,
    llm: BaseLLM,
    *,
    search_tool: ExaFollowUpResearchTool | None = None,
) -> ReportQuestionLog:
    if not state.competitor:
        raise ValueError("Cannot answer report questions without a resolved competitor.")
    if is_report_qa_termination(question):
        raise ValueError("Termination input should be handled before report Q&A routing.")

    report_context = _report_context(state)
    decision = _route_question(state, question, report_context, llm)
    route = str(decision.get("route") or "search_web")
    reason = str(decision.get("reason") or "No routing reason returned.")
    search_query = _search_query_from_decision(state, question, decision) if route == "search_web" else None
    sources: list[SourceRecord] = []

    if route == "answer_from_report":
        answer = _answer_from_report(state, question, report_context, llm)
    else:
        search_tool = search_tool or ExaFollowUpResearchTool()
        result = search_tool.run(
            ToolInput(
                competitor_name=state.competitor.name,
                domain=state.competitor.domain,
                query=search_query,
                category="report_qa",
                allow_third_party=True,
            )
        )
        sources = result.sources
        state.discovered_sources.extend(source for source in sources if source.source_id not in {existing.source_id for existing in state.discovered_sources})
        state.tool_call_logs.append(
            ToolCallLog(
                tool_name=result.tool_name,
                category="report_qa",
                query=search_query,
                success=result.success,
                sources_returned=len(sources),
                api_request=result.metadata.get("api_request"),
                api_response=result.metadata.get("api_response"),
                error=result.error,
                timestamp=utc_now_iso(),
            )
        )
        if not result.success or not sources:
            answer = (
                "This was not clearly answered in the report, and the follow-up Exa search did not return "
                f"usable sources. Search error: {result.error or 'no usable public sources returned'}"
            )
        else:
            answer = _answer_from_follow_up_sources(state, question, report_context, sources, llm)

    qa_log = ReportQuestionLog(
        question=question,
        route=route,
        answer=answer,
        reason=reason,
        search_query=search_query,
        source_ids=[source.source_id for source in sources],
        timestamp=utc_now_iso(),
    )
    state.report_question_logs.append(qa_log)
    return qa_log


def _route_question(state: AgentState, question: str, report_context: str, llm: BaseLLM) -> dict:
    model = getattr(llm, "model", "unknown")
    provider = getattr(llm, "provider", "llm")
    response = ""
    try:
        response = llm.complete(
            json.dumps(
                {
                    "task": (
                        "Decide whether the user's follow-up question can be answered from the report context. "
                        "Use answer_from_report only when the report contains enough evidence to answer directly. "
                        "Use search_web when the question asks for information that is missing, newer than the report, "
                        "more detailed than the report, or requires additional public sources."
                    ),
                    "competitor": state.competitor.model_dump(mode="json") if state.competitor else None,
                    "question": question,
                    "report_context": report_context,
                    "return_schema": {
                        "route": "answer_from_report | search_web",
                        "reason": "short explanation",
                        "search_query": "public web search query if route is search_web, otherwise null",
                    },
                },
                indent=2,
            ),
            system_prompt="You are a strict report Q&A router. Return valid JSON only.",
            json_mode=True,
        ).strip()
        decision = _parse_json_response(response)
        route = str(decision.get("route") or "").strip()
        if route not in {"answer_from_report", "search_web"}:
            raise ValueError(f"Invalid route: {route}")
        state.llm_call_logs.append(
            LLMCallLog(
                stage="report_qa_route",
                provider=provider,
                model=model,
                success=True,
                **llm_token_usage_fields(llm),
                response_text=response,
                timestamp=utc_now_iso(),
            )
        )
        return decision
    except Exception as exc:
        state.llm_call_logs.append(
            LLMCallLog(
                stage="report_qa_route",
                provider=provider,
                model=model,
                success=False,
                **llm_token_usage_fields(llm),
                response_text=response or None,
                error=str(exc),
                timestamp=utc_now_iso(),
            )
        )
        return {
            "route": "search_web",
            "reason": f"Router failed, so defaulting to follow-up search: {exc}",
            "search_query": _default_search_query(state, question),
        }


def _answer_from_report(state: AgentState, question: str, report_context: str, llm: BaseLLM) -> str:
    model = getattr(llm, "model", "unknown")
    provider = getattr(llm, "provider", "llm")
    response = ""
    try:
        response = llm.complete(
            json.dumps(
                {
                    "task": (
                        "Answer the user's question using only the report context. "
                        "If the context is insufficient, say so and do not invent facts. "
                        "Reference the relevant report section names when useful."
                    ),
                    "question": question,
                    "report_context": report_context,
                },
                indent=2,
            ),
            system_prompt="You answer follow-up questions from the generated competitive brief only.",
        ).strip()
        state.llm_call_logs.append(
            LLMCallLog(
                stage="report_qa_answer_from_report",
                provider=provider,
                model=model,
                success=True,
                **llm_token_usage_fields(llm),
                response_text=response,
                timestamp=utc_now_iso(),
            )
        )
        return response
    except Exception as exc:
        state.llm_call_logs.append(
            LLMCallLog(
                stage="report_qa_answer_from_report",
                provider=provider,
                model=model,
                success=False,
                **llm_token_usage_fields(llm),
                response_text=response or None,
                error=str(exc),
                timestamp=utc_now_iso(),
            )
        )
        return f"I could not answer from the report because the LLM call failed: {exc}"


def _answer_from_follow_up_sources(
    state: AgentState,
    question: str,
    report_context: str,
    sources: list[SourceRecord],
    llm: BaseLLM,
) -> str:
    model = getattr(llm, "model", "unknown")
    provider = getattr(llm, "provider", "llm")
    source_context = [
        {
            "citation_number": index,
            "source_id": source.source_id,
            "title": source.title,
            "url": source.url,
            "content": source.content[:MAX_FOLLOW_UP_SOURCE_CHARS],
            "is_official": source.is_official,
            "is_third_party": source.is_third_party,
            "published_at": source.published_at,
        }
        for index, source in enumerate(sources, start=1)
    ]
    response = ""
    try:
        response = llm.complete(
            json.dumps(
                {
                    "task": (
                        "Answer the user's question using the new public web sources first, and use the report context "
                        "only for continuity. Use numeric inline citations like [1]. End with a Sources list."
                    ),
                    "question": question,
                    "report_context": report_context,
                    "new_sources": source_context,
                },
                indent=2,
            ),
            system_prompt="You answer competitive research follow-up questions with source-grounded citations.",
        ).strip()
        state.llm_call_logs.append(
            LLMCallLog(
                stage="report_qa_answer_with_exa",
                provider=provider,
                model=model,
                success=True,
                **llm_token_usage_fields(llm),
                response_text=response,
                timestamp=utc_now_iso(),
            )
        )
        return _ensure_sources_list(response, sources)
    except Exception as exc:
        state.llm_call_logs.append(
            LLMCallLog(
                stage="report_qa_answer_with_exa",
                provider=provider,
                model=model,
                success=False,
                **llm_token_usage_fields(llm),
                response_text=response or None,
                error=str(exc),
                timestamp=utc_now_iso(),
            )
        )
        return f"I found follow-up sources, but could not draft the answer because the LLM call failed: {exc}"


def _report_context(state: AgentState) -> str:
    if state.final_markdown_path:
        path = Path(state.final_markdown_path)
        if path.exists():
            return _compact_context(path.read_text(encoding="utf-8"))
    parts = []
    if state.competitor:
        parts.append(f"# Competitive Marketing Brief: {state.competitor.name}")
    if state.coverage_summary:
        parts.append("## Source Coverage")
        parts.extend(
            f"- {summary.category}: {summary.status}; {summary.notes}"
            for summary in state.coverage_summary.categories
        )
    parts.extend(section.markdown for section in state.category_report_sections)
    if state.messaging_summary:
        parts.append("## Messaging Summary")
        parts.extend(
            f"- {theme.theme}: confidence {theme.confidence}"
            for theme in state.messaging_summary.top_messaging_themes
        )
    parts.extend(f"- Recent change: {change.change}" for change in state.recent_changes)
    parts.extend(f"- Opportunity: {opportunity.campaign_angle}" for opportunity in state.rippling_opportunities)
    return _compact_context("\n\n".join(parts))


def _compact_context(text: str) -> str:
    cleaned = text.strip()
    if len(cleaned) <= MAX_REPORT_CONTEXT_CHARS:
        return cleaned
    head = cleaned[: MAX_REPORT_CONTEXT_CHARS // 2].rstrip()
    tail = cleaned[-MAX_REPORT_CONTEXT_CHARS // 2 :].lstrip()
    return f"{head}\n\n[...middle of report context omitted for prompt size...]\n\n{tail}"


def _search_query_from_decision(state: AgentState, question: str, decision: dict) -> str:
    search_query = str(decision.get("search_query") or "").strip()
    if search_query:
        return search_query
    return _default_search_query(state, question)


def _default_search_query(state: AgentState, question: str) -> str:
    competitor_name = state.competitor.name if state.competitor else ""
    if competitor_name and competitor_name.lower() not in question.lower():
        return f"{competitor_name} {question}".strip()
    return question.strip()


def _parse_json_response(response: str) -> dict:
    stripped = response.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    return json.loads(stripped)


def _ensure_sources_list(answer: str, sources: list[SourceRecord]) -> str:
    if "\nSources" in answer or "\n**Sources**" in answer:
        return answer
    lines = [answer.rstrip(), "", "Sources"]
    for index, source in enumerate(sources, start=1):
        if source.url:
            lines.append(f"[{index}] - {source.title}: {source.url}")
        else:
            lines.append(f"[{index}] - {source.title} ({source.source_id})")
    return "\n".join(lines)
