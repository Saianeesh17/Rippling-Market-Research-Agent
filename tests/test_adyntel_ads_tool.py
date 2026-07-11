from __future__ import annotations

from src.schemas import ToolInput
from src.tools.adyntel_ads_tool import AdyntelMetaAdsTool


class FakeAdyntelMetaAdsTool(AdyntelMetaAdsTool):
    def __init__(self):
        self.calls = 0
        self.payload = None

    def _post(self, payload):
        self.calls += 1
        self.payload = payload
        return (
            200,
            {
                "results": [
                    [
                        {
                            "ad_archive_id": f"meta-{index}",
                            "publisherPlatform": ["facebook", "instagram"],
                            "startDate": 1782864000,
                            "snapshot": {
                                "page_name": "Gusto",
                                "page_profile_uri": "https://facebook.com/gusto",
                                "link_url": f"https://gusto.com/ad-{index}",
                                "body": {"text": f"Run payroll faster with Gusto ad {index}."},
                                "cta_text": "Learn more",
                            },
                        }
                        for index in range(1, 8)
                    ]
                ]
            },
        )


def test_adyntel_ads_tool_requires_resolved_domain(monkeypatch):
    monkeypatch.setenv("ADYNTEL_EMAIL", "test@example.com")
    monkeypatch.setenv("ADYNTEL_API_KEY", "test-key")
    tool = AdyntelMetaAdsTool()

    result = tool.run(ToolInput(competitor_name="Unknown", category="paid_ads"))

    assert not result.success
    assert "No company domain" in (result.error or "")


def test_adyntel_ads_tool_requires_credentials_on_cache_miss(monkeypatch):
    monkeypatch.setenv("ADYNTEL_EMAIL", "")
    monkeypatch.setenv("ADYNTEL_API_KEY", "")
    tool = AdyntelMetaAdsTool()

    result = tool.run(
        ToolInput(
            competitor_name="Gusto",
            category="paid_ads",
            resolved_company_domain="gusto.com",
        )
    )

    assert not result.success
    assert "ADYNTEL_EMAIL" in (result.error or "")


def test_adyntel_ads_tool_limits_to_five_ads_and_redacts_credentials(monkeypatch):
    monkeypatch.setenv("ADYNTEL_EMAIL", "test@example.com")
    monkeypatch.setenv("ADYNTEL_API_KEY", "test-key")
    monkeypatch.setenv("ADYNTEL_MAX_ADS_PER_PLATFORM", "99")
    tool = FakeAdyntelMetaAdsTool()

    result = tool.run(
        ToolInput(
            competitor_name="Gusto",
            domain="https://www.gusto.com/",
            category="paid_ads",
            resolved_company_domain="gusto.com",
        )
    )

    assert result.success
    assert tool.payload == {
        "api_key": "test-key",
        "email": "test@example.com",
        "company_domain": "gusto.com",
    }
    assert len(result.sources) == 5
    assert result.metadata["api_request"]["json"]["api_key"] == "<redacted>"
    assert result.metadata["api_request"]["json"]["email"] == "<redacted>"
    assert result.metadata["api_request"]["json"]["company_domain"] == "gusto.com"
    assert result.metadata["api_response"]["ads_returned_by_api"] == 7
    assert len(result.metadata["api_response"]["logged_ads"]) == 5
    assert result.sources[0].source_type == "paid_ads"
    assert result.sources[0].url == "https://gusto.com/ad-1"


def test_adyntel_ads_tool_uses_cache_before_ttl_expiry(monkeypatch):
    monkeypatch.setenv("ADYNTEL_EMAIL", "test@example.com")
    monkeypatch.setenv("ADYNTEL_API_KEY", "test-key")
    monkeypatch.setenv("ADYNTEL_AD_CACHE_TTL_HOURS", "120")
    tool = FakeAdyntelMetaAdsTool()
    tool_input = ToolInput(
        competitor_name="Gusto",
        category="paid_ads",
        resolved_company_domain="gusto.com",
    )

    first = tool.run(tool_input)
    monkeypatch.setenv("ADYNTEL_EMAIL", "")
    monkeypatch.setenv("ADYNTEL_API_KEY", "")
    second = tool.run(tool_input)

    assert first.success
    assert second.success
    assert tool.calls == 1
    assert second.metadata["cache"]["hit"] is True
    assert second.metadata["api_response"]["cache_hit"] is True
