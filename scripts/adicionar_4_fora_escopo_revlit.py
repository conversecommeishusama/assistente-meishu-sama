#!/usr/bin/env python3
"""Adiciona os 4 arquivos fora do escopo (Conversas sobre a Fé, Luz dos
Ensinamentos, Palácio de Cristal, Medicina do Amanhã) à fila de revisão
literária de forma INCREMENTAL, preservando o done já existente.

Mesmo padrão do adicionar_suplemento_revlit.py: fragmenta cada fonte em
chunks (~12k chars, fronteiras de parágrafo), grava _src.txt + _manifest.json,
e adiciona os itens ao final do pending da QUEUE_EXECUTOR.json (sem resetar
done/in_progress). Atualiza também o ESCOPO.json (adiciona os 4).

Fonte: livros_publicacao_pt_revisado/ (read-only).
Uso: python3 scripts/adicionar_4_fora_escopo_revlit.py [--dry-run]
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
FONTE_DIR = RAIZ / "livros_publicacao_pt_revisado"
FILA = REV / "QUEUE_EXECUTOR.json"
ESCOPO = REV / "ESCOPO.json"
CHUNKS = REV / "chunks"

# Os 4 arquivos fora do escopo que o usuário decidiu trabalhar
ARQUIVOS = [
    "19480905 - Conversas sobre a Fé.txt",
    "19510520 - Luz dos Ensinamentos.txt",
    "19541211 - Palavras de Meishu-Sama no Palácio de Cristal.txt",
    "Medicina_do_Amanha.txt",
]


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

    fila = json.loads(FILA.read_text(encoding="utf-8"))
    escopo = json.loads(ESCOPO.read_text(encoding="utf-8"))
    pending = fila.get("pending", [])
    done = fila.get("done", [])
    escopo_arqs = escopo.get("arquivos", [])

    novos_pending_total = []
    escopo_adicionados = []

    for basename in ARQUIVOS:
        fonte_rel = f"livros_publicacao_pt_revisado/{basename}"
        caminho = FONTE_DIR / basename
        if not caminho.exists():
            print(f"ERRO: fonte não existe: {caminho}", file=sys.stderr)
            return 1

        nome_livro = os.path.splitext(basename)[0]

        # Verificar se já está na fila
        ja = any(
            i.get("livro") == nome_livro
            for i in pending + done + fila.get("in_progress", [])
        )
        if ja:
            print(f"{basename}: JÁ está na fila — pulando.")
            continue
        # Verificar se já está no escopo
        ja_escopo = any(a.get("arquivo") == basename for a in escopo_arqs)
        if ja_escopo:
            print(f"{basename}: JÁ está no ESCOPO — pulando (só fila?).")

        texto = caminho.read_text(encoding="utf-8")
        unidades = pc.dividir_em_unidades(texto)
        chunks = pc.empacotar(unidades, 12000, 3000)
        if "".join(chunks) != texto:
            print(f"ERRO: concatenação dos chunks != original ({basename})", file=sys.stderr)
            return 1
        print(f"{basename}: {len(texto)} chars -> {len(chunks)} chunks (fidelidade OK)")

        if not dry_run:
            chunk_dir = CHUNKS / nome_livro
            chunk_dir.mkdir(parents=True, exist_ok=True)
            chunk_infos = []
            novos_pending = []
            for idx, c in enumerate(chunks):
                (chunk_dir / f"{idx:03d}_src.txt").write_text(c, encoding="utf-8")
                chunk_infos.append({
                    "idx": idx,
                    "chars": len(c),
                    "paragrafos": pc.contar_paragrafos(c),
                })
                novos_pending.append({
                    "livro": nome_livro,
                    "arquivo": basename,
                    "chunk": idx,
                    "total_chunks": len(chunks),
                })
            manifest = {
                "arquivo": basename,
                "fonte": fonte_rel,
                "chars_fonte": len(texto),
                "total_chunks": len(chunks),
                "chunks": chunk_infos,
                "montado": False,
            }
            (chunk_dir / "_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            novos_pending_total.extend(novos_pending)
            escopo_adicionados.append({
                "arquivo": basename,
                "fonte": fonte_rel,
                "chars": len(texto),
                "total_chunks": len(chunks),
            })
        else:
            print(f"  (dry-run) Seriam adicionados {len(chunks)} chunks.")

    if not dry_run and novos_pending_total:
        # Adicionar ao pending (no final)
        fila["pending"] = pending + novos_pending_total
        FILA.write_text(json.dumps(fila, ensure_ascii=False, indent=2), encoding="utf-8")

        # Atualizar ESCOPO (adicionar os 4, preservando os 50)
        if escopo_adicionados:
            escopo["total_arquivos"] = len(escopo_arqs) + len(escopo_adicionados)
            escopo["total_chunks"] = escopo.get("total_chunks", 0) + sum(
                a["total_chunks"] for a in escopo_adicionados
            )
            escopo["arquivos"] = escopo_arqs + escopo_adicionados
            ESCOPO.write_text(json.dumps(escopo, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"\nAdicionados {len(novos_pending_total)} chunks ao pending.")
        print(f"pending agora: {len(fila['pending'])} | done: {len(fila['done'])}")
        print(f"ESCOPO agora: {len(escopo['arquivos'])} arquivos | {escopo['total_chunks']} chunks")
    elif dry_run:
        print("\n(dry-run) Nada gravado em disco.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
