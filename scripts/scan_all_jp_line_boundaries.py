#!/usr/bin/env python3
"""Varredura linha-a-linha de TODOS os livros JP — detecta fronteiras reais."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402

# --- Marcadores linha-a-linha (JP only) ---

RE_GOKOWA_FULL_DATE = re.compile(
    r"^昭和(?:元|[一二三四五六七八九十百\d]+)年[一二三四五六七八九十百\d]+月[一二三四五六七八九十百\d]+日\s*$"
)
RE_GOKOWA_MD = re.compile(
    r"^[一二三四五六七八九十百\d]+月[一二三四五六七八九十百\d]+日(?:（[^）]*）)?(?:〔[^〕]*〕)?\s*$"
)
RE_OCHISHIJI_BRACKET = re.compile(r"^［[^］]+］\s*$")
RE_OCHISHIJI_BRACKET_HALF = re.compile(r"^［[一二三四五六七八九十百\d]+月[一二三四五六七八九十百\d]+日］")
RE_KOZA_LECTURE = re.compile(r"^[\s　]*第[一二三四五六七八九十百\d]+講座")
RE_HEN_PAREN = re.compile(r"^（[一二三四五六七八九十百\d]+）")
RE_NUMBERED_CSV = re.compile(r"^(\d+)\s*,")
RE_SHINKO_DIV = re.compile(r"─{8,}")
RE_SHINKO_PAGE = re.compile(r"^[～~]\s*\d+\s*$")
RE_BRACKET_TITLE = re.compile(r"^〔[^〕]+〕\s*$")
RE_BRACKET_SECTION = re.compile(r"^【[^】]+】\s*$")
RE_CHAPTER = re.compile(r"^第[一二三四五六七八九十百\d]+[章篇節部]")
RE_QA_DASH = re.compile(r"^――")
RE_CENTERED_TITLE = re.compile(r"^[\s　]{4,}(.{2,50})[\s　]*$")
RE_PREFACE = re.compile(r"^(序文|序　文|信仰雑話\s*序文)\s*$")
RE_MIOSHIE_DATE = RE_GOKOWA_MD  # mesmo padrão
RE_SECTION_TITLE = re.compile(
    r"^(序文|奇蹟とは何ぞや|霊主体従|霊と体|医学が結核を作る|"
    r"観音教の治療は医学上合理的なる生気療法也|炭鉱にての奇蹟の数々|霊光自由無碍)"
)
RE_KOZA_TOPIC = re.compile(
    r"^[\s　]*(?:（[一二三四五六七八九十百\d]+）|"
    r"[一二三四五六七八九十]+、|[０-９]+、|\([0-9]+\))"
)


@dataclass
class LineMarker:
    line_no: int
    kind: str
    text: str


@dataclass
class FileScan:
    filename: str
    total_lines: int
    body_lines: int
    markers: list[LineMarker] = field(default_factory=list)
    marker_counts: dict[str, int] = field(default_factory=dict)
    proposed_splits: int = 0
    split_kinds: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def scan_lines(body: str, filename: str) -> FileScan:
    lines = body.splitlines()
    scan = FileScan(filename=filename, total_lines=len(lines), body_lines=len(lines))
    counts: Counter[str] = Counter()

    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s:
            continue

        def mark(kind: str) -> None:
            counts[kind] += 1
            scan.markers.append(LineMarker(i + 1, kind, s[:100]))

        if RE_PREFACE.match(s):
            mark("preface")
        elif RE_GOKOWA_FULL_DATE.match(s):
            mark("gokowa_date_full")
        elif RE_GOKOWA_MD.match(s):
            mark("gokowa_date_md")
        elif RE_OCHISHIJI_BRACKET.match(s) or RE_OCHISHIJI_BRACKET_HALF.match(s):
            mark("ochishiji_date")
        elif RE_KOZA_LECTURE.match(s):
            mark("koza_lecture")
        elif RE_HEN_PAREN.match(s):
            mark("jikan_hen")
        elif RE_NUMBERED_CSV.match(s):
            mark("numbered_csv")
        elif RE_SHINKO_DIV.search(raw) and len(s) >= 20:
            mark("shinko_divider")
        elif RE_SHINKO_PAGE.match(s):
            mark("shinko_page")
        elif RE_BRACKET_TITLE.match(s):
            mark("bracket_testimony")
        elif RE_BRACKET_SECTION.match(s):
            mark("bracket_section")
        elif RE_CHAPTER.match(s):
            mark("chapter")
        elif RE_QA_DASH.match(s):
            mark("qa_question")
        elif RE_SECTION_TITLE.match(s):
            mark("section_title")
        elif RE_KOZA_TOPIC.match(s) and len(s) <= 80:
            mark("koza_topic")

    scan.marker_counts = dict(counts)

    # Proposta de splits por prioridade de marcador dominante
    splits, kinds = propose_splits(counts, filename)
    scan.proposed_splits = splits
    scan.split_kinds = kinds

    if splits <= 1:
        top = counts.most_common(5)
        if top:
            scan.notes.append(
                "monolith_mas_marcadores: " + ", ".join(f"{k}={v}" for k, v in top)
            )
    return scan


def propose_splits(counts: Counter, filename: str) -> tuple[int, list[str]]:
    """Estima nº de trechos a partir dos marcadores encontrados linha-a-linha."""
    kinds_used: list[str] = []

    if "御讃歌" in filename or "讃歌集" in filename:
        n = counts.get("numbered_csv", 0)
        return (n + 1 if counts.get("preface") else n), ["numbered_csv_hymn"]

    if "山と水" in filename:
        n = counts.get("numbered_csv", 0)
        return (n + 1 if n else 1), ["numbered_csv_poem"]

    if "信仰雑話" in filename:
        n = counts.get("shinko_divider", 0) + counts.get("shinko_page", 0)
        return max(n, 1), ["shinko_dividers"]

    gokowa_dates = counts.get("gokowa_date_full", 0) + counts.get("gokowa_date_md", 0)
    if "御光話録" in filename and gokowa_dates >= 1:
        return gokowa_dates, ["gokowa_session_date"]
    if "御光話録" in filename and counts.get("qa_question", 0) >= 3:
        kinds_used.append("gokowa_qa_only_no_date_lines")
        return 1, kinds_used  # sessão única sem datas — nota, não ignorar Q count

    ochishiji = counts.get("ochishiji_date", 0)
    if "御垂示録" in filename and ochishiji >= 1:
        return ochishiji, ["ochishiji_bracket_date"]

    mioshie = counts.get("gokowa_date_md", 0)  # datas mioshie mesmo regex
    if "御教え集" in filename and mioshie >= 1:
        return mioshie, ["mioshie_session_date"]

    koza = counts.get("koza_lecture", 0)
    koza_topics = counts.get("koza_topic", 0) + counts.get("jikan_hen", 0)
    if "講座" in filename:
        if koza >= 1:
            return koza, ["koza_lecture"]
        if koza_topics >= 3:
            return koza_topics, ["koza_internal_topics"]

    hen = counts.get("jikan_hen", 0)
    if hen >= 2:
        return hen, ["jikan_hen_paren"]

    bracket = counts.get("bracket_testimony", 0)
    if bracket >= 2:
        return bracket + (1 if counts.get("section_title") else 0), ["bracket_testimony"]

    miracle = counts.get("section_title", 0) + counts.get("bracket_testimony", 0)
    if "奇蹟" in filename and miracle >= 2:
        return miracle, ["miracle_markers"]

    csv = counts.get("numbered_csv", 0)
    if csv >= 10:
        return csv, ["numbered_csv_auto"]

    chapter = counts.get("chapter", 0)
    if chapter >= 2:
        return chapter, ["chapters"]

    sect = counts.get("bracket_section", 0)
    if sect >= 3:
        return sect, ["bracket_sections"]

    shinko_div = counts.get("shinko_divider", 0)
    if shinko_div >= 5:
        return shinko_div, ["shinko_style_dividers"]

    return 1, ["monolith_no_dominant_marker"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    out = args.out or (wr / "segmentacao_manual" / "JP_LINE_SCAN_ALL.json")

    results: list[dict] = []
    for jp_path in sorted((wr / "jp").glob("*.txt")):
        fn = jp_path.name
        try:
            text = jp_path.read_text(encoding="utf-8")
            _, blocks = split_file(text)
            body = parse_article(blocks[0]).content if blocks else text
            scan = scan_lines(body, fn)
            results.append(
                {
                    "filename": fn,
                    "body_lines": scan.body_lines,
                    "marker_counts": scan.marker_counts,
                    "proposed_splits": scan.proposed_splits,
                    "split_kinds": scan.split_kinds,
                    "notes": scan.notes,
                    "sample_markers": [
                        {"line": m.line_no, "kind": m.kind, "text": m.text}
                        for m in scan.markers[:8]
                    ],
                    "total_markers": len(scan.markers),
                }
            )
        except Exception as exc:
            results.append({"filename": fn, "error": str(exc)})

    multi = sum(1 for r in results if r.get("proposed_splits", 0) > 1)
    mono = sum(1 for r in results if r.get("proposed_splits", 0) <= 1)
    total_splits = sum(r.get("proposed_splits", 0) for r in results)

    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "line_by_line_jp_scan_all",
        "files_total": len(results),
        "files_multi_split": multi,
        "files_monolith": mono,
        "proposed_splits_total": total_splits,
        "files": results,
    }
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"files={len(results)} multi={multi} monolith={mono} total_splits={total_splits}")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
