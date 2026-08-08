#!/usr/bin/env python3
"""Detect likely JP/PT content mismatches in paired entries."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text  # noqa: E402
from paragraph_glossary import align_paragraphs  # noqa: E402

OUTPUT = PROJECT_ROOT / "reports" / "translation_review" / "pair_mismatch_audit.json"


def body_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith(("Title:", "Publication source:", "Original publication", "Date:", "Language:", "Collection ID:", "Original path:")):
            continue
        if line.strip():
            lines.append(line.strip())
    return "\n".join(lines)


def first_body_paragraph(text: str) -> str:
    body = body_text(text)
    parts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not parts:
        return body[:500]
    return parts[0][:500]


def mismatch_score(jp: str, pt: str) -> dict:
    pairs = align_paragraphs(jp, pt)
    if len(pairs) < 2:
        return {"flag": "few_paragraphs", "ratio": 1.0}
    jp_body = first_body_paragraph(jp)
    pt_body = first_body_paragraph(pt)
    jp_para1 = pairs[1].jp if len(pairs) > 1 else jp_body
    pt_para1 = pairs[1].pt if len(pairs) > 1 else pt_body
    len_ratio = len(pt_para1) / max(len(jp_para1), 1)
    jp_chars = set(re.findall(r"[\u3040-\u30ff\u4e00-\u9fff]", jp_para1))
    pt_words = set(re.findall(r"[a-zà-ÿ]{5,}", pt_para1.lower()))
    # Heuristic: very different lengths + no shared romanization hints
    suspicious = len_ratio < 0.3 or len_ratio > 3.5
    if pairs[1].jp and pairs[1].pt:
        jp_head = pairs[1].jp.splitlines()[0][:40]
        pt_head = pairs[1].pt.splitlines()[0][:40]
        title_mismatch = jp_head and pt_head and jp_head not in pt and pt_head not in jp
    else:
        title_mismatch = False
    return {
        "len_ratio": round(len_ratio, 2),
        "title_mismatch": title_mismatch,
        "flag": "suspect" if suspicious or title_mismatch else "ok",
        "jp_preview": jp_para1[:120],
        "pt_preview": pt_para1[:120],
    }


def main() -> int:
    pairs = pair_entries(load_entries())
    suspects = []
    for pair in pairs:
        try:
            jp = read_entry_text(pair.jp)
            pt = permanent_pt_path(pair.pt).read_text(encoding="utf-8")
            score = mismatch_score(jp, pt)
            if score["flag"] == "suspect":
                suspects.append(
                    {
                        "pt_path": str(permanent_pt_path(pair.pt).relative_to(PROJECT_ROOT)),
                        "title": pair.pt.get("title"),
                        **score,
                    }
                )
        except Exception:
            continue
    summary = {
        "texts": len(pairs),
        "suspects": len(suspects),
        "suspect_rate_pct": round(len(suspects) / len(pairs) * 100, 1) if pairs else 0,
        "samples": suspects[:30],
    }
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "samples"}, ensure_ascii=False))
    print(f"report={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
