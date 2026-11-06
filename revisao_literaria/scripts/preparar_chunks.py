#!/usr/bin/env python3
"""Preparo determinístico da fase de revisão literária.

Lê os 56 arquivos escritos (volumes 12-32 de publicacao_livros/) de
livros_publicacao_pt_revisado/ (read-only), fragmenta cada um em chunks que
respeitam fronteiras de parágrafo (nunca corta no meio de frase, divisória
ou bloco de verso, porque esses elementos já ficam isolados por linha em
branco no texto-fonte), e grava:

  revisao_literaria/ESCOPO.json
  revisao_literaria/chunks/{arquivo_base}/_manifest.json
  revisao_literaria/chunks/{arquivo_base}/NNN_src.txt
  revisao_literaria/QUEUE_EXECUTOR.json

Não escreve nada fora de revisao_literaria/. Não toca no japonês.

Uso: python3 preparar_chunks.py [--dry-run] [--alvo N] [--minimo N]
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys

REPO = "/var/www/goshinsho"
FONTE_DIR = os.path.join(REPO, "livros_publicacao_pt_revisado")
DEST = os.path.join(REPO, "revisao_literaria")


def descobrir_escopo():
    """Reconstrói os 56 arquivos escritos (volumes 12-32) a partir dos
    MANIFESTO.json, que são a fonte de verdade da fronteira oral/escrito
    já usada pelo pipeline de publicação. Dedupe por nome de arquivo-fonte
    (alguns arquivos, ex. Eiko.txt, são reaproveitados em >1 volume)."""
    vistos = {}
    for i in range(12, 33):
        candidatos = glob.glob(os.path.join(REPO, "publicacao_livros", f"{i:02d}_*", "MANIFESTO.json"))
        if not candidatos:
            print(f"AVISO: volume {i} sem MANIFESTO.json", file=sys.stderr)
            continue
        manifesto = json.load(open(candidatos[0], encoding="utf-8"))
        for item in manifesto.get("arquivos", []):
            fonte = re.sub(r"\s*\(redivisão por ano\)\s*$", "", item["fonte"]).strip()
            # MANIFESTO.json pode estar desatualizado em relação a remoções
            # de escopo feitas depois da última reconstrução (ex.: títulos
            # de terceiros retirados em 2026-08-13 e movidos para
            # backups/remocao_fora_escopo_*/). Só livros que ainda vivem em
            # livros_publicacao_pt_revisado/ entram nesta fase.
            if not fonte.startswith("livros_publicacao_pt_revisado/"):
                print(f"AVISO: ignorando fonte fora de livros_publicacao_pt_revisado/ (provável remoção de escopo): {fonte}", file=sys.stderr)
                continue
            vistos[fonte] = item.get("caracteres", 0)
    arquivos = []
    for fonte in sorted(vistos):
        caminho_abs = os.path.join(REPO, fonte)
        if not os.path.exists(caminho_abs):
            print(f"ERRO: fonte não existe em disco: {fonte}", file=sys.stderr)
            continue
        arquivos.append(fonte)
    return arquivos


def dividir_em_unidades(texto):
    """Divide o texto em unidades atômicas (bloco de conteúdo + separador
    que o segue), na ordem original. Concatenar todas as unidades reproduz
    o texto original byte a byte — é a garantia de fidelidade mecânica."""
    partes = re.split(r"(\n{2,})", texto)
    unidades = []
    i = 0
    while i < len(partes):
        bloco = partes[i]
        sep = partes[i + 1] if i + 1 < len(partes) else ""
        unidades.append(bloco + sep)
        i += 2
    return unidades


def empacotar(unidades, alvo, minimo):
    """Agrupa unidades em chunks perto do tamanho-alvo, sem nunca cortar
    uma unidade ao meio. Sobra final menor que `minimo` é fundida no chunk
    anterior."""
    chunks = []
    atual = []
    atual_len = 0
    for u in unidades:
        if atual and atual_len + len(u) > alvo:
            chunks.append("".join(atual))
            atual = []
            atual_len = 0
        atual.append(u)
        atual_len += len(u)
    if atual:
        resto = "".join(atual)
        if chunks and len(resto) < minimo:
            chunks[-1] += resto
        else:
            chunks.append(resto)
    return chunks


def contar_paragrafos(chunk):
    return len([p for p in re.split(r"\n{2,}", chunk) if p.strip()])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--alvo", type=int, default=12000)
    ap.add_argument("--minimo", type=int, default=3000)
    args = ap.parse_args()

    arquivos = descobrir_escopo()
    print(f"Escopo: {len(arquivos)} arquivos escritos (volumes 12-32).")

    escopo_out = []
    fila_pending = []
    total_chunks = 0
    erros = []

    for fonte_rel in arquivos:
        caminho_abs = os.path.join(REPO, fonte_rel)
        basename = os.path.basename(fonte_rel)
        nome_sem_ext = os.path.splitext(basename)[0]
        texto = open(caminho_abs, encoding="utf-8").read()

        unidades = dividir_em_unidades(texto)
        chunks = empacotar(unidades, args.alvo, args.minimo)

        # Verificação mecânica de fidelidade: concatenar os chunks tem que
        # reproduzir o arquivo original exatamente.
        if "".join(chunks) != texto:
            erros.append(fonte_rel)
            continue

        chunk_infos = []
        for idx, c in enumerate(chunks):
            chunk_infos.append({
                "idx": idx,
                "chars": len(c),
                "paragrafos": contar_paragrafos(c),
            })
            fila_pending.append({
                "livro": nome_sem_ext,
                "arquivo": basename,
                "chunk": idx,
                "total_chunks": len(chunks),
            })

        escopo_out.append({
            "arquivo": basename,
            "fonte": fonte_rel,
            "chars": len(texto),
            "total_chunks": len(chunks),
        })
        total_chunks += len(chunks)

        if not args.dry_run:
            chunk_dir = os.path.join(DEST, "chunks", nome_sem_ext)
            os.makedirs(chunk_dir, exist_ok=True)
            for idx, c in enumerate(chunks):
                with open(os.path.join(chunk_dir, f"{idx:03d}_src.txt"), "w", encoding="utf-8") as f:
                    f.write(c)
            manifest = {
                "arquivo": basename,
                "fonte": fonte_rel,
                "chars_fonte": len(texto),
                "total_chunks": len(chunks),
                "chunks": chunk_infos,
                "montado": False,
            }
            with open(os.path.join(chunk_dir, "_manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

        print(f"  {basename}: {len(texto)} chars -> {len(chunks)} chunks")

    if erros:
        print(f"\nERRO: {len(erros)} arquivo(s) falharam na verificação de fidelidade (concatenação != original):", file=sys.stderr)
        for e in erros:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nTotal: {len(escopo_out)} livros, {total_chunks} chunks.")

    if args.dry_run:
        print("(--dry-run: nada gravado em disco)")
        return

    with open(os.path.join(DEST, "ESCOPO.json"), "w", encoding="utf-8") as f:
        json.dump({
            "gerado_em": datetime.datetime.now().isoformat(),
            "total_arquivos": len(escopo_out),
            "total_chunks": total_chunks,
            "alvo_chars_por_chunk": args.alvo,
            "arquivos": escopo_out,
        }, f, ensure_ascii=False, indent=2)

    with open(os.path.join(DEST, "QUEUE_EXECUTOR.json"), "w", encoding="utf-8") as f:
        json.dump({
            "gerado_por": "preparar_chunks.py",
            "gerado_em": datetime.datetime.now().isoformat(),
            "fase": "revisao_literaria_executor",
            "protocol_file": "revisao_literaria/PROTOCOLO_LITERARIO.md",
            "pending": fila_pending,
            "in_progress": [],
            "done": [],
            "failed": [],
        }, f, ensure_ascii=False, indent=2)

    with open(os.path.join(DEST, "QUEUE_AUDITOR.json"), "w", encoding="utf-8") as f:
        json.dump({
            "gerado_por": "montar_livro.py",
            "gerado_em": datetime.datetime.now().isoformat(),
            "fase": "revisao_literaria_auditor",
            "protocol_file": "revisao_literaria/AUDITORIA_PROMPT.md",
            "pending": [],
            "in_progress": [],
            "done": [],
            "failed": [],
        }, f, ensure_ascii=False, indent=2)

    print("Gravado: ESCOPO.json, QUEUE_EXECUTOR.json, QUEUE_AUDITOR.json, chunks/*/")


if __name__ == "__main__":
    main()
