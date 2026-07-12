from __future__ import annotations

import json
import re
from collections import defaultdict
from statistics import mean

from src.config import SOURCE_CATEGORIES, utc_now_iso
from src.llm.base import BaseLLM
from src.schemas import CategoryReportSection, LLMCallLog, ReportCitation, SourceAnalysis, SourceRecord
from src.state import AgentState
from src.text_cleanup import clean_source_title, clean_template_placeholders


CATEGORY_TITLES = {
    "website_positioning": "Website Positioning",
    "product_pages": "Product And Use-Case Pages",
    "pricing": "Pricing And Packaging",
    "paid_ads": "Paid Ads Messaging",
    "social": "Social And LinkedIn Posts",
    "press_news": "Press And News",
    "comparison_pages": "Comparison Pages",
}


def generate_category_report_sections(state: AgentState, llm: BaseLLM | None = None) -> AgentState:
    sources_by_category: dict[str, list[SourceRecord]] = defaultdict(list)
    analyses_by_category: dict[str, list[SourceAnalysis]] = defaultdict(list)
    for source in state.discovered_sources:
        sources_by_category[source.source_type].append(source)
    for analysis in state.source_analyses:
        analyses_by_category[analysis.category].append(analysis)

    sections = []
    for category in SOURCE_CATEGORIES:
        sources = sources_by_category.get(category, [])
        if not sources:
            continue
        analyses = analyses_by_category.get(category, [])
        section = _try_llm_section(state, category, sources, analyses, llm) if llm else None
        sections.append(section or _deterministic_section(category, sources, analyses))

    state.category_report_sections = sections
    state.logs.append(f"Generated {len(sections)} category report sections.")
    return state


def _try_llm_section(
    state: AgentState,
    category: str,
    sources: list[SourceRecord],
    analyses: list[SourceAnalysis],
    llm: BaseLLM,
) -> CategoryReportSection | None:
    model = getattr(llm, "model", "unknown")
    provider = getattr(llm, "provider", "llm")
    response = ""
    try:
        prompt = json.dumps(
            {
                "task": (
                    "Write this research category's report section only. Use only the provided sources and analyses. "
                    "Use numeric inline citations like [1] and [2], not markdown links in the prose. "
                    "End the section with a Sources list mapping each number to source title and URL. "
                    "Put the section heading on its own line, use blank lines between paragraphs, "
                    "and never return the whole section as one single paragraph. "
                    "Do not write final strategic recommendations."
                ),
                "category": category,
                "title": CATEGORY_TITLES.get(category, category.replace("_", " ").title()),
                "sources": [
                    {
                        "citation_number": index,
                        "source_id": source.source_id,
                        "title": clean_source_title(source.title),
                        "url": source.url,
                        "content": clean_template_placeholders(source.content[:1800]),
                        "is_official": source.is_official,
                        "is_third_party": source.is_third_party,
                        "published_at": source.published_at,
                        "reliability_weight": source.reliability_weight,
                    }
                    for index, source in enumerate(sources, start=1)
                ],
                "analyses": [analysis.model_dump(mode="json") for analysis in analyses],
            },
            indent=2,
        )
        response = llm.complete(
            prompt,
            system_prompt=(
                "You are a category-specific competitive research subagent. "
                "Produce concise markdown for one report section with inline citations."
            ),
        ).strip()
        if not response:
            raise ValueError("LLM returned an empty category report section.")
        response = _normalize_category_markdown(
            response,
            CATEGORY_TITLES.get(category, category.replace("_", " ").title()),
        )
        response = _ensure_numbered_sources(response, sources)
        response = _normalize_category_markdown(
            response,
            CATEGORY_TITLES.get(category, category.replace("_", " ").title()),
        )
        state.llm_call_logs.append(
            LLMCallLog(
                stage=f"category_report_{category}",
                provider=provider,
                model=model,
                success=True,
                response_text=response,
                timestamp=utc_now_iso(),
            )
        )
        return _section(category, sources, response, generated_by=f"llm:{provider}", confidence=_avg_source_confidence(sources))
    except Exception as exc:
        state.llm_call_logs.append(
            LLMCallLog(
                stage=f"category_report_{category}",
                provider=provider,
                model=model,
                success=False,
                response_text=response or None,
                error=str(exc),
                timestamp=utc_now_iso(),
            )
        )
        state.logs.append(f"LLM category report failed for {category}; using deterministic fallback: {exc}")
        return None


def _deterministic_section(
    category: str,
    sources: list[SourceRecord],
    analyses: list[SourceAnalysis],
) -> CategoryReportSection:
    title = CATEGORY_TITLES.get(category, category.replace("_", " ").title())
    lines = [f"### {title}", ""]
    visible_sources = sources[:5]
    for index, source in enumerate(visible_sources, start=1):
        summary = _source_summary(source, analyses)
        caveat = " Third-party evidence; treat as lower confidence." if source.is_third_party else ""
        lines.append(f"- {summary} [{index}]{caveat}")
    if category == "pricing" and any(source.is_third_party for source in sources):
        lines.append("- Pricing evidence includes third-party public sources, so exact packaging claims should remain caveated.")
    lines.extend(_numbered_sources_lines(visible_sources))
    markdown = "\n".join(lines)
    return _section(category, sources, markdown, generated_by="deterministic-subagent", confidence=_avg_source_confidence(sources))


def _section(
    category: str,
    sources: list[SourceRecord],
    markdown: str,
    *,
    generated_by: str,
    confidence: float,
) -> CategoryReportSection:
    return CategoryReportSection(
        section_id=f"section_{category}",
        category=category,
        title=CATEGORY_TITLES.get(category, category.replace("_", " ").title()),
        markdown=markdown,
        source_ids=[source.source_id for source in sources],
        citations=[
            ReportCitation(source_id=source.source_id, title=clean_source_title(source.title), url=source.url)
            for source in sources
        ],
        generated_by=generated_by,
        confidence=confidence,
    )


def _ensure_numbered_sources(markdown: str, sources: list[SourceRecord]) -> str:
    rewritten = _rewrite_markdown_links_to_numbers(markdown, sources)
    if re.search(r"(?m)^\s*(?:#+\s*)?(?:\*\*)?Sources(?:\*\*)?:?\s*$", rewritten):
        return rewritten
    cited_numbers = _cited_numbers(rewritten)
    cited_sources = [source for index, source in enumerate(sources, start=1) if index in cited_numbers]
    if not cited_sources:
        cited_sources = sources[:5]
    return "\n".join([rewritten.rstrip(), *_numbered_sources_lines(cited_sources)])


def _normalize_category_markdown(markdown: str, title: str) -> str:
    normalized = clean_template_placeholders(markdown).replace("\r\n", "\n").replace("\r", "\n").strip()
    normalized = _normalize_opening_heading(normalized, title)
    normalized = _normalize_sources_block(normalized)
    normalized = _remove_duplicate_sources_blocks(normalized)
    normalized = _break_inline_subheads(normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _normalize_opening_heading(markdown: str, title: str) -> str:
    lines = markdown.splitlines()
    if not lines:
        return markdown

    first = lines[0].strip()
    title_pattern = re.escape(title)
    match = re.match(rf"^(?P<hashes>#{{1,3}}\s+)?(?P<title>{title_pattern})(?P<rest>\s+\S.*)?$", first, flags=re.IGNORECASE)
    if not match:
        return markdown

    heading = f"## {title}"
    rest = (match.group("rest") or "").strip()
    remaining = lines[1:]
    if rest:
        return "\n".join([heading, "", rest, *remaining]).strip()
    return "\n".join([heading, *remaining]).strip()


def _normalize_sources_block(markdown: str) -> str:
    match = re.search(r"(?i)(\*\*Sources\*\*|#{1,4}\s+Sources|Sources:)", markdown)
    if not match:
        return markdown

    before = markdown[: match.start()].rstrip()
    source_text = markdown[match.end() :].strip()
    source_text = re.sub(r"\s+(\[\d+\]\s+)", r"\n\1", source_text)
    source_text = re.sub(r"\s+(\d+\.\s+)", r"\n\1", source_text)
    source_text = re.sub(r"\n{2,}", "\n", source_text).strip()
    if source_text:
        return f"{before}\n\n### Sources\n{source_text}".strip()
    return f"{before}\n\n### Sources".strip()


def _break_inline_subheads(markdown: str) -> str:
    return re.sub(r"(?<!\n)\s+(\*\*[^*\n]{3,90}(?:\.\*\*|:\*\*))\s+", r"\n\n\1 ", markdown)


def _remove_duplicate_sources_blocks(markdown: str) -> str:
    markers = list(re.finditer(r"(?im)^\s*(?:#{1,4}\s+Sources|Sources|\*\*Sources\*\*)\s*:?\s*$", markdown))
    if len(markers) <= 1:
        return markdown
    return markdown[: markers[1].start()].rstrip()


def _rewrite_markdown_links_to_numbers(markdown: str, sources: list[SourceRecord]) -> str:
    rewritten = markdown
    for index, source in enumerate(sources, start=1):
        candidates = [source.source_id, source.title]
        if source.url:
            candidates.append(source.url)
        for candidate in candidates:
            if not candidate:
                continue
            escaped = re.escape(str(candidate))
            rewritten = re.sub(rf"\[([^\]]*{escaped}[^\]]*)\]\([^)]+\)", f"[{index}]", rewritten)
            rewritten = re.sub(rf"\[{escaped}\]", f"[{index}]", rewritten)
    return rewritten


def _numbered_sources_lines(sources: list[SourceRecord]) -> list[str]:
    if not sources:
        return []
    lines = ["", "Sources"]
    for index, source in enumerate(sources, start=1):
        title = clean_source_title(source.title) or source.source_id
        if source.url:
            lines.append(f"[{index}] - {title}: {source.url}")
        else:
            lines.append(f"[{index}] - {title} ({source.source_id})")
    return lines


def _cited_numbers(markdown: str) -> set[int]:
    return {int(match) for match in re.findall(r"\[(\d+)\]", markdown)}


def _source_summary(source: SourceRecord, analyses: list[SourceAnalysis]) -> str:
    first_line = next((line.strip() for line in source.content.splitlines() if line.strip()), "")
    if first_line.startswith("Resolved LinkedIn company URL:"):
        return first_line
    matching = next((analysis for analysis in analyses if analysis.source_id == source.source_id), None)
    if matching and matching.observations:
        return matching.observations[0]
    if first_line:
        return first_line[:240]
    return source.content.split(".")[0][:240]


def _avg_source_confidence(sources: list[SourceRecord]) -> float:
    if not sources:
        return 0.0
    return round(mean(source.reliability_weight * source.confidence_modifier for source in sources), 2)
