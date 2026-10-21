#!/usr/bin/env python3
"""Daemon XTTS persistente — mantém o modelo de voz Meishu-Sama carregado.

O problema da abordagem por-subprocess: cada trecho recarregava o modelo XTTS
(~2GB, 30-60s) — um desperdício enorme. Este daemon carrega o modelo UMA vez
e fica processando tarefas em fila (diretório de spool), gravando cada áudio.

Protocolo (spool em dir):
  - <dir>/tarefa_<id>.json  -> {"texto": "...", "destino": "/caminho/out.mp3"}
  - O daemon processa, grava o MP3 e move a tarefa para <dir>/done/ (ou .erro).

Uso:
  <venv_xtts>/bin/python scripts/daemon_xtts.py [--spool DIR] [--amostra ARQ]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

# 2026-10-21: limite de threads por daemon. Sem isto, cada processo do XTTS
# pedia o total de cores da máquina (14), e com 5 daemons em paralelo isso dava
# ~70 threads de cálculo a competir por 14 cores (oversubscrição ~5x). Medido
# em produção: load average 45, CPU user 96%, e o lote travado em [17/71]
# durante 13h, roubando CPU do gunicorn. Os limites têm de ser definidos ANTES
# de importar torch/numpy (daí ficarem no topo do módulo).
THREADS_POR_DAEMON = int(os.environ.get("XTTS_THREADS", "2"))
for _var in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ.setdefault(_var, str(THREADS_POR_DAEMON))

AMOSTRA_PADRAO = "/var/www/goshinsho/amostras_voz/amostra_meishu_30s_limpa.wav"
MODELO = "tts_models/multilingual/multi-dataset/xtts_v2"


def quebrar(t: str, limite: int = 200) -> list[str]:
    """Quebra em segmentos <= limite (limite do XTTS em pt-BR ~200 chars)."""
    if len(t) <= limite:
        return [t]
    segs, atual = [], ""
    for parte in re.split(r"(?<=[,;:.…])\s+", t):
        if len(atual) + len(parte) + 1 <= limite:
            atual = (atual + " " + parte).strip() if atual else parte
        else:
            if atual:
                segs.append(atual.strip())
            if len(parte) > limite:
                palavras, atual = parte.split(), ""
                for p in palavras:
                    if len(atual) + len(p) + 1 <= limite:
                        atual = (atual + " " + p).strip() if atual else p
                    else:
                        segs.append(atual.strip())
                        atual = p
            else:
                atual = parte
    if atual.strip():
        segs.append(atual.strip())
    return segs


def sintetizar_texto(tts, texto: str, destino: str, amostra: str) -> None:
    """Sintetiza o texto (com quebra em segmentos + concat) no destino."""
    segs = quebrar(texto)
    tmp_dir = os.path.dirname(os.path.abspath(destino)) or "."
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_files = []
    try:
        for i, seg in enumerate(segs):
            tmp = os.path.join(tmp_dir, f"_dxtts_{os.getpid()}_{i}.wav")
            tts.tts_to_file(text=seg, speaker_wav=amostra, language="pt", file_path=tmp)
            # Remove silêncio nas bordas (evita gap na concatenação).
            subprocess.run(
                ["ffmpeg", "-y", "-i", tmp,
                 "-af", ("silenceremove=start_periods=1:start_threshold=-40dB:"
                         "start_silence=0.15,areverse,"
                         "silenceremove=start_periods=1:start_threshold=-40dB:"
                         "start_silence=0.15,areverse"),
                 "-ar", "24000", "-ac", "1", tmp + ".c.wav"],
                check=True, capture_output=True,
            )
            os.replace(tmp + ".c.wav", tmp)
            tmp_files.append(tmp)
        lista = os.path.join(tmp_dir, f"_dxtts_lista_{os.getpid()}.txt")
        with open(lista, "w") as f:
            for t in tmp_files:
                f.write(f"file '{t}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista,
             "-c:a", "libmp3lame", "-q:a", "2", destino],
            check=True, capture_output=True,
        )
        try:
            os.remove(lista)
        except OSError:
            pass
    finally:
        for t in tmp_files:
            try:
                os.remove(t)
            except OSError:
                pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spool", default="/var/www/goshinsho/data/tts_spool")
    ap.add_argument("--amostra", default=AMOSTRA_PADRAO)
    args = ap.parse_args()

    spool = args.spool
    done_dir = os.path.join(spool, "done")
    err_dir = os.path.join(spool, "erro")
    os.makedirs(spool, exist_ok=True)
    os.makedirs(done_dir, exist_ok=True)
    os.makedirs(err_dir, exist_ok=True)

    if not os.path.exists(args.amostra):
        print(f"ERRO: amostra não encontrada: {args.amostra}", file=sys.stderr)
        return 1

    print(f"Carregando XTTS (modelo {MODELO})...", file=sys.stderr, flush=True)
    t0 = time.time()
    from TTS.api import TTS
    # 2026-10-21: `torch.set_num_threads` cobre o que as variáveis de ambiente
    # não alcançam (o torch inicializa o seu próprio pool). Reforça o limite
    # por daemon definido no topo do módulo.
    try:
        import torch

        torch.set_num_threads(THREADS_POR_DAEMON)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            # Só pode ser chamado uma vez, antes de trabalho paralelo começar.
            pass
    except Exception as exc:  # pragma: no cover - defensivo
        print(f"AVISO: não foi possível limitar threads do torch: {exc}",
              file=sys.stderr, flush=True)
    print(f"Threads por daemon: {THREADS_POR_DAEMON} (OMP/MKL/torch)",
          file=sys.stderr, flush=True)
    tts = TTS(MODELO).to("cpu")
    print(f"Modelo carregado em {time.time()-t0:.0f}s. Aguardando tarefas em {spool}",
          file=sys.stderr, flush=True)

    while True:
        # Procura tarefas pendentes (json na raiz do spool).
        tarefas = [f for f in os.listdir(spool)
                   if f.startswith("tarefa_") and f.endswith(".json")]
        if not tarefas:
            time.sleep(2)
            continue

        for nome in sorted(tarefas):
            caminho = os.path.join(spool, nome)
            try:
                with open(caminho) as f:
                    dados = json.load(f)
                texto = dados.get("texto", "")
                destino = dados.get("destino", "")
                if not texto or not destino:
                    raise ValueError("tarefa sem texto/destino")
                os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
                t1 = time.time()
                sintetizar_texto(tts, texto, destino, args.amostra)
                print(f"[{nome}] OK em {time.time()-t1:.0f}s -> {os.path.basename(destino)}",
                      file=sys.stderr, flush=True)
                os.replace(caminho, os.path.join(done_dir, nome))
            except Exception as e:
                print(f"[{nome}] ERRO: {e}", file=sys.stderr, flush=True)
                try:
                    os.replace(caminho, os.path.join(err_dir, nome))
                except OSError:
                    pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
