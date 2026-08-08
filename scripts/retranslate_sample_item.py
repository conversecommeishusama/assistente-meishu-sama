#!/usr/bin/env python3
"""Retranslate a single text with protocolo_retraducao.txt."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_deepseek_revision_pilot import (
    MODEL,
    call_deepseek,
    format_glossary_block,
    load_env_api_key,
    load_glossary,
    select_glossary_entries,
)
from retranslate_qa import sanitize_pt_translation, validate_translation

JP_PATH = PROJECT_ROOT / (
    "data/publication_sources/jp/evangelho-do-reino-dos-ceus/"
    "5-de-fevereiro-de-1947-o-principio-da-terapia-do-futuro-publication-jp-1308.txt"
)
PT_WRONG_PATH = PROJECT_ROOT / (
    "data/publication_sources/pt/hikari/"
    "6-de-agosto-de-1949-a-trindade-dos-orgaos-internos-e-a-purificacao-espiritual-publication-pt-0383.txt"
)
PT_CANONICAL_PATH = PROJECT_ROOT / (
    "data/publication_sources/pt/evangelho-do-reino-dos-ceus/"
    "5-de-fevereiro-de-1947-o-principio-da-terapia-do-futuro-publication-pt-0382.txt"
)
PROTOCOL = PROJECT_ROOT / "protocolo_retraducao.txt"
OUT_DIR = PROJECT_ROOT / "reports/translation_review/acceptance_sample_30_glossary/retranslate_09"


def strip_metadata(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith(
            ("Title:", "Publication source:", "Original publication", "Date:", "Language:", "Collection ID:", "Paired ", "Original path:", "Display ")
        ):
            continue
        if line.strip():
            lines.append(line)
    return "\n".join(lines)


def main() -> int:
    from openai import OpenAI

    jp_body = strip_metadata(JP_PATH.read_text(encoding="utf-8"))
    pt_wrong = strip_metadata(PT_WRONG_PATH.read_text(encoding="utf-8"))
    pt_canonical = strip_metadata(PT_CANONICAL_PATH.read_text(encoding="utf-8"))
    protocol = PROTOCOL.read_text(encoding="utf-8")
    glossary = load_glossary()
    gloss_block = format_glossary_block(select_glossary_entries(jp_body, "", glossary, 50))

    prompt = f"""{protocol}

### LEMBRETE
- Nenhum caractere japonês na saída (kanji, hiragana, katakana).
- Em explicações etimológicas: português ou romaji apenas.

{gloss_block}

### TEXTO JAPONÊS (fonte única — traduza por completo):

{jp_body}

### TRADUÇÃO EM PORTUGUÊS (PT-BR):
"""

    client = OpenAI(api_key=load_env_api_key(), base_url="https://api.deepseek.com/v1")
    pt_new, usage = call_deepseek(client, prompt)
    pt_new = sanitize_pt_translation(pt_new.strip()).text
    pt_new, qa = validate_translation(jp_body, pt_new, sanitize=False)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "pt_retraduzido.txt").write_text(pt_new.strip() + "\n", encoding="utf-8")

    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "protocol": str(PROTOCOL.relative_to(PROJECT_ROOT)),
        "jp_path": str(JP_PATH.relative_to(PROJECT_ROOT)),
        "note": (
            "Item 9 da amostra usou pareamento zip incorreto no corpus. "
            "JP correto: 末療法の原理 (jp-1308). PT da amostra era outro artigo (Trindade, pt-0383). "
            "Par canônico: pt-0382."
        ),
        "usage": usage,
        "chars_jp": len(jp_body),
        "chars_pt_new": len(pt_new),
        "qa_ok": qa.ok,
        "qa_issues": qa.issues,
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    md = f"""# Item 9 — Retradução (protocolo com fluidez)

**Data:** {meta['timestamp'][:10]}  
**Modelo:** {MODEL}  
**Protocolo:** `protocolo_retraducao.txt`

## Contexto importante

Na amostra #9, o pipeline comparou por engano:
- **JP usado na avaliação:** 末療法の原理 (`publication-jp-1308`, Evangelho do Reino dos Céus, 1947)
- **PT do arquivo da amostra:** "Trindade dos Órgãos Internos…" (`publication-pt-0383`, Hikari, 1949) — **outro artigo**

O par canônico correto no acervo é **jp-1308 ↔ pt-0382** ("O Princípio da Terapia do Futuro").

Esta retradução parte **só do japonês** com o protocolo novo (fluidez + glossário).

---

## Japonês (fonte)

{jp_body}

---

## Português ANTES (arquivo errado da amostra #9 — Trindade)

{pt_wrong[:2000]}{"..." if len(pt_wrong) > 2000 else ""}

---

## Português CANÔNICO atual (pt-0382 — para referência)

{pt_canonical}

---

## Português RETRADUZIDO (novo protocolo)

{pt_new.strip()}

---

## Sua avaliação

| Campo | Marque |
|-------|--------|
| **humano_retraducao** | [ ] A aceito  [ ] B edição leve  [ ] C retraduzir  [ ] D mismatch |

Observações:

"""
    (OUT_DIR / "avaliacao_item09.md").write_text(md, encoding="utf-8")
    print(f"written: {OUT_DIR / 'avaliacao_item09.md'}")
    print(f"tokens: {usage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
