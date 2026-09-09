#!/usr/bin/env python3
"""Teste de throughput/volume na Fish Audio.

Pega ~10 trechos reais de MEISHU-SAMA do corpus (via mesma segmentação),
gera cada um com a tag híbrida aprovada + speed 0.75, e mede:
  - tempo por trecho
  - bytes por trecho
  - projeção p/ os 16.262 trechos

Uso:
    /var/www/goshinsho/.venv/bin/python scripts/testar_volume_fish.py
"""
from __future__ import annotations

import os
import sys
import time

from dotenv import load_dotenv

RAIZ = "/var/www/goshinsho"
load_dotenv(os.path.join(RAIZ, ".env"))

TEXTOS_DIR = os.path.join(RAIZ, "data/pacote_gpu/textos")
MODELO = "s2.1-pro-free"
SPEED = 0.75
VOICE_ID = "ac0db2ec3d054298ad1e8bd26848588b"
TAG = "[standard Brazilian Portuguese, clear diction, no foreign accent, precise articulation, careful speech] "

N_TESTE = 10


def quebrar_como_front(texto: str) -> list[str]:
    import re
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


def identificar_meishu(texto: str) -> bool:
    import re
    t = texto.lstrip()
    if re.match(r"^\s*(?:meishu[- ]sama|gr[ãa]o[- ]mestre|mestre)\s*:", t, re.IGNORECASE):
        return True
    if re.match(r"^\s*([^:]{2,40}):\s*", t):
        return False
    return True  # texto corrido


def main() -> int:
    chave = os.environ.get("GOSHINSHO_FISH_AUDIO_API_KEY") or os.environ.get("FISH_API_KEY", "")
    if not chave:
        print("ERRO: chave não encontrada")
        return 1

    from fishaudio import FishAudio
    client = FishAudio(api_key=chave)

    # Coleta trechos Meishu do 1º texto (Suplemento) e de mais alguns.
    todos_meishu = []
    for nome in sorted(os.listdir(TEXTOS_DIR)):
        if not nome.endswith(".txt") or ".bak" in nome:
            continue
        with open(os.path.join(TEXTOS_DIR, nome), encoding="utf-8") as f:
            conteudo = f.read()
        for tr in quebrar_como_front(conteudo):
            if identificar_meishu(tr):
                # remove rótulo "Meishu-Sama:" do início p/ leitura natural
                import re
                tr_limpo = re.sub(r"^\s*(?:meishu[- ]sama|gr[ãa]o[- ]mestre|mestre)\s*:\s*", "", tr)
                todos_meishu.append(tr_limpo)
        if len(todos_meishu) >= N_TESTE:
            break

    amostra = todos_meishu[:N_TESTE]
    print(f"=== Teste de volume: {len(amostra)} trechos Meishu ===")
    print(f"Voz: kikivoice remaster | Speed: {SPEED} | Modelo: {MODELO}\n")

    total_t = 0.0
    total_bytes = 0
    total_chars = 0
    for i, tr in enumerate(amostra, 1):
        texto = TAG + tr
        t0 = time.time()
        audio = client.tts.convert(
            text=texto, reference_id=VOICE_ID, format="mp3",
            speed=SPEED, model=MODELO,
        )
        dt = time.time() - t0
        total_t += dt
        total_bytes += len(audio)
        total_chars += len(tr)
        print(f"  [{i}/{len(amostra)}] {len(tr):>4} chars → {dt:5.1f}s ({len(audio)} bytes)")

    media_t = total_t / len(amostra)
    media_chars = total_chars / len(amostra)
    print(f"\n=== Resultados ===")
    print(f"Média: {media_t:.1f}s/trecho | {media_chars:.0f} chars/trecho")
    print(f"Throughput: {len(amostra)/total_t*60:.1f} trechos/min")
    # Projeção p/ 16.262 trechos (só os 6,28M chars Meishu)
    trechos_totais = 16262
    proj_min = trechos_totais / (len(amostra)/total_t*60)
    print(f"Projeção p/ {trechos_totais} trechos: ~{proj_min/60:.1f} horas")
    print(f"(se free tier tiver limite diário, pode precisar de vários dias)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
