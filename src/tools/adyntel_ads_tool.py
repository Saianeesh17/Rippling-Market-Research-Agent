from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from src.cache import get_cached_json, set_cached_json
from src.config import utc_now_iso
from src.data.dummy_sources import slugify
from src.schemas import SourceRecord, ToolInput, ToolResult
from src.tools.base import BaseSourceTool
from src.tools.domain_utils import normalize_company_domain


ADYNTEL_BASE_URL = "https://api.adyntel.com"
MAX_ADYNTEL_ADS_PER_PLATFORM = 5
DEFAULT_AD_CACHE_TTL_HOURS = 120


class BaseAdyntelAdsTool(BaseSourceTool):
    source_category = "paid_ads"
    reliability_weight = 0.82
    requires_api_key = True
    allowed_agents = ["paid_ads"]

    platform: str = ""
    endpoint_path: str = ""
    display_name: str = ""

    def run(self, tool_input: ToolInput) -> ToolResult:
        max_ads = min(
            MAX_ADYNTEL_ADS_PER_PLATFORM,
            _env_int("ADYNTEL_MAX_ADS_PER_PLATFORM", default=MAX_ADYNTEL_ADS_PER_PLATFORM),
        )
        ttl_hours = _env_int("ADYNTEL_AD_CACHE_TTL_HOURS", default=DEFAULT_AD_CACHE_TTL_HOURS)
        company_domain = normalize_company_domain(tool_input.resolved_company_domain or tool_input.domain)
        api_request = self._api_request(company_domain, max_ads)

        if not company_domain:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="No company domain was resolved; run ExaCompanyDomainSearchTool before Adyntel ad search.",
                metadata={"api_request": api_request},
            )

        cache_key = self._cache_key(company_domain, max_ads)
        cached = get_cached_json(
            self._cache_namespace(),
            cache_key,
            ttl_seconds=max(0, ttl_hours) * 60 * 60,
        )
        if cached and isinstance(cached.get("ads"), list):
            return self._result_from_ads(
                tool_input,
                company_domain,
                max_ads,
                list(cached["ads"]),
                raw_response=cached.get("api_response", {}),
                api_request=api_request,
                cache_hit=True,
                ttl_hours=ttl_hours,
            )

        email = os.getenv("ADYNTEL_EMAIL", "").strip()
        api_key = os.getenv("ADYNTEL_API_KEY", "").strip()
        if not email or not api_key:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="ADYNTEL_EMAIL and ADYNTEL_API_KEY must be set for live Adyntel ad search.",
                metadata={
                    "cache": {
                        "hit": False,
                        "namespace": self._cache_namespace(),
                        "ttl_hours": ttl_hours,
                    },
                    "api_request": api_request,
                },
            )

        payload = {
            "api_key": api_key,
            "email": email,
            "company_domain": company_domain,
        }
        try:
            status_code, data = self._post(payload)
        except httpx.HTTPStatusError as exc:
            response = exc.response
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                metadata={
                    "cache": {
                        "hit": False,
                        "namespace": self._cache_namespace(),
                        "ttl_hours": ttl_hours,
                    },
                    "api_request": api_request,
                    "api_response": {
                        "status_code": response.status_code,
                        "text": response.text[:2000],
                    },
                },
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                metadata={
                    "cache": {
                        "hit": False,
                        "namespace": self._cache_namespace(),
                        "ttl_hours": ttl_hours,
                    },
                    "api_request": api_request,
                },
            )

        raw_ads = [] if status_code == 204 else self._extract_ads(data)
        ads = raw_ads[:max_ads]
        raw_response = {
            "status_code": status_code,
            "ads_returned_by_api": len(raw_ads),
            "logged_ads": [_compact_for_log(ad) for ad in ads],
        }
        set_cached_json(
            self._cache_namespace(),
            cache_key,
            {
                "company_domain": company_domain,
                "ads": ads,
                "api_response": raw_response,
            },
        )

        return self._result_from_ads(
            tool_input,
            company_domain,
            max_ads,
            ads,
            raw_response=raw_response,
            api_request=api_request,
            cache_hit=False,
            ttl_hours=ttl_hours,
        )

    def _api_request(self, company_domain: str, max_ads: int) -> dict[str, Any]:
        return {
            "method": "POST",
            "url": f"{_base_url()}{self.endpoint_path}",
            "json": {
                "api_key": "<redacted>",
                "email": "<redacted>",
                "company_domain": company_domain or None,
            },
            "max_ads_logged": max_ads,
            "cache_hit": False,
        }

    def _result_from_ads(
        self,
        tool_input: ToolInput,
        company_domain: str,
        max_ads: int,
        ads: list[dict[str, Any]],
        *,
        raw_response: Any,
        api_request: dict[str, Any],
        cache_hit: bool,
        ttl_hours: int,
    ) -> ToolResult:
        sources = [
            self._source_from_ad(tool_input, company_domain, ad, index)
            for index, ad in enumerate(ads[:max_ads], start=1)
        ]
        request_with_cache = dict(api_request)
        request_with_cache["cache_hit"] = cache_hit
        return ToolResult(
            tool_name=self.name,
            success=True,
            sources=[source for source in sources if source is not None],
            metadata={
                "resolved_company_domain": company_domain,
                "platform": self.platform,
                "cache": {
                    "hit": cache_hit,
                    "namespace": self._cache_namespace(),
                    "ttl_hours": ttl_hours,
                },
                "api_request": request_with_cache,
                "api_response": {
                    "cache_hit": cache_hit,
                    **(raw_response if isinstance(raw_response, dict) else {"raw_response": raw_response}),
                },
            },
        )

    def _post(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{_base_url()}{self.endpoint_path}",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        if response.status_code == 204:
            return response.status_code, {}
        response.raise_for_status()
        data = response.json()
        return response.status_code, data if isinstance(data, dict) else {"data": data}

    def _extract_ads(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        ads = data.get("ads")
        if isinstance(ads, list):
            return [ad for ad in ads if isinstance(ad, dict)]
        if isinstance(data.get("data"), list):
            return [ad for ad in data["data"] if isinstance(ad, dict)]
        return []

    def _source_from_ad(
        self,
        tool_input: ToolInput,
        company_domain: str,
        ad: dict[str, Any],
        index: int,
    ) -> SourceRecord | None:
        content = self._content_for_ad(ad)
        if not content:
            content = json.dumps(_compact_for_log(ad), ensure_ascii=True)[:1400]
        if not content:
            return None

        title = self._title_for_ad(ad, index)
        source_hash = hashlib.sha1(
            json.dumps(_compact_for_log(ad), sort_keys=True, ensure_ascii=True, default=str).encode("utf-8")
        ).hexdigest()[:10]
        return SourceRecord(
            source_id=f"adyntel_{self.platform}_{slugify(tool_input.competitor_name)}_{source_hash}",
            competitor_name=tool_input.competitor_name,
            source_type="paid_ads",
            title=title[:140],
            url=self._url_for_ad(ad),
            content=content,
            publisher=self._publisher_for_ad(ad),
            is_official=True,
            is_third_party=False,
            is_public=True,
            published_at=self._published_at_for_ad(ad),
            discovered_at=utc_now_iso(),
            discovery_tool=self.name,
            reliability_weight=self.reliability_weight,
            relevance_score=0.5,
            confidence_modifier=0.84,
            notes=(
                f"Real public {self.display_name} ad library result through Adyntel; "
                "limited to 5 ads per platform for testing."
            ),
        )

    def _content_for_ad(self, ad: dict[str, Any]) -> str:
        raise NotImplementedError

    def _title_for_ad(self, ad: dict[str, Any], index: int) -> str:
        headline = _first_nonempty(
            [
                _nested_string(ad, ["headline", "title"]),
                _nested_string(ad, ["snapshot", "title"]),
                _nested_string(ad, ["snapshot", "body", "text"]),
                _nested_string(ad, ["commentary", "text"]),
                _nested_string(ad, ["advertiser_name"]),
            ]
        )
        return f"{self.display_name} ad {index}: {headline[:90]}" if headline else f"{self.display_name} ad {index}"

    def _url_for_ad(self, ad: dict[str, Any]) -> str | None:
        return _first_nonempty(
            [
                _nested_string(ad, ["original_url"]),
                _nested_string(ad, ["view_details_link"]),
                _nested_string(ad, ["snapshot", "link_url"]),
                _nested_string(ad, ["snapshot", "page_profile_uri"]),
                _nested_string(ad, ["url"]),
            ]
        ) or None

    def _publisher_for_ad(self, ad: dict[str, Any]) -> str:
        return _first_nonempty(
            [
                _nested_string(ad, ["advertiser", "name"]),
                _nested_string(ad, ["advertiser_name"]),
                _nested_string(ad, ["snapshot", "page_name"]),
                _nested_string(ad, ["pageName"]),
                f"Adyntel {self.display_name}",
            ]
        )

    def _published_at_for_ad(self, ad: dict[str, Any]) -> str | None:
        start = ad.get("start") or ad.get("start_date") or ad.get("startDate")
        if isinstance(start, str) and start.strip():
            return start.strip()
        if isinstance(start, (int, float)):
            return datetime.fromtimestamp(float(start), tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return None

    def _cache_namespace(self) -> str:
        return f"adyntel_ads_{self.platform}"

    def _cache_key(self, company_domain: str, max_ads: int) -> str:
        return f"{self.platform}|{company_domain}|max_ads={max_ads}|endpoint={self.endpoint_path}"


class AdyntelMetaAdsTool(BaseAdyntelAdsTool):
    name = "AdyntelMetaAdsTool"
    description = "Real Adyntel adapter for public Meta Facebook and Instagram ads."
    platform = "meta"
    endpoint_path = "/facebook"
    display_name = "Meta"

    def _extract_ads(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        results = data.get("results")
        if isinstance(results, list):
            return _flatten_dicts(results)
        return super()._extract_ads(data)

    def _content_for_ad(self, ad: dict[str, Any]) -> str:
        snapshot = ad.get("snapshot") if isinstance(ad.get("snapshot"), dict) else {}
        cards = snapshot.get("cards") if isinstance(snapshot.get("cards"), list) else []
        card_text = []
        for card in cards[:3]:
            if isinstance(card, dict):
                card_text.extend(
                    [
                        _nested_string(card, ["title"]),
                        _nested_string(card, ["body"]),
                        _nested_string(card, ["link_description"]),
                    ]
                )
        parts = [
            f"Page: {_first_nonempty([_nested_string(snapshot, ['page_name']), _nested_string(ad, ['pageName'])])}",
            f"Body: {_nested_string(snapshot, ['body', 'text'])}",
            f"CTA: {_nested_string(snapshot, ['cta_text'])}",
            f"Platforms: {', '.join(str(item) for item in ad.get('publisherPlatform', []) if item)}",
            f"Cards: {' | '.join(item for item in card_text if item)}",
        ]
        return "\n".join(part for part in parts if not part.endswith(": "))


class AdyntelLinkedInAdsTool(BaseAdyntelAdsTool):
    name = "AdyntelLinkedInAdsTool"
    description = "Real Adyntel adapter for public LinkedIn ads."
    platform = "linkedin"
    endpoint_path = "/linkedin"
    display_name = "LinkedIn"

    def _content_for_ad(self, ad: dict[str, Any]) -> str:
        parts = [
            f"Advertiser: {_nested_string(ad, ['advertiser', 'name'])}",
            f"Commentary: {_nested_string(ad, ['commentary', 'text'])}",
            f"Headline: {_nested_string(ad, ['headline', 'title'])}",
            f"Description: {_nested_string(ad, ['headline', 'description'])}",
            f"Creative type: {_nested_string(ad, ['creative_type']) or _nested_string(ad, ['type'])}",
        ]
        return "\n".join(part for part in parts if not part.endswith(": "))


class AdyntelGoogleAdsTool(BaseAdyntelAdsTool):
    name = "AdyntelGoogleAdsTool"
    description = "Real Adyntel adapter for public Google Ads Transparency Center ads."
    platform = "google"
    endpoint_path = "/google"
    display_name = "Google"

    def _content_for_ad(self, ad: dict[str, Any]) -> str:
        variants = ad.get("variants") if isinstance(ad.get("variants"), list) else []
        variant_text = []
        for variant in variants[:3]:
            if isinstance(variant, dict):
                variant_text.append(_strip_html(_nested_string(variant, ["content"])))
        parts = [
            f"Advertiser: {_nested_string(ad, ['advertiser_name'])}",
            f"Format: {_nested_string(ad, ['format'])}",
            f"Start: {_nested_string(ad, ['start'])}",
            f"Last seen: {_nested_string(ad, ['last_seen'])}",
            f"Creative variants: {' | '.join(item for item in variant_text if item)}",
        ]
        return "\n".join(part for part in parts if not part.endswith(": "))


def _base_url() -> str:
    return os.getenv("ADYNTEL_BASE_URL", ADYNTEL_BASE_URL).rstrip("/")


def _env_int(name: str, *, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _nested_string(data: dict[str, Any], path: list[str]) -> str:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    if isinstance(current, str):
        return current.strip()
    if current is None:
        return ""
    if isinstance(current, (int, float, bool)):
        return str(current)
    return ""


def _first_nonempty(values: list[str]) -> str:
    return next((value.strip() for value in values if isinstance(value, str) and value.strip()), "")


def _flatten_dicts(items: list[Any]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            flattened.append(item)
        elif isinstance(item, list):
            flattened.extend(_flatten_dicts(item))
    return flattened


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def _compact_for_log(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "<truncated>"
    if isinstance(value, dict):
        return {str(key): _compact_for_log(item, depth=depth + 1) for key, item in list(value.items())[:40]}
    if isinstance(value, list):
        return [_compact_for_log(item, depth=depth + 1) for item in value[:5]]
    if isinstance(value, str):
        return value if len(value) <= 1000 else f"{value[:1000]}...<truncated>"
    return value
