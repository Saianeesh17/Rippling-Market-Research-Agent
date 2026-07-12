from __future__ import annotations

from src.config import utc_now_iso
from src.nodes.category_report_sections import _ensure_numbered_sources
from src.nodes.category_report_sections import _normalize_category_markdown
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


def test_numbered_sources_drop_template_placeholder_titles():
    source = SourceRecord(
        source_id="src_1",
        competitor_name="Gusto",
        source_type="paid_ads",
        title="Meta ad 2: {{product.name}}",
        url="https://gusto.com/ad",
        content="Ad content.",
        discovered_at=utc_now_iso(),
        discovery_tool="AdyntelMetaAdsTool",
        reliability_weight=0.8,
        relevance_score=0.7,
        confidence_modifier=0.8,
    )

    rewritten = _ensure_numbered_sources("Gusto runs a Meta ad [1].", [source])

    assert "{{product.name}}" not in rewritten
    assert "[1] - Meta ad 2: https://gusto.com/ad" in rewritten


def test_category_markdown_normalizer_splits_single_line_heading_and_sources():
    markdown = (
        "## Website Positioning Gusto leads with payroll and HR simplicity [1]. "
        "**Segmentation by size.** It targets SMBs and solopreneurs [2]. "
        "**Sources** [1] Gusto homepage — https://gusto.com/ "
        "[2] Gusto product page — https://gusto.com/product"
    )

    normalized = _normalize_category_markdown(markdown, "Website Positioning")

    assert normalized.startswith("## Website Positioning\n\nGusto leads")
    assert "## Website Positioning Gusto" not in normalized
    assert "\n\n**Segmentation by size.** It targets" in normalized
    assert "\n\n### Sources\n[1] Gusto homepage" in normalized
    assert "\n[2] Gusto product page" in normalized


def test_category_markdown_normalizer_removes_duplicate_sources_blocks():
    markdown = (
        "## Product And Use-Case Pages\n\n"
        "Gusto describes payroll and HR workflows [1].\n\n"
        "### Sources\n"
        "1. Gusto product page — https://gusto.com/product\n"
        "Sources\n"
        "[1] - Gusto product page: https://gusto.com/product"
    )

    normalized = _normalize_category_markdown(markdown, "Product And Use-Case Pages")

    assert normalized.count("Sources") == 1
    assert "[1] - Gusto product page" not in normalized
