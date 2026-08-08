#!/usr/bin/env python3
"""Run stratified acceptance sample (30 texts): revise + AI reviewer + human workbook."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text  # noqa: E402
from paragraph_glossary import align_paragraphs  # noqa: E402
from run_deepseek_revision_pilot import (  # noqa: E402
    MODEL,
    assess_paragraph_quality,
    call_deepseek,
    evaluate_text,
    format_glossary_block,
    load_env_api_key,
    load_glossary,
    parse_revision_response,
    revise_text_with_deepseek,
    select_glossary_entries,
)

OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review" / "acceptance_sample_30"
PROTOCOL_PATH = PROJECT_ROOT / "protocolo_revisao.txt"
CORPUS_AUDIT = PROJECT_ROOT / "reports" / "translation_review" / "corpus_quality_audit.json"

SEED_PATHS = [
    "data/publication_sources/pt/eiko/16-de-janeiro-de-1952-forca-absoluta-publication-pt-0256.txt",
    "data/publication_sources/pt/hikari/13-de-agosto-de-1949-os-tres-grandes-desastres-e-os-tres-pequenos-desastres-publication-pt-0300.txt",
    "data/publication_sources/pt/guia-rapido-da-igreja-messianica-mundial/20-de-novembro-de-1950-seguir-a-razao-publication-pt-0141.txt",
    "data/publication_sources/pt/hikari/10-de-setembro-de-1949-lavar-os-olhos-publication-pt-0670.txt",
    "data/publication_sources/pt/hikari/23-de-julho-de-1949-o-significado-de-inari-publication-pt-0110.txt",
]

VERDICTS = ("aceito", "edicao_leve", "retraduzir", "mismatch_grave")

REVIEWER_PROMPT = """Você é um avaliador independente de tradução JP→PT-BR (escritos de Meishu-Sama).
Compare o japonês com o português. Não invente conteúdo. Seja rigoroso.

Critérios:
- aceito: fiel ao JP, terminologia adequada, publicável no Goshinsho sem edição
- edicao_leve: sentido correto, pequenos ajustes terminológicos ou gramaticais
- retraduzir: problemas relevantes de fidelidade, mas mesmo tema/artigo
- mismatch_grave: português parece outro artigo ou contradiz fortemente o JP

Responda APENAS JSON:
{{
  "verdict": "aceito|edicao_leve|retraduzir|mismatch_grave",
  "score": 1-5,
  "fidelity": "alta|media|baixa",
  "terminology": "ok|parcial|ruim",
  "reason": "uma ou duas frases objetivas"
}}

### JAPONÊS
{jp_excerpt}

### PORTUGUÊS
{pt_excerpt}
"""


def body_excerpt(jp: str, pt: str, max_chars: int = 3500) -> tuple[str, str]:
    """Use aligned paragraph 1 (main body) or first substantial chunk."""
    pairs = align_paragraphs(jp, pt)
    for pair in pairs[1:] if len(pairs) > 1 else pairs:
        if len(pair.jp) > 80 and len(pair.pt) > 80:
            return pair.jp[:max_chars], pair.pt[:max_chars]
    return jp[:max_chars], pt[:max_chars]


def validate_revision(pt_before: str, pt_after: str, jp: str) -> dict:
    issues = []
    ratio = len(pt_after) / max(len(pt_before), 1)
    if ratio < 0.55 or ratio > 1.45:
        issues.append(f"length_ratio={ratio:.2f}")
    if re.search(r"Kotodama\s*\(\s*Kotodama", pt_after, re.I):
        issues.append("kotodama_nested")
    if re.search(r"\blinha espiritual\b", pt_after, re.I):
        issues.append("linha_espiritual")
    pairs = align_paragraphs(jp, pt_after)
    auto = assess_paragraph_quality(
        pairs[1].pt if len(pairs) > 1 else pt_after[:2000],
        pairs[1].jp if len(pairs) > 1 else jp[:2000],
        load_glossary(),
    )
    if auto.issues:
        issues.extend(auto.issues)
    return {"passed": not issues, "issues": issues, "length_ratio": round(ratio, 3)}


def ai_review(client, jp_excerpt: str, pt_excerpt: str) -> tuple[dict, dict]:
    prompt = REVIEWER_PROMPT.format(jp_excerpt=jp_excerpt, pt_excerpt=pt_excerpt)
    raw, usage = call_deepseek(client, prompt)
    parsed = None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except json.JSONDecodeError:
                parsed = None
    if not parsed:
        parsed = {"verdict": "unknown", "score": 0, "reason": raw[:200]}
    v = str(parsed.get("verdict", "unknown")).lower()
    if v not in VERDICTS:
        parsed["verdict"] = "unknown"
    return parsed, usage


def select_sample(pairs: list, n: int = 30) -> list:
    by_path = {str(permanent_pt_path(p.pt).relative_to(PROJECT_ROOT)): p for p in pairs}
    chosen: list = []
    seen = set()

    for path in SEED_PATHS:
        if path in by_path and path not in seen:
            chosen.append(by_path[path])
            seen.add(path)

    if CORPUS_AUDIT.exists():
        audit = json.loads(CORPUS_AUDIT.read_text(encoding="utf-8"))
        for row in audit.get("rows_with_issues", []):
            path = row["pt_path"]
            if path in by_path and path not in seen and len(chosen) < n:
                chosen.append(by_path[path])
                seen.add(path)

    sized = []
    for pair in pairs:
        path = str(permanent_pt_path(pair.pt).relative_to(PROJECT_ROOT))
        if path in seen:
            continue
        try:
            jp = read_entry_text(pair.jp)
            pt = permanent_pt_path(pair.pt).read_text(encoding="utf-8")
            sized.append((len(jp) + len(pt), pair, path))
        except Exception:
            continue
    sized.sort(key=lambda x: x[0])
    if sized:
        step = max(1, len(sized) // max(n - len(chosen), 1))
        for i in range(0, len(sized), step):
            if len(chosen) >= n:
                break
            _, pair, path = sized[i]
            if path not in seen:
                chosen.append(pair)
                seen.add(path)

    return chosen[:n]


def verdict_rates(rows: list, key: str) -> dict:
    counts = {v: 0 for v in VERDICTS}
    unknown = 0
    for row in rows:
        v = row.get(key, {}).get("verdict", "unknown")
        if v in counts:
            counts[v] += 1
        else:
            unknown += 1
    total = len(rows)
    accept_like = counts["aceito"] + counts["edicao_leve"]
    return {
        "total": total,
        "counts": counts,
        "unknown": unknown,
        "aceito_ou_leve_pct": round(accept_like / total * 100, 1) if total else 0,
        "aceito_pct": round(counts["aceito"] / total * 100, 1) if total else 0,
    }


def build_human_workbook(rows: list) -> str:
    lines = [
        "# Amostra de aceitação — 30 textos (avaliação humana)",
        "",
        "Marque **uma** opção por texto após ler JP, PT antes e PT depois da revisão.",
        "",
        "| # | Veredicto | Significado |",
        "|--:|-----------|-------------|",
        "| A | aceito | Publicável no Goshinsho sem edição |",
        "| B | edicao_leve | Sentido ok; ajustes pontuais |",
        "| C | retraduzir | Mesmo artigo, retradução necessária |",
        "| D | mismatch_grave | PT não corresponde ao JP |",
        "",
        "**Campos:** preencha `humano_antes` e `humano_depois` em cada seção.",
        "",
    ]
    for i, row in enumerate(rows, 1):
        lines.extend(
            [
                f"---\n\n## {i}. {row['title']}",
                "",
                f"**Arquivo:** `{row['pt_path']}`",
                "",
                f"- IA antes: **{row['review_before'].get('verdict')}** (score {row['review_before'].get('score')})",
                f"- IA depois: **{row['review_after'].get('verdict')}** (score {row['review_after'].get('score')})",
                f"- Validador automático: {'PASS' if row['validators']['passed'] else 'FAIL'} {row['validators'].get('issues', [])}",
                "",
                f"**humano_antes:** [ ] A  [ ] B  [ ] C  [ ] D",
                f"**humano_depois:** [ ] A  [ ] B  [ ] C  [ ] D",
                "",
                "### Japonês (trecho)",
                "",
                row["jp_excerpt"][:2500],
                "",
                "### Português ANTES",
                "",
                row["pt_before_excerpt"][:2500],
                "",
                "### Português DEPOIS (revisão protocolo)",
                "",
                row["pt_after_excerpt"][:2500],
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=30)
    parser.add_argument("--max-paragraphs", type=int, default=6)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    from openai import OpenAI

    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()
    pairs = pair_entries(load_entries())
    sample = select_sample(pairs, args.sample)

    manifest = [
        {
            "index": i + 1,
            "pt_path": str(permanent_pt_path(p.pt).relative_to(PROJECT_ROOT)),
            "title": p.pt.get("title") or p.pt.get("display_source_name_pt"),
        }
        for i, p in enumerate(sample)
    ]
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    client = OpenAI(api_key=load_env_api_key(), base_url="https://api.deepseek.com/v1")
    rows = []
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for i, pair in enumerate(sample, 1):
        pt_path = permanent_pt_path(pair.pt)
        rel = str(pt_path.relative_to(PROJECT_ROOT))
        jp_text = read_entry_text(pair.jp)
        pt_before = pt_path.read_text(encoding="utf-8")

        pt_revised_chunk, _, u_rev = revise_text_with_deepseek(
            client, jp_text, pt_before, protocol, glossary, max_paragraphs=args.max_paragraphs
        )
        for k in usage_total:
            usage_total[k] += u_rev.get(k, 0)

        # Merge: keep metadata from original, replace revised paragraphs at start
        orig_pairs = align_paragraphs(jp_text, pt_before)
        rev_pairs = align_paragraphs(jp_text, pt_revised_chunk)
        merged = []
        for idx in range(len(orig_pairs)):
            if idx < len(rev_pairs) and rev_pairs[idx].pt.strip():
                merged.append(rev_pairs[idx].pt)
            else:
                merged.append(orig_pairs[idx].pt)
        pt_after = "\n\n".join(merged)

        jp_ex, pt_before_ex = body_excerpt(jp_text, pt_before)
        _, pt_after_ex = body_excerpt(jp_text, pt_after)

        review_before, u1 = ai_review(client, jp_ex, pt_before_ex)
        review_after, u2 = ai_review(client, jp_ex, pt_after_ex)
        for u in (u1, u2):
            for k in usage_total:
                usage_total[k] += u.get(k, 0)

        validators = validate_revision(pt_before, pt_after, jp_text)
        metrics = evaluate_text(jp_text, pt_before, pt_after, glossary)

        row = {
            "index": i,
            "pt_path": rel,
            "title": pair.pt.get("title") or pair.pt.get("display_source_name_pt"),
            "jp_excerpt": jp_ex,
            "pt_before_excerpt": pt_before_ex,
            "pt_after_excerpt": pt_after_ex,
            "review_before": review_before,
            "review_after": review_after,
            "validators": validators,
            "metrics": metrics,
            "usage_revision": u_rev,
        }
        rows.append(row)

        (args.output_dir / "jsonl" / f"{i:02d}.json").parent.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "jsonl" / f"{i:02d}.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"[{i}/{len(sample)}] {rel}\n"
            f"  IA antes: {review_before.get('verdict')} | depois: {review_after.get('verdict')} | "
            f"validador: {'OK' if validators['passed'] else 'FAIL'}"
        )
        time.sleep(0.4)

    rates_before = verdict_rates(rows, "review_before")
    rates_after = verdict_rates(rows, "review_after")

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "sample_size": len(rows),
        "max_paragraphs_revised": args.max_paragraphs,
        "usage_total": usage_total,
        "ai_reviewer_note": "Taxas abaixo são julgamento de IA independente, NÃO substituem avaliação humana.",
        "rates_pt_before": rates_before,
        "rates_pt_after_revision": rates_after,
        "validators_pass_pct": round(
            sum(1 for r in rows if r["validators"]["passed"]) / len(rows) * 100, 1
        ),
        "avg_auto_quality_before": round(
            sum(r["metrics"]["quality_before"] for r in rows) / len(rows), 1
        ),
        "avg_auto_quality_after": round(
            sum(r["metrics"]["quality_after"] for r in rows) / len(rows), 1
        ),
        "rows": [
            {
                "index": r["index"],
                "pt_path": r["pt_path"],
                "title": r["title"],
                "review_before": r["review_before"],
                "review_after": r["review_after"],
                "validators": r["validators"],
                "metrics": r["metrics"],
            }
            for r in rows
        ],
    }

    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md_lines = [
        "# Amostra 30 — resultados (avaliador IA)",
        "",
        f"**Data:** {summary['timestamp'][:10]}  ",
        f"**Aviso:** {summary['ai_reviewer_note']}",
        "",
        "## Taxas (avaliador IA)",
        "",
        "| Momento | aceito | edicao_leve | retraduzir | mismatch_grave | aceito+leve |",
        "|---------|-------:|------------:|-----------:|---------------:|------------:|",
    ]
    for label, rates in [
        ("PT antes (atual)", rates_before),
        ("PT depois (revisão)", rates_after),
    ]:
        c = rates["counts"]
        md_lines.append(
            f"| {label} | {c['aceito']} | {c['edicao_leve']} | {c['retraduzir']} | "
            f"{c['mismatch_grave']} | **{rates['aceito_ou_leve_pct']}%** |"
        )
    md_lines.extend(
        [
            "",
            f"- Validadores automáticos passaram: **{summary['validators_pass_pct']}%**",
            f"- Qualidade automática média: {summary['avg_auto_quality_before']}% → {summary['avg_auto_quality_after']}%",
            f"- Tokens API: {usage_total['total_tokens']:,}",
            "",
            "## Tabela por texto",
            "",
            "| # | Título | IA antes | IA depois | Validador |",
            "|--:|--------|----------|-----------|-----------|",
        ]
    )
    for r in rows:
        md_lines.append(
            f"| {r['index']} | {r['title'][:40]} | {r['review_before'].get('verdict')} | "
            f"{r['review_after'].get('verdict')} | {'OK' if r['validators']['passed'] else 'FAIL'} |"
        )
    md_lines.append("\n\nPreencha avaliação humana em `human_workbook.md`.\n")

    (args.output_dir / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")
    (args.output_dir / "human_workbook.md").write_text(build_human_workbook(rows), encoding="utf-8")

    print(f"\nsummary={args.output_dir / 'summary.json'}")
    print(f"workbook={args.output_dir / 'human_workbook.md'}")
    print(
        f"IA aceito+leve: antes {rates_before['aceito_ou_leve_pct']}% | "
        f"depois {rates_after['aceito_ou_leve_pct']}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
