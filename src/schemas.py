from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CompetitorProfile(BaseModel):
    name: str
    domain: Optional[str] = None
    category: str
    description: str
    confidence: float


class ResearchTask(BaseModel):
    category: str
    priority: str
    reason: str


class ResearchPlan(BaseModel):
    tasks: List[ResearchTask]
    max_sources: int = 30
    max_replanning_cycles: int = 2


class SourceRecord(BaseModel):
    source_id: str
    competitor_name: str
    source_type: str
    title: str
    url: Optional[str] = None
    content: str
    publisher: Optional[str] = None
    is_official: bool = False
    is_third_party: bool = False
    is_public: bool = True
    published_at: Optional[str] = None
    discovered_at: str
    discovery_tool: str
    reliability_weight: float
    relevance_score: float
    confidence_modifier: float
    notes: Optional[str] = None


class SourceInventory(BaseModel):
    total_sources: int
    category_counts: Dict[str, int] = Field(default_factory=dict)
    source_ids_by_category: Dict[str, List[str]] = Field(default_factory=dict)
    official_source_count: int = 0
    third_party_source_count: int = 0
    tools_used: List[str] = Field(default_factory=list)


class CoverageCategorySummary(BaseModel):
    category: str
    status: str
    source_count: int
    official_count: int
    third_party_count: int
    avg_reliability: float
    notes: str


class CoverageSummary(BaseModel):
    categories: List[CoverageCategorySummary]
    overall_status: str
    strong_categories: List[str] = Field(default_factory=list)
    weak_categories: List[str] = Field(default_factory=list)


class CoverageGap(BaseModel):
    category: str
    severity: str
    reason: str
    suggested_next_tool: Optional[str] = None


class PlannerDecision(BaseModel):
    action: str
    reason: str
    next_category: Optional[str] = None
    next_tool: Optional[str] = None


class ToolInput(BaseModel):
    competitor_name: str
    domain: Optional[str] = None
    query: Optional[str] = None
    category: Optional[str] = None
    linkedin_company_url: Optional[str] = None
    resolved_company_domain: Optional[str] = None
    max_results: int = 10
    allow_third_party: bool = True
    preferred_source_type: Optional[str] = None


class ToolResult(BaseModel):
    tool_name: str
    success: bool
    sources: List[SourceRecord] = Field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolSpec(BaseModel):
    name: str
    description: str
    source_category: str
    requires_api_key: bool = False
    reliability_weight: float
    allowed_agents: List[str] = Field(default_factory=list)


class ToolCallLog(BaseModel):
    tool_name: str
    category: str
    query: Optional[str] = None
    success: bool
    sources_returned: int
    api_request: Optional[Dict[str, Any]] = None
    api_response: Optional[Any] = None
    error: Optional[str] = None
    timestamp: str


class LLMCallLog(BaseModel):
    stage: str
    provider: str
    model: str
    success: bool
    response_text: Optional[str] = None
    error: Optional[str] = None
    timestamp: str


class SourceAnalysis(BaseModel):
    analysis_id: str
    source_id: str
    category: str
    observations: List[str]
    themes: List[str]
    confidence: float


class ReportCitation(BaseModel):
    source_id: str
    title: str
    url: Optional[str] = None


class CategoryReportSection(BaseModel):
    section_id: str
    category: str
    title: str
    markdown: str
    source_ids: List[str]
    citations: List[ReportCitation] = Field(default_factory=list)
    generated_by: str
    confidence: float


class ExtractedClaim(BaseModel):
    claim_id: str
    claim: str
    theme: str
    source_ids: List[str]
    evidence_snippets: List[str]
    source_types: List[str]
    persona: Optional[str] = None
    funnel_stage: Optional[str] = None
    confidence: float
    timestamp: str


class MessagingTheme(BaseModel):
    theme: str
    frequency: int
    confidence: float
    supporting_claim_ids: List[str]


class PositioningSummary(BaseModel):
    primary_positioning: str
    target_personas: List[str]
    target_segments: List[str]
    main_differentiators_claimed: List[str]
    confidence: float


class MessagingSummary(BaseModel):
    top_messaging_themes: List[MessagingTheme]
    positioning_summary: PositioningSummary


class RecentChange(BaseModel):
    change: str
    evidence_source_ids: List[str]
    interpretation: str
    confidence: float


class RipplingPositioningPillar(BaseModel):
    pillar: str
    description: str


class RipplingOpportunity(BaseModel):
    opportunity_id: str
    competitor_strategy: str
    competitor_gap: str
    why_gap_matters: str
    rippling_advantage: str
    campaign_angle: str
    example_copy: str
    supporting_claim_ids: List[str]
    mapped_rippling_pillars: List[str]
    confidence: float


class CampaignRecommendation(BaseModel):
    recommendation_id: str
    angle: str
    target_segment: str
    message: str
    recommended_channels: List[str]
    example_copy: str
    why_it_works: str
    supporting_opportunity_ids: List[str]
    confidence: float


class EvalSummary(BaseModel):
    source_coverage_score: float
    claim_grounding_score: float
    unsupported_claim_count: int
    json_schema_valid: bool
    recommendation_specificity_score: float
    third_party_caveat_score: float
    public_source_compliance: bool
    weak_sections: List[str]
    overall_quality_score: float
    explanation: str


class FinalReport(BaseModel):
    competitor: Optional[CompetitorProfile]
    research_plan: Optional[ResearchPlan]
    source_inventory: Optional[SourceInventory]
    coverage_summary: Optional[CoverageSummary]
    coverage_gaps: List[CoverageGap]
    tool_call_logs: List[ToolCallLog]
    llm_call_logs: List[LLMCallLog] = Field(default_factory=list)
    category_report_sections: List[CategoryReportSection] = Field(default_factory=list)
    extracted_claims: List[ExtractedClaim]
    messaging_summary: Optional[MessagingSummary]
    recent_changes: List[RecentChange]
    rippling_opportunities: List[RipplingOpportunity]
    campaign_recommendations: List[CampaignRecommendation]
    eval_summary: Optional[EvalSummary]
