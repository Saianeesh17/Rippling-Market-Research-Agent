from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from src.schemas import (
    CampaignRecommendation,
    CategoryReportSection,
    CompetitorProfile,
    CoverageGap,
    CoverageSummary,
    EvalSummary,
    ExtractedClaim,
    LLMCallLog,
    MessagingSummary,
    PlannerDecision,
    RecentChange,
    ResearchPlan,
    RipplingOpportunity,
    SourceAnalysis,
    SourceInventory,
    SourceRecord,
    ToolCallLog,
)


class AgentState(BaseModel):
    user_input: str
    competitor: Optional[CompetitorProfile] = None
    research_plan: Optional[ResearchPlan] = None
    discovered_sources: List[SourceRecord] = Field(default_factory=list)
    source_inventory: Optional[SourceInventory] = None
    coverage_summary: Optional[CoverageSummary] = None
    coverage_gaps: List[CoverageGap] = Field(default_factory=list)
    planner_decision: Optional[PlannerDecision] = None
    tool_call_logs: List[ToolCallLog] = Field(default_factory=list)
    llm_call_logs: List[LLMCallLog] = Field(default_factory=list)
    source_analyses: List[SourceAnalysis] = Field(default_factory=list)
    category_report_sections: List[CategoryReportSection] = Field(default_factory=list)
    extracted_claims: List[ExtractedClaim] = Field(default_factory=list)
    messaging_summary: Optional[MessagingSummary] = None
    recent_changes: List[RecentChange] = Field(default_factory=list)
    rippling_opportunities: List[RipplingOpportunity] = Field(default_factory=list)
    campaign_recommendations: List[CampaignRecommendation] = Field(default_factory=list)
    eval_summary: Optional[EvalSummary] = None
    final_markdown_path: Optional[str] = None
    final_json_path: Optional[str] = None
    final_log_path: Optional[str] = None
    logs: List[str] = Field(default_factory=list)
    replanning_cycles: int = 0
    real_sources_only: bool = False
