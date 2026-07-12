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
X_TWITTER_POSTS_SEARCH_ACTOR_PATH = "/acts/simpleapi~x-twitter-posts-search/run-sync-get-dataset-items"
MAX_X_TWITTER_POSTS_PER_TEST_RUN = 5


class ApifyXTwitterPostsSearchTool(BaseSourceTool):
    name = "ApifyXTwitterPostsSearchTool"
    description = "Real Apify actor adapter for public Twitter/X posts search by handle."
    source_category = "social"
    reliability_weight = 0.74
    requires_api_key = True
    allowed_agents = ["social"]
    required_context_fields = ["twitter_handle"]

    def run(self, tool_input: ToolInput) -> ToolResult:
        token = os.getenv("APIFY_TOKEN", "").strip()
        if not token:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="APIFY_TOKEN is not set; skipping real Twitter/X posts scraper.",
            )

        handle = _normalize_handle(tool_input.twitter_handle)
        if not handle:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="No Twitter/X handle was resolved; run ExaTwitterHandleSearchTool before Apify.",
            )

        max_posts = min(
            MAX_X_TWITTER_POSTS_PER_TEST_RUN,
            _env_int("APIFY_X_TWITTER_MAX_POSTS", default=MAX_X_TWITTER_POSTS_PER_TEST_RUN),
        )
        payload = {
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
            "startUrls": [handle],
        }
        cache_key = self._cache_key(handle, max_posts)
        ttl_hours = _env_int("APIFY_X_TWITTER_CACHE_TTL_HOURS", default=5)
        cached = get_cached_json("apify_x_twitter_posts", cache_key, ttl_seconds=max(0, ttl_hours) * 60 * 60)
        if cached and isinstance(cached.get("items"), list):
            return self._result_from_items(
                tool_input,
                handle,
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

        set_cached_json("apify_x_twitter_posts", cache_key, {"items": items})
        return self._result_from_items(
            tool_input,
            handle,
            max_posts,
            payload,
            items,
            cache_hit=False,
            ttl_hours=ttl_hours,
        )

    def _result_from_items(
        self,
        tool_input: ToolInput,
        handle: str,
        max_posts: int,
        payload: dict[str, Any],
        items: list[dict[str, Any]],
        *,
        cache_hit: bool,
        ttl_hours: int,
    ) -> ToolResult:
        sources = [
            self._source_from_item(tool_input, handle, item, index)
            for index, item in enumerate(items[:max_posts], start=1)
        ]
        sources = [source for source in sources if source is not None]
        logged_items = items[:max_posts]
        return ToolResult(
            tool_name=self.name,
            success=True,
            sources=sources,
            metadata={
                "twitter_handle": handle,
                "maxPosts": max_posts,
                "cache": {
                    "hit": cache_hit,
                    "namespace": "apify_x_twitter_posts",
                    "ttl_hours": ttl_hours,
                },
                "api_request": {
                    "method": "POST",
                    "url": f"{APIFY_BASE_URL}{X_TWITTER_POSTS_SEARCH_ACTOR_PATH}",
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
        url = f"{APIFY_BASE_URL}{X_TWITTER_POSTS_SEARCH_ACTOR_PATH}"
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, params={"token": token}, json=payload)
            response.raise_for_status()
            data = response.json()
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            items = data.get("items") or data.get("data") or data.get("tweets") or []
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return []

    def _cache_key(self, handle: str, max_posts: int) -> str:
        return f"{handle.lower()}|max_posts={max_posts}|actor={X_TWITTER_POSTS_SEARCH_ACTOR_PATH}"

    def _source_from_item(self, tool_input: ToolInput, handle: str, item: dict[str, Any], index: int) -> SourceRecord | None:
        text = _first_string(
            item,
            [
                "text",
                "full_text",
                "fullText",
                "tweetText",
                "content",
                "body",
                "description",
            ],
        )
        if not text:
            text = json.dumps(item, ensure_ascii=True)[:1500]
        if not text:
            return None

        post_url = _first_string(item, ["url", "tweetUrl", "twitterUrl", "postUrl", "link"])
        published_at = _first_string(item, ["createdAt", "created_at", "date", "publishedAt", "timestamp"])
        author = _author_name(item) or handle
        likes = item.get("likeCount") or item.get("likes") or item.get("favorite_count")
        reposts = item.get("retweetCount") or item.get("retweets") or item.get("replyCount")
        source_hash = hashlib.sha1(f"{post_url or text[:80]}-{index}".encode("utf-8")).hexdigest()[:10]

        content_parts = [
            f"Post: {text}",
            f"Author: {author}",
        ]
        if likes is not None:
            content_parts.append(f"Likes: {likes}")
        if reposts is not None:
            content_parts.append(f"Reposts or replies: {reposts}")

        return SourceRecord(
            source_id=f"apify_x_twitter_{slugify(tool_input.competitor_name)}_{source_hash}",
            competitor_name=tool_input.competitor_name,
            source_type="social",
            title=f"Twitter/X post {index}",
            url=post_url or None,
            content="\n".join(content_parts),
            publisher=author,
            is_official=True,
            is_third_party=False,
            is_public=True,
            published_at=published_at or None,
            discovered_at=utc_now_iso(),
            discovery_tool=self.name,
            reliability_weight=self.reliability_weight,
            relevance_score=0.5,
            confidence_modifier=0.78,
            notes="Real public Twitter/X post scraped through Apify actor; limited to 5 posts per run for testing.",
        )


def _normalize_handle(value: str | None) -> str:
    if not value:
        return ""
    handle = value.strip().lstrip("@")
    if not handle:
        return ""
    return f"@{handle}"


def _first_string(item: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _author_name(item: dict[str, Any]) -> str:
    author = item.get("author") or item.get("user")
    if isinstance(author, str):
        return author.strip()
    if isinstance(author, dict):
        return _first_string(author, ["name", "username", "screenName", "handle"])
    return _first_string(item, ["authorName", "username", "screenName", "handle"])


def _env_int(name: str, *, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default
