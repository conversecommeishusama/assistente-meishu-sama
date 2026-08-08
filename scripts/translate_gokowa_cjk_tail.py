#!/usr/bin/env python3
"""Traduz turnos de diálogo (Interlocutor:/Meishu-Sama:) que ainda contêm
japonês não traduzido — achado sistémico: alguns ficheiros Gokōwa-roku têm
uma secção inteira nunca traduzida (ex.: nº17, ~70 turnos finais, incluindo
o "编輯後記"/posfácio editorial). Usa protocolo_traducao.txt + glossario_
traducao.json (nunca o glossário de busca), em lotes JSON para eficiência,
preservando rótulo e ordem — não reestrutura nada, só traduz.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root, article_sep  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from align_gokowa_jp_pt import _split_paragraphs  # noqa: E402
from run_deepseek_revision_pilot import load_env_api_key, load_glossary  # noqa: E402
from translation_protocol_core import (  # noqa: E402
    PROTOCOL_PATH,
    format_glossary_block,
    select_glossary_entries,
    call_deepseek,
    _contains_cjk,
)

WORK = work_root("livros_acervo")
BATCH_SIZE = 8

PROMPT_TMPL = """{protocol}

### TAREFA
Traduza os turnos de diálogo japoneses abaixo (Gokōwa-roku) para português
brasileiro, um a um, respeitando o glossário e o protocolo acima. Cada turno é
uma fala isolada (pergunta do Interlocutor ou resposta de Meishu-Sama) dentro
de uma sequência já em curso — traduza cada um pelo seu conteúdo, sem
adicionar cabeçalho, título, numeração de edição ou comentário.

{glossary_block}

### TURNOS (JSON de entrada):
{turns_json}

RESPONDA APENAS em JSON válido: uma lista de strings, na MESMA ordem e
MESMA quantidade dos turnos de entrada, cada uma a tradução em português do
turno correspondente, nada mais.
"""


def _extract_json_list(raw: str) -> list[str] | None:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"```\s*$", "", raw)
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        m = re.search(r"\[.*\]", raw, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
                if isinstance(data, list):
                    return data
            except Exception:
                return None
    return None


def translate_batch(client, protocol: str, glossary: dict, jp_texts: list[str]) -> list[str] | None:
    haystack = "\n".join(jp_texts)
    gloss = format_glossary_block(select_glossary_entries(haystack, glossary))
    turns_json = json.dumps(jp_texts, ensure_ascii=False, indent=1)
    prompt = PROMPT_TMPL.format(protocol=protocol, glossary_block=gloss, turns_json=turns_json)
    raw, _u = call_deepseek(client, prompt, max_tokens=4000)
    result = _extract_json_list(raw)
    if result is None or len(result) != len(jp_texts):
        return None
    return [str(x).strip() for x in result]


def process_file(filename: str, *, dry_run: bool = False) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=load_env_api_key(), base_url="https://api.deepseek.com/v1")
    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()

    pt_path = WORK / "pt" / filename
    raw = pt_path.read_text(encoding="utf-8")
    file_pre, blocks = split_file(raw)
    art = parse_article(blocks[0])
    body = art.content
    paras = _split_paragraphs(body)

    cjk_idx = [i for i, p in enumerate(paras) if _contains_cjk(p)]
    if not cjk_idx:
        return {"file": filename, "status": "no_cjk"}

    n_translated = 0
    n_failed = 0
    i = 0
    while i < len(cjk_idx):
        batch_idx = cjk_idx[i : i + BATCH_SIZE]
        labels = []
        jp_texts = []
        for idx in batch_idx:
            p = paras[idx]
            if p.startswith("Interlocutor:"):
                labels.append("Interlocutor")
                jp_texts.append(p[len("Interlocutor:") :].strip())
            elif p.startswith("Meishu-Sama:"):
                labels.append("Meishu-Sama")
                jp_texts.append(p[len("Meishu-Sama:") :].strip())
            else:
                labels.append(None)
                jp_texts.append(p.strip())
        result = translate_batch(client, protocol, glossary, jp_texts)
        if result is None:
            n_failed += len(batch_idx)
            i += BATCH_SIZE
            time.sleep(0.3)
            continue
        for idx, label, pt_text in zip(batch_idx, labels, result):
            if _contains_cjk(pt_text):
                n_failed += 1
                continue
            paras[idx] = f"{label}: {pt_text}" if label else pt_text
            n_translated += 1
        i += BATCH_SIZE
        time.sleep(0.3)

    new_body = "\n\n".join(paras)
    pre = [f"{k}: {v}" for k, v in art.fields.items()] + ["---"]
    block = "\n".join(pre)
    if art.meta:
        block += "\n" + art.meta + "\n\n"
    else:
        block += "\n\n"
    block += new_body.strip() + "\n"
    out = file_pre.rstrip() + f"\n{article_sep()}\n" + block

    if not dry_run:
        pt_path.write_text(out, encoding="utf-8")

    return {
        "file": filename,
        "status": "ok",
        "cjk_paragraphs_found": len(cjk_idx),
        "translated": n_translated,
        "failed": n_failed,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for fn in args.file:
        r = process_file(fn, dry_run=args.dry_run)
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
