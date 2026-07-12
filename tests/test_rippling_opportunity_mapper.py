from __future__ import annotations

import json

from src.config import utc_now_iso
from src.data.dummy_rippling_positioning import RIPPLING_CURRENT_POSITION
from src.llm.base import BaseLLM
from src.nodes.rippling_opportunity_mapper import map_rippling_opportunities
from src.schemas import CategoryReportSection, CompetitorProfile, ExtractedClaim, ReportCitation, SourceRecord
from src.state import AgentState


class OpportunityLLM(BaseLLM):
    provider = "test"
    model = "test-model"

    def __init__(self):
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, system_prompt: str | None = None, json_mode: bool = False) -> str:
        self.prompts.append(prompt)
        assert json_mode is True
        return json.dumps(
            {
                "opportunities": [
                    {
                        "competitor_strategy": "Gusto leads with payroll and HR simplicity for SMB buyers.",
                        "competitor_gap": "Gusto does not clearly connect HR data to IT, spend, and finance actions.",
                        "why_gap_matters": "Scaling buyers feel the pain when employee changes require manual handoffs across teams.",
                        "rippling_advantage": "Rippling can use its unified workforce platform positioning to connect those actions.",
                        "campaign_angle": "Reframe payroll buying around the operating layer behind every employee change.",
                        "example_copy": "Payroll is the moment. Rippling connects every employee action before and after it.",
                        "supporting_evidence_ids": ["claim_001", "section_website_positioning"],
                        "mapped_rippling_pillars": [
                            "Unified HR, IT, and Finance",
                            "Employee lifecycle automation",
                        ],
                        "confidence": 0.81,
                    }
                ]
            }
        )


class InvalidOpportunityLLM(BaseLLM):
    provider = "test"
    model = "test-model"

    def complete(self, prompt: str, *, system_prompt: str | None = None, json_mode: bool = False) -> str:
        return json.dumps({"not_opportunities": []})


def _real_source_state() -> AgentState:
    return AgentState(
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
            )
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
            )
        ],
        extracted_claims=[
            ExtractedClaim(
                claim_id="claim_001",
                claim="Website positioning: Gusto leads with payroll and HR simplicity for SMB buyers.",
                theme="website positioning",
                source_ids=["src_website"],
                evidence_snippets=["Gusto positions around payroll, HR, benefits, compliance, and SMB simplicity."],
                source_types=["website_positioning"],
                confidence=0.74,
                timestamp=utc_now_iso(),
            )
        ],
    )


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


def test_llm_generates_real_source_opportunities_from_rippling_positioning():
    state = _real_source_state()
    llm = OpportunityLLM()

    state = map_rippling_opportunities(state, llm=llm)

    assert llm.prompts
    assert RIPPLING_CURRENT_POSITION in llm.prompts[0]
    assert "allowed_evidence_ids" in llm.prompts[0]
    assert state.rippling_opportunities[0].competitor_gap == (
        "Gusto does not clearly connect HR data to IT, spend, and finance actions."
    )
    assert state.rippling_opportunities[0].supporting_claim_ids == [
        "claim_001",
        "section_website_positioning",
    ]
    assert state.rippling_opportunities[0].mapped_rippling_pillars == [
        "Unified HR, IT, and Finance",
        "Employee lifecycle automation",
    ]
    assert state.rippling_opportunities[0].confidence == 0.81
    assert state.llm_call_logs[-1].stage == "rippling_opportunity_mapper"
    assert state.llm_call_logs[-1].success is True


def test_llm_opportunity_mapper_falls_back_when_response_is_invalid():
    state = _real_source_state()

    state = map_rippling_opportunities(state, llm=InvalidOpportunityLLM())

    assert state.rippling_opportunities
    assert "workforce operating system" in state.rippling_opportunities[0].campaign_angle.lower()
    assert state.llm_call_logs[-1].stage == "rippling_opportunity_mapper"
    assert state.llm_call_logs[-1].success is False
