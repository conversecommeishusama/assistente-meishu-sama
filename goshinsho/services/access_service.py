import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACCESS_LOG_PATH = PROJECT_ROOT / "logs" / "access_devices.jsonl"


def _hash(value):
    return hashlib.sha256((value or "unknown").encode("utf-8")).hexdigest()[:16]


def device_fingerprint(ip, user_agent):
    return _hash(f"{ip}|{user_agent}")


def record_access(ip, user_agent, user=None, path="/"):
    ACCESS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip_hash": _hash(ip),
        "user_agent_hash": _hash(user_agent),
        "device_hash": _hash(f"{ip}|{user_agent}"),
        "path": path,
        "user_email": (user or {}).get("email"),
    }
    with ACCESS_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _parse_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def summarize_access(limit=20000, since=None, until=None):
    if not ACCESS_LOG_PATH.exists():
        return {"entries": 0, "unique_ips": 0, "unique_devices": 0, "recent": []}

    lines = ACCESS_LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
    entries = []
    for line in lines:
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _parse_timestamp(raw.get("timestamp"))
        if since is not None and (ts is None or ts < since):
            continue
        if until is not None and (ts is None or ts > until):
            continue
        entries.append(raw)

    return {
        "entries": len(entries),
        "unique_ips": len({entry.get("ip_hash") for entry in entries if entry.get("ip_hash")}),
        "unique_devices": len({entry.get("device_hash") for entry in entries if entry.get("device_hash")}),
        "recent": entries[-20:],
    }
