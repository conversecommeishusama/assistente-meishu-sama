#!/usr/bin/env python3
"""Batch deduplication for livros_trabalho/pt retranslate duplicate-then-retranslate bug."""
from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PT_DIR = ROOT / "reports/livros_trabalho/pt"
SPEC_DIR = ROOT / "reports/livros_trabalho/segmentacao_manual"
BACKUP_DIR = SPEC_DIR / "pt_backup_pre_prose_restore"

DONE = {
    "19521201-結核信仰療法.txt",
    "19530101-アメリカを救う.txt",
    "19511225-御垂示録5号.txt",
    "19530505-革命的増産の自然農法解説.txt",
    "19510225-御教え集6号.txt",
    "19530315-御教え集19号.txt",
}
SKIP = {"19491130-自観叢書第8篇『明麿近詠集』.txt"}


def find_near_duplicates(text: str, window: int = 3000, ngram_words: int = 15) -> list[tuple[int, int, str]]:
    words = re.findall(r"\S+", text)
    offsets: list[int] = []
    idx = 0
    for w in words:
        idx = text.find(w, idx)
        offsets.append(idx)
        idx += len(w)
    seen: dict[str, int] = {}
    hits: list[tuple[int, int, str]] = []
    for i in range(len(words) - ngram_words):
        gram = " ".join(words[i : i + ngram_words])
        key = gram.lower()
        if key in seen:
            prev_i = seen[key]
            gap = offsets[i] - offsets[prev_i]
            if 0 < gap < window and offsets[prev_i] > 1500:
                hits.append((offsets[prev_i], offsets[i], gram))
        seen[key] = i
    return hits


def cluster_events(hits: list[tuple[int, int, str]], merge_gap: int = 200) -> list[list]:
    events: list[list] = []
    last_a = -9999
    for a, b, g in sorted(hits):
        if a - last_a > merge_gap:
            events.append([a, b, g])
        else:
            events[-1][1] = max(events[-1][1], b)
        last_a = a
    return events


def is_false_positive_gram(gram: str) -> bool:
    g = gram.lower()
    if "#k" in g or "shinkō zatsuwa" in g or "shinko zatsuwa" in g:
        return True
    if "cultivo natural | cultivo com fertilizantes" in g:
        return True
    if g.count("|") >= 3:
        return True
    # repeated biblical fragments used in exposition (keep both)
    if "perca um dos teus membros" in g and "inferno" in g:
        return True
    return False


def word_sim(a: str, b: str) -> float:
    wa = re.findall(r"\S+", a.lower())
    wb = re.findall(r"\S+", b.lower())
    return SequenceMatcher(None, wa, wb, autojunk=False).ratio()


def ends_sentence(s: str) -> bool:
    s = s.rstrip()
    if not s:
        return False
    if s.endswith("..."):
        return True
    return s[-1] in '.!?"»)]'


def resolve_remove_span(text: str, a: int, b: int) -> tuple[int, int] | None:
    """Return [start, end) of redundant first telling to delete."""
    region_start = max(0, a - 700)
    region_end = min(len(text), b + 3200)
    chunk = text[region_start:region_end]
    a_off = a - region_start
    b_off = b - region_start

    # Strategy 1: paragraph-boundary restart
    breaks = [m.start() for m in re.finditer(r"\n\n+", chunk)]
    best: tuple[int, int, float] | None = None
    for pb in breaks:
        if pb < a_off - 100 or pb > b_off + 500:
            continue
        prev_breaks = [p for p in breaks if p < pb - 60]
        start_off = prev_breaks[-1] if prev_breaks else max(0, pb - 2400)
        if start_off < a_off - 800:
            start_off = max(0, a_off - 350)
        first = chunk[start_off:pb].strip()
        second = chunk[pb : pb + 2400].strip()
        if len(first) < 100 or len(second) < 100:
            continue
        sim = word_sim(first[-700:], second[:700])
        if sim < 0.38:
            continue
        truncated = not ends_sentence(first)
        score = sim + (0.2 if truncated else 0) + min(len(first), len(second)) / 20000
        cand = (region_start + start_off, region_start + pb, score)
        if best is None or cand[2] > best[2]:
            best = cand
    if best:
        return best[0], best[1]

    # Strategy 2: align word streams from a and b; drop earlier shorter copy
    seg_a = text[a : a + 2600]
    seg_b = text[b : b + 2600]
    wa = re.findall(r"\S+", seg_a)
    wb = re.findall(r"\S+", seg_b)
    n = min(len(wa), len(wb))
    k = 0
    while k < n and wa[k].lower() == wb[k].lower():
        k += 1
    if k < 16:
        return None

    def word_end(base: int, seg: str, wi: int) -> int:
        cnt = 0
        for m in re.finditer(r"\S+", seg):
            if cnt == wi:
                return base + m.end()
            cnt += 1
        return base + len(seg)

    end_a = word_end(a, seg_a, k - 1)
    end_b = word_end(b, seg_b, k - 1)
    len_a = end_a - a
    len_b = end_b - b
    if len_a <= len_b:
        return a, end_a
    return b, end_b


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    spans = sorted(spans)
    merged: list[tuple[int, int]] = []
    for s, e in spans:
        if merged and s < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def residual_events(text: str) -> int:
    hits = find_near_duplicates(text)
    events = cluster_events(hits)
    return len([e for e in events if not is_false_positive_gram(e[2])])


def process_file(fname: str, dry_run: bool = False) -> dict:
    path = PT_DIR / fname
    text = path.read_text(encoding="utf-8")
    events = [e for e in cluster_events(find_near_duplicates(text)) if not is_false_positive_gram(e[2])]
    if not events:
        return {"file": fname, "status": "clean", "removed": 0, "residual": 0}

    spans: list[tuple[int, int]] = []
    for a, b, _g in events:
        span = resolve_remove_span(text, a, b)
        if span:
            spans.append(span)
    spans = merge_spans(spans)
    if not spans:
        return {"file": fname, "status": "unresolved", "events": len(events), "residual": len(events)}

    if dry_run:
        return {"file": fname, "status": "would_fix", "spans": spans, "events": len(events)}

    backup = BACKUP_DIR / (fname + "_dedupe.bak")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")

    new = text
    for s, e in sorted(spans, reverse=True):
        new = new[:s] + new[e:]
    path.write_text(new, encoding="utf-8")
    return {
        "file": fname,
        "status": "fixed",
        "removed": len(text) - len(new),
        "spans": len(spans),
        "residual": residual_events(new),
        "events": len(events),
    }


def queue_files() -> list[str]:
    out: list[tuple[int, str]] = []
    for spec in SPEC_DIR.glob("*.txt.json"):
        try:
            meta = json.loads(spec.read_text(encoding="utf-8"))
        except Exception:
            continue
        if meta.get("profile") == "gokowa_roku_qa":
            continue
        fname = spec.name[:-5]
        if fname in DONE or fname in SKIP:
            continue
        pt = PT_DIR / fname
        if not pt.is_file():
            continue
        text = pt.read_text(encoding="utf-8", errors="ignore")
        n = residual_events(text)
        if n:
            out.append((n, fname))
    out.sort(key=lambda x: (-x[0], x[1]))
    return [f for _, f in out]


def main() -> int:
    dry = "--dry-run" in sys.argv
    only: set[str] | None = None
    for arg in sys.argv[1:]:
        if arg.endswith(".txt"):
            only = only or set()
            only.add(arg)

    files = queue_files()
    if only:
        files = [f for f in files if f in only]

    results = {"clean": 0, "fixed": 0, "partial": 0, "unresolved": 0, "removed": 0}
    partial: list[tuple] = []
    unresolved: list[tuple] = []

    for fname in files:
        r = process_file(fname, dry_run=dry)
        st = r["status"]
        if st == "fixed":
            if r["residual"] == 0:
                results["fixed"] += 1
                results["removed"] += r["removed"]
                print(f"OK [{fname}]: -{r['removed']} chars, {r['spans']} cortes")
            else:
                results["partial"] += 1
                partial.append((fname, r["residual"], r.get("removed", 0)))
                print(f"PARTIAL [{fname}]: residual={r['residual']} removed={r.get('removed', 0)}")
        elif st == "unresolved":
            results["unresolved"] += 1
            unresolved.append((fname, r.get("events", 0)))
            print(f"FAIL [{fname}]: unresolved ({r.get('events', 0)} eventos)")
        elif st == "would_fix":
            print(f"PLAN [{fname}]: {len(r['spans'])} cortes")

    print("\n--- RESUMO ---")
    for k, v in results.items():
        print(f"{k}: {v}")
    if partial:
        print("partial:", partial[:20])
    if unresolved:
        print("unresolved:", unresolved[:20])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
