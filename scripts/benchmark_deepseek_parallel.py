#!/usr/bin/env python3
"""Benchmark DeepSeek API sob carga paralela (simula 2 runners de tradução).

Não altera o run de tradução em massa — só mede latência, erros e rate limits.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from retranslate_core import MODEL, MAX_OUTPUT_TOKENS, split_jp_chunks  # noqa: E402
from run_deepseek_revision_pilot import load_env_api_key, load_glossary, select_glossary_entries, format_glossary_block  # noqa: E402
from translation_protocol_core import (  # noqa: E402
    PROTOCOL_PATH,
    build_review_prompt,
    build_translate_prompt,
    strip_metadata,
)

DEFAULT_OUT = PROJECT_ROOT / "reports" / "translation_review" / "benchmark_parallel_api"
SAMPLE_JP = PROJECT_ROOT / "textos_japones" / "19500921-地上天国出来るまで.txt"


@dataclass
class CallResult:
    stream: str
    call_type: str
    ok: bool
    latency_s: float
    status_code: int | None = None
    error: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    response_chars: int = 0
    rate_limit_headers: dict = field(default_factory=dict)


def _extract_rate_headers(resp: requests.Response) -> dict:
    keys = (
        "x-ratelimit-limit-requests",
        "x-ratelimit-remaining-requests",
        "x-ratelimit-reset-requests",
        "retry-after",
    )
    out = {}
    for k in keys:
        v = resp.headers.get(k) or resp.headers.get(k.title())
        if v:
            out[k] = v
    return out


def api_call(
    api_key: str,
    prompt: str,
    *,
    stream: str,
    call_type: str,
    max_tokens: int = MAX_OUTPUT_TOKENS,
    timeout: int = 600,
) -> CallResult:
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    t0 = time.perf_counter()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        latency = time.perf_counter() - t0
        rl = _extract_rate_headers(resp)
        if resp.status_code != 200:
            return CallResult(
                stream=stream,
                call_type=call_type,
                ok=False,
                latency_s=latency,
                status_code=resp.status_code,
                error=resp.text[:500],
                rate_limit_headers=rl,
            )
        data = resp.json()
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        return CallResult(
            stream=stream,
            call_type=call_type,
            ok=True,
            latency_s=latency,
            status_code=200,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            response_chars=len(content),
            rate_limit_headers=rl,
        )
    except requests.exceptions.Timeout:
        return CallResult(
            stream=stream,
            call_type=call_type,
            ok=False,
            latency_s=time.perf_counter() - t0,
            error="timeout",
        )
    except Exception as exc:
        return CallResult(
            stream=stream,
            call_type=call_type,
            ok=False,
            latency_s=time.perf_counter() - t0,
            error=str(exc)[:500],
        )


def load_sample_prompts() -> tuple[str, str, str]:
    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()
    jp_raw = SAMPLE_JP.read_text(encoding="utf-8")
    jp_body = strip_metadata(jp_raw)
    chunks = split_jp_chunks(jp_body)
    chunk = chunks[0]
    title = jp_body.split("\n", 1)[0][:80]
    gloss = format_glossary_block(select_glossary_entries(chunk, "", glossary))
    translate_prompt = build_translate_prompt(protocol, gloss, chunk, part=1, total_parts=len(chunks), title=title)
    # review: 4 short paragraph pairs
    jp_para = chunk[:3500]
    pt_stub = "Parágrafo de teste em português para benchmark de revisão.\n\n" * 4
    review_prompt = build_review_prompt(
        [{"index": i, "jp": jp_para[:800], "pt": pt_stub} for i in range(4)],
        protocol,
        gloss,
    )
    return translate_prompt, review_prompt, f"translate={len(translate_prompt)} review={len(review_prompt)}"


def run_stream(
    api_key: str,
    stream_id: str,
    translate_prompt: str,
    review_prompt: str,
    rounds: int,
    results: list[CallResult],
    lock: Lock,
) -> None:
    """Um runner: alterna tradução e revisão (como run_two_pass)."""
    for i in range(rounds):
        for call_type, prompt in (("translate", translate_prompt), ("review", review_prompt)):
            r = api_call(api_key, prompt, stream=stream_id, call_type=call_type)
            with lock:
                results.append(r)
            if not r.ok:
                return
            time.sleep(0.3)


def summarize(results: list[CallResult]) -> dict:
    ok = [r for r in results if r.ok]
    fail = [r for r in results if not r.ok]
    latencies = [r.latency_s for r in ok]
    latencies.sort()
    by_type: dict[str, list[float]] = {}
    for r in ok:
        by_type.setdefault(r.call_type, []).append(r.latency_s)
    status_codes = {}
    for r in fail:
        key = str(r.status_code or r.error or "unknown")[:40]
        status_codes[key] = status_codes.get(key, 0) + 1
    return {
        "total_calls": len(results),
        "ok": len(ok),
        "fail": len(fail),
        "success_rate": round(len(ok) / len(results), 3) if results else 0,
        "latency_s": {
            "min": round(min(latencies), 2) if latencies else None,
            "median": round(latencies[len(latencies) // 2], 2) if latencies else None,
            "p95": round(latencies[int(len(latencies) * 0.95)], 2) if latencies else None,
            "max": round(max(latencies), 2) if latencies else None,
        },
        "latency_by_type": {
            k: round(sum(v) / len(v), 2) for k, v in by_type.items()
        },
        "tokens": {
            "prompt": sum(r.prompt_tokens for r in ok),
            "completion": sum(r.completion_tokens for r in ok),
        },
        "errors": status_codes,
        "rate_limit_headers_sample": next(
            (r.rate_limit_headers for r in results if r.rate_limit_headers),
            {},
        ),
    }


def run_phase(
    name: str,
    api_key: str,
    translate_prompt: str,
    review_prompt: str,
    *,
    workers: int,
    rounds: int,
) -> dict:
    results: list[CallResult] = []
    lock = Lock()
    t0 = time.perf_counter()
    if workers == 1:
        run_stream(api_key, "A", translate_prompt, review_prompt, rounds, results, lock)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [
                pool.submit(
                    run_stream,
                    api_key,
                    chr(ord("A") + i),
                    translate_prompt,
                    review_prompt,
                    rounds,
                    results,
                    lock,
                )
                for i in range(workers)
            ]
            for f in as_completed(futs):
                f.result()
    elapsed = time.perf_counter() - t0
    summary = summarize(results)
    summary["phase"] = name
    summary["workers"] = workers
    summary["rounds_per_worker"] = rounds
    summary["elapsed_s"] = round(elapsed, 1)
    summary["max_concurrent"] = workers
    return summary


def verdict(sequential: dict, parallel2: dict, stress4: dict | None) -> dict:
    issues = []
    rec = "ok_for_two_runners"

    if parallel2["fail"] > 0:
        issues.append(f"parallel_2_failures={parallel2['fail']}")
        rec = "not_recommended"
    if parallel2.get("errors", {}).get("429") or any("429" in str(k) for k in parallel2.get("errors", {})):
        issues.append("rate_limit_429")
        rec = "not_recommended"
    if any("timeout" in str(k).lower() for k in parallel2.get("errors", {})):
        issues.append("timeouts")
        rec = "caution"

    seq_med = (sequential.get("latency_s") or {}).get("median")
    par_med = (parallel2.get("latency_s") or {}).get("median")
    slowdown = None
    if seq_med and par_med and seq_med > 0:
        slowdown = round(par_med / seq_med, 2)
        if slowdown > 2.0:
            issues.append(f"latency_slowdown_x{slowdown}")
            if rec == "ok_for_two_runners":
                rec = "caution"

    if stress4 and stress4["fail"] > 0:
        issues.append(f"stress_4_failures={stress4['fail']}")

    messages = {
        "ok_for_two_runners": "API aguenta 2 runners — sem erros; latência aceitável.",
        "caution": "Possível degradação (latência ou timeouts) — piloto com 2 runners antes de escalar.",
        "not_recommended": "Erros sob carga paralela — manter 1 runner ou reduzir concorrência.",
    }
    return {
        "recommendation": rec,
        "message": messages[rec],
        "issues": issues,
        "latency_slowdown_parallel_vs_sequential": slowdown,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Benchmark API DeepSeek com carga paralela")
    p.add_argument("--rounds", type=int, default=2, help="Rondas translate+review por worker")
    p.add_argument("--skip-stress", action="store_true", help="Não correr fase com 4 workers")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    api_key = load_env_api_key()
    translate_prompt, review_prompt, sizes = load_sample_prompts()
    print(f"Amostra: {SAMPLE_JP.name} | {sizes}")

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "sample_jp": str(SAMPLE_JP.relative_to(PROJECT_ROOT)),
        "rounds_per_worker": args.rounds,
        "phases": [],
    }

    print("\n=== Fase 1: sequencial (baseline) ===")
    s1 = run_phase("sequential_1_worker", api_key, translate_prompt, review_prompt, workers=1, rounds=args.rounds)
    report["phases"].append(s1)
    print(json.dumps({k: s1[k] for k in ("ok", "fail", "latency_s", "elapsed_s", "errors")}, indent=2))

    print("\n=== Fase 2: 2 workers (simula 2 runners) ===")
    s2 = run_phase("parallel_2_workers", api_key, translate_prompt, review_prompt, workers=2, rounds=args.rounds)
    report["phases"].append(s2)
    print(json.dumps({k: s2[k] for k in ("ok", "fail", "latency_s", "elapsed_s", "errors")}, indent=2))

    s4 = None
    if not args.skip_stress:
        print("\n=== Fase 3: 4 workers (stress) ===")
        s4 = run_phase("stress_4_workers", api_key, translate_prompt, review_prompt, workers=4, rounds=1)
        report["phases"].append(s4)
        print(json.dumps({k: s4[k] for k in ("ok", "fail", "latency_s", "elapsed_s", "errors")}, indent=2))

    report["verdict"] = verdict(s1, s2, s4)
    print("\n=== Veredito ===")
    print(json.dumps(report["verdict"], ensure_ascii=False, indent=2))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"benchmark_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nRelatório: {out.relative_to(PROJECT_ROOT)}")
    return 0 if report["verdict"]["recommendation"] != "not_recommended" else 1


if __name__ == "__main__":
    raise SystemExit(main())
