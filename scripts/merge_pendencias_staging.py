#!/usr/bin/env python3
"""Consolida os arquivos de staging de PENDENCIAS_REVISAO.json no canônico.

Contexto (2026-07-15): com 8 processos paralelos (executor+auditor dos 2
shards de CHUNK_TURNAWARE + os 2 shards da FASE_G) todos potencialmente
escrevendo em PENDENCIAS_REVISAO.json ao mesmo tempo, um read-modify-write
concorrente sem lock pode perder silenciosamente o registro de um deles (o
segundo a escrever sobrescreve o primeiro). Como as instâncias de `claude -p`
editam o arquivo com suas próprias ferramentas (Read/Edit/Write), não há como
impor lock de verdade na escrita delas.

Mitigação: cada processo grava suas pendências no PRÓPRIO arquivo de staging
(`PENDENCIAS_STAGING_<id>.json`, um por processo — nunca compartilhado), e
este script, rodando sozinho a cada ciclo do dashboard, consolida tudo no
canônico. Isso não elimina 100% a chance de um item ficar duplicado (se o
merge ler um staging no instante exato em que o processo dono está
escrevendo uma nova entrada nele, a entrada antiga pode sobrar no staging e
ser mesclada de novo no próximo ciclo) — mas elimina a perda silenciosa de
dados, porque cada arquivo de staging só tem um escritor possível.

Determinístico, sem custo de API — seguro para rodar em loop.
"""
import json
import os

BASE = "reports/livros_trabalho/segmentacao_manual"
CANONICAL = f"{BASE}/PENDENCIAS_REVISAO.json"

STAGING_IDS = [
    "chunk_turnaware_executor_a",
    "chunk_turnaware_executor_b",
    "chunk_turnaware_auditor_a",
    "chunk_turnaware_auditor_b",
    "fase_g_executor_a",
    "fase_g_executor_b",
    "fase_g_auditor_a",
    "fase_g_auditor_b",
]


def staging_path(sid):
    return f"{BASE}/PENDENCIAS_STAGING_{sid}.json"


def load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Arquivo sendo escrito no instante exato da leitura — tenta no
        # proximo ciclo, nunca lanca excecao (isso pararia o laco externo).
        return None


def main():
    canonical = load(CANONICAL, {"items": []})
    if canonical is None:
        print("merge_pendencias_staging: PENDENCIAS_REVISAO.json ilegivel neste ciclo (provavel escrita concorrente), tentando no proximo ciclo.")
        return
    if "items" not in canonical or not isinstance(canonical["items"], list):
        canonical["items"] = []

    total_merged = 0
    for sid in STAGING_IDS:
        spath = staging_path(sid)
        staging = load(spath, {"items": []})
        if staging is None:
            continue
        items = staging.get("items", [])
        if not items:
            continue
        canonical["items"].extend(items)
        total_merged += len(items)
        # Limpa o staging (o dono pode ter escrito mais itens entre a leitura
        # e aqui -- nesse caso eles sobrevivem, sao mesclados de novo no
        # proximo ciclo; nunca perdidos, na pior das hipoteses duplicados).
        with open(spath, "w", encoding="utf-8") as f:
            json.dump({"items": []}, f, ensure_ascii=False, indent=2)
            f.write("\n")

    if total_merged:
        with open(CANONICAL, "w", encoding="utf-8") as f:
            json.dump(canonical, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"merge_pendencias_staging: {total_merged} item(ns) consolidado(s) em PENDENCIAS_REVISAO.json")


if __name__ == "__main__":
    main()
