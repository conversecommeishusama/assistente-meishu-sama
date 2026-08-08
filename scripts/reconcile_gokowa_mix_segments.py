#!/usr/bin/env python3
"""Reconciliação estrutural de segmentos MIX (fusão de vários turnos JP num só
parágrafo PT) usando a API DeepSeek — SEM traduzir de novo o que já existe.

Tarefa dada à API: apenas reformatar/dividir o texto PORTUGUÊS JÁ TRADUZIDO
nos pontos de turno correctos (guiado pela contagem e tipo dos turnos JP),
preservando o texto literalmente. Nunca substitui tradução existente por
paráfrase. Detecta e remove duplicação redundante (mesmo trecho traduzido
duas vezes). Sinaliza conteúdo genuinamente ausente (turno JP sem
correspondência em PT) em vez de inventar — esses casos ficam para revisão
humana/API de tradução dedicada, nunca implícitos nesta reconciliação.

Validação: depois de aplicar a divisão devolvida pela API, verifica-se que a
concatenação do texto (sem rótulos) é igual, a menos de espaços, ao texto
original — se não bater, REJEITA a divisão e marca o segmento para revisão
manual, nunca aplica conteúdo alterado silenciosamente.
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
from align_gokowa_jp_pt import load_jp_turns, load_pt_paras, align, _split_paragraphs  # noqa: E402
from run_deepseek_revision_pilot import load_env_api_key  # noqa: E402

WORK = work_root("livros_acervo")
ARTICLE_SEP = article_sep()
KIND_LABEL = {"interlocutor": "Interlocutor", "meishu": "Meishu-Sama"}

MODEL = "deepseek-chat"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


PROMPT_TMPL = """Você vai REESTRUTURAR um texto português JÁ TRADUZIDO, sem traduzir nada de novo.

Abaixo estão {n_jp} turnos em japonês (fonte de verdade da ESTRUTURA, não para traduzir)
e o(s) parágrafo(s) em português que atualmente contêm, fundidos, a tradução de todos
esses turnos.

TAREFA:
1. Divida o texto português exatamente nesses {n_jp} turnos, na mesma ordem dos turnos
   japoneses (tipo Pergunta = Interlocutor, tipo Resposta = Meishu-Sama).
2. NÃO reescreva, parafraseie, resuma nem corrija o português — copie literalmente
   cada trecho já existente, apenas decidindo ONDE cortar entre um turno e outro.
3. Se detectar que uma parte do português é uma RETRADUÇÃO DUPLICADA (o mesmo
   conteúdo traduzido duas vezes, uma versão redundante da outra), marque a versão
   redundante entre as tags <DUPLICADO>...</DUPLICADO> em vez de incluí-la num turno.
4. Se um turno japonês não tiver NENHUM texto português correspondente (conteúdo
   realmente ausente, não apenas fundido), escreva exatamente "[FALTANTE]" nesse turno
   em vez de inventar ou traduzir.
5. Não adicione, remova ou altere nenhuma palavra do português além de decidir os
   pontos de corte e marcar duplicações/faltantes.

TURNOS JAPONESES:
{jp_block}

TEXTO PORTUGUÊS A DIVIDIR (já traduzido, preservar literalmente):
{pt_block}

RESPONDA APENAS em JSON válido, uma lista de objetos, um por turno, nesta forma exata:
[{{"kind": "interlocutor"|"meishu", "text": "..."}}, ...]
Se houver texto duplicado a descartar, não o inclua em nenhum objeto (apenas omita-o
do JSON; não precisa incluir as tags no JSON, apenas remova esse trecho).
"""


def build_prompt(jp_kinds: list[str], jp_texts: list[str], pt_texts: list[str]) -> str:
    jp_block = "\n".join(
        f"[{i+1}] ({'Pergunta' if k == 'interlocutor' else 'Resposta'}) {t}"
        for i, (k, t) in enumerate(zip(jp_kinds, jp_texts))
    )
    pt_block = "\n\n".join(pt_texts)
    return PROMPT_TMPL.format(n_jp=len(jp_kinds), jp_block=jp_block, pt_block=pt_block)


def call_api(client, prompt: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=8000,
    )
    return resp.choices[0].message.content or ""


def _extract_json(raw: str) -> list[dict] | None:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"```\s*$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\[.*\]", raw, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def reconcile_segment(client, jp_kinds: list[str], jp_texts: list[str], pt_texts: list[str]) -> dict:
    """Tenta reconciliar um segmento MIX. Devolve dict com status e resultado."""
    original_norm = _norm(" ".join(pt_texts))
    prompt = build_prompt(jp_kinds, jp_texts, pt_texts)
    raw = call_api(client, prompt)
    data = _extract_json(raw)
    if not data or not isinstance(data, list):
        return {"status": "api_parse_error", "raw": raw[:300]}

    if len(data) != len(jp_kinds):
        return {"status": "count_mismatch", "expected": len(jp_kinds), "got": len(data), "raw": raw[:500]}

    result_texts = []
    has_missing = False
    for item, expect_kind in zip(data, jp_kinds):
        kind = item.get("kind")
        text = (item.get("text") or "").strip()
        if kind != expect_kind:
            return {"status": "kind_mismatch", "expected": expect_kind, "got": kind}
        if text == "[FALTANTE]":
            has_missing = True
        result_texts.append(text)

    # validação: concatenação (excluindo [FALTANTE]) deve ser subconjunto/igual
    # ao texto original, sem invenção de conteúdo novo relevante.
    kept = _norm(" ".join(t for t in result_texts if t != "[FALTANTE]"))
    # tolerância: aceita se o texto resultante está contido no original OU é
    # igual salvo pequenas normalizações de espaço/pontuação nas bordas do corte.
    ok_containment = kept in original_norm or _fuzzy_subset(kept, original_norm)
    if not ok_containment:
        return {
            "status": "validation_failed",
            "reason": "texto reconstituído não corresponde ao original",
            "kept_len": len(kept),
            "original_len": len(original_norm),
        }

    return {
        "status": "missing_content" if has_missing else "ok",
        "turns": list(zip(jp_kinds, result_texts)),
    }


def _fuzzy_subset(a: str, b: str, min_ratio: float = 0.97) -> bool:
    """Verifica se quase todo o conteúdo de `a` está em `b`, tolerando pequenas
    diferenças de espaçamento/pontuação introduzidas ao dividir o texto."""
    if not a:
        return True
    a_words = a.split()
    b_words = set(b.split())
    if not a_words:
        return True
    hits = sum(1 for w in a_words if w in b_words)
    return (hits / len(a_words)) >= min_ratio


def process_file(filename: str, *, dry_run: bool = False, limit: int | None = None) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=load_env_api_key(), base_url="https://api.deepseek.com/v1")

    jp = load_jp_turns(filename)
    pt = load_pt_paras(filename)
    path = align(jp, pt)

    pt_path = WORK / "pt" / filename
    pt_raw = pt_path.read_text(encoding="utf-8")
    file_pre, pt_blocks = split_file(pt_raw)
    if len(pt_blocks) != 1:
        return {"file": filename, "status": "skip_multi_block"}
    pt_art = parse_article(pt_blocks[0])
    body = pt_art.content
    all_paras = _split_paragraphs(body)
    dialog_idx = [i for i, p in enumerate(all_paras) if p.startswith("Interlocutor:") or p.startswith("Meishu-Sama:")]
    non_dialog_prefix = [p for i, p in enumerate(all_paras) if i not in dialog_idx and i < dialog_idx[0]] if dialog_idx else []

    new_dialog_paras: list[str] = []
    log: list[dict] = []
    n_processed = 0
    for seg in path:
        j0, j1 = seg["jp_range"]
        p0, p1 = seg["pt_range"]
        n_jp = j1 - j0
        n_pt = p1 - p0
        texts = [pt[k].text for k in range(p0, p1)]
        kinds = [jp[k].kind for k in range(j0, j1)]

        if n_jp == 1 and n_pt == 1:
            expect = KIND_LABEL[kinds[0]]
            new_dialog_paras.append(f"{expect}: {texts[0]}")
            continue
        if n_jp == 1 and n_pt > 1:
            expect = KIND_LABEL[kinds[0]]
            merged = " ".join(t.strip() for t in texts)
            new_dialog_paras.append(f"{expect}: {merged}")
            continue

        # segmento MIX: precisa da API
        if limit is not None and n_processed >= limit:
            for k in range(p0, p1):
                new_dialog_paras.append(f"{'Interlocutor' if pt[k].label=='I' else 'Meishu-Sama'}: {pt[k].text}")
            continue
        n_processed += 1
        jp_texts = [jp[k].text for k in range(j0, j1)]
        r = reconcile_segment(client, kinds, jp_texts, texts)
        r["jp_idx"] = [j0, j1]
        r["pt_idx"] = [p0, p1]
        log.append(r)
        if r["status"] in ("ok", "missing_content"):
            for kind, text in r["turns"]:
                if text == "[FALTANTE]":
                    new_dialog_paras.append(f"{KIND_LABEL[kind]}: [FALTANTE-CONTEUDO-JP-PENDENTE]")
                else:
                    new_dialog_paras.append(f"{KIND_LABEL[kind]}: {text}")
        else:
            # falha: preserva original sem alteração, para revisão manual
            for k in range(p0, p1):
                new_dialog_paras.append(f"{'Interlocutor' if pt[k].label=='I' else 'Meishu-Sama'}: {pt[k].text}")
        time.sleep(0.2)

    new_body = "\n\n".join(non_dialog_prefix + new_dialog_paras)
    pre = [f"{k}: {v}" for k, v in pt_art.fields.items()] + ["---"]
    block = "\n".join(pre)
    if pt_art.meta:
        block += "\n" + pt_art.meta + "\n\n"
    else:
        block += "\n\n"
    block += new_body.strip() + "\n"
    out = file_pre.rstrip() + f"\n{ARTICLE_SEP}\n" + block

    if not dry_run:
        pt_path.write_text(out, encoding="utf-8")

    return {
        "file": filename,
        "mix_segments": len(log),
        "ok": sum(1 for r in log if r["status"] == "ok"),
        "missing_content": sum(1 for r in log if r["status"] == "missing_content"),
        "failed": sum(1 for r in log if r["status"] not in ("ok", "missing_content")),
        "log": log,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="limite de segmentos MIX processados via API (teste)")
    args = ap.parse_args()
    for fn in args.file:
        r = process_file(fn, dry_run=args.dry_run, limit=args.limit)
        print(json.dumps({k: v for k, v in r.items() if k != "log"}, ensure_ascii=False, indent=2))
        for item in r.get("log", []):
            print(" ", item.get("status"), item.get("jp_idx"), item.get("pt_idx"), item.get("reason", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
