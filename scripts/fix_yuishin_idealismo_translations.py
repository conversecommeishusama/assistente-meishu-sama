#!/usr/bin/env python3
"""Corrige idealismo→espiritualismo quando o JP traz 唯心/精神为義 (não 理想)."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

YUISHIN_MARKERS = (
    "唯心主義",
    "唯心为義",
    "唯心为義者",
    "唯心思想",
    "唯心観",
    "唯心为観",
    "唯心的",
    "精神为義",
)

IDEAL_ONLY_MARKER = "理想"

REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bIdealismo\b"), "Espiritualismo"),
    (re.compile(r"\bidealismo\b"), "espiritualismo"),
    (re.compile(r"\bIdealista\b"), "Espiritualista"),
    (re.compile(r"\bidealista\b"), "espiritualista"),
    (re.compile(r"\bidealistas\b"), "espiritualistas"),
    (re.compile(r"\bvisão idealista\b", re.I), "visão espiritualista"),
    (re.compile(r"\bpensamento idealista\b", re.I), "pensamento espiritualista"),
    (re.compile(r"\bO Idealismo\b"), "O Espiritualismo"),
    (re.compile(r"\bo idealismo\b"), "o espiritualismo"),
    (re.compile(r"\bidealismo\b"), "espiritualismo"),
    (re.compile(r"\bIdealismo\b"), "Espiritualismo"),
    (re.compile(r"\be o Idealismo\b"), "e o Espiritualismo"),
    (re.compile(r"\be o idealismo\b"), "e o espiritualismo"),
    (re.compile(r"\bentre o Materialismo e o Idealismo\b"), "entre o Materialismo e o Espiritualismo"),
    (re.compile(r"\bentre o materialismo e o idealismo\b"), "entre o materialismo e o espiritualismo"),
    (re.compile(r"\bMaterialismo e Idealismo\b"), "Materialismo e Espiritualismo"),
    (re.compile(r"\bmaterialismo e idealismo\b"), "materialismo e espiritualismo"),
    (re.compile(r"\bMaterialismo e idealismo\b"), "Materialismo e espiritualismo"),
    (re.compile(r"\bluta contra o idealismo\b", re.I), "luta contra o espiritualismo"),
    (re.compile(r"\bvenerável idealista\b", re.I), "venerável espiritualista"),
    (re.compile(r"\bidealista\b"), "espiritualista"),
)


def jp_needs_yuishin_fix(jp_text: str) -> bool:
    if not any(marker in jp_text for marker in YUISHIN_MARKERS):
        return False
    return True


def pt_has_idealism(pt_text: str) -> bool:
    return bool(re.search(r"\bidealism", pt_text, flags=re.I))


def apply_fixes(pt_text: str) -> tuple[str, int]:
    updated = pt_text
    total = 0
    for pattern, replacement in REPLACEMENTS:
        updated, count = pattern.subn(replacement, updated)
        total += count
    return updated, total


def fix_file(pt_path: Path, jp_path: Path, *, apply: bool) -> dict:
    jp_text = jp_path.read_text(encoding="utf-8")
    pt_text = pt_path.read_text(encoding="utf-8")
    if not jp_needs_yuishin_fix(jp_text):
        return {"path": str(pt_path), "skipped": "no_yuishin_in_jp"}
    if not pt_has_idealism(pt_text):
        return {"path": str(pt_path), "skipped": "no_idealism_in_pt"}
    new_text, count = apply_fixes(pt_text)
    if count and apply:
        pt_path.write_text(new_text, encoding="utf-8")
    return {"path": str(pt_path), "replacements": count, "jp": str(jp_path)}


def _pairing_key(path: Path) -> str:
    rel = path.as_posix()
    rel = re.sub(r"/corpus/data/publication_sources/(?:pt|jp)/", "/", rel)
    rel = re.sub(r"/data/publication_sources/(?:pt|jp)/", "/", rel)
    return re.sub(r"-publication-(?:pt|jp)-\d+\.txt$", "", rel)


def paired_jp_path(pt_path: Path) -> Path | None:
    rel = pt_path.as_posix()
    if "/corpus/data/publication_sources/jp/" in rel:
        name = pt_path.name
        return PROJECT_ROOT / "data" / "publication_sources" / "jp" / pt_path.parent.name / name
    if "/data/publication_sources/pt/" in rel:
        key = _pairing_key(pt_path)
        jp_dir = PROJECT_ROOT / "data" / "publication_sources" / "jp" / pt_path.parent.name
        if not jp_dir.exists():
            return None
        for candidate in jp_dir.glob("*.txt"):
            if _pairing_key(candidate) == key:
                return candidate
        return None
    if "/data/publication_sources/jp/" in rel:
        return pt_path
    return None


def collect_targets(extra_roots: list[Path]) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    seen: set[str] = set()
    roots = extra_roots + [
        PROJECT_ROOT / "reports/translation_review/translation_mass/20260620T190000Z/corpus",
        PROJECT_ROOT / "data/publication_sources/pt",
    ]
    for root in roots:
        if not root.exists():
            continue
        for pt_path in root.rglob("*.txt"):
            if "/data/publication_sources/jp/" in pt_path.as_posix() and "/corpus/" not in pt_path.as_posix():
                continue
            if "idealism" not in pt_path.read_text(encoding="utf-8").lower():
                continue
            jp_path = paired_jp_path(pt_path)
            if jp_path is None or not jp_path.exists():
                continue
            key = str(pt_path)
            if key in seen:
                continue
            seen.add(key)
            pairs.append((pt_path, jp_path))
    return pairs


def update_entries_jsonl(*, apply: bool) -> int:
    entries_path = PROJECT_ROOT / "data/publication_sources/entries.jsonl"
    lines = entries_path.read_text(encoding="utf-8").splitlines()
    changed = 0
    out: list[str] = []
    jp_by_key: dict[str, dict] = {}
    for line in lines:
        if line.strip():
            row = json.loads(line)
            if row.get("lang") == "jp" and row.get("clean_path"):
                jp_by_key[_pairing_key(PROJECT_ROOT / row["clean_path"])] = row

    subs = (
        ("A Batalha entre o Materialismo e o Idealismo", "A Batalha entre o Materialismo e o Espiritualismo"),
        ("Materialismo e Idealismo", "Materialismo e Espiritualismo"),
        ("entre o materialismo e o idealismo", "entre o materialismo e o espiritualismo"),
        ("visão idealista", "visão espiritualista"),
        ("pensamento idealista", "pensamento espiritualista"),
        ("venerável idealista", "venerável espiritualista"),
        ("luta contra o idealismo", "luta contra o espiritualismo"),
        ("O idealismo", "O espiritualismo"),
        ("o idealismo", "o espiritualismo"),
        ("Idealismo", "Espiritualismo"),
        ("idealismo", "espiritualismo"),
        ("Idealista", "Espiritualista"),
        ("idealista", "espiritualista"),
        ("idealistas", "espiritualistas"),
    )

    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        jp_row = None
        clean = row.get("clean_path")
        if row.get("lang") == "jp":
            jp_row = row
        elif clean:
            jp_row = jp_by_key.get(_pairing_key(PROJECT_ROOT / clean))

        if jp_row:
            jp_path = PROJECT_ROOT / (jp_row.get("clean_path") or "")
            if jp_path.exists() and jp_needs_yuishin_fix(jp_path.read_text(encoding="utf-8")):
                for field in ("title", "paired_title_pt", "display_source_name", "display_source_name_pt", "body"):
                    val = row.get(field)
                    if not isinstance(val, str) or "idealism" not in val.lower():
                        continue
                    new_val = val
                    for old, new in subs:
                        new_val = new_val.replace(old, new)
                    if new_val != val:
                        row[field] = new_val
                        changed += 1
        out.append(json.dumps(row, ensure_ascii=False))
    if apply and changed:
        entries_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--extra-root", action="append", default=[])
    args = parser.parse_args()
    extra = [Path(p) for p in args.extra_root]
    pairs = collect_targets(extra)
    reports = [fix_file(pt, jp, apply=args.apply) for pt, jp in pairs]
    fixed = [r for r in reports if r.get("replacements")]
    skipped = [r for r in reports if r.get("skipped")]
    entry_changes = update_entries_jsonl(apply=args.apply)
    print(f"scanned={len(pairs)} fixed_files={len(fixed)} skipped={len(skipped)} entry_fields={entry_changes}")
    for row in fixed:
        print(f"  {row['replacements']:3d}  {row['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
