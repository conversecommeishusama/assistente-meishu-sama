#!/usr/bin/env python3
"""Gera spec JSON inicial (P1b) a partir da heurística split_livros_work_articles."""

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
from livros_qa_markers import is_pt_question_line  # noqa: E402
from split_livros_work_articles import (  # noqa: E402
    Slice,
    process_file,
)

MANUAL_DIR_NAME = "segmentacao_manual"


def _first_anchor_line(text: str, *, min_len: int = 10) -> str:
    for line in text.splitlines():
        s = line.strip()
        if len(s) >= min_len:
            return s
    return text.strip()[:80]


def _jp_anchor(sl: Slice) -> str:
    lines = [l.strip() for l in sl.jp.splitlines() if l.strip()]
    if not lines:
        return ""
    head = lines[0]
    if len(head) <= 80:
        return head
    second = lines[1] if len(lines) > 1 else ""
    if second and len(second) >= 12:
        return f"{head}\n\n{second}" if len(head) < 40 else second[:80]
    return head[:80]


def _pt_anchor(sl: Slice, profile: str = "") -> str:
    if not sl.pt.strip():
        return ""
    if profile == "gokowa_roku_qa":
        for line in sl.pt.splitlines():
            s = line.strip()
            if is_pt_question_line(s):
                return s[:120]
        for line in sl.pt.splitlines():
            s = line.strip()
            if re.search(r"\d{1,2} de (?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)", s, re.I):
                return s[:120]
    if profile == "ochishiji_roku":
        for line in sl.pt.splitlines():
            s = line.strip()
            if s.startswith("[") and "de " in s.lower():
                return s[:120]
        m = re.search(r"\[\d{1,2}(?:º)? de (?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)", sl.pt, re.I)
        if m:
            return m.group(0)[:120]
    if profile == "mioshie_shu":
        for line in sl.pt.splitlines():
            s = line.strip()
            if re.match(r"^\d{1,2}(?:º)? de agosto$", s, re.I):
                return s.replace("º de", " de")
    for line in sl.pt.splitlines():
        s = line.strip()
        if len(s) >= 12 and not s.startswith("Title:"):
            return s[:120]
    return sl.pt.strip()[:120]


def slice_to_boundary(sl: Slice, *, notes: list[str], profile: str = "") -> dict:
    jp_a = _jp_anchor(sl)
    pt_a = _pt_anchor(sl, profile)
    title_jp = sl.title_jp.split(" — ")[-1][:120]
    note = "; ".join(notes + sl.notes) if (notes or sl.notes) else ""
    return {
        "kind": sl.kind,
        "title_jp": title_jp,
        "title_pt": "",
        "jp_anchor": jp_a,
        "pt_anchor": pt_a,
        "notes": note,
    }


def build_spec(result, *, editor_notes: str = "") -> dict:
    articles = []
    for sl in result.slices:
        notes: list[str] = []
        if not sl.pt.strip():
            notes.append("PT vazio nesta fatia — rever pt_anchor")
        elif len(sl.pt) < len(sl.jp) * 0.35:
            notes.append(f"PT curto ({len(sl.pt)} vs JP {len(sl.jp)}) — rever pareamento")
        articles.append(slice_to_boundary(sl, notes=notes, profile=result.profile))
    return {
        "filename": result.filename,
        "profile": result.profile,
        "method": "manual",
        "approved": False,
        "editor_notes": editor_notes or f"Spec bootstrap heurístico ({result.profile}). Revisar comparativo antes de approved=true.",
        "bootstrap_warnings": result.warnings,
        "articles": articles,
    }


def update_manifest(manual_dir: Path, filename: str, status: str = "draft_spec") -> None:
    manifest_path = manual_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest.get("files", []):
        if entry.get("filename") == filename:
            entry["status"] = status
            entry["spec"] = f"{filename}.json"
            break
    manifest["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Bootstrap spec manual P1b a partir de heurística")
    p.add_argument("--file", action="append", required=True, help="Nome do ficheiro .txt")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--note", action="append", default=[], help="Nota editorial (por ficheiro, na mesma ordem)")
    p.add_argument("--force", action="store_true", help="Sobrescrever spec existente")
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    manual_dir = wr / MANUAL_DIR_NAME
    manual_dir.mkdir(parents=True, exist_ok=True)

    for i, fn in enumerate(args.file):
        spec_path = manual_dir / f"{fn}.json"
        if spec_path.is_file() and not args.force:
            print(f"SKIP (exists): {spec_path}", file=sys.stderr)
            continue
        jp_path = wr / "jp" / fn
        pt_path = wr / "pt" / fn
        if not jp_path.is_file() or not pt_path.is_file():
            print(f"MISSING: {fn}", file=sys.stderr)
            continue
        result = process_file(jp_path, pt_path)
        note = args.note[i] if i < len(args.note) else ""
        spec = build_spec(result, editor_notes=note)
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        update_manifest(manual_dir, fn)
        print(f"{spec_path}  ({len(spec['articles'])} artigos, profile={spec['profile']})")
        if result.warnings:
            print("  warnings:", "; ".join(result.warnings[:5]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
