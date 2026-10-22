#!/usr/bin/env python3
"""Worker de pré-geração (v2) que usa o DAEMON XTTS persistente.

Em vez de lançar um subprocess XTTS por trecho (que recarrega o modelo a cada
vez — lento), este worker envia os trechos XTTS (falas do Meishu-Sama) para o
spool do daemon_xtts.py (que mantém o modelo carregado). Os trechos do
Interlocutor (edge-tts) são gerados direto (rápidos, ~1s).

Uso:
  <venv_prod>/bin/python scripts/gerar_texto_meishu_v2.py "<arquivo.txt>"
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid

RAIZ = "/var/www/goshinsho"
SPOOL = os.path.join(RAIZ, "data", "tts_spool")
SPOOL_DONE = os.path.join(SPOOL, "done")
SPOOL_ERRO = os.path.join(SPOOL, "erro")


def quebrar_como_front(texto: str) -> list[str]:
    trechos = []
    paragrafos = [re.sub(r"\s+", " ", p).strip()
                  for p in re.split(r"\n+", texto) if p.strip()]
    for par in paragrafos:
        partes = re.split(r"(?<=[.!?…])\s+", par)
        if len(partes) <= 1:
            trechos.append(par)
        else:
            bloco = ""
            for parte in partes:
                if len(bloco) + len(parte) + 1 > 700 and bloco:
                    trechos.append(bloco.strip())
                    bloco = parte
                else:
                    bloco = (bloco + " " + parte).strip() if bloco else parte
            if bloco:
                trechos.append(bloco.strip())
    return trechos


def _sanitizar(texto: str) -> str:
    """Sanitiza para o XTTS (mesma lógica do tts_service._sanitizar_xtts)."""
    out = re.sub(r"^\s*[^:]{2,40}:\s*", "", texto)
    out = out.replace(";", ",").replace(":", ",")
    out = re.sub(r"\.(?=\s+[A-ZÀ-Ú])", ",", out)
    out = re.sub(r"\.\s*$", ",", out)
    out = re.sub(r"\s*\[[^\]]*\]\s*", " ", out)
    out = re.sub(r"\s*\([^)]*\)\s*", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: gerar_texto_meishu_v2.py '<arquivo.txt>'", file=sys.stderr)
        return 2
    nome = sys.argv[1]
    caminho = os.path.join(RAIZ, "textos_leitura_colaborativa", nome)
    if not os.path.exists(caminho):
        print(f"arquivo não encontrado: {caminho}", file=sys.stderr)
        return 1

    sys.path.insert(0, RAIZ)
    os.chdir(RAIZ)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, ".env"))
    from goshinsho.services import tts_service

    with open(caminho) as f:
        texto = f.read()
    trechos = quebrar_como_front(texto)

    # Separa: XTTS (Meishu/corrido) vão pro daemon; edge (Interlocutor) direto.
    pend_xtts = []   # lista de (texto_original)
    t0 = time.time()
    n_ok_edge = 0
    for trecho in trechos:
        falante = tts_service._identificar_falante(trecho)
        if falante == "outro":
            # Interlocutor -> Antonio (edge-tts), rápido e direto.
            try:
                tts_service.sintetizar(trecho, voz="meishu")
                n_ok_edge += 1
            except Exception:
                pass
        else:
            # Meishu/corrido -> XTTS (via daemon). Checa cache primeiro.
            texto_tts = _sanitizar(trecho)
            if not texto_tts:
                continue
            # Verifica se já está no cache (mesma chave do tts_service).
            chave = tts_service._chave_cache(
                f"xtts:{tts_service.VOZ_MEISHU_CACHE}", trecho, "+0%")
            destino = os.path.join(tts_service._cache_dir(), f"{chave}.mp3")
            if not os.path.exists(destino):
                pend_xtts.append((trecho, texto_tts, destino))

    print(f"[{nome}] {len(trechos)} trechos | {n_ok_edge} Interlocutor(edge) | {len(pend_xtts)} XTTS p/ daemon",
          file=sys.stderr, flush=True)

    # Envia os XTTS para o daemon e aguarda cada um (em ordem).
    for i, (trecho_orig, texto_tts, destino) in enumerate(pend_xtts):
        os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
        tarefa_id = f"{os.getpid()}_{i}_{uuid.uuid4().hex[:8]}"
        tarefa = os.path.join(SPOOL, f"tarefa_{tarefa_id}.json")
        with open(tarefa, "w") as f:
            json.dump({"texto": texto_tts, "destino": destino}, f)
        # Aguarda o daemon processar (polling no arquivo destino).
        espera = 0
        while not os.path.exists(destino) and espera < 900:
            time.sleep(5)
            espera += 5
        if not os.path.exists(destino):
            print(f"[{nome}] timeout trecho XTTS {i}", file=sys.stderr, flush=True)
        elif (i + 1) % 5 == 0:
            print(f"[{nome}] XTTS {i+1}/{len(pend_xtts)} em {time.time()-t0:.0f}s",
                  file=sys.stderr, flush=True)

    print(f"[{nome}] FIM em {time.time()-t0:.0f}s", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
