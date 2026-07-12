from __future__ import annotations

from src.data.dummy_sources import slugify
from src.schemas import ToolInput
from src.tools.exa_research_tools import BaseExaResearchTool


class ExaFollowUpResearchTool(BaseExaResearchTool):
    name = "ExaFollowUpResearchTool"
    description = "Real Exa adapter for post-report follow-up research questions."
    source_category = "follow_up_research"
    allowed_agents = ["report_qa"]
    category = "follow_up_research"
    reliability_weight = 0.74
    source_label = "Follow-up research result"
    external_reliability_weight = 0.64
    external_confidence_modifier = 0.68

    def _official_query(self, tool_input: ToolInput) -> str:
        return self._question_query(tool_input)

    def _external_query(self, tool_input: ToolInput, company_domain: str) -> str:
        return self._question_query(tool_input)

    def _highlight_query(self, tool_input: ToolInput) -> str:
        return self._question_query(tool_input)

    def _cache_key(self, tool_input: ToolInput, company_domain: str, max_results: int) -> str:
        return "|".join(
            [
                self.name,
                slugify(tool_input.competitor_name),
                company_domain,
                slugify(self._question_query(tool_input)),
                f"max={max_results}",
            ]
        )

    def _question_query(self, tool_input: ToolInput) -> str:
        question = (tool_input.query or "").strip()
        competitor = tool_input.competitor_name.strip()
        if not question:
            return competitor
        if competitor.lower() in question.lower():
            return question
        return f"{competitor} {question}".strip()
