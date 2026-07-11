from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from src.cache import get_cached_json, set_cached_json
from src.config import utc_now_iso
from src.data.dummy_sources import slugify
from src.schemas import SourceRecord, ToolInput, ToolResult
from src.tools.base import BaseSourceTool
from src.tools.domain_utils import normalize_company_domain


MAX_EXA_RESEARCH_RESULTS = 5
DEFAULT_EXA_RESEARCH_CACHE_TTL_HOURS = 24
DEFAULT_EXA_CONTENT_MAX_AGE_HOURS = 24
DEFAULT_PRESS_RECENCY_MONTHS = 18

LOW_QUALITY_DOMAIN_SUFFIXES = {
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "youtube.com",
    "tiktok.com",
    "reddit.com",
    "pinterest.com",
}

PRICING_THIRD_PARTY_DOMAIN_SUFFIXES = {
    "g2.com",
    "capterra.com",
    "getapp.com",
    "softwareadvice.com",
    "trustradius.com",
    "saasworthy.com",
}


class BaseExaResearchTool(BaseSourceTool):
    reliability_weight = 0.78
    requires_api_key = True
    allowed_agents: list[str] = []

    category: str = ""
    official_query_suffix: str = ""
    external_query_suffix: str = ""
    source_label: str = "Exa search result"
    min_official_sources_before_external = 1
    external_reliability_weight = 0.62
    external_confidence_modifier = 0.68
    official_confidence_modifier = 0.84
    recency_months_env: str | None = None
    exa_category_for_external: str | None = None

    def run(self, tool_input: ToolInput) -> ToolResult:
        max_results = min(MAX_EXA_RESEARCH_RESULTS, _env_int("EXA_RESEARCH_MAX_RESULTS", default=MAX_EXA_RESEARCH_RESULTS))
        ttl_hours = _env_int("EXA_RESEARCH_CACHE_TTL_HOURS", default=DEFAULT_EXA_RESEARCH_CACHE_TTL_HOURS)
        company_domain = normalize_company_domain(tool_input.resolved_company_domain or tool_input.domain)
        cache_key = self._cache_key(tool_input, company_domain, max_results)
        cached = get_cached_json("exa_research", cache_key, ttl_seconds=max(0, ttl_hours) * 60 * 60)
        if cached and isinstance(cached.get("results"), list):
            sources = self._sources_from_results(
                tool_input,
                company_domain,
                list(cached["results"]),
                max_results=max_results,
            )
            return ToolResult(
                tool_name=self.name,
                success=bool(sources),
                sources=sources,
                error=None if sources else "Cached Exa response contained no usable sources for this research category.",
                metadata={
                    "resolved_company_domain": company_domain or None,
                    "cache": {"hit": True, "namespace": "exa_research", "ttl_hours": ttl_hours},
                    "api_request": {"cache_hit": True, "would_have_requested": cached.get("api_request")},
                    "api_response": {"cache_hit": True, "cached_value": cached},
                },
            )

        api_key = os.getenv("EXA_API_KEY", "").strip()
        request_plan = self._request_plan(tool_input, company_domain, max_results)
        if not api_key:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="EXA_API_KEY is not set and Exa research cache missed.",
                metadata={
                    "cache": {"hit": False, "namespace": "exa_research", "ttl_hours": ttl_hours},
                    "api_request": {"calls": request_plan, "cache_hit": False},
                },
            )

        all_results: list[dict[str, Any]] = []
        executed_calls: list[dict[str, Any]] = []
        try:
            for request in request_plan:
                results = self._search(api_key, request)
                executed_calls.append(request)
                all_results.extend(self._tag_results(results, source_scope=str(request["source_scope"])))
                current_sources = self._sources_from_results(
                    tool_input,
                    company_domain,
                    all_results,
                    max_results=max_results,
                )
                if request["source_scope"] == "official" and len(current_sources) >= self.min_official_sources_before_external:
                    break
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                metadata={
                    "cache": {"hit": False, "namespace": "exa_research", "ttl_hours": ttl_hours},
                    "api_request": {"calls": executed_calls or request_plan, "cache_hit": False},
                },
            )

        sources = self._sources_from_results(tool_input, company_domain, all_results, max_results=max_results)
        cached_payload = {
            "company_domain": company_domain,
            "results": all_results,
            "api_request": {"calls": executed_calls, "cache_hit": False},
            "api_response": {
                "results_returned_by_api": len(all_results),
                "sources_accepted": len(sources),
                "logged_results": all_results[:max_results],
            },
        }
        set_cached_json("exa_research", cache_key, cached_payload)
        return ToolResult(
            tool_name=self.name,
            success=bool(sources),
            sources=sources,
            error=None if sources else "Exa returned no usable sources for this research category.",
            metadata={
                "resolved_company_domain": company_domain or None,
                "cache": {"hit": False, "namespace": "exa_research", "ttl_hours": ttl_hours},
                "api_request": cached_payload["api_request"],
                "api_response": cached_payload["api_response"],
            },
        )

    def _request_plan(self, tool_input: ToolInput, company_domain: str, max_results: int) -> list[dict[str, Any]]:
        contents = {
            "highlights": {"query": self._highlight_query(tool_input), "maxCharacters": 2000},
            "text": {"maxCharacters": 2600},
            "maxAgeHours": _env_int("EXA_RESEARCH_CONTENT_MAX_AGE_HOURS", default=DEFAULT_EXA_CONTENT_MAX_AGE_HOURS),
        }
        calls: list[dict[str, Any]] = []
        if company_domain:
            calls.append(
                {
                    "query": self._official_query(tool_input),
                    "type": "auto",
                    "num_results": max_results,
                    "include_domains": [company_domain],
                    "exclude_domains": None,
                    "category": None,
                    "start_published_date": self._start_published_date(),
                    "contents": contents,
                    "source_scope": "official",
                }
            )
        calls.append(
            {
                "query": self._external_query(tool_input, company_domain),
                "type": "auto",
                "num_results": max_results,
                "include_domains": None,
                "exclude_domains": [company_domain] if company_domain else None,
                "category": self.exa_category_for_external,
                "start_published_date": self._start_published_date(),
                "contents": contents,
                "source_scope": "external",
            }
        )
        return calls

    def _search(self, api_key: str, request: dict[str, Any]) -> list[dict[str, Any]]:
        from exa_py import Exa

        exa = Exa(api_key=api_key)
        kwargs = {
            "type": request["type"],
            "num_results": request["num_results"],
            "contents": request["contents"],
        }
        if request.get("include_domains"):
            kwargs["include_domains"] = request["include_domains"]
        if request.get("exclude_domains"):
            kwargs["exclude_domains"] = request["exclude_domains"]
        if request.get("category"):
            kwargs["category"] = request["category"]
        if request.get("start_published_date"):
            kwargs["start_published_date"] = request["start_published_date"]
        response = exa.search(request["query"], **kwargs)
        normalized = []
        for result in getattr(response, "results", []) or []:
            highlights = getattr(result, "highlights", None)
            scores = getattr(result, "highlight_scores", None) or getattr(result, "highlightScores", None)
            normalized.append(
                {
                    "title": getattr(result, "title", None),
                    "url": getattr(result, "url", None),
                    "published_date": (
                        getattr(result, "published_date", None)
                        or getattr(result, "publishedDate", None)
                        or getattr(result, "published_at", None)
                    ),
                    "author": getattr(result, "author", None),
                    "text": getattr(result, "text", None),
                    "highlights": highlights if isinstance(highlights, list) else [],
                    "highlight_scores": scores if isinstance(scores, list) else [],
                    "summary": getattr(result, "summary", None),
                }
            )
        return normalized

    def _sources_from_results(
        self,
        tool_input: ToolInput,
        company_domain: str,
        results: list[dict[str, Any]],
        *,
        max_results: int,
    ) -> list[SourceRecord]:
        sources = []
        seen_urls: set[str] = set()
        for result in results:
            source = self._source_from_result(tool_input, company_domain, result)
            if not source or not source.url or source.url in seen_urls:
                continue
            seen_urls.add(source.url)
            sources.append(source)
            if len(sources) >= max_results:
                break
        return sources

    def _source_from_result(
        self,
        tool_input: ToolInput,
        company_domain: str,
        result: dict[str, Any],
    ) -> SourceRecord | None:
        url = str(result.get("url") or "").strip()
        result_domain = normalize_company_domain(url)
        if not url or not result_domain or _is_low_quality_domain(result_domain):
            return None

        content = _content_from_result(result)
        if len(content) < 80:
            return None

        title = str(result.get("title") or self.source_label).strip()
        is_official = _is_official_domain(result_domain, company_domain)
        is_third_party = not is_official
        if not is_official and str(result.get("source_scope")) == "official":
            return None
        quality = self._quality_for_result(result_domain, is_official)
        if quality["drop"]:
            return None

        source_hash = hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:10]
        return SourceRecord(
            source_id=f"exa_{self.category}_{slugify(tool_input.competitor_name)}_{source_hash}",
            competitor_name=tool_input.competitor_name,
            source_type=self.category,
            title=title[:140],
            url=url,
            content=content,
            publisher=str(result.get("author") or ("Official website" if is_official else result_domain)),
            is_official=is_official,
            is_third_party=is_third_party,
            is_public=True,
            published_at=_string_or_none(result.get("published_date")),
            discovered_at=utc_now_iso(),
            discovery_tool=self.name,
            reliability_weight=quality["reliability_weight"],
            relevance_score=0.5,
            confidence_modifier=quality["confidence_modifier"],
            notes=quality["notes"],
        )

    def _quality_for_result(self, result_domain: str, is_official: bool) -> dict[str, Any]:
        if is_official:
            return {
                "drop": False,
                "reliability_weight": self.reliability_weight,
                "confidence_modifier": self.official_confidence_modifier,
                "notes": "Official public page discovered and extracted through Exa.",
            }
        if self.category == "pricing" and _domain_matches_any(result_domain, PRICING_THIRD_PARTY_DOMAIN_SUFFIXES):
            return {
                "drop": False,
                "reliability_weight": 0.52,
                "confidence_modifier": 0.55,
                "notes": "Third-party pricing evidence from a software marketplace; use as lower-confidence context.",
            }
        return {
            "drop": False,
            "reliability_weight": self.external_reliability_weight,
            "confidence_modifier": self.external_confidence_modifier,
            "notes": "External public source discovered through Exa; lower confidence than official pages.",
        }

    def _tag_results(self, results: list[dict[str, Any]], *, source_scope: str) -> list[dict[str, Any]]:
        tagged = []
        for result in results:
            result_copy = dict(result)
            result_copy["source_scope"] = source_scope
            tagged.append(result_copy)
        return tagged

    def _official_query(self, tool_input: ToolInput) -> str:
        return f"{tool_input.competitor_name} {self.official_query_suffix}".strip()

    def _external_query(self, tool_input: ToolInput, company_domain: str) -> str:
        domain_hint = f" {company_domain}" if company_domain else ""
        return f"{tool_input.competitor_name}{domain_hint} {self.external_query_suffix}".strip()

    def _highlight_query(self, tool_input: ToolInput) -> str:
        return f"{tool_input.competitor_name} {self.official_query_suffix} {self.external_query_suffix}".strip()

    def _cache_key(self, tool_input: ToolInput, company_domain: str, max_results: int) -> str:
        return "|".join(
            [
                self.name,
                tool_input.competitor_name.strip().lower(),
                company_domain,
                self.category,
                f"max={max_results}",
                f"press_months={_env_int('EXA_PRESS_RECENCY_MONTHS', default=DEFAULT_PRESS_RECENCY_MONTHS)}",
            ]
        )

    def _start_published_date(self) -> str | None:
        if not self.recency_months_env:
            return None
        months = _env_int(self.recency_months_env, default=DEFAULT_PRESS_RECENCY_MONTHS)
        if months <= 0:
            return None
        start = datetime.now(timezone.utc) - timedelta(days=months * 30)
        return start.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ExaWebsitePositioningTool(BaseExaResearchTool):
    name = "ExaWebsitePositioningTool"
    description = "Real Exa adapter for homepage and website positioning research."
    source_category = "website_positioning"
    allowed_agents = ["website_positioning"]
    category = "website_positioning"
    reliability_weight = 0.88
    official_query_suffix = "homepage positioning product marketing target customers value proposition"
    external_query_suffix = "website positioning value proposition target customers product overview"
    source_label = "Website positioning page"


class ExaProductPagesTool(BaseExaResearchTool):
    name = "ExaProductPagesTool"
    description = "Real Exa adapter for public product and use-case page research."
    source_category = "product_pages"
    allowed_agents = ["product_pages"]
    category = "product_pages"
    reliability_weight = 0.86
    official_query_suffix = "product pages solutions use cases features workflows"
    external_query_suffix = "product pages solutions features use cases overview"
    source_label = "Product page"
    min_official_sources_before_external = 2


class ExaPricingResearchTool(BaseExaResearchTool):
    name = "ExaPricingResearchTool"
    description = "Real Exa adapter for public pricing and packaging research."
    source_category = "pricing"
    allowed_agents = ["pricing"]
    category = "pricing"
    reliability_weight = 0.84
    official_query_suffix = "pricing page packages tiers plans fees"
    external_query_suffix = "pricing packages plans tiers third-party pricing review"
    source_label = "Pricing page"
    external_reliability_weight = 0.56
    external_confidence_modifier = 0.58


class ExaPressNewsResearchTool(BaseExaResearchTool):
    name = "ExaPressNewsResearchTool"
    description = "Real Exa adapter for recent product launches, press, and announcements."
    source_category = "press_news"
    allowed_agents = ["press_news"]
    category = "press_news"
    reliability_weight = 0.82
    official_query_suffix = "recent product launch press release announcement new product"
    external_query_suffix = "recent product launch announcement press news"
    source_label = "Recent press or announcement"
    external_reliability_weight = 0.66
    external_confidence_modifier = 0.7
    recency_months_env = "EXA_PRESS_RECENCY_MONTHS"
    exa_category_for_external = "news"


def _content_from_result(result: dict[str, Any]) -> str:
    parts = []
    summary = _string_or_none(result.get("summary"))
    if summary:
        parts.append(f"Summary: {summary}")
    highlights = result.get("highlights")
    if isinstance(highlights, list) and highlights:
        parts.append("Highlights: " + " | ".join(str(item).strip() for item in highlights[:5] if str(item).strip()))
    text = _string_or_none(result.get("text"))
    if text:
        parts.append(f"Page text excerpt: {text[:2600]}")
    return "\n".join(part for part in parts if part.strip())


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _is_low_quality_domain(domain: str) -> bool:
    return _domain_matches_any(domain, LOW_QUALITY_DOMAIN_SUFFIXES)


def _domain_matches_any(domain: str, suffixes: set[str]) -> bool:
    normalized = normalize_company_domain(domain)
    return any(normalized == suffix or normalized.endswith(f".{suffix}") for suffix in suffixes)


def _is_official_domain(result_domain: str, company_domain: str) -> bool:
    normalized_result = normalize_company_domain(result_domain)
    normalized_company = normalize_company_domain(company_domain)
    return bool(
        normalized_company
        and (
            normalized_result == normalized_company
            or normalized_result.endswith(f".{normalized_company}")
        )
    )


def _env_int(name: str, *, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default
