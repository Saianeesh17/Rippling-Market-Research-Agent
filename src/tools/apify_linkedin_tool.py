from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import httpx

from src.cache import get_cached_json, set_cached_json
from src.config import utc_now_iso
from src.data.dummy_sources import slugify
from src.schemas import SourceRecord, ToolInput, ToolResult
from src.tools.base import BaseSourceTool


APIFY_BASE_URL = "https://api.apify.com/v2"
LINKEDIN_COMPANY_POSTS_ACTOR_PATH = (
    "/acts/automation-lab~linkedin-company-posts-scraper/run-sync-get-dataset-items"
)
MAX_LINKEDIN_POSTS_PER_TEST_RUN = 5


class ApifyLinkedInCompanyPostsTool(BaseSourceTool):
    name = "ApifyLinkedInCompanyPostsTool"
    description = "Real Apify actor adapter for public LinkedIn company posts."
    source_category = "social"
    reliability_weight = 0.78
    requires_api_key = True
    allowed_agents = ["social"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        token = os.getenv("APIFY_TOKEN", "").strip()
        if not token:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="APIFY_TOKEN is not set; skipping real LinkedIn company posts scraper.",
            )

        company_input = self._company_input(tool_input)
        if not company_input:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="No LinkedIn company URL was resolved; run ExaLinkedInCompanySearchTool before Apify.",
            )
        max_posts = min(
            MAX_LINKEDIN_POSTS_PER_TEST_RUN,
            _env_int("APIFY_LINKEDIN_MAX_POSTS_PER_COMPANY", default=MAX_LINKEDIN_POSTS_PER_TEST_RUN),
        )
        payload = {
            "companyUrls": [company_input],
            "maxPostsPerCompany": max_posts,
            "maxCompanies": 1,
        }
        cache_key = self._cache_key(company_input, max_posts)
        ttl_hours = _env_int("APIFY_LINKEDIN_CACHE_TTL_HOURS", default=5)
        cached = get_cached_json("apify_linkedin_posts", cache_key, ttl_seconds=max(0, ttl_hours) * 60 * 60)
        if cached and isinstance(cached.get("items"), list):
            return self._result_from_items(
                tool_input,
                company_input,
                max_posts,
                payload,
                list(cached["items"]),
                cache_hit=True,
                ttl_hours=ttl_hours,
            )

        try:
            items = self._fetch_items(token, payload)
        except Exception as exc:
            return ToolResult(tool_name=self.name, success=False, error=str(exc))

        set_cached_json("apify_linkedin_posts", cache_key, {"items": items})
        return self._result_from_items(
            tool_input,
            company_input,
            max_posts,
            payload,
            items,
            cache_hit=False,
            ttl_hours=ttl_hours,
        )

    def _result_from_items(
        self,
        tool_input: ToolInput,
        company_input: str,
        max_posts: int,
        payload: dict[str, Any],
        items: list[dict[str, Any]],
        *,
        cache_hit: bool,
        ttl_hours: int,
    ) -> ToolResult:
        sources = [
            self._source_from_item(tool_input, item, index)
            for index, item in enumerate(items[:MAX_LINKEDIN_POSTS_PER_TEST_RUN], start=1)
        ]
        sources = [source for source in sources if source is not None]
        logged_items = items[:MAX_LINKEDIN_POSTS_PER_TEST_RUN]
        return ToolResult(
            tool_name=self.name,
            success=True,
            sources=sources,
            metadata={
                "company_input": company_input,
                "maxPostsPerCompany": max_posts,
                "cache": {
                    "hit": cache_hit,
                    "namespace": "apify_linkedin_posts",
                    "ttl_hours": ttl_hours,
                },
                "api_request": {
                    "method": "POST",
                    "url": f"{APIFY_BASE_URL}{LINKEDIN_COMPANY_POSTS_ACTOR_PATH}",
                    "query_params": {"token": "<redacted>"},
                    "json": payload,
                    "cache_hit": cache_hit,
                },
                "api_response": {
                    "cache_hit": cache_hit,
                    "dataset_items_returned": len(items),
                    "logged_items": logged_items,
                },
            },
        )

    def _fetch_items(self, token: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{APIFY_BASE_URL}{LINKEDIN_COMPANY_POSTS_ACTOR_PATH}"
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, params={"token": token}, json=payload)
            response.raise_for_status()
            data = response.json()
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            items = data.get("items") or data.get("data") or []
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return []

    def _company_input(self, tool_input: ToolInput) -> str:
        if tool_input.linkedin_company_url:
            return tool_input.linkedin_company_url
        if "linkedin.com/company/" in tool_input.competitor_name.lower():
            return tool_input.competitor_name.strip()
        return ""

    def _cache_key(self, company_input: str, max_posts: int) -> str:
        return f"{company_input}|max_posts={max_posts}|actor={LINKEDIN_COMPANY_POSTS_ACTOR_PATH}"

    def _source_from_item(self, tool_input: ToolInput, item: dict[str, Any], index: int) -> SourceRecord | None:
        headline = _first_string(item, ["headline", "title", "postTitle"])
        body = _first_string(
            item,
            [
                "text",
                "postText",
                "body",
                "postBody",
                "fullPostBody",
                "content",
                "description",
            ],
        )
        if not headline and not body:
            body = json.dumps(item, ensure_ascii=True)[:1500]
        if not body:
            return None

        post_url = _first_string(item, ["url", "postUrl", "postURL", "link", "postLink"])
        author = _author_name(item)
        published_at = _first_string(item, ["date", "postedAt", "publishedAt", "postDate", "createdAt"])
        like_count = item.get("likeCount") or item.get("likes") or item.get("numLikes")
        source_hash = hashlib.sha1(f"{post_url or body[:80]}-{index}".encode("utf-8")).hexdigest()[:10]
        title = headline or f"LinkedIn company post {index}"
        content_parts = []
        if headline:
            content_parts.append(f"Headline: {headline}")
        content_parts.append(f"Body: {body}")
        if author:
            content_parts.append(f"Author: {author}")
        if like_count is not None:
            content_parts.append(f"Likes: {like_count}")

        return SourceRecord(
            source_id=f"apify_linkedin_{slugify(tool_input.competitor_name)}_{source_hash}",
            competitor_name=tool_input.competitor_name,
            source_type="social",
            title=title[:140],
            url=post_url or None,
            content="\n".join(content_parts),
            publisher=author or "LinkedIn",
            is_official=True,
            is_third_party=False,
            is_public=True,
            published_at=published_at or None,
            discovered_at=utc_now_iso(),
            discovery_tool=self.name,
            reliability_weight=self.reliability_weight,
            relevance_score=0.5,
            confidence_modifier=0.82,
            notes="Real public LinkedIn company post scraped through Apify actor; limited to 5 posts per run for testing.",
        )


def _first_string(item: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _author_name(item: dict[str, Any]) -> str:
    author = item.get("author")
    if isinstance(author, str):
        return author.strip()
    if isinstance(author, dict):
        return _first_string(author, ["name", "title", "companyName"])
    return _first_string(item, ["authorName", "companyName", "pageName"])


def _env_int(name: str, *, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default
