from __future__ import annotations

import re


_TEMPLATE_PLACEHOLDER_RE = re.compile(r"\{\{\s*[^{}]+\s*\}\}")


def clean_template_placeholders(text: str) -> str:
    cleaned = _TEMPLATE_PLACEHOLDER_RE.sub("", str(text))
    cleaned = re.sub(r":\s+([-–—])", r" \1", cleaned)
    cleaned = re.sub(r":\s*:", ":", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"(?m)[ \t]+$", "", cleaned)
    return cleaned


def clean_source_title(title: str | None) -> str:
    cleaned = clean_template_placeholders(title or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.rstrip(" :-")
