#!/usr/bin/env python3
"""Wrapper de sync_revisao_editorial_auditor_queue.py com os defaults do
shard B (mesmo padrao de sync_fase_g_periodicos_auditor_queue_b.py) -- o
laco externo (run_stateless_claude_loop.sh) chama o presync sem argumentos,
entao os defaults precisam apontar pras filas certas por shard.
"""
import runpy
import sys

sys.argv = [
    sys.argv[0],
    "reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_QUEUE_B.json",
    "reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_AUDITORIA_EXTERNA_QUEUE_B.json",
]
runpy.run_path("scripts/sync_revisao_editorial_auditor_queue.py", run_name="__main__")
