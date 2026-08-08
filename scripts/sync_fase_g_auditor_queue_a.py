#!/usr/bin/env python3
"""Wrapper do shard A da Fase G — reaproveita a lógica genérica de
sync_chunk_turnaware_auditor_queue.py (sincroniza done do executor -> pending
do auditor por nome de arquivo, sem nada específico de chunk_turnaware),
apontando para os caminhos das filas da Fase G via sys.argv.
"""
import runpy
import sys

sys.argv = [
    "sync_chunk_turnaware_auditor_queue.py",
    "reports/livros_trabalho/segmentacao_manual/FASE_G_REVISAO_SEMANTICA_QUEUE.json",
    "reports/livros_trabalho/segmentacao_manual/FASE_G_AUDITORIA_EXTERNA_QUEUE.json",
]

runpy.run_path("scripts/sync_chunk_turnaware_auditor_queue.py", run_name="__main__")
