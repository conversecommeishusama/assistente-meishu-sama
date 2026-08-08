#!/usr/bin/env python3
"""Re-run AI reviewer on acceptance sample 30 WITH glossary in prompt."""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_deepseek_revision_pilot import call_deepseek, format_glossary_block, load_env_api_key, load_glossary, select_glossary_entries  # noqa: E402
from run_acceptance_sample import VERDICTS, build_human_workbook, verdict_rates  # noqa: E402

INPUT_DIR = PROJECT_ROOT / "reports" / "translation_review" / "acceptance_sample_30"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review" / "acceptance_sample_30_glossary"

REVIEWER_PROMPT = """Voce e um avaliador independente de traducao JP para PT-BR (escritos de Meishu-Sama).
Compare o japones com o portugues. Nao invente conteudo. Seja rigoroso.

Use OBRIGATORIAMENTE o glossario abaixo quando o termo japones aparecer no trecho.
- Terminologia fora do glossario sem justificativa no JP: penalize em "terminology".
- mismatch_grave: portugues parece OUTRO artigo ou contradiz fortemente o JP (nao use so por termo errado).

Criterios de verdict:
- aceito: fiel ao JP, terminologia conforme glossario, publicavel no Goshinsho sem edicao
- edicao_leve: sentido correto, pequenos ajustes terminologicos ou gramaticais
- retraduzir: problemas relevantes de fidelidade, mas mesmo tema/artigo
- mismatch_grave: portugues parece outro artigo ou contradiz fortemente o JP

{glossary_block}

Responda APENAS JSON valido:
{{
  "verdict": "aceito|edicao_leve|retraduzir|mismatch_grave",
  "score": 1-5,
  "fidelity": "alta|media|baixa",
  "terminology": "ok|parcial|ruim",
  "glossary_violations": ["lista curta de termos JP presentes com forma PT incorreta"],
  "reason": "uma ou duas frases objetivas"
}}

### JAPONES
{jp_excerpt}

### PORTUGUES
{pt_excerpt}
"""


def parse_review(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        parsed = json.loads(m.group(0)) if m else None
    if not parsed:
        return {"verdict": "unknown", "score": 0, "glossary_violations": [], "reason": raw[:200]}
    v = str(parsed.get("verdict", "unknown")).lower()
    if v not in VERDICTS:
        parsed["verdict"] = "unknown"
    parsed.setdefault("glossary_violations", [])
    return parsed


def ai_review_glossary(client, jp_excerpt: str, pt_excerpt: str, glossary: dict) -> tuple[dict, dict]:
    entries = select_glossary_entries(jp_excerpt, pt_excerpt, glossary, max_entries=50)
    block = format_glossary_block(entries)
    prompt = REVIEWER_PROMPT.format(glossary_block=block, jp_excerpt=jp_excerpt, pt_excerpt=pt_excerpt)
    raw, usage = call_deepseek(client, prompt)
    return parse_review(raw), usage


def main() -> int:
    from openai import OpenAI

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    glossary = load_glossary()
    client = OpenAI(api_key=load_env_api_key(), base_url="https://api.deepseek.com/v1")

    rows = []
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for path in sorted((INPUT_DIR / "jsonl").glob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        jp = row["jp_excerpt"]
        rb, u1 = ai_review_glossary(client, jp, row["pt_before_excerpt"], glossary)
        ra, u2 = ai_review_glossary(client, jp, row["pt_after_excerpt"], glossary)
        for u in (u1, u2):
            for k in usage_total:
                usage_total[k] += u.get(k, 0)

        row["review_before_no_glossary"] = row.get("review_before")
        row["review_after_no_glossary"] = row.get("review_after")
        row["review_before"] = rb
        row["review_after"] = ra
        rows.append(row)

        print(
            f"[{row['index']}/30] {row['title'][:40]}\n"
            f"  glossario: antes={rb.get('verdict')} depois={ra.get('verdict')}\n"
            f"  sem glossario: antes={row['review_before_no_glossary'].get('verdict')} "
            f"depois={row['review_after_no_glossary'].get('verdict')}"
        )
        (OUTPUT_DIR / "jsonl" / path.name).parent.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "jsonl" / path.name).write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(0.35)

    rates_before = verdict_rates(rows, "review_before")
    rates_after = verdict_rates(rows, "review_after")
    rates_before_ng = verdict_rates(
        [{"review_before": r["review_before_no_glossary"]} for r in rows], "review_before"
    )
    rates_after_ng = verdict_rates(
        [{"review_after": r["review_after_no_glossary"]} for r in rows], "review_after"
    )

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reviewer": "deepseek-chat with glossario.json (relevant terms per excerpt)",
        "sample_size": len(rows),
        "usage_total": usage_total,
        "note": "Compare with acceptance_sample_30 for reviewer WITHOUT glossary.",
        "rates_with_glossary_before": rates_before,
        "rates_with_glossary_after": rates_after,
        "rates_without_glossary_before": rates_before_ng,
        "rates_without_glossary_after": rates_after_ng,
        "rows": [
            {
                "index": r["index"],
                "pt_path": r["pt_path"],
                "title": r["title"],
                "before_glossary": r["review_before"],
                "after_glossary": r["review_after"],
                "before_no_glossary": r["review_before_no_glossary"],
                "after_no_glossary": r["review_after_no_glossary"],
            }
            for r in rows
        ],
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# Amostra 30 — avaliador IA COM glossario",
        "",
        f"**Data:** {summary['timestamp'][:10]}",
        "",
        "## Comparativo (aceito + edicao_leve)",
        "",
        "| Avaliador | PT antes | PT depois (revisao) |",
        "|-----------|--------:|-------------------:|",
        f"| Sem glossario | {rates_before_ng['aceito_ou_leve_pct']}% | {rates_after_ng['aceito_ou_leve_pct']}% |",
        f"| **Com glossario** | **{rates_before['aceito_ou_leve_pct']}%** | **{rates_after['aceito_ou_leve_pct']}%** |",
        "",
        "## Contagens com glossario — PT antes",
        "",
        f"- aceito: {rates_before['counts']['aceito']}",
        f"- edicao_leve: {rates_before['counts']['edicao_leve']}",
        f"- retraduzir: {rates_before['counts']['retraduzir']}",
        f"- mismatch_grave: {rates_before['counts']['mismatch_grave']}",
        "",
        "## Contagens com glossario — PT depois",
        "",
        f"- aceito: {rates_after['counts']['aceito']}",
        f"- edicao_leve: {rates_after['counts']['edicao_leve']}",
        f"- retraduzir: {rates_after['counts']['retraduzir']}",
        f"- mismatch_grave: {rates_after['counts']['mismatch_grave']}",
        "",
        "## Por texto",
        "",
        "| # | Titulo | sem gloss. antes | com gloss. antes | sem gloss. depois | com gloss. depois |",
        "|--:|--------|------------------|--------------------|--------------------|-------------------|",
    ]
    for r in rows:
        md.append(
            f"| {r['index']} | {r['title'][:35]} | "
            f"{r['review_before_no_glossary'].get('verdict')} | {r['review_before'].get('verdict')} | "
            f"{r['review_after_no_glossary'].get('verdict')} | {r['review_after'].get('verdict')} |"
        )
    md.append("\n\nAvaliacao humana: `human_workbook.md`\n")
    (OUTPUT_DIR / "summary.md").write_text("\n".join(md), encoding="utf-8")

    wb = build_human_workbook(rows)
    wb = wb.replace(
        "avaliacao humana",
        "avaliacao humana (avaliador IA abaixo JA inclui glossario)",
        1,
    )
    for r in rows:
        old = f"- IA antes: **{r['review_before'].get('verdict')}**"
        # workbook uses review_before - already glossary version in rows
    (OUTPUT_DIR / "human_workbook.md").write_text(
        build_human_workbook(rows).replace(
            "# Amostra de aceitação — 30 textos (avaliação humana)",
            "# Amostra 30 — avaliacao humana (IA com glossario ja aplicada)",
        ),
        encoding="utf-8",
    )

    print(f"\nsummary={OUTPUT_DIR / 'summary.md'}")
    print(
        f"Com glossario aceito+leve: antes {rates_before['aceito_ou_leve_pct']}% | "
        f"depois {rates_after['aceito_ou_leve_pct']}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
