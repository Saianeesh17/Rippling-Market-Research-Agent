from __future__ import annotations

from datetime import datetime, timezone

SOURCE_CATEGORIES = [
    "website_positioning",
    "product_pages",
    "pricing",
    "paid_ads",
    "social",
    "press_news",
    "comparison_pages",
]

PUBLIC_SOURCE_RULE = "Only public-source-style dummy data is allowed in this prototype."


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

