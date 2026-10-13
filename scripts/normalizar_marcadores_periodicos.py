#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normaliza os marcadores de pergunta/resposta dos artigos de periódico.

Problema (achado da auditoria R2): o par japonês （お伺）／（御垂示） é uniforme,
mas o português alterna entre dezenas de formas, com parênteses de meia e de
largura total, negrito, e nomes diferentes:

  pergunta: (Pergunta) （Pergunta） **(Pergunta)** **Pergunta:** (Consulta)
            (Indagação) …
  resposta: (Instrução Divina) (Orientação Divina) (Orientação) (Revelação
            Divina) (Instrução de Meishu-Sama) (Ensinamento) …

Convenção do acervo (verificada em `textos_leitura_colaborativa/`, que o app lê,
e nos livros): **pergunta = `(Pergunta)`, resposta = `(Resposta Divina)`**.

Método: só se normaliza uma linha quando a linha INTEIRA é um marcador. Antes de
gravar, valida-se que o número final de `(Pergunta)` e `(Resposta Divina)`
coincide com o número de `（お伺）` e `（御垂示）` no japonês — artigo que não
valide é ignorado e reportado (evita tocar em diálogos com falantes nomeados).

Uso:  .venv/bin/python scripts/normalizar_marcadores_periodicos.py [--aplicar]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_auditoria"

CANON_Q = "(Pergunta)"
CANON_A = "(Resposta Divina)"

PERGUNTA = r"(?:Pergunta|Consulta|Indagação|Inquirição|Question)"
RESPOSTA = (r"(?:Instrução Divina|Instrução de Meishu-Sama|Instrução|"
            r"Orientação Divina|Orientação|Revelação Divina|Revelação|"
            r"Ensinamento Divino|Ensinamento|Resposta Divina|"
            r"Resposta de Meishu-Sama|Resposta)")

# linha inteira = marcador. Aceita: parênteses de meia/largura total, negrito
# markdown, dois pontos, e a forma sem parênteses (ex.: `**Pergunta:**`).
RE_MARCADOR = re.compile(
    rf"^\s*\*{{0,2}}(?:[\(\uff08]\s*)?(?P<nome>{PERGUNTA}|{RESPOSTA})"
    rf"\s*(?:[\)\uff09])?\s*:?\s*\*{{0,2}}$"
)

# Marcador em qualquer posição: parentetizado, em negrito, ou precedido de quebra
# de linha. Serve para o separar quando vem colado ao texto (ex.: `(Pergunta) — …`
# ou `… está correta. (Indagação) Em relação…`).
RE_INLINE = re.compile(
    rf"(?:[\(\uff08]\s*(?:{PERGUNTA}|{RESPOSTA})\s*[\)\uff09]"
    rf"|\*\*\s*(?:{PERGUNTA}|{RESPOSTA})\s*\*\*\s*:?"
    rf"|^[ \t]*(?:{PERGUNTA}|{RESPOSTA})\s*:)",
    re.MULTILINE,
)


def _classificar(nome: str) -> str:
    return CANON_Q if re.fullmatch(PERGUNTA, nome.strip()) else CANON_A


UPPER = re.compile(
    r"^[ \t]*(?P<nome>CONSULTA|PERGUNTA|INSTRUÇÃO DIVINA|RESPOSTA DIVINA)"
    r"[ \t]*:?[ \t]*$",
    re.MULTILINE,
)
UPPER_MAP = {
    "CONSULTA": CANON_Q, "PERGUNTA": CANON_Q,
    "INSTRUÇÃO DIVINA": CANON_A, "RESPOSTA DIVINA": CANON_A,
}


def normalizar(texto: str) -> tuple[str, int, int]:
    # 0) formas em maiúsculas usadas em alguns relatos (CONSULTA /
    #    INSTRUÇÃO DIVINA) → forma parentetizada canónica
    texto = UPPER.sub(lambda m: UPPER_MAP[m.group("nome")], texto)
    # 1) separar todos os marcadores em linha própria
    novo = RE_INLINE.sub(lambda m: f"\n\n{m.group(0).strip()}\n\n", texto)
    # 2) canonicalizar as linhas que são só marcador
    linhas = novo.split("\n")
    nq = na = 0
    for i, linha in enumerate(linhas):
        m = RE_MARCADOR.match(linha)
        if not m:
            continue
        canon = _classificar(m.group("nome"))
        linhas[i] = canon
        nq += canon == CANON_Q
        na += canon == CANON_A
    novo = "\n".join(linhas)
    # 3) colapsar linhas em branco repetidas
    novo = re.sub(r"\n{3,}", "\n\n", novo)
    return novo.strip() + "\n", nq, na


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    alterados: dict[str, dict] = {}
    pulados: list[str] = []
    tot_q = tot_a = 0

    for f in sorted(ITENS.glob("*.json")):
        if f.name.startswith("."):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        jp = d.get("texto_jp") or ""
        jq = len(re.findall(r"（お伺）", jp))
        ja = len(re.findall(r"（御垂示）", jp))
        if not (jq or ja):
            continue

        novo, nq, na = normalizar(d.get("texto_pt") or "")
        falhas = []
        if nq != jq:
            falhas.append(f"perguntas PT={nq} JP={jq}")
        if na != ja:
            falhas.append(f"respostas PT={na} JP={ja}")
        if falhas:
            pulados.append(f"{f.stem}: {', '.join(falhas)}")
            continue
        if novo == (d.get("texto_pt") or ""):
            continue
        d["texto_pt"] = novo
        d.setdefault("reparos", []).append(
            {"tipo": "normalizar_marcadores", "data": stamp}
        )
        alterados[f.stem] = d
        tot_q += nq
        tot_a += na

    print(f"artigos normalizados: {len(alterados)} | "
          f"perguntas: {tot_q} | respostas: {tot_a}")
    if pulados:
        print(f"\nNÃO normalizados ({len(pulados)}) — contagem divergente do JP:")
        for p in pulados:
            print("   ", p)

    if args.aplicar and alterados:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        for nome, d in alterados.items():
            arq = ITENS / f"{nome}.json"
            shutil.copy2(arq, BACKUPS / f"{nome}_marc_r3_{stamp}.json")
            arq.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
        print(f"gravados {len(alterados)} ficheiros")
    elif args.aplicar:
        print("nada a alterar")
    else:
        print("(dry-run; use --aplicar para gravar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
