from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from src.cache import get_cached_json, set_cached_json
from src.config import utc_now_iso
from src.data.dummy_sources import slugify
from src.schemas import SourceRecord, ToolInput, ToolResult
from src.tools.base import BaseSourceTool
from src.tools.domain_utils import https_url_for_domain, normalize_company_domain


EXCLUDED_COMPANY_DOMAIN_SUFFIXES = {
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "youtube.com",
    "crunchbase.com",
    "wikipedia.org",
    "glassdoor.com",
    "g2.com",
    "capterra.com",
    "trustpilot.com",
    "bloomberg.com",
    "forbes.com",
}

INVALID_TWITTER_HANDLES = {
    "home",
    "explore",
    "search",
    "share",
    "intent",
    "i",
    "settings",
    "messages",
    "notifications",
    "login",
    "signup",
}


class ExaLinkedInCompanySearchTool(BaseSourceTool):
    name = "ExaLinkedInCompanySearchTool"
    description = "Real Exa web search adapter that resolves a competitor's LinkedIn company URL."
    source_category = "social"
    reliability_weight = 0.68
    requires_api_key = True
    allowed_agents = ["social"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        query = self._query(tool_input)
        cache_key = self._cache_key(tool_input)
        api_request = {
            "sdk": "exa_py.Exa.search",
            "query": query,
            "type": "auto",
            "num_results": 5,
            "include_domains": ["linkedin.com"],
            "contents": {"highlights": True},
        }

        cached = get_cached_json("linkedin_url", cache_key)
        if cached and cached.get("linkedin_company_url"):
            selected_url = str(cached["linkedin_company_url"])
            results = cached.get("results", [])
            sources = [self._source_from_result(tool_input, selected_url, results if isinstance(results, list) else [])]
            return ToolResult(
                tool_name=self.name,
                success=True,
                sources=sources,
                metadata={
                    "linkedin_company_url": selected_url,
                    "cache": {"hit": True, "namespace": "linkedin_url", "key": cache_key},
                    "api_request": {"cache_hit": True, "would_have_requested": api_request},
                    "api_response": {"cache_hit": True, "cached_value": cached},
                },
            )

        api_key = os.getenv("EXA_API_KEY", "").strip()
        if not api_key:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="EXA_API_KEY is not set and LinkedIn URL cache missed; cannot resolve LinkedIn company URL before Apify.",
                metadata={
                    "cache": {"hit": False, "namespace": "linkedin_url", "key": cache_key},
                    "api_request": api_request,
                },
            )

        try:
            results = self._search(api_key, api_request)
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                metadata={
                    "cache": {"hit": False, "namespace": "linkedin_url", "key": cache_key},
                    "api_request": api_request,
                },
            )

        selected_url = _select_linkedin_company_url(results)
        sources = []
        if selected_url:
            set_cached_json(
                "linkedin_url",
                cache_key,
                {
                    "linkedin_company_url": selected_url,
                    "results": results,
                },
            )
            sources.append(self._source_from_result(tool_input, selected_url, results))

        return ToolResult(
            tool_name=self.name,
            success=bool(selected_url),
            sources=sources,
            error=None if selected_url else "Exa did not return a LinkedIn company URL.",
            metadata={
                "linkedin_company_url": selected_url,
                "cache": {"hit": False, "namespace": "linkedin_url", "key": cache_key},
                "api_request": api_request,
                "api_response": {
                    "selected_linkedin_company_url": selected_url,
                    "results": results,
                },
            },
        )

    def _search(self, api_key: str, request: dict[str, Any]) -> list[dict[str, Any]]:
        from exa_py import Exa

        exa = Exa(api_key=api_key)
        response = exa.search(
            request["query"],
            type=request["type"],
            num_results=request["num_results"],
            include_domains=request["include_domains"],
            contents=request["contents"],
        )
        normalized = []
        for result in getattr(response, "results", []) or []:
            highlights = getattr(result, "highlights", None)
            normalized.append(
                {
                    "title": getattr(result, "title", None),
                    "url": getattr(result, "url", None),
                    "highlights": highlights if isinstance(highlights, list) else [],
                }
            )
        return normalized

    def _query(self, tool_input: ToolInput) -> str:
        parts = [tool_input.competitor_name, "official LinkedIn company page"]
        if tool_input.domain:
            parts.append(tool_input.domain)
        return " ".join(parts)

    def _cache_key(self, tool_input: ToolInput) -> str:
        return "|".join(
            [
                tool_input.competitor_name.strip().lower(),
                (tool_input.domain or "").strip().lower(),
            ]
        )

    def _source_from_result(
        self,
        tool_input: ToolInput,
        selected_url: str,
        results: list[dict[str, Any]],
    ) -> SourceRecord:
        selected = next((result for result in results if _normalize_linkedin_company_url(str(result.get("url", ""))) == selected_url), {})
        highlights = selected.get("highlights") or []
        content = "\n".join(
            [
                f"Resolved LinkedIn company URL: {selected_url}",
                f"Search title: {selected.get('title') or 'LinkedIn company page'}",
                f"Highlights: {' | '.join(str(item) for item in highlights[:3])}",
            ]
        )
        return SourceRecord(
            source_id=f"exa_linkedin_{slugify(tool_input.competitor_name)}",
            competitor_name=tool_input.competitor_name,
            source_type="social",
            title="Resolved LinkedIn company page",
            url=selected_url,
            content=content,
            publisher="Exa search",
            is_official=True,
            is_third_party=False,
            is_public=True,
            discovered_at=utc_now_iso(),
            discovery_tool=self.name,
            reliability_weight=self.reliability_weight,
            relevance_score=0.5,
            confidence_modifier=0.76,
            notes="LinkedIn company URL resolved via Exa before calling Apify.",
        )


class ExaTwitterHandleSearchTool(BaseSourceTool):
    name = "ExaTwitterHandleSearchTool"
    description = "Real Exa web search adapter that resolves a competitor's official Twitter/X handle."
    source_category = "social"
    reliability_weight = 0.64
    requires_api_key = True
    allowed_agents = ["social"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        query = self._query(tool_input)
        cache_key = self._cache_key(tool_input)
        api_request = {
            "sdk": "exa_py.Exa.search",
            "query": query,
            "type": "auto",
            "num_results": 5,
            "local_url_filter_domains": ["x.com", "twitter.com"],
            "contents": {"highlights": True},
        }

        cached = get_cached_json("twitter_handle", cache_key)
        if cached and cached.get("twitter_handle"):
            handle = str(cached["twitter_handle"])
            results = cached.get("results", [])
            sources = [self._source_from_result(tool_input, handle, results if isinstance(results, list) else [])]
            return ToolResult(
                tool_name=self.name,
                success=True,
                sources=sources,
                metadata={
                    "twitter_handle": handle,
                    "twitter_profile_url": _twitter_profile_url(handle),
                    "cache": {"hit": True, "namespace": "twitter_handle", "key": cache_key},
                    "api_request": {"cache_hit": True, "would_have_requested": api_request},
                    "api_response": {"cache_hit": True, "cached_value": cached},
                },
            )

        api_key = os.getenv("EXA_API_KEY", "").strip()
        if not api_key:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="EXA_API_KEY is not set and Twitter/X handle cache missed; cannot resolve handle before Apify.",
                metadata={
                    "cache": {"hit": False, "namespace": "twitter_handle", "key": cache_key},
                    "api_request": api_request,
                },
            )

        try:
            results = self._search(api_key, api_request)
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                metadata={
                    "cache": {"hit": False, "namespace": "twitter_handle", "key": cache_key},
                    "api_request": api_request,
                },
            )

        handle = _select_twitter_handle(results)
        sources = []
        if handle:
            set_cached_json(
                "twitter_handle",
                cache_key,
                {
                    "twitter_handle": handle,
                    "twitter_profile_url": _twitter_profile_url(handle),
                    "results": results,
                },
            )
            sources.append(self._source_from_result(tool_input, handle, results))

        return ToolResult(
            tool_name=self.name,
            success=bool(handle),
            sources=sources,
            error=None if handle else "Exa did not return a proper Twitter/X handle.",
            metadata={
                "twitter_handle": handle,
                "twitter_profile_url": _twitter_profile_url(handle) if handle else None,
                "cache": {"hit": False, "namespace": "twitter_handle", "key": cache_key},
                "api_request": api_request,
                "api_response": {
                    "selected_twitter_handle": handle,
                    "results": results,
                },
            },
        )

    def _search(self, api_key: str, request: dict[str, Any]) -> list[dict[str, Any]]:
        from exa_py import Exa

        exa = Exa(api_key=api_key)
        response = exa.search(
            request["query"],
            type=request["type"],
            num_results=request["num_results"],
            contents=request["contents"],
        )
        normalized = []
        for result in getattr(response, "results", []) or []:
            highlights = getattr(result, "highlights", None)
            normalized.append(
                {
                    "title": getattr(result, "title", None),
                    "url": getattr(result, "url", None),
                    "highlights": highlights if isinstance(highlights, list) else [],
                }
            )
        return normalized

    def _query(self, tool_input: ToolInput) -> str:
        parts = [tool_input.competitor_name, "official Twitter X account"]
        if tool_input.domain:
            parts.append(tool_input.domain)
        return " ".join(parts)

    def _cache_key(self, tool_input: ToolInput) -> str:
        return "|".join(
            [
                tool_input.competitor_name.strip().lower(),
                (tool_input.domain or "").strip().lower(),
            ]
        )

    def _source_from_result(
        self,
        tool_input: ToolInput,
        handle: str,
        results: list[dict[str, Any]],
    ) -> SourceRecord:
        selected = next((result for result in results if _normalize_twitter_handle_from_url(str(result.get("url", ""))) == handle), {})
        highlights = selected.get("highlights") or []
        profile_url = _twitter_profile_url(handle)
        content = "\n".join(
            [
                f"Resolved Twitter/X handle: {handle}",
                f"Profile URL: {profile_url}",
                f"Search title: {selected.get('title') or 'Twitter/X profile'}",
                f"Highlights: {' | '.join(str(item) for item in highlights[:3])}",
            ]
        )
        return SourceRecord(
            source_id=f"exa_twitter_{slugify(tool_input.competitor_name)}",
            competitor_name=tool_input.competitor_name,
            source_type="social",
            title="Resolved Twitter/X profile",
            url=profile_url,
            content=content,
            publisher="Exa search",
            is_official=True,
            is_third_party=False,
            is_public=True,
            discovered_at=utc_now_iso(),
            discovery_tool=self.name,
            reliability_weight=self.reliability_weight,
            relevance_score=0.5,
            confidence_modifier=0.72,
            notes="Twitter/X handle resolved via Exa before calling Apify.",
        )


class ExaCompanyDomainSearchTool(BaseSourceTool):
    name = "ExaCompanyDomainSearchTool"
    description = "Real Exa web search adapter that resolves a competitor's official website domain."
    source_category = "paid_ads"
    reliability_weight = 0.7
    requires_api_key = True
    allowed_agents = ["website_positioning", "product_pages", "pricing", "paid_ads", "press_news"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        query = self._query(tool_input)
        cache_key = self._cache_key(tool_input)
        api_request = {
            "sdk": "exa_py.Exa.search",
            "query": query,
            "type": "auto",
            "num_results": 5,
            "contents": {"highlights": True},
        }

        cached = get_cached_json("company_domain", cache_key)
        if cached and cached.get("company_domain"):
            resolved_domain = str(cached["company_domain"])
            return ToolResult(
                tool_name=self.name,
                success=True,
                metadata={
                    "resolved_company_domain": resolved_domain,
                    "company_url": https_url_for_domain(resolved_domain),
                    "cache": {"hit": True, "namespace": "company_domain", "key": cache_key},
                    "api_request": {"cache_hit": True, "would_have_requested": api_request},
                    "api_response": {"cache_hit": True, "cached_value": cached},
                },
            )

        known_domain = normalize_company_domain(tool_input.domain)
        if known_domain:
            payload = {
                "company_domain": known_domain,
                "company_url": https_url_for_domain(known_domain),
                "source": "competitor_profile",
            }
            set_cached_json("company_domain", cache_key, payload)
            return ToolResult(
                tool_name=self.name,
                success=True,
                metadata={
                    "resolved_company_domain": known_domain,
                    "company_url": payload["company_url"],
                    "cache": {"hit": False, "namespace": "company_domain", "key": cache_key},
                    "api_request": {"cache_hit": False, "skipped": "domain_already_available"},
                    "api_response": {"cache_hit": False, "selected_company_domain": known_domain, "source": "competitor_profile"},
                },
            )

        api_key = os.getenv("EXA_API_KEY", "").strip()
        if not api_key:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="EXA_API_KEY is not set and company domain cache missed; cannot resolve website domain before Adyntel.",
                metadata={
                    "cache": {"hit": False, "namespace": "company_domain", "key": cache_key},
                    "api_request": api_request,
                },
            )

        try:
            results = self._search(api_key, api_request)
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                metadata={
                    "cache": {"hit": False, "namespace": "company_domain", "key": cache_key},
                    "api_request": api_request,
                },
            )

        resolved_domain = _select_company_domain(results)
        if resolved_domain:
            set_cached_json(
                "company_domain",
                cache_key,
                {
                    "company_domain": resolved_domain,
                    "company_url": https_url_for_domain(resolved_domain),
                    "results": results,
                },
            )

        return ToolResult(
            tool_name=self.name,
            success=bool(resolved_domain),
            error=None if resolved_domain else "Exa did not return a likely official company website domain.",
            metadata={
                "resolved_company_domain": resolved_domain,
                "company_url": https_url_for_domain(resolved_domain),
                "cache": {"hit": False, "namespace": "company_domain", "key": cache_key},
                "api_request": api_request,
                "api_response": {
                    "selected_company_domain": resolved_domain,
                    "results": results,
                },
            },
        )

    def _search(self, api_key: str, request: dict[str, Any]) -> list[dict[str, Any]]:
        from exa_py import Exa

        exa = Exa(api_key=api_key)
        response = exa.search(
            request["query"],
            type=request["type"],
            num_results=request["num_results"],
            contents=request["contents"],
        )
        normalized = []
        for result in getattr(response, "results", []) or []:
            highlights = getattr(result, "highlights", None)
            normalized.append(
                {
                    "title": getattr(result, "title", None),
                    "url": getattr(result, "url", None),
                    "highlights": highlights if isinstance(highlights, list) else [],
                }
            )
        return normalized

    def _query(self, tool_input: ToolInput) -> str:
        return f"{tool_input.competitor_name} official website"

    def _cache_key(self, tool_input: ToolInput) -> str:
        return "|".join(
            [
                tool_input.competitor_name.strip().lower(),
                normalize_company_domain(tool_input.domain),
            ]
        )


def _select_linkedin_company_url(results: list[dict[str, Any]]) -> str | None:
    for result in results:
        url = _normalize_linkedin_company_url(str(result.get("url", "")))
        if url:
            return url
    return None


def _normalize_linkedin_company_url(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if "linkedin.com" not in parsed.netloc.lower():
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if "company" not in parts:
        return None
    company_index = parts.index("company")
    if company_index + 1 >= len(parts):
        return None
    slug = parts[company_index + 1]
    if not slug:
        return None
    return f"https://www.linkedin.com/company/{slug}/posts/?feedView=all"


def _select_twitter_handle(results: list[dict[str, Any]]) -> str | None:
    for result in results:
        handle = _normalize_twitter_handle_from_url(str(result.get("url", "")))
        if handle:
            return handle
    return None


def _normalize_twitter_handle_from_url(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in {"x.com", "twitter.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 1:
        return None
    handle = parts[0].strip().lstrip("@")
    if not handle or handle.lower() in INVALID_TWITTER_HANDLES:
        return None
    if not (1 <= len(handle) <= 15):
        return None
    if not all(ch.isalnum() or ch == "_" for ch in handle):
        return None
    return f"@{handle}"


def _twitter_profile_url(handle: str) -> str:
    normalized = handle.strip().lstrip("@")
    return f"https://x.com/{normalized}"


def _select_company_domain(results: list[dict[str, Any]]) -> str | None:
    for result in results:
        domain = normalize_company_domain(str(result.get("url", "")))
        if domain and not _is_excluded_company_domain(domain):
            return domain
    return None


def _is_excluded_company_domain(domain: str) -> bool:
    normalized = normalize_company_domain(domain)
    return any(normalized == excluded or normalized.endswith(f".{excluded}") for excluded in EXCLUDED_COMPANY_DOMAIN_SUFFIXES)
