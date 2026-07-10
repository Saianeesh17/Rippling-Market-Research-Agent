from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


DEFAULT_CACHE_DIR = ".agent_cache"


def get_cached_json(namespace: str, key: str, *, ttl_seconds: int | None = None) -> dict[str, Any] | None:
    path = cache_path(namespace, key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    saved_at = payload.get("saved_at_epoch")
    if ttl_seconds is not None:
        if not isinstance(saved_at, (int, float)):
            return None
        if time.time() - float(saved_at) > ttl_seconds:
            return None
    data = payload.get("data")
    return data if isinstance(data, dict) else None


def set_cached_json(namespace: str, key: str, data: dict[str, Any]) -> Path:
    path = cache_path(namespace, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at_epoch": time.time(),
        "data": data,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, default=str), encoding="utf-8")
    return path


def cache_path(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    safe_namespace = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in namespace)
    return cache_dir() / safe_namespace / f"{digest}.json"


def cache_dir() -> Path:
    return Path(os.getenv("AGENT_CACHE_DIR", DEFAULT_CACHE_DIR))
