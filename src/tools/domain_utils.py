from __future__ import annotations

from urllib.parse import urlparse


def normalize_company_domain(value: str | None) -> str:
    if not value:
        return ""
    raw = value.strip()
    if not raw:
        return ""

    if "://" not in raw and not raw.startswith("//"):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    host = parsed.netloc or parsed.path.split("/")[0]
    host = host.split("@")[-1].split(":")[0].strip().lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host or "." not in host or any(ch.isspace() for ch in host):
        return ""
    return host


def https_url_for_domain(domain: str | None) -> str | None:
    normalized = normalize_company_domain(domain)
    return f"https://{normalized}" if normalized else None
