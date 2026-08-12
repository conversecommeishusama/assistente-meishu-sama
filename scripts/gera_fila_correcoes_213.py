#!/usr/bin/env python3
"""Gera a fila de correção dos 213 (CORRECOES_213_QUEUE.json) a partir de
CORRECOES_213_PROPOSTAS.json, respeitando o que já foi aplicado.

O item da fila é "ARQUIVO|ARTIGO|?|?" (mesmo formato do AUDITORIA_QUEUE).
Casos já processados (gravados ou verificados como já-corretos) vão para done.

Uso:
    python3 scripts/gera_fila_correcoes_213.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
R = RAIZ / "reports/varredura_padronizacao"
FONTE_CASOS = R / "CORRECOES_213_PROPOSTAS.json"
FILA = R / "CORRECOES_213_QUEUE.json"


def obra_para_arquivo(obra: str) -> str | None:
    """Mapeia o campo 'obra' do JSON para o nome real do arquivo .txt."""
    nome = re.sub(r"^\d{8}-", "", obra)
    # candidatos diretos
    for d in ["livros_publicacao_pt_revisado", "reports/livros_trabalho/pt"]:
        cand = Path(d) / f"{nome}.txt"
        if cand.exists():
            return cand.name
    # busca por nome (sem data)
    for f in (RAIZ / "livros_publicacao_pt_revisado").glob("*.txt"):
        b = f.name
        if b == nome + ".txt" or b.endswith("_" + nome + ".txt"):
            return b
    for f in (RAIZ / "livros_publicacao_pt_revisado").glob("*.txt"):
        if nome in f.name:
            return f.name
    return None


def casos_aplicados() -> set[str]:
    """Lê o registro de progresso manual para saber quais casos já foram feitos."""
    prog = R / "PROGRESSO_CORRECOES_MANUAIS.md"
    if not prog.exists():
        return set()
    STATUS = (
        "GRAVADO",
        "sem ação",
        "já correto",
        "já-correto",
        "REJEITADA",
        "DUVIDA",
        "DÚVIDA",
    )
    aplicados = set()
    # bloco = linha da tabela ("| N | ... | ✅ GRAVADO |") OU o tópico em prosa
    # usado a partir do caso 30 ("- **Caso 41** (obra, art. N): ... GRAVADO."),
    # que se estende por várias linhas até o próximo tópico de caso.
    caso_atual: int | None = None
    bloco: list[str] = []

    def fecha() -> None:
        if caso_atual is not None and any(s in "\n".join(bloco) for s in STATUS):
            aplicados.add(caso_atual)

    for line in prog.read_text(encoding="utf-8").splitlines():
        m_tab = re.match(r"\|\s*(\d+)\s*\|", line)
        m_top = re.match(r"-\s*\*\*Casos?\s+(\d+)\*\*", line)
        if m_tab:
            fecha()
            caso_atual, bloco = int(m_tab.group(1)), [line]
            fecha()
            caso_atual, bloco = None, []
        elif m_top:
            fecha()
            caso_atual, bloco = int(m_top.group(1)), [line]
        elif caso_atual is not None:
            bloco.append(line)
    fecha()
    return aplicados


def main() -> None:
    casos = json.loads(FONTE_CASOS.read_text(encoding="utf-8"))
    aplicados = casos_aplicados()
    print(f"casos totais: {len(casos)}; já processados (progresso): {len(aplicados)}")

    # A fila em disco é a memória do laço: um item que já saiu para `done` NUNCA
    # pode voltar a `pending` só porque o registro em prosa não foi reconhecido
    # aqui (isso já apagou o progresso de 9 casos três vezes).
    done_em_disco: set[str] = set()
    if FILA.exists():
        try:
            done_em_disco = set(json.loads(FILA.read_text(encoding="utf-8")).get("done", []))
        except json.JSONDecodeError:
            print("AVISO: fila em disco ilegível; seguindo só pelo progresso")

    pending, done = [], []
    nao_mapeados = []
    for i, caso in enumerate(casos, start=1):
        arq = obra_para_arquivo(caso["obra"])
        if arq is None:
            nao_mapeados.append((i, caso["obra"]))
            continue
        item = f"{arq}|{caso['artigo']}|?|?"
        if i in aplicados or item in done_em_disco:
            done.append(item)
        else:
            pending.append(item)

    # deduplicar mantendo ordem
    pending = list(dict.fromkeys(pending))
    done = list(dict.fromkeys(done))

    FILA.write_text(
        json.dumps({"pending": pending, "done": done}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"fila: {len(pending)} pending, {len(done)} done")
    if nao_mapeados:
        print("NÃO MAPEADOS:")
        for i, obra in nao_mapeados:
            print(f"  caso {i}: {obra}")
    print(f"fila salva em {FILA}")


if __name__ == "__main__":
    main()
