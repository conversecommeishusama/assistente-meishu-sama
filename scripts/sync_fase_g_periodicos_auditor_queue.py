#!/usr/bin/env python3
"""Sincroniza a fila do auditor externo da Fase G periodicos com a fila do
executor, por shard. Mesma logica de sync_chunk_turnaware_auditor_queue.py,
mas a chave unica de cada item e' `entry_id` (nao `ficheiro`/`arquivo` --
o campo `periodico_arquivo` NAO e' unico por artigo, varios artigos
compartilham o mesmo periodico, entao nao pode ser usado como chave).

Uso: sync_fase_g_periodicos_auditor_queue.py <shard: A|B>
"""
import sys
import json

SHARD = sys.argv[1] if len(sys.argv) > 1 else "A"
EXECUTOR_QUEUE = f"reports/periodicos_trabalho/FASE_G_PERIODICOS_EXECUCAO_QUEUE_{SHARD}.json"
AUDITOR_QUEUE = f"reports/periodicos_trabalho/FASE_G_PERIODICOS_AUDITORIA_QUEUE_{SHARD}.json"


def extract_id(entry):
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict) and entry.get("entry_id"):
        return entry["entry_id"]
    print(f"sync: aviso -- entrada sem entry_id reconhecido, pulando: {entry!r}", file=sys.stderr)
    return None


def main():
    with open(EXECUTOR_QUEUE, encoding="utf-8") as f:
        executor = json.load(f)
    with open(AUDITOR_QUEUE, encoding="utf-8") as f:
        auditor = json.load(f)

    executor_done_entries = {e["entry_id"]: e for e in executor.get("done", []) if isinstance(e, dict) and e.get("entry_id")}
    executor_done_ids = set(executor_done_entries.keys())
    auditor_done_ids = set(n for n in (extract_id(e) for e in auditor.get("done", [])) if n)
    auditor_pending = auditor.get("pending", [])
    auditor_pending_ids = set(n for n in (extract_id(e) for e in auditor_pending) if n)

    novos_ids = [i for i in executor_done_ids if i not in auditor_done_ids and i not in auditor_pending_ids]
    if novos_ids:
        print(f"sync: {len(novos_ids)} item(ns) novo(s) do executor adicionado(s) a pending do auditor (shard {SHARD})")
        for i in novos_ids:
            e = executor_done_entries[i]
            auditor_pending.append({
                "entry_id": e["entry_id"],
                "periodico_arquivo": e.get("periodico_arquivo", ""),
            })
        auditor["pending"] = auditor_pending

    executor_finished = len(executor.get("pending", [])) == 0
    auditor_caught_up = executor_done_ids.issubset(auditor_done_ids) and len(auditor["pending"]) == 0
    concluido = executor_finished and auditor_caught_up
    if concluido != auditor.get("concluido", False):
        print(f"sync: campo concluido -> {concluido} (shard {SHARD})")
    auditor["concluido"] = concluido

    with open(AUDITOR_QUEUE, "w", encoding="utf-8") as f:
        json.dump(auditor, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
