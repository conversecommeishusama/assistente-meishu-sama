#!/usr/bin/env python3
"""Wrapper do shard B — chama sync_chunk_turnaware_auditor_queue.py com os
caminhos das filas B fixos. Existe porque run_stateless_claude_loop.sh
invoca o presync sempre como `python3 "$PRESYNC"` (um único caminho de
arquivo, sem argumentos posicionais) — este wrapper injeta os argumentos via
sys.argv antes de rodar o script original, sem duplicar a lógica de sync.
"""
import runpy
import sys

sys.argv = [
    "sync_chunk_turnaware_auditor_queue.py",
    "reports/livros_trabalho/segmentacao_manual/CHUNK_TURNAWARE_QUEUE_B.json",
    "reports/livros_trabalho/segmentacao_manual/CHUNK_TURNAWARE_AUDITORIA_EXTERNA_QUEUE_B.json",
]

runpy.run_path("scripts/sync_chunk_turnaware_auditor_queue.py", run_name="__main__")
