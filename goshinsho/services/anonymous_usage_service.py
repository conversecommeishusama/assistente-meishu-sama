"""Persistent anonymous trial quota by device (IP + User-Agent), lifetime limit."""

from __future__ import annotations

import fcntl
import json
from datetime import datetime, timezone
from pathlib import Path

from .access_service import device_fingerprint


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUOTA_STORE_PATH = PROJECT_ROOT / "logs" / "anonymous_quota.json"

# One taste per device; registering grants 3 unlimited days + 5/month after.
ANONYMOUS_FREE_QUESTIONS = 1


def _device_used(entry: dict | None) -> int:
    if not entry:
        return 0
    return max(int(entry.get("used") or 0), 0)


def _load_store() -> dict:
    if not QUOTA_STORE_PATH.exists():
        return {}
    try:
        return json.loads(QUOTA_STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _with_store(mutator):
    QUOTA_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not QUOTA_STORE_PATH.exists():
        QUOTA_STORE_PATH.write_text("{}", encoding="utf-8")

    with QUOTA_STORE_PATH.open("r+", encoding="utf-8") as file:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX)
        try:
            file.seek(0)
            raw = file.read()
            store = json.loads(raw) if raw.strip() else {}
            result = mutator(store)
            file.seek(0)
            file.truncate()
            file.write(json.dumps(store, ensure_ascii=False, indent=2))
            file.flush()
            return result
        finally:
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)


def anonymous_quota_status(ip: str, user_agent: str, session_used: int = 0) -> dict:
    device_hash = device_fingerprint(ip, user_agent)

    def read(store):
        used_device = _device_used(store.get(device_hash))
        remaining_device = max(ANONYMOUS_FREE_QUESTIONS - used_device, 0)
        remaining_session = max(ANONYMOUS_FREE_QUESTIONS - int(session_used or 0), 0)
        remaining = min(remaining_device, remaining_session)
        return {
            "device_hash": device_hash,
            "used_device": used_device,
            "used_session": int(session_used or 0),
            "remaining_questions": remaining,
            "limit": ANONYMOUS_FREE_QUESTIONS,
            "limited": remaining <= 0,
            "lifetime_limit": True,
        }

    return _with_store(read)


def consume_anonymous_quota(ip: str, user_agent: str) -> dict:
    now = datetime.now(timezone.utc)
    device_hash = device_fingerprint(ip, user_agent)

    def write(store):
        used_device = _device_used(store.get(device_hash))
        if used_device >= ANONYMOUS_FREE_QUESTIONS:
            return {"remaining_questions": 0, "limited": True}

        used_device += 1
        store[device_hash] = {
            "used": used_device,
            "first_used_at": store.get(device_hash, {}).get("first_used_at") or now.isoformat(),
            "updated_at": now.isoformat(),
        }
        remaining = max(ANONYMOUS_FREE_QUESTIONS - used_device, 0)
        return {"remaining_questions": remaining, "limited": remaining <= 0}

    return _with_store(write)


def summarize_anonymous_usage(limit: int = 5000) -> dict:
    store = _load_store()
    used_once = sum(1 for entry in store.values() if _device_used(entry) >= ANONYMOUS_FREE_QUESTIONS)
    return {
        "devices_tracked": min(len(store), limit),
        "devices_exhausted": used_once,
        "limit_per_device": ANONYMOUS_FREE_QUESTIONS,
        "reset_policy": "lifetime",
    }
