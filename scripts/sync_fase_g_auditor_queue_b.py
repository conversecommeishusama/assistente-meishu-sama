#!/usr/bin/env python3
"""Wrapper do shard B da Fase G — ver sync_fase_g_auditor_queue_a.py (irmão,
mesmo mecanismo, caminhos do shard B)."""
import runpy
import sys

sys.argv = [
    "sync_chunk_turnaware_auditor_queue.py",
    "reports/livros_trabalho/segmentacao_manual/FASE_G_REVISAO_SEMANTICA_QUEUE_B.json",
    "reports/livros_trabalho/segmentacao_manual/FASE_G_AUDITORIA_EXTERNA_QUEUE_B.json",
]

runpy.run_path("scripts/sync_chunk_turnaware_auditor_queue.py", run_name="__main__")
