#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Revisão em ondas de 『伝導の手引』 I/II — leitura paralela JP ↔ PT.

Método do projecto (HANDOFF_LIVRO_1947_EVANGELHO §4): rondas **R** (auditoria)
→ **M** (correcção), repetidas até convergir. Aqui cada ronda faz as duas
coisas na mesma chamada, bloco a bloco:

  * recebe pares (japonês, português) de um item, na ordem do original;
  * devolve, para cada par, `ok` ou a correcção integral do bloco + motivo;
  * a correcção é validada (sem CJK, sem 『』「」, rótulos de fala, razão PT/JP)
    antes de substituir o texto;
  * cada ronda grava um relatório em `reports/traducao_dendo/revisao/`.

A revisão é feita **linha a linha** (§6.2): nenhum bloco é aprovado por
amostragem, ratio ou contagem de parágrafos.

Uso:
    .venv/bin/python scripts/revisar_dendo.py --vol 1 --ronda R1 --workers 6
    .venv/bin/python scripts/revisar_dendo.py --vol 1 --ronda R2 --workers 6
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

from retraducao_completa_gokowa import MODELO  # noqa: E402
from traduzir_dendo import (  # noqa: E402
    CONTEXTO, CJK_RE, MARCA_JP_RE, MODELO_TRAD, glossario_relevante,
)

OUT = RAIZ / "reports" / "traducao_dendo"
REV = OUT / "revisao"
LIMITE_LOTE = 2400
TIMEOUT_API = 300.0
MAX_TOKENS = 12000
TEMPERATURA = 0.1

ALTA = {"glossario", "sentido", "estrutura", "data_formato"}
MEDIA = {"gramatica", "fluidez"}

PROMPT_REVISAO = """Você é o REVISOR TRADUTOLÓGICO do projecto Goshinsho (JP → PT-BR), no modo REVISÃO PÓS-TRADUÇÃO do protocolo (§6.2): leitura PARALELA, LINHA A LINHA.

{contexto}

GLOSSÁRIO OBRIGATÓRIO (termo japonês → forma única):
{glossario}

TAREFA — para CADA item da entrada (um par japonês ↔ português, na ordem do original):
1. Leia o japonês como fonte de verdade semântica.
2. Leia o português correspondente.
3. Verifique, um por um:
   □ fidelidade: nada omitido, nada acrescentado, mesma ordem das ideias;
   □ glossário: toda forma portuguesa é a forma fixada (inclusive nos títulos);
   □ nenhum kanji/hiragana/katakana, nenhum 『』「」;
   □ rótulos de fala: `Interlocutor:` (ou `Nome:`) na pergunta; `Meishu-Sama:`
     no início da resposta; `continuacao` sem rótulo; discurso sem rótulo;
   □ português correcto (concordância, regência, pontuação, maiúsculas);
   □ calques japoneses que o português natural corrige sem mudar o sentido.

ERROS TÍPICOS A PROCURAR (achados reais deste acervo):
- `Meishu-sama` (errado) → `Meishu-Sama`;
- `linha espiritual` → `elo espiritual`; `purificação espiritual` genérica →
  `Johrei`; `Hinayana`/`Mahayana` → `Shojo`/`Daijo`;
- 御神体 traduzido como `objeto de culto`, `talismã`, `corpo divino` →
  `Imagem da Luz Divina`;
- `Divindade maligna` / `Divindades malignas` / `Espírito maligno` — grafia do
  acervo com MAIÚSCULA (não "divindade maligna"); 邪神/邪霊 formando composto
  com outro termo contam como parte dele;
- nomes de obras com grafia fixa: `Gosuiji-roku`, `Gokōwa-roku`, `Mioshie-shū`,
  `Eikō`, `Kyusei`; nomes divinos: `Komyo-Nyorai`, `Kannon`, `Byōbu Kannon`,
  `Miroku Ōkami`, `Ryūjin`;
- `Chieshōkaku` (智慧証覚): na 1.ª menção de cada artigo, com a glosa
  `(Inteligência da Percepção Verdadeira)`; depois só `Chieshōkaku`;
- títulos numerados: manter a numeração do original (１ → 1.), sem inventar;
- frases passivas artificiais, repetições desnecessárias, `o mesmo`, `aquilo
  de` (calque de あれ) — corrigir só se o sentido não mudar.
4. Se o português cumpre tudo, devolva `{{"i":<id>,"ok":true}}`.
   Se viola algo, devolva a correcção INTEGRAL do bloco, com o mínimo de
   alterações necessárias:
   {{"i":<id>,"ok":false,"pt":"<bloco corrigido>","tipo":"glossario|sentido|estrutura|gramatica|fluidez|data_formato","motivo":"<curto>"}}
5. NÃO reescreva por gosto estilístico; NÃO resuma; NÃO junte nem divida
   blocos. Na dúvida, mantenha (`ok: true`).
6. Blocos que começam por 〔 são fichas de fonte já convertidas: NÃO os altere.

ENTRADA (JSON):
{entrada}

Responda APENAS com JSON válido, sem markdown:
{{"itens":[...]}}
"""


def _cliente():
    from goshinsho.services.agentic_search import _client
    return _client()


def _json(raw: str) -> dict | None:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    ini, fim = raw.find("{"), raw.rfind("}")
    if ini < 0 or fim <= ini:
        return None
    try:
        return json.loads(raw[ini:fim + 1])
    except Exception:  # noqa: BLE001
        return None


def pedir_revisao(pares: list[dict], vol: int) -> dict[str, dict]:
    texto = "\n".join(p["jp"] + "\n" + p["pt"] for p in pares)
    entrada = json.dumps({"itens": pares}, ensure_ascii=False)
    prompt = PROMPT_REVISAO.format(
        contexto=CONTEXTO.format(romano="I" if vol == 1 else "II"),
        glossario=glossario_relevante(texto + " " + entrada),
        entrada=entrada)
    resp = _cliente().with_options(timeout=TIMEOUT_API).chat.completions.create(
        model=MODELO_TRAD, max_tokens=MAX_TOKENS, temperature=TEMPERATURA,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    d = _json(resp.choices[0].message.content or "")
    if not d or "itens" not in d:
        return {}
    return {str(it["i"]): it for it in d["itens"]
            if isinstance(it, dict) and "i" in it}


def aceitar(novo: str, jp: str, papel: str) -> bool:
    if not novo or len(re.sub(r"\s", "", novo)) < 2:
        return False
    if CJK_RE.search(novo) or MARCA_JP_RE.search(novo):
        return False
    if papel == "interlocutor" and not re.match(r"^[A-ZÀ-Ú][^:]{0,40}:", novo):
        return False
    if papel == "mestre_inicio" and not novo.startswith("Meishu-Sama:"):
        return False
    if papel != "titulo" and len(jp) >= 60:
        r = len(novo) / max(1, len(jp))
        if r < 0.8 or r > 4.6:
            return False
    return True


def lotes(itens: list[dict]) -> list[list[dict]]:
    out, buf, tam = [], [], 0
    for it in itens:
        if buf and tam + len(it["jp"]) + len(it["pt"]) > LIMITE_LOTE:
            out.append(buf)
            buf, tam = [], 0
        buf.append(it)
        tam += len(it["jp"]) + len(it["pt"])
    if buf:
        out.append(buf)
    return out


def revisar_unidade(caminho: Path, vol: int) -> tuple[list[dict], int]:
    d = json.loads(caminho.read_text(encoding="utf-8"))
    pares: list[dict] = []
    if d.get("titulo_pt"):
        pares.append({"i": "T", "jp": d["titulo_jp"], "pt": d["titulo_pt"],
                      "papel": "titulo"})
    for n, b in enumerate(d["blocos"]):
        if b["jp"].strip().startswith("〔") or not b["pt"]:
            continue
        pares.append({"i": str(n), "jp": b["jp"], "pt": b["pt"],
                      "papel": b.get("papel", "discurso")})
    if not pares:
        return [], 0

    achados: list[dict] = []
    alterados = 0
    for lote in lotes(pares):
        resposta: dict[str, dict] = {}
        ultimo_erro = ""
        for tentativa in range(4):
            try:
                resposta = pedir_revisao(lote, vol)
                ultimo_erro = ""
            except Exception as e:  # noqa: BLE001
                ultimo_erro = str(e)
                resposta = {}
            if len(resposta) >= len(lote):
                break
            time.sleep(1 + tentativa * 2)
        if not resposta:
            # lote inteiro sem revisão: registar UMA vez, com o nº de blocos
            achados.append({"i": "lote", "tipo": "lote_falhou",
                            "motivo": ultimo_erro[:160],
                            "blocos": len(lote)})
            continue
        for p in lote:
            r = resposta.get(p["i"])
            if not r or r.get("ok"):
                continue
            novo = str(r.get("pt") or "").strip()
            if not aceitar(novo, p["jp"], p["papel"]):
                achados.append({"i": p["i"], "tipo": "correcao_invalida",
                                "motivo": r.get("motivo", ""),
                                "pt_proposto": novo[:200]})
                continue
            if novo == p["pt"]:
                continue
            if p["i"] == "T":
                d["titulo_pt"] = novo
            else:
                d["blocos"][int(p["i"])]["pt"] = novo
            alterados += 1
            achados.append({"i": p["i"], "tipo": r.get("tipo", "sentido"),
                            "motivo": r.get("motivo", ""),
                            "antes": p["pt"][:300], "depois": novo[:300]})

    if alterados:
        d.setdefault("revisoes", []).append({
            "data": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "alterados": alterados,
        })
        caminho.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
    return achados, alterados


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", type=int, choices=(1, 2), required=True)
    ap.add_argument("--ronda", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--so", help="apenas a unidade com este uid")
    args = ap.parse_args()

    pasta = OUT / "itens" / f"dendo{args.vol}"
    arquivos = sorted(p for p in pasta.glob("*.json") if ".bak" not in p.name)
    if args.so:
        arquivos = [p for p in arquivos if p.stem == args.so]

    print(f"vol {args.vol} | {args.ronda} | unidades={len(arquivos)} "
          f"| workers={args.workers}\n")
    todos: list[dict] = []
    total_alt = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futuros = {pool.submit(revisar_unidade, p, args.vol): p for p in arquivos}
        for fut in as_completed(futuros):
            p = futuros[fut]
            try:
                achados, alt = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"[EXCECAO] {p.stem}: {e}", flush=True)
                continue
            total_alt += alt
            for a in achados:
                todos.append(dict(a, uid=p.stem))
            if achados:
                print(f"[{p.stem}] achados={len(achados)} corrigidos={alt}",
                      flush=True)

    por_tipo: dict[str, int] = {}
    for a in todos:
        t = a.get("tipo", "erro_api")
        por_tipo[t] = por_tipo.get(t, 0) + 1
    altas = sum(v for k, v in por_tipo.items() if k in ALTA)
    medias = sum(v for k, v in por_tipo.items() if k in MEDIA)

    REV.mkdir(parents=True, exist_ok=True)
    destino = REV / f"dendo{args.vol}_{args.ronda}.json"
    destino.write_text(json.dumps({
        "vol": args.vol, "ronda": args.ronda,
        "data": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "unidades": len(arquivos), "achados": len(todos),
        "correcoes": total_alt, "por_tipo": por_tipo,
        "alta": altas, "media": medias,
        "detalhe": todos,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"\n{args.ronda}: achados={len(todos)} | correcções={total_alt} "
          f"| alta={altas} | média={medias}")
    print("  por tipo:", por_tipo)
    print(f"  relatório -> {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
