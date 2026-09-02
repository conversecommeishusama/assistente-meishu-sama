#!/usr/bin/env python3
"""Worker de pré-geração de áudio (voz Meishu-Sama) para UM texto da Leitura.

Gera todos os trechos de um texto (como o front os envia ao /api/tts) com a
voz 'meishu' — que decide: Meishu-Sama → XTTS local, Interlocutor → Antônio
(edge-tts). Usa o MESMO tts_service da rota /api/tts, então respeita o cache
(GOSHINSHO_TTS_CACHE) e não regenera o que já existe.

Uso:
    <venv_prod>/bin/python scripts/gerar_texto_meishu.py "<nome do arquivo .txt>"

Saída: os MP3 ficam no cache (data/tts_cache). Escreve o progresso em stderr.
"""
from __future__ import annotations

import os
import re
import sys
import time

RAIZ = "/var/www/goshinsho"


def quebrar_como_front(texto: str) -> list[str]:
    """Reproduz a segmentação do leitura_tts.js (quebrarEmFrases)."""
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


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: gerar_texto_meishu.py '<arquivo.txt>'", file=sys.stderr)
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

    # Pré-computa o nome do arquivo de cache de cada trecho para pular os que
    # já existem (o cache é por provedor+voz+texto+rate).
    rate = "+0%"
    pendentes = []
    for t in trechos:
        # Identifica provedor (igual ao tts_service): xtts p/ meishu/corrido,
        # edge p/ interlocutor. Usamos o mesmo _chave_cache.
        voz_origem = "meishu"
        if not tts_service.voz_meishu_disponivel():
            provedor, voz_real = "edge", "pt-BR-AntonioNeural"
        else:
            falante = tts_service._identificar_falante(t)
            if falante == "outro":
                provedor, voz_real = "edge", tts_service.VOZ_INTERLOCUTOR
            else:
                provedor, voz_real = "xtts", "meishu"
        chave = tts_service._chave_cache(f"{provedor}:{voz_real}", t, rate)
        destino = os.path.join(tts_service._cache_dir(), f"{chave}.mp3")
        if not os.path.exists(destino):
            pendentes.append(t)

    print(f"[{nome}] {len(trechos)} trechos, {len(pendentes)} a gerar", file=sys.stderr)
    t0 = time.time()
    n_ok = 0
    n_erro = 0
    for i, trecho in enumerate(trechos):
        # Já está no cache? (pode ter sido gerado por outro worker)
        voz_origem = "meishu"
        if not tts_service.voz_meishu_disponivel():
            provedor, voz_real = "edge", "pt-BR-AntonioNeural"
        else:
            falante = tts_service._identificar_falante(trecho)
            if falante == "outro":
                provedor, voz_real = "edge", tts_service.VOZ_INTERLOCUTOR
            else:
                provedor, voz_real = "xtts", "meishu"
        chave = tts_service._chave_cache(f"{provedor}:{voz_real}", trecho, rate)
        destino = os.path.join(tts_service._cache_dir(), f"{chave}.mp3")
        if os.path.exists(destino):
            continue
        try:
            tts_service.sintetizar(trecho, voz="meishu")
            n_ok += 1
            if n_ok % 5 == 0:
                print(f"  [{nome}] {i+1}/{len(trechos)} (+{n_ok}) {time.time()-t0:.0f}s", file=sys.stderr)
        except Exception as e:
            n_erro += 1
            print(f"  [{nome}] ERRO trecho {i}: {str(e)[:100]}", file=sys.stderr)
            time.sleep(1)

    print(f"[{nome}] FIM: {n_ok} gerados, {n_erro} erros, em {time.time()-t0:.0f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
