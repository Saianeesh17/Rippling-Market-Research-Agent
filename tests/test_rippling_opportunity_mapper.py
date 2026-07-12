from __future__ import annotations

from src.config import utc_now_iso
from src.nodes.rippling_opportunity_mapper import map_rippling_opportunities
from src.schemas import CategoryReportSection, CompetitorProfile, ReportCitation, SourceRecord
from src.state import AgentState


def test_real_source_opportunities_fall_back_to_category_sections_when_claims_are_missing():
    state = AgentState(
        user_input="Gusto",
        real_sources_only=True,
        competitor=CompetitorProfile(
            name="Gusto",
            domain="gusto.com",
            category="unknown",
            description="Real-source test profile.",
            confidence=0.7,
        ),
        discovered_sources=[
            SourceRecord(
                source_id="src_website",
                competitor_name="Gusto",
                source_type="website_positioning",
                title="Official homepage",
                url="https://gusto.com",
                content="Gusto positions around payroll, HR, benefits, compliance, and SMB simplicity.",
                discovered_at=utc_now_iso(),
                discovery_tool="ExaWebsitePositioningTool",
                reliability_weight=0.88,
                relevance_score=0.8,
                confidence_modifier=0.84,
            ),
            SourceRecord(
                source_id="src_press",
                competitor_name="Gusto",
                source_type="press_news",
                title="Gusto Cofounder",
                url="https://gusto.com/company-news/cofounder",
                content="Gusto announces Cofounder AI for small business operations.",
                discovered_at=utc_now_iso(),
                discovery_tool="ExaPressNewsTool",
                reliability_weight=0.82,
                relevance_score=0.8,
                confidence_modifier=0.84,
            ),
        ],
        category_report_sections=[
            CategoryReportSection(
                section_id="section_website_positioning",
                category="website_positioning",
                title="Website Positioning",
                markdown="## Website Positioning\n\nGusto leads with payroll and HR simplicity [1].",
                source_ids=["src_website"],
                citations=[ReportCitation(source_id="src_website", title="Official homepage", url="https://gusto.com")],
                generated_by="test",
                confidence=0.82,
            ),
            CategoryReportSection(
                section_id="section_press_news",
                category="press_news",
                title="Press And News",
                markdown="## Press And News\n\nGusto is pushing Cofounder AI [1].",
                source_ids=["src_press"],
                citations=[ReportCitation(source_id="src_press", title="Gusto Cofounder", url="https://gusto.com/company-news/cofounder")],
                generated_by="test",
                confidence=0.78,
            ),
        ],
    )

    state = map_rippling_opportunities(state)

    assert len(state.rippling_opportunities) >= 2
    assert all(opportunity.supporting_claim_ids for opportunity in state.rippling_opportunities)
    assert state.rippling_opportunities[0].supporting_claim_ids == ["section_website_positioning"]
    assert "workforce operating system" in state.rippling_opportunities[0].campaign_angle.lower()
