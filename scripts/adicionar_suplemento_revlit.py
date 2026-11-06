#!/usr/bin/env python3
"""Adiciona o Gokōwa-roku (Suplemento) consolidado à fila de revisão literária
de forma INCREMENTAL, sem perturbar o pipeline ativo.

- Fragmenta o consolidado em chunks (~12k chars, fronteiras de parágrafo),
  usando a MESMA lógica do preparar_chunks.py.
- Cria revisao_literaria/chunks/Gokōwa-roku (Suplemento)/ com _src.txt + manifest.
- Adiciona os itens ao final do pending da QUEUE_EXECUTOR.json (sem resetar
  done/in_progress/progresso dos 50 livros já em andamento).
- Não toca em nada fora de revisao_literaria/.

Uso:
    python3 scripts/adicionar_suplemento_revlit.py [--dry-run]
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
REV = RAIZ / "revisao_literaria"
FONTE = REV / "orais" / "19480101 - Gokōwa-roku (Suplemento).txt"
FILA = REV / "QUEUE_EXECUTOR.json"
CHUNKS = REV / "chunks"

NOME_LIVRO = "Gokōwa-roku (Suplemento)"
ARQUIVO = "19480101 - Gokōwa-roku (Suplemento).txt"


def carregar_preparar_chunks():
    spec = importlib.util.spec_from_file_location(
        "pc", str(REV / "scripts" / "preparar_chunks.py")
    )
    pc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pc)
    return pc


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    pc = carregar_preparar_chunks()

    if not FONTE.exists():
        print(f"ERRO: fonte não existe: {FONTE}", file=sys.stderr)
        return 1

    texto = FONTE.read_text(encoding="utf-8")
    unidades = pc.dividir_em_unidades(texto)
    chunks = pc.empacotar(unidades, 12000, 3000)
    if "".join(chunks) != texto:
        print("ERRO: concatenação dos chunks != original", file=sys.stderr)
        return 1
    print(f"Chunks do Suplemento: {len(chunks)} (fidelidade OK)")

    fila = json.loads(FILA.read_text(encoding="utf-8"))
    pending = fila.get("pending", [])
    done = fila.get("done", [])

    # verificar se já está na fila
    ja_na_fila = any(i.get("livro") == NOME_LIVRO for i in pending + done + fila.get("in_progress", []))
    if ja_na_fila:
        print("Suplemento JÁ está na fila — nada a fazer.")
        return 0

    # gravar chunks (se não dry-run)
    chunk_dir = CHUNKS / NOME_LIVRO
    if not dry_run:
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunk_infos = []
        novos_pending = []
        for idx, c in enumerate(chunks):
            (chunk_dir / f"{idx:03d}_src.txt").write_text(c, encoding="utf-8")
            chunk_infos.append({"idx": idx, "chars": len(c), "paragrafos": pc.contar_paragrafos(c)})
            novos_pending.append({
                "livro": NOME_LIVRO,
                "arquivo": ARQUIVO,
                "chunk": idx,
                "total_chunks": len(chunks),
            })
        manifest = {
            "arquivo": ARQUIVO,
            "fonte": str(FONTE),
            "chars_fonte": len(texto),
            "total_chunks": len(chunks),
            "chunks": chunk_infos,
            "montado": False,
        }
        (chunk_dir / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        # adicionar ao pending (no final)
        fila["pending"] = pending + novos_pending
        FILA.write_text(json.dumps(fila, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Adicionados {len(novos_pending)} chunks do Suplemento ao pending.")
        print(f"pending agora: {len(fila['pending'])} | done: {len(fila['done'])}")
    else:
        print(f"(dry-run) Seriam adicionados {len(chunks)} chunks ao pending.")
        print(f"(dry-run) pending atual: {len(pending)} | done: {len(done)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
