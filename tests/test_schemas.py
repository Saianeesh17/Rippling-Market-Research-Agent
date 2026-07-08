from __future__ import annotations

from src.config import utc_now_iso
from src.schemas import SourceRecord


def test_source_record_schema_accepts_quality_metadata():
    source = SourceRecord(
        source_id="src_1",
        competitor_name="Gusto",
        source_type="pricing",
        title="Third-party pricing estimate",
        content="Public third-party pricing estimate.",
        is_third_party=True,
        discovered_at=utc_now_iso(),
        discovery_tool="DummyThirdPartyPricingTool",
        reliability_weight=0.55,
        relevance_score=0.6,
        confidence_modifier=0.68,
    )

    assert source.is_public
    assert source.reliability_weight == 0.55

