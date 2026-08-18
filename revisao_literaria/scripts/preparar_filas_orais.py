#!/usr/bin/env python3
"""Prepara as filas particionadas da revisão literária das palavras orais.

Lê o ESCOPO das palavras orais (ou um escopo separado) e distribui os chunks
entre N filas executor (round-robin) e cria N filas auditor (uma por executor
lote, ou compartilhadas).

Os arquivos orais ainda estão sendo retraduzidos/auditados/ajustados — esta
preparação cria a estrutura PRONTA para quando o trabalho atual terminar.

Uso:
    python3 revisao_literaria/scripts/preparar_filas_orais.py <N_EXEC> <N_AUD>
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
REV = RAIZ / "revisao_literaria"
CHUNKS = REV / "chunks"
ESCOPO = REV / "ESCOPO.json"
ORIG = RAIZ / "livros_publicacao_pt_revisado"

PADRAO_ORAL = re.compile(r"(Gok[ōo]wa|Gosuiji|Mioshie|Suplemento|Supl\.)", re.I)


def agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def main() -> int:
    n_exec = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    n_aud = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    # Identificar arquivos orais
    orais = [f for f in ORIG.iterdir() if f.is_file() and f.suffix == '.txt' and PADRAO_ORAL.search(f.name)]
    print(f"Arquivos orais identificados: {len(orais)}")

    # Montar itens de chunk para cada arquivo (se já houver chunks preparados)
    # Nota: os chunks orais serão preparados por preparar_chunks.py quando o
    # escopo for criado. Aqui, criamos a ESTRUTURA das filas e distribuímos
    # os arquivos (não chunks) como itens placeholder até a preparação real.
    itens_exec = []
    for f in sorted(orais):
        itens_exec.append({
            "livro": f.stem,
            "arquivo": f.name,
            "chunk": 0,
            "total_chunks": 0,  # preenchido por preparar_chunks.py
        })

    # Distribuir round-robin entre N filas executor
    filas_exec = [[] for _ in range(n_exec)]
    for i, item in enumerate(itens_exec):
        filas_exec[i % n_exec].append(item)

    for i in range(n_exec):
        q = {
            "gerado_por": "preparar_filas_orais.py",
            "gerado_em": agora(),
            "fase": "revisao_literaria_oral_executor",
            "protocol_file": "revisao_literaria/EXECUCAO_PROMPT.md",
            "pending": filas_exec[i],
            "in_progress": [],
            "done": [],
            "failed": [],
        }
        path = REV / f"QUEUE_EXECUTOR_ORAL_{i}.json"
        path.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  QUEUE_EXECUTOR_ORAL_{i}.json: {len(filas_exec[i])} itens")

    # Filas auditor (compartilham o escopo total)
    for i in range(n_aud):
        q = {
            "gerado_por": "preparar_filas_orais.py",
            "gerado_em": agora(),
            "fase": "revisao_literaria_oral_auditor",
            "protocol_file": "revisao_literaria/AUDITORIA_PROMPT.md",
            "pending": [],
            "in_progress": [],
            "done": [],
            "failed": [],
        }
        path = REV / f"QUEUE_AUDITOR_ORAL_{i}.json"
        path.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  QUEUE_AUDITOR_ORAL_{i}.json: criada (vazia, aguardando montagem)")

    print(f"\nEstrutura pronta: {n_exec} filas executor + {n_aud} filas auditor.")
    print("Quando a retradução/auditoria/ajuste dos orais terminar:")
    print("  1. Rodar preparar_chunks.py para gerar os chunks reais")
    print("  2. Atualizar QUEUE_EXECUTOR_ORAL_* com os chunks reais")
    print("  3. Lançar com: bash revisao_literaria/scripts/lancar_orais_paralelo.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
