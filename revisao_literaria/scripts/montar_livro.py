#!/usr/bin/env python3
"""Montagem determinística (sem IA) — roda como `presync.py` do laço
executor (run_stateless_claude_loop.sh). A cada iteração do laço, varre
revisao_literaria/chunks/*, e para todo livro cujos chunks estejam 100%
`_out.txt` gravados e ainda não montado, concatena em ordem e grava em
revisao_literaria/livros_publicacao_pt_literaria/{arquivo}, então enfileira
o livro para auditoria.

Rede de segurança: verifica que a soma de caracteres do resultado montado
não fugiu de uma faixa plausível em relação ao original (proteção contra a
classe de bug do incidente ImplantaV2 — perda silenciosa de parágrafos).
Livro fora da faixa NÃO é promovido nem enfileirado — fica registrado em
ALERTAS_MONTAGEM.jsonl para checagem manual, e a próxima passada tenta de
novo (útil quando o auditor reabre um chunk e ele é corrigido).
"""
import datetime
import fcntl
import glob
import json
import os

REPO = "/var/www/goshinsho"
DEST = os.path.join(REPO, "revisao_literaria")
CHUNKS_DIR = os.path.join(DEST, "chunks")
SAIDA_DIR = os.path.join(DEST, "livros_publicacao_pt_literaria")
FILA_AUDITOR = os.path.join(DEST, "QUEUE_AUDITOR.json")
FILA_EXECUTOR = os.path.join(DEST, "QUEUE_EXECUTOR.json")
ALERTAS = os.path.join(DEST, "ALERTAS_MONTAGEM.jsonl")

RATIO_MIN = 0.5
RATIO_MAX = 2.0


def carregar_fila_auditor():
    if not os.path.exists(FILA_AUDITOR):
        return {
            "gerado_por": "montar_livro.py",
            "gerado_em": datetime.datetime.now().isoformat(),
            "fase": "revisao_literaria_auditor",
            "protocol_file": "revisao_literaria/AUDITORIA_PROMPT.md",
            "pending": [], "in_progress": [], "done": [], "failed": [],
        }
    with open(FILA_AUDITOR, encoding="utf-8") as f:
        return json.load(f)


def salvar_fila_auditor(fila):
    with open(FILA_AUDITOR, "w", encoding="utf-8") as f:
        json.dump(fila, f, ensure_ascii=False, indent=2)


def lock_fila_auditor():
    """Adquire lock exclusivo (fcntl.flock) sobre a fila do auditor.

    Evita race condition entre o montador (presync do executor E do auditor)
    e o harness auditor ao ler/gravar QUEUE_AUDITOR.json — cada um podia
    sobrescrever o enfileiramento do outro, deixando livros montados órfãos
    da fila de auditoria. O lock é liberado ao fechar o descritor.
    """
    if not os.path.exists(FILA_AUDITOR):
        open(FILA_AUDITOR, "w", encoding="utf-8").write("{}")
    fd = os.open(FILA_AUDITOR, os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def unlock_fila_auditor(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def livros_com_chunk_em_aberto():
    """Livros que ainda têm chunk na fila do executor (pending/in_progress).

    Sem isto, um chunk reaberto pelo auditor era remontado na iteração
    seguinte a partir do `_out.txt` ANTIGO — `all(os.path.exists(...))`
    abaixo só verifica que o arquivo existe, não que foi reprocessado. O
    livro voltava para a fila de auditoria com o mesmo defeito intacto e o
    auditor relia o livro inteiro à toa (visto em 2026-08-14, 19 s após a
    reabertura de 4 chunks de "19350000 - Curso Kannon (1~7)").
    """
    if not os.path.exists(FILA_EXECUTOR):
        return set()
    fila = json.load(open(FILA_EXECUTOR, encoding="utf-8"))
    return {
        item["livro"]
        for item in fila.get("pending", []) + fila.get("in_progress", [])
    }


def registrar_alerta(livro, motivo, detalhe):
    with open(ALERTAS, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "livro": livro, "motivo": motivo, "detalhe": detalhe,
            "at": datetime.datetime.now().isoformat(),
        }, ensure_ascii=False) + "\n")


def main():
    os.makedirs(SAIDA_DIR, exist_ok=True)
    # Lock exclusivo sobre a fila do auditor durante todo o processamento —
    # serializa contra o harness auditor e o outro laço (race condition fix).
    fd = lock_fila_auditor()
    try:
        return _main()
    finally:
        unlock_fila_auditor(fd)


def _main():
    fila_auditor = carregar_fila_auditor()
    ja_na_fila_auditor = {
        item["livro"] for item in
        fila_auditor["pending"] + fila_auditor["in_progress"] + fila_auditor["done"]
    }

    em_aberto = livros_com_chunk_em_aberto()

    montados_agora = 0
    for manifest_path in sorted(glob.glob(os.path.join(CHUNKS_DIR, "*", "_manifest.json"))):
        livro_dir = os.path.dirname(manifest_path)
        livro = os.path.basename(livro_dir)
        manifest = json.load(open(manifest_path, encoding="utf-8"))

        if manifest.get("montado"):
            continue

        if livro in em_aberto:
            continue  # chunk reaberto ainda não reprocessado pelo executor

        total = manifest["total_chunks"]
        out_paths = [os.path.join(livro_dir, f"{i:03d}_out.txt") for i in range(total)]
        if not all(os.path.exists(p) for p in out_paths):
            continue  # livro ainda com chunk pendente

        partes = [open(p, encoding="utf-8").read() for p in out_paths]
        texto_final = "".join(partes)
        chars_final = len(texto_final)
        chars_fonte = manifest["chars_fonte"]
        ratio = chars_final / chars_fonte if chars_fonte else 0

        if not (RATIO_MIN <= ratio <= RATIO_MAX):
            registrar_alerta(livro, "ratio_tamanho_fora_da_faixa", {
                "chars_fonte": chars_fonte, "chars_final": chars_final, "ratio": round(ratio, 3),
            })
            continue  # não promove, não enfileira — precisa de checagem manual

        destino = os.path.join(SAIDA_DIR, manifest["arquivo"])
        with open(destino, "w", encoding="utf-8") as f:
            f.write(texto_final)

        manifest["montado"] = True
        manifest["montado_em"] = datetime.datetime.now().isoformat()
        manifest["chars_final"] = chars_final
        manifest["ratio_tamanho"] = round(ratio, 3)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        if livro not in ja_na_fila_auditor:
            fila_auditor["pending"].append({
                "livro": livro,
                "arquivo": manifest["arquivo"],
            })
            ja_na_fila_auditor.add(livro)

        montados_agora += 1

    if montados_agora:
        salvar_fila_auditor(fila_auditor)
        print(f"{datetime.datetime.now().isoformat()} — montar_livro.py: {montados_agora} livro(s) montado(s) e enfileirado(s) para auditoria.")


if __name__ == "__main__":
    main()
