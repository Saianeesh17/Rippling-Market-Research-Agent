from __future__ import annotations

from src.config import SOURCE_CATEGORIES
from src.schemas import ResearchPlan, ResearchTask
from src.state import AgentState


REASONS = {
    "website_positioning": "Homepage and public website pages usually contain core positioning.",
    "product_pages": "Product pages reveal category emphasis, use cases, personas, and differentiation.",
    "pricing": "Pricing and packaging pages reveal target segment, sales motion, and buying friction.",
    "paid_ads": "Ad copy reveals active campaign hooks, pain points, and funnel messaging.",
    "social": "Public social posts reveal recurring themes and recent content emphasis.",
    "press_news": "Press and news-like sources reveal launches, category expansion, and public messaging shifts.",
    "comparison_pages": "Comparison pages reveal objections, claimed strengths, and buying criteria.",
}


def create_research_plan(state: AgentState) -> AgentState:
    tasks = [
        ResearchTask(
            category=category,
            priority="high" if category in {"website_positioning", "product_pages", "pricing"} else "medium",
            reason=REASONS[category],
        )
        for category in SOURCE_CATEGORIES
    ]
    state.research_plan = ResearchPlan(tasks=tasks, max_sources=40, max_replanning_cycles=2)
    state.logs.append("Created bounded public-source research plan.")
    return state

