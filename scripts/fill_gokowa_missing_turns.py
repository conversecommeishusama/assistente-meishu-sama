#!/usr/bin/env python3
"""Traduz turnos genuinamente ausentes (placeholder [FALTANTE-CONTEUDO-JP-PENDENTE])
deixados por reconcile_gokowa_mix_segments.py, usando o protocolo e glossário
oficiais de tradução (protocolo_traducao.txt + glossario_traducao.json) — nunca
o glossário de busca. Cada turno é traduzido isoladamente com o parágrafo
vizinho como contexto, nunca em lote grande, para preservar precisão.
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

from acervo_work_paths import work_root  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from align_gokowa_jp_pt import load_jp_turns, _split_paragraphs  # noqa: E402
from run_deepseek_revision_pilot import load_env_api_key, load_glossary  # noqa: E402
from translation_protocol_core import (  # noqa: E402
    PROTOCOL_PATH,
    format_glossary_block,
    select_glossary_entries,
    call_deepseek,
    extract_prose_from_response,
)
from retranslate_qa import sanitize_pt_translation  # noqa: E402

WORK = work_root("livros_acervo")
PLACEHOLDER = "[FALTANTE-CONTEUDO-JP-PENDENTE]"
KIND_LABEL = {"interlocutor": "Interlocutor", "meishu": "Meishu-Sama"}

# Prompt minimalista para UM turno de diálogo isolado (não um artigo inteiro):
# sem cabeçalho A1-A4, sem título, sem [data] — apenas a frase traduzida.
# Usar o prompt de artigo completo (build_translate_prompt) aqui faria o
# modelo alucinar cabeçalho/título, como confirmado em teste real.
TURN_PROMPT_TMPL = """{protocol}

### TAREFA
Traduza APENAS a frase japonesa abaixo para português brasileiro, como uma
única fala de diálogo já em curso (Gokōwa-roku / Gosuiji-roku). Contexto:
é {kind_desc} dentro de uma sequência de perguntas e respostas a Meishu-Sama.

REGRAS ESTRITAS:
- NÃO inclua título, cabeçalho, data, nome de publicação, numeração ou rótulo
  "Interlocutor:"/"Meishu-Sama:" — isso já é adicionado fora desta tradução.
- NÃO invente nenhum dado (datas, números de edição, nomes) que não esteja no
  japonês abaixo.
- Devolva APENAS a tradução da frase, nada mais, sem comentários.

{glossary_block}

### FRASE JAPONESA:
{jp_text}

### TRADUÇÃO (só a frase, em português):
"""


def translate_one_turn(client, protocol: str, glossary: dict, jp_text: str, *, kind: str) -> str:
    gloss = format_glossary_block(select_glossary_entries(jp_text, glossary))
    kind_desc = "uma PERGUNTA do Interlocutor" if kind == "interlocutor" else "uma RESPOSTA de Meishu-Sama"
    prompt = TURN_PROMPT_TMPL.format(
        protocol=protocol, kind_desc=kind_desc, glossary_block=gloss, jp_text=jp_text
    )
    pt, _u = call_deepseek(client, prompt, max_tokens=2000)
    pt = extract_prose_from_response(pt)
    pt = sanitize_pt_translation(pt).text
    pt = pt.strip()
    _guard_no_header_hallucination(pt, jp_text)
    return pt


class HallucinationGuard(Exception):
    pass


_HEADER_HALLUCINATION_MARKERS = (
    "publicado em", "publicada em", "Gokōwa-roku nº", "Gosuiji-roku nº",
    "Edição nº", "Consultar a edição",
)
# "Era Showa" tem equivalente legítimo em japonês (昭和) que pode aparecer no
# turno real — checado à parte, não como marcador estritamente ausente.
_SHOWA_MARKER = "era showa"
_SHOWA_JP_EQUIV = "昭和"


def _guard_no_header_hallucination(pt_text: str, jp_text: str) -> None:
    """Detecta o padrão de falha observado em teste: o modelo, mesmo instruído
    a traduzir só a frase, às vezes gera uma linha de cabeçalho/título
    (nº de edição, data em Era Showa) que não existe no japonês de entrada.
    Estrutural: nunca aceitar conteúdo com marcador de cabeçalho ausente do
    JP fonte — é sinal de invenção, não de tradução."""
    for marker in _HEADER_HALLUCINATION_MARKERS:
        if marker.lower() in pt_text.lower() and marker.lower() not in jp_text.lower():
            raise HallucinationGuard(f"marcador de cabeçalho '{marker}' ausente do JP mas presente na tradução")
    if _SHOWA_MARKER in pt_text.lower() and _SHOWA_JP_EQUIV not in jp_text:
        raise HallucinationGuard("menção a 'Era Showa' sem equivalente 昭和 no JP fonte")


def process_file(filename: str, *, dry_run: bool = False) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=load_env_api_key(), base_url="https://api.deepseek.com/v1")
    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()

    jp = load_jp_turns(filename)
    pt_path = WORK / "pt" / filename
    pt_raw = pt_path.read_text(encoding="utf-8")
    file_pre, pt_blocks = split_file(pt_raw)
    pt_art = parse_article(pt_blocks[0])
    body = pt_art.content
    paras = _split_paragraphs(body)

    # reconstitui, na ordem, o índice do turno JP correspondente a cada
    # parágrafo de diálogo (mesma lógica de contagem posicional usada no
    # relabel — aqui só para localizar QUAL turno falta, não para rotular).
    dialogue_positions = [i for i, p in enumerate(paras) if p.startswith("Interlocutor:") or p.startswith("Meishu-Sama:")]
    if len(dialogue_positions) != len(jp):
        return {"file": filename, "status": "count_mismatch", "pt_dialogue": len(dialogue_positions), "jp_turns": len(jp)}

    filled = 0
    fills: list[dict] = []
    for para_i, jp_i in zip(dialogue_positions, range(len(jp))):
        para = paras[para_i]
        if PLACEHOLDER not in para:
            continue
        label = "Interlocutor" if para.startswith("Interlocutor:") else "Meishu-Sama"
        kind = "interlocutor" if label == "Interlocutor" else "meishu"
        jp_text = jp[jp_i].text
        try:
            pt_new = translate_one_turn(client, protocol, glossary, jp_text, kind=kind)
        except HallucinationGuard as exc:
            fills.append({"jp_idx": jp_i, "jp_text": jp_text, "status": "rejected", "reason": str(exc)})
            time.sleep(0.2)
            continue
        paras[para_i] = f"{label}: {pt_new}"
        fills.append({"jp_idx": jp_i, "jp_text": jp_text, "pt_new": pt_new, "status": "ok"})
        filled += 1
        time.sleep(0.2)

    new_body = "\n\n".join(paras)
    pre = [f"{k}: {v}" for k, v in pt_art.fields.items()] + ["---"]
    block = "\n".join(pre)
    if pt_art.meta:
        block += "\n" + pt_art.meta + "\n\n"
    else:
        block += "\n\n"
    block += new_body.strip() + "\n"
    from acervo_work_paths import article_sep

    out = file_pre.rstrip() + f"\n{article_sep()}\n" + block

    if not dry_run:
        pt_path.write_text(out, encoding="utf-8")

    rejected = [f for f in fills if f.get("status") == "rejected"]
    return {"file": filename, "status": "ok", "filled": filled, "rejected": len(rejected), "fills": fills}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()
    for fn in args.file:
        r = process_file(fn, dry_run=args.dry_run)
        fills = r.pop("fills", [])
        print(json.dumps(r, ensure_ascii=False))
        for f in fills:
            if f.get("status") == "rejected":
                print("  REJECTED:", f["jp_idx"], f["reason"], f["jp_text"][:40])
            elif args.show:
                print(f"  [{f['jp_idx']}] JP: {f['jp_text']}")
                print(f"        PT: {f['pt_new']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
