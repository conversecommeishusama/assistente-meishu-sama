#!/usr/bin/env python3
"""Worker de pré-geração (v2, usa daemon XTTS persistente).

O orquestrador (pre_gerar_lote_orais.py) sobe N daemons XTTS (modelo
residente) e N workers. Cada worker:
- Interlocutor (rótulo não-Meishu) -> edge-tts (Antônio), direto e rápido.
- Meishu-Sama / texto corrido -> envia tarefa ao daemon XTTS do seu spool
  (env XTTS_SPOOL) e aguarda o MP3 pronto (sem recarregar o modelo).

Uso (chamado pelo orquestrador):
  <venv_prod>/bin/python scripts/gerar_texto_worker_v2.py "<arquivo.txt>"
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid

RAIZ = "/var/www/goshinsho"


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


def _sanitizar_xtts(texto: str) -> str:
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
        print("uso: gerar_texto_worker_v2.py '<arquivo.txt>'", file=sys.stderr)
        return 2
    nome = sys.argv[1]
    caminho = os.path.join(RAIZ, "textos_leitura_colaborativa", nome)
    if not os.path.exists(caminho):
        print(f"arquivo não encontrado: {caminho}", file=sys.stderr)
        return 1

    spool = os.environ.get("XTTS_SPOOL", os.path.join(RAIZ, "data", "tts_spool", "d0"))
    os.makedirs(spool, exist_ok=True)

    sys.path.insert(0, RAIZ)
    os.chdir(RAIZ)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, ".env"))
    from goshinsho.services import tts_service

    with open(caminho) as f:
        texto = f.read()
    trechos = quebrar_como_front(texto)
    arquivo = os.path.basename(caminho)

    t0 = time.time()
    n_edge = 0
    n_xtts = 0

    for i, trecho in enumerate(trechos):
        # 2026-10-23: a autoria vem ANTES do falante. Um trecho de obra de
        # terceiros (testemunho de fiel, manual institucional) não pode sair na
        # voz do Meishu-Sama, mesmo sem rótulo de fala.
        if tts_service.provedor_canonico(trecho, arquivo=arquivo)[0] == "edge":
            try:
                tts_service.sintetizar(trecho, voz="meishu", arquivo=arquivo)
                n_edge += 1
            except Exception:
                pass
            continue

        falante = tts_service._identificar_falante(trecho)
        if falante == "outro":
            # Interlocutor -> Antônio (edge-tts), direto (rápido, ~1s).
            try:
                tts_service.sintetizar(trecho, voz="meishu")
                n_edge += 1
            except Exception:
                pass
            continue

        # Meishu/corrido -> XTTS (via daemon). Sanitiza e checa cache.
        texto_tts = _sanitizar_xtts(trecho)
        if not texto_tts:
            continue
        # 2026-10-22: a chave era "xtts:meishu" (sem versão) e o app procura
        # "xtts:meishu:v2" — o lote gravava ficheiros que o serviço nunca
        # encontrava e regerava o que já existia. Usar a constante do serviço.
        chave = tts_service._chave_cache(
            f"xtts:{tts_service.VOZ_MEISHU_CACHE}", trecho, "+0%")
        destino = os.path.join(tts_service._cache_dir(), f"{chave}.mp3")
        if os.path.exists(destino):
            continue  # já gerado
        # Já existe noutra chave (Fish pago ou XTTS antigo)? Não vale a pena
        # regerar: o áudio do mesmo texto é o mesmo.
        if any(os.path.exists(os.path.join(tts_service._cache_dir(),
                                          tts_service._chave_cache(f"{p}:{v}", trecho, "+0%") + ".mp3"))
               for p, v in tts_service._chaves_historicas("xtts", tts_service.VOZ_MEISHU_CACHE)):
            continue

        # Envia tarefa ao daemon e aguarda o MP3.
        os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
        tid = f"{os.getpid()}_{i}_{uuid.uuid4().hex[:8]}"
        tarefa = os.path.join(spool, f"tarefa_{tid}.json")
        try:
            with open(tarefa, "w") as f:
                json.dump({"texto": texto_tts, "destino": destino}, f)
        except OSError as e:
            print(f"[{nome}] erro spool: {e}", file=sys.stderr)
            time.sleep(2)
            continue

        espera = 0
        while not os.path.exists(destino) and espera < 600:
            time.sleep(5)
            espera += 5
        if os.path.exists(destino):
            n_xtts += 1
        else:
            print(f"[{nome}] timeout XTTS trecho {i}", file=sys.stderr)

        if (n_xtts) % 5 == 0 and n_xtts:
            print(f"[{nome}] XTTS {n_xtts} em {time.time()-t0:.0f}s", file=sys.stderr, flush=True)

    print(f"[{nome}] FIM: {n_edge} edge + {n_xtts} xtts em {time.time()-t0:.0f}s", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
