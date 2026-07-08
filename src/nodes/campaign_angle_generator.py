from __future__ import annotations

from src.schemas import CampaignRecommendation
from src.state import AgentState


def generate_campaign_angles(state: AgentState) -> AgentState:
    recommendations = []
    for index, opportunity in enumerate(state.rippling_opportunities, start=1):
        recommendations.append(
            CampaignRecommendation(
                recommendation_id=f"rec_{index:03d}",
                angle=opportunity.campaign_angle,
                target_segment="Scaling SMBs and mid-market companies",
                message=(
                    "When HR, IT, and Finance start breaking across disconnected tools, "
                    "Rippling gives teams one workforce system."
                ),
                recommended_channels=["paid search", "comparison landing page", "outbound email"],
                example_copy=opportunity.example_copy,
                why_it_works=(
                    "The angle is tied to evidence-backed competitor messaging and the visible gap in cross-functional workflows."
                ),
                supporting_opportunity_ids=[opportunity.opportunity_id],
                confidence=round(min(0.95, opportunity.confidence - 0.02), 2),
            )
        )
    state.campaign_recommendations = recommendations
    state.logs.append(f"Generated {len(recommendations)} campaign recommendations.")
    return state

