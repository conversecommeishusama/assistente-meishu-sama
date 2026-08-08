#!/usr/bin/env python3
"""Corrige artigos sinalizados pelo glossario_traducao — só aplica mudanças que melhoram a auditoria."""

from __future__ import annotations

import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from audit_translation_glossary import load_translation_glossary  # noqa: E402
from fix_periodicos_work_headers import ARTICLE_SEP, Article, format_article, parse_article, split_file  # noqa: E402
from periodicos_traducao_glossary import (  # noqa: E402
    WORK_ROOT,
    apply_pass_to_texts,
    audit_article_row,
    collect_articles,
    load_entries,
)
from resolve_glossary_pending_queue import (  # noqa: E402
    acceptable_in_text,
    apply_window_rules,
    targeted_file_fix,
)
from apply_periodicos_johrei import set_meta_line  # noqa: E402
from periodicos_traducao_glossary import expanded_candidates  # noqa: E402
import re  # noqa: E402
from glossary_term_queue import _jp_window, _metadata_like  # noqa: E402


def hit_count(audit: dict) -> int:
    return len(audit.get("hits", []))


def apply_window_fixes_for_article(jp_full: str, pt_text: str, missing_terms: list[str], glossary: dict) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    text = pt_text
    for term in missing_terms:
        if term not in jp_full:
            continue
        expected = expanded_candidates(glossary[term])
        if acceptable_in_text(term, expected, text):
            continue
        new_text, file_findings = targeted_file_fix(
            term=term, jp_text=jp_full, pt_text=text, expected=expected
        )
        if file_findings:
            text = new_text
            findings.extend(file_findings)
            if acceptable_in_text(term, expected, text):
                continue
        for match in re.finditer(re.escape(term), jp_full):
            if _metadata_like(_jp_window(jp_full, match.start())):
                continue
            new_text, win_findings = apply_window_rules(
                term=term, jp_text=jp_full, pt_text=text, jp_offset=match.start()
            )
            if win_findings:
                text = new_text
                findings.extend(win_findings)
            break
    return text, findings


def try_improve_article(row: dict, glossary: dict) -> tuple[str, str, str, dict, bool]:
    """Devolve (body, pt_meta, title, report, changed)."""
    ja, pa = row["jp_art"], row["pt_art"]
    before = audit_article_row(row, glossary)
    jp_full = ja.meta + "\n" + ja.content
    missing = [h[8:] for h in before.get("hits", []) if h.startswith("missing:")]

    title_pt = pa.fields.get("title_pt", "")
    body = pa.content
    pt_meta = pa.meta

    candidates: list[tuple[str, str, str]] = [("original", body, title_pt)]
    trial_body = body
    trial_body, _ = apply_window_fixes_for_article(jp_full, trial_body, missing, glossary)
    trial_body, trial_meta, trial_title, _ = apply_pass_to_texts(ja, pa, trial_body, pt_meta, title_pt)
    candidates.append(("patched", trial_body, trial_title))

    best_label, best_body, best_title = candidates[0]
    best_audit = before

    for label, cand_body, cand_title in candidates[1:]:
        trial_row = {
            "jp_art": ja,
            "pt_art": Article({**pa.fields, "title_pt": cand_title}, pa.meta, cand_body),
            "file": row["file"],
        }
        after = audit_article_row(trial_row, glossary)
        if after["ok"] or hit_count(after) < hit_count(best_audit):
            best_label, best_body, best_title, best_audit = label, cand_body, cand_title, after

    changed = best_label != "original"
    info = {
        "entry_id": ja.fields.get("entry_id"),
        "hits_before": hit_count(before),
        "hits_after": hit_count(best_audit),
        "ok_after": best_audit["ok"],
        "applied": best_label,
    }
    if changed:
        trial_body, trial_meta, trial_title, _ = apply_pass_to_texts(ja, pa, best_body, pt_meta, best_title)
        return trial_body, trial_meta, trial_title, info, True
    return body, pt_meta, title_pt, info, False


def rebuild_zip() -> Path:
    zip_path = WORK_ROOT / "periodicos_trabalho.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(WORK_ROOT.rglob("*")):
            if path.is_file() and path.name != zip_path.name:
                zf.write(path, path.relative_to(WORK_ROOT).as_posix())
    return zip_path


def main() -> int:
    glossary = load_translation_glossary()
    rows = collect_articles()
    flagged = [r for r in rows if not audit_article_row(r, glossary)["ok"]]

    report: list[dict] = []
    changed_count = 0

    by_file: dict[str, list[dict]] = {}
    for r in flagged:
        by_file.setdefault(r["file"], []).append(r)

    for fname, file_rows in by_file.items():
        jp_path = WORK_ROOT / "jp" / fname
        pt_path = WORK_ROOT / "pt" / fname
        jp_header, jp_blocks = split_file(jp_path.read_text(encoding="utf-8"))
        pt_header, pt_blocks = split_file(pt_path.read_text(encoding="utf-8"))
        if len(jp_blocks) != len(pt_blocks):
            raise RuntimeError(f"block mismatch in {fname}")

        improvements: dict[str, tuple[str, str, str]] = {}
        for r in file_rows:
            body, pt_meta, title_pt, info, changed = try_improve_article(r, glossary)
            report.append(info)
            if changed:
                changed_count += 1
                improvements[r["jp_art"].fields.get("entry_id", "")] = (body, pt_meta, title_pt)

        out_jp: list[str] = []
        out_pt: list[str] = []
        for jp_block, pt_block in zip(jp_blocks, pt_blocks):
            jp_art = parse_article(jp_block)
            pt_art = parse_article(pt_block)
            eid = jp_art.fields.get("entry_id", "")
            if eid in improvements:
                body, pt_meta, title_pt = improvements[eid]
                jp_fields = dict(jp_art.fields)
                pt_fields = dict(pt_art.fields)
                jp_fields["title_pt"] = title_pt
                pt_fields["title_pt"] = title_pt
                jp_meta = set_meta_line(jp_art.meta, "Paired Portuguese title: ", title_pt)
                pt_meta = set_meta_line(pt_meta, "Title: ", title_pt)
                out_jp.append(format_article(jp_fields, jp_meta, jp_art.content))
                out_pt.append(format_article(pt_fields, pt_meta, body))
            else:
                out_jp.append(jp_block if jp_block.lstrip().startswith(ARTICLE_SEP) else ARTICLE_SEP + jp_block)
                out_pt.append(pt_block if pt_block.lstrip().startswith(ARTICLE_SEP) else ARTICLE_SEP + pt_block)

        if len(out_jp) != len(jp_blocks):
            raise RuntimeError(f"block count dropped in {fname}: {len(jp_blocks)} -> {len(out_jp)}")

        jp_path.write_text(jp_header + "".join(out_jp), encoding="utf-8")
        pt_path.write_text(pt_header.replace("/jp/", "/pt/") + "".join(out_pt), encoding="utf-8")

    # Cabeçalhos: não invocar fix_periodicos_work_headers aqui — pode truncar se JP/PT dessincronizados.

    audited = [audit_article_row(r, glossary) for r in collect_articles()]
    ok = sum(1 for a in audited if a["ok"])
    still = [a for a in audited if not a["ok"]]

    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "flagged_input": len(flagged),
        "articles_changed": changed_count,
        "articles_ok": ok,
        "articles_flagged": len(still),
        "ok_pct": round(ok / len(audited) * 100, 2) if audited else 0,
        "report": report,
        "still_flagged": still,
    }
    out_path = WORK_ROOT / "GLOSSARY_FLAGGED_FIX.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_path = rebuild_zip()
    print(json.dumps({k: v for k, v in out.items() if k not in ("report", "still_flagged")}, ensure_ascii=False, indent=2))
    print(f"zip={zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
