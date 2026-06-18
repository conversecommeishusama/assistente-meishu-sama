import contextvars
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from flask import has_request_context, request


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = PROJECT_ROOT / "logs" / "deepseek_usage.jsonl"
_USAGE_CONTEXT = contextvars.ContextVar("deepseek_usage_context", default={})


def set_deepseek_usage_context(**context):
    current = dict(_USAGE_CONTEXT.get() or {})
    current.update({key: value for key, value in context.items() if value is not None})
    return _USAGE_CONTEXT.set(current)


def reset_deepseek_usage_context(token):
    _USAGE_CONTEXT.reset(token)


def _usage_to_dict(response):
    usage = getattr(response, "usage", None)
    if not usage:
        return {}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def record_deepseek_usage(response, purpose, model="deepseek-chat"):
    usage = _usage_to_dict(response)
    if not usage:
        return

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "purpose": purpose,
        **usage,
        **(_USAGE_CONTEXT.get() or {}),
    }
    if has_request_context():
        entry.update({"endpoint": request.endpoint, "path": request.path, "method": request.method})

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def summarize_deepseek_usage(limit=5000):
    if not LOG_PATH.exists():
        return {"entries": 0, "total_tokens": 0, "by_user": [], "by_purpose": [], "recent": [], "cost": {}}

    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    def grouped(field):
        totals = defaultdict(lambda: {"calls": 0, "total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0})
        for entry in entries:
            key = entry.get(field) or "unknown"
            totals[key]["calls"] += 1
            totals[key]["total_tokens"] += int(entry.get("total_tokens") or 0)
            totals[key]["prompt_tokens"] += int(entry.get("prompt_tokens") or 0)
            totals[key]["completion_tokens"] += int(entry.get("completion_tokens") or 0)
        return [{"name": key, **value} for key, value in sorted(totals.items(), key=lambda item: item[1]["total_tokens"], reverse=True)]

    prompt_tokens = sum(int(entry.get("prompt_tokens") or 0) for entry in entries)
    completion_tokens = sum(int(entry.get("completion_tokens") or 0) for entry in entries)
    answer_count = sum(1 for entry in entries if entry.get("purpose") == "answer_generation") or 1
    input_usd = prompt_tokens * 0.14 / 1_000_000
    output_usd = completion_tokens * 0.28 / 1_000_000
    total_usd = input_usd + output_usd

    return {
        "entries": len(entries),
        "total_tokens": prompt_tokens + completion_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "by_user": grouped("user_email")[:20],
        "by_purpose": grouped("purpose")[:20],
        "recent": entries[-25:],
        "cost": {
            "input_usd": input_usd,
            "output_usd": output_usd,
            "total_usd": total_usd,
            "per_answer_usd": total_usd / answer_count,
            "per_answer_brl": (total_usd / answer_count) * 5.4,
            "answer_count": answer_count,
        },
    }
