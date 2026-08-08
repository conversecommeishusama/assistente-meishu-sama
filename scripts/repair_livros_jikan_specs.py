#!/usr/bin/env python3
"""Reconstrói specs jikan_hen a partir de marcadores JP （N） e PT correspondentes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402

HEN_LINE_RE = re.compile(r"^（([０-９一二三四五六七八九十百\d]+)）")
PT_FAITH_RE = re.compile(
    r"\((\d{1,2})\)\s*(Fé[^:]{3,60}?)\s*(?:é|:)\s*",
    re.I,
)
PT_ROMAN_RE = re.compile(r"^\(([IVXLC]+)\)\s", re.M)


def _body(path: Path) -> str:
    _, blocks = split_file(path.read_text(encoding="utf-8"))
    return parse_article(blocks[0]).content if blocks else ""


def _kanji_num(token: str) -> int | None:
    token = token.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if token.isdigit():
        return int(token)
    m = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if token in m:
        return m[token]
    if "十" in token:
        left, _, right = token.partition("十")
        tens = m.get(left, 1 if not left else 0)
        ones = m.get(right, 0) if right else 0
        return tens * 10 + ones
    return None


def split_jp_sections(jp: str) -> list[tuple[str, str, str]]:
    """Retorna (num_label, title_line, block) por secção （N）."""
    lines = jp.splitlines()
    idxs: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = HEN_LINE_RE.match(line.strip())
        if m:
            idxs.append((i, m.group(1)))
    if not idxs:
        return []
    out: list[tuple[str, str, str]] = []
    for n, (start, num_tok) in enumerate(idxs):
        end = idxs[n + 1][0] if n + 1 < len(idxs) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        title_line = lines[start].strip()
        out.append((num_tok, title_line, block))
    return out


def find_pt_faith_anchors(pt: str) -> dict[int, str]:
    """Mapeia N -> anchor PT ``(N) Fé ... é:`` (primeira ocorrência expandida)."""
    anchors: dict[int, str] = {}
    for m in PT_FAITH_RE.finditer(pt):
        n = int(m.group(1))
        if n in anchors:
            continue
        # prefer expanded form with " é:" after summary list
        snippet = pt[m.start() : m.end()]
        if " é" in snippet or snippet.rstrip().endswith(":"):
            anchors[n] = pt[m.start() : m.end()].strip()
    return anchors


def find_pt_section_starts(pt: str, n_sections: int) -> list[str]:
    """Roman (I) or proportional fallback markers."""
    starts: list[tuple[int, str]] = []
    for m in PT_ROMAN_RE.finditer(pt):
        starts.append((m.start(), m.group(0).strip()))
    if len(starts) >= n_sections:
        return [a for _, a in sorted(starts)[:n_sections]]
    return []


def rebuild_spec(fn: str, wr: Path, *, dry_run: bool = False) -> dict | None:
    spec_path = wr / "segmentacao_manual" / f"{fn}.json"
    if not spec_path.is_file():
        return None
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("profile") != "jikan_hen":
        return None

    jp = _body(wr / "jp" / fn)
    pt = _body(wr / "pt" / fn)
    sections = split_jp_sections(jp)
    if not sections:
        return {"filename": fn, "skipped": "no_jp_sections"}

    pt_faith = find_pt_faith_anchors(pt)
    articles = []
    for num_tok, title_line, block in sections:
        n = _kanji_num(num_tok)
        jp_anchor = title_line if len(title_line) <= 120 else block.splitlines()[0][:120]
        pt_anchor = ""
        if n and n in pt_faith:
            pt_anchor = pt_faith[n][:120]
        elif n:
            # fallback: search "(N) " expanded
            pat = re.compile(rf"\({n}\)\s+Fé[^.]{{5,50}}?\s+é:\s*", re.I)
            m = pat.search(pt)
            if m:
                pt_anchor = pt[m.start() : m.end()].strip()[:120]
        if not pt_anchor:
            # needle from JP body
            for line in block.splitlines()[1:4]:
                s = line.strip()
                if len(s) >= 15:
                    pos = pt.find(s[:40])
                    if pos >= 0:
                        pt_anchor = pt[pos : pos + 80].splitlines()[0][:120]
                        break
        articles.append(
            {
                "kind": "section",
                "title_jp": f"（{num_tok}）",
                "title_pt": "",
                "jp_anchor": jp_anchor,
                "pt_anchor": pt_anchor,
                "notes": "",
            }
        )

    spec["articles"] = articles
    spec["audited_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    spec["audit_method"] = "jikan_section_rebuild"
    spec["editor_notes"] = (
        "Spec reconstruído por repair_livros_jikan_specs.py — secções （N） JP + anchors PT."
    )

    if not dry_run:
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "filename": fn,
        "sections": len(articles),
        "pt_anchors": sum(1 for a in articles if a["pt_anchor"]),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Rebuild jikan_hen specs")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--file", default="")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    manual = wr / "segmentacao_manual"
    files = [args.file] if args.file else [
        sp.stem.replace(".txt", "") + ".txt" if not sp.stem.endswith(".txt") else sp.stem
        for sp in sorted(manual.glob("*自観叢書*.json"))
    ]

    results = []
    for fn in files:
        if not fn.endswith(".txt"):
            fn += ".txt"
        r = rebuild_spec(fn, wr, dry_run=args.dry_run)
        if r:
            results.append(r)
            print(r)

    print(f"rebuilt={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
