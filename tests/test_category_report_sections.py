from __future__ import annotations

from src.config import utc_now_iso
from src.nodes.category_report_sections import _ensure_numbered_sources
from src.nodes.category_report_sections import _source_summary
from src.schemas import SourceRecord


def test_llm_markdown_links_are_rewritten_to_numbered_citations():
    source = SourceRecord(
        source_id="src_1",
        competitor_name="Gusto",
        source_type="social",
        title="LinkedIn post",
        url="https://www.linkedin.com/posts/example",
        content="Post content.",
        discovered_at=utc_now_iso(),
        discovery_tool="test",
        reliability_weight=0.8,
        relevance_score=0.7,
        confidence_modifier=0.8,
    )

    markdown = "Gusto discusses AI hiring in [src_1](https://www.linkedin.com/posts/example)."
    rewritten = _ensure_numbered_sources(markdown, [source])

    assert "[1]" in rewritten
    assert "[src_1](" not in rewritten
    assert "Sources" in rewritten
    assert "[1] - LinkedIn post: https://www.linkedin.com/posts/example" in rewritten


def test_source_summary_preserves_linkedin_url():
    source = SourceRecord(
        source_id="src_1",
        competitor_name="Gusto",
        source_type="social",
        title="Resolved LinkedIn company page",
        url="https://www.linkedin.com/company/gustohq/posts/?feedView=all",
        content="Resolved LinkedIn company URL: https://www.linkedin.com/company/gustohq/posts/?feedView=all\nSearch title: Gusto",
        discovered_at=utc_now_iso(),
        discovery_tool="ExaLinkedInCompanySearchTool",
        reliability_weight=0.8,
        relevance_score=0.7,
        confidence_modifier=0.8,
    )

    assert _source_summary(source, []) == "Resolved LinkedIn company URL: https://www.linkedin.com/company/gustohq/posts/?feedView=all"
