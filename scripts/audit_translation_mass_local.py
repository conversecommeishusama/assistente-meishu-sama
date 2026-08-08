#!/usr/bin/env python3
"""Auditoria local final da tradução em massa (sem API)."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from post_translation_glossary import apply_post_translation_glossary, audit_glossary_text
from retranslate_core import strip_metadata
from retranslate_qa import pt_text_for_ratio, validate_translation
from run_deepseek_revision_pilot import load_glossary
from run_translation_mass import DONE_STATUSES, load_progress

DEFAULT_RUN = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / "20260620T190000Z"


def resolve_staging(run_dir: Path, row: dict) -> Path | None:
    rel = row.get("staging_path")
    if rel:
        p = PROJECT_ROOT / rel
        if p.exists():
            return p
    jp_rel = row["jp_path"]
    for candidate in (
        run_dir / "corpus" / jp_rel,
        run_dir / "corpus" / "data" / "publication_sources" / "pt" / Path(jp_rel).name.replace("-jp-", "-pt-"),
    ):
        if candidate.exists():
            return candidate
    pt_target = row.get("pt_target")
    if pt_target:
        p = run_dir / "corpus" / pt_target
        if p.exists():
            return p
    return None


def tier_for(result: dict) -> str:
    if result.get("missing_staging"):
        return "missing_staging"
    if result.get("truncation"):
        return "truncamento"
    if result.get("qa_blocking"):
        return "qa"
    if result.get("expansion_severe"):
        return "expansao"
    if result.get("glossary_missing_count", 0) > 0:
        return "glossary"
    return "ok"


def audit_row(run_dir: Path, jp_rel: str, row: dict, glossary: dict) -> dict:
    jp_path = PROJECT_ROOT / jp_rel
    staging = resolve_staging(run_dir, row)
    out: dict = {
        "jp_path": jp_rel,
        "status_run": row.get("status"),
        "staging_path": str(staging.relative_to(PROJECT_ROOT)) if staging else None,
        "pt_target": row.get("pt_target"),
        "missing_staging": staging is None,
    }
    if staging is None or not jp_path.exists():
        out["tier"] = "missing_staging"
        return out

    jp_body = strip_metadata(jp_path.read_text(encoding="utf-8"))
    pt_body = staging.read_text(encoding="utf-8")
    _, qa = validate_translation(jp_body, pt_body, sanitize=False)
    ratio = len(pt_text_for_ratio(pt_body)) / max(len(jp_body), 1)
    miss = audit_glossary_text(jp_body, pt_body, glossary)

    blocking = [i for i in qa.issues if not i.startswith("glossary_residual_")]
    out.update(
        {
            "chars_jp": len(jp_body),
            "chars_pt": len(pt_body),
            "ratio": round(ratio, 3),
            "truncation": ratio < 0.45 and len(jp_body) >= 50,
            "expansion_severe": ratio > 4.0,
            "qa_ok": qa.ok,
            "qa_issues": qa.issues,
            "qa_blocking": bool(blocking),
            "glossary_missing": [
                {"term": m["japanese_term"], "expected": m["expected_pt"][:3]}
                for m in miss
            ],
            "glossary_missing_count": len(miss),
        }
    )
    out["tier"] = tier_for(out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Local final audit of translation mass run.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--apply-safe-fixes", action="store_true")
    parser.add_argument("--quarantine-truncation", action="store_true")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    glossary = load_glossary()
    done = load_progress(run_dir / "progress.jsonl")
    results = [audit_row(run_dir, jp_rel, row, glossary) for jp_rel, row in sorted(done.items())]

    tier_counts = Counter(r["tier"] for r in results)
    term_counts: Counter[str] = Counter()
    for r in results:
        for m in r.get("glossary_missing") or []:
            term_counts[m["term"]] += 1

    fixes_applied = []
    quarantined = []

    if args.apply_safe_fixes or args.quarantine_truncation:
        quarantine_dir = run_dir / "quarentena" / "truncamento"
        for r in results:
            if r.get("missing_staging"):
                continue
            staging = PROJECT_ROOT / r["staging_path"]
            jp_body = strip_metadata((PROJECT_ROOT / r["jp_path"]).read_text(encoding="utf-8"))
            pt_body = staging.read_text(encoding="utf-8")

            if args.quarantine_truncation and r.get("truncation"):
                rel_name = staging.relative_to(run_dir / "corpus") if staging.is_relative_to(run_dir / "corpus") else staging.name
                dest = quarantine_dir / "corpus" / rel_name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if staging.exists():
                    __import__("shutil").move(str(staging), str(dest))
                    r["quarantined_to"] = str(dest.resolve().relative_to(PROJECT_ROOT.resolve()))
                    quarantined.append(r["jp_path"])

            if args.apply_safe_fixes and not r.get("truncation"):
                pt_new, report = apply_post_translation_glossary(jp_body, pt_body, glossary)
                if report.get("fixes_applied", 0) > 0:
                    staging.write_text(pt_new.rstrip() + "\n", encoding="utf-8")
                    fixes_applied.append(
                        {
                            "jp_path": r["jp_path"],
                            "fixes": report["fixes_applied"],
                            "residual_after": report["residual_terms"],
                        }
                    )

    out_jsonl = run_dir / "avaliacao_final_local.jsonl"
    out_jsonl.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n",
        encoding="utf-8",
    )

    md = []
    md.append("# Avaliação final local — tradução em massa")
    md.append("")
    md.append(f"Gerado: {datetime.now(timezone.utc).isoformat()}")
    md.append(f"Run: `{run_dir.relative_to(PROJECT_ROOT)}`")
    md.append(f"Glossário: `glossario_traducao.json`")
    md.append(f"Ficheiros auditados: **{len(results)}**")
    md.append("")
    md.append("## Resumo por tier")
    md.append("")
    md.append("| Tier | Significado | Quantidade |")
    md.append("|------|-------------|----------:|")
    labels = {
        "ok": "OK (ratio + glossário + QA)",
        "glossary": "Glossário em falta (revisar)",
        "expansao": "Expansão PT suspeita",
        "qa": "QA bloqueante",
        "truncamento": "Truncamento (texto incompleto?)",
        "missing_staging": "Staging em falta",
    }
    for tier in ("ok", "glossary", "expansao", "qa", "truncamento", "missing_staging"):
        if tier_counts.get(tier):
            md.append(f"| `{tier}` | {labels.get(tier, tier)} | {tier_counts[tier]} |")
    md.append("")
    md.append(f"**Limpos:** {tier_counts.get('ok', 0)} ({100 * tier_counts.get('ok', 0) / max(len(results), 1):.1f}%)")
    md.append("")
    if args.apply_safe_fixes:
        md.append(f"## Correcções automáticas aplicadas: **{len(fixes_applied)}**")
        md.append("")
        for f in fixes_applied[:20]:
            md.append(f"- `{Path(f['jp_path']).name[:55]}`: +{f['fixes']} fixes, residual={f['residual_after']}")
        if len(fixes_applied) > 20:
            md.append(f"- … +{len(fixes_applied) - 20} ficheiros")
        md.append("")
    if quarantined:
        md.append(f"## Quarentena truncamento: **{len(quarantined)}**")
        md.append("")
        for jp in quarantined:
            md.append(f"- `{jp}`")
        md.append("")

    def section(title: str, tier: str, limit: int = 30):
        md.append(f"## {title}")
        md.append("")
        items = [r for r in results if r.get("tier") == tier]
        md.append(f"**{len(items)}** ficheiros.")
        md.append("")
        for r in items[:limit]:
            name = Path(r["jp_path"]).name[:58]
            extra = ""
            if tier == "truncamento":
                extra = f" ratio={r.get('ratio')} jp={r.get('chars_jp')} pt={r.get('chars_pt')}"
            elif tier == "glossary":
                terms = ", ".join(m["term"] for m in (r.get("glossary_missing") or [])[:4])
                extra = f" ({terms})"
            elif tier == "qa":
                extra = f" {r.get('qa_issues')}"
            md.append(f"- `{name}`{extra}")
        if len(items) > limit:
            md.append(f"- … +{len(items) - limit} (ver jsonl)")
        md.append("")

    section("Truncamento — prioridade máxima", "truncamento")
    section("QA bloqueante", "qa")
    section("Expansão suspeita", "expansao")
    md.append("## Glossário — termos mais frequentes em falta")
    md.append("")
    md.append("| Termo | Falhas |")
    md.append("|-------|-------:|")
    for term, n in term_counts.most_common(20):
        md.append(f"| `{term}` | {n} |")
    md.append("")
    md.append("Detalhe por ficheiro: `avaliacao_final_local.jsonl`")

    (run_dir / "AVALIACAO_FINAL_LOCAL.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"audited={len(results)} ok={tier_counts.get('ok',0)} trunc={tier_counts.get('truncamento',0)} glossary={tier_counts.get('glossary',0)}")
    print(f"wrote {out_jsonl.name} AVALIACAO_FINAL_LOCAL.md fixes={len(fixes_applied)} quarantine={len(quarantined)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
