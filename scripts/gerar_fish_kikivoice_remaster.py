#!/usr/bin/env python3
"""Gera uma versão na Fish Audio clonando a amostra KIKIVOICE REMASTERIZADA
(amostra_meishu_kikivoice_remaster.wav — kikivoice + o mesmo tratamento de
limpeza/equalização de clareza usado na remaster do 1952).

Objetivo: o usuário aprovou a versão kikivoice mas quer dicção ainda mais
clara. Aplicar o tratamento (afftdn + equalização 1500/3500Hz + loudnorm)
pode realçar a clareza mantendo a qualidade do kikivoice.

Gera o MESMO trecho (L43, speed 0.75) p/ comparar.

Uso:
    .venv/bin/python scripts/gerar_fish_kikivoice_remaster.py
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(RAIZ, ".env"))

AMOSTRA = os.path.join(RAIZ, "amostras_voz", "amostra_meishu_kikivoice_remaster.wav")
MODELO = "s2.1-pro-free"
SPEED = 0.75

TEXTO = (
    "Eu também gosto de obras de arte, mas as antigas é que são as "
    "verdadeiramente novas. As recentes não têm novidade genuína alguma. "
    "Na música também deve haver esse aspecto. É algo verdadeiramente "
    "misterioso. Eu não consigo entender o jazz. Afinal, é para dançar. "
    "Não é possível apreciar a música em si."
)

SAIDA = os.path.join(RAIZ, "static", "validacao_audio",
                     "teste_voz_fish_kikivoice_remaster_L43_speed0.75.mp3")


def main() -> int:
    chave = os.environ.get("GOSHINSHO_FISH_AUDIO_API_KEY") or os.environ.get("FISH_API_KEY", "")
    if not chave:
        print("ERRO: chave Fish Audio não encontrada no .env")
        return 1
    if not os.path.exists(AMOSTRA):
        print(f"ERRO: amostra não encontrada: {AMOSTRA}")
        return 1

    from fishaudio import FishAudio
    client = FishAudio(api_key=chave)

    print("=== Fish Audio — clone do KIKIVOICE REMASTERIZADO ===")
    print(f"Amostra: {os.path.basename(AMOSTRA)}")
    print(f"Speed: {SPEED} | Modelo: {MODELO}\n")

    print("[1/2] Clonando voz a partir de amostra_meishu_kikivoice_remaster.wav...")
    with open(AMOSTRA, "rb") as f:
        voz = client.voices.create(
            title="Meishu-Sama (kikivoice remaster)",
            voices=[f.read()],
            description="Kikivoice + tratamento de clareza (afftdn + eq 1500/3500Hz + loudnorm)",
            visibility="private",
        )
    print(f"      voice_id: {voz.id}  (state: {getattr(voz, 'state', '?')})")

    print("[2/2] Gerando áudio (L43, speed 0.75)...")
    audio = client.tts.convert(
        text=TEXTO,
        reference_id=voz.id,
        format="mp3",
        speed=SPEED,
        model=MODELO,
    )
    with open(SAIDA, "wb") as f:
        f.write(audio)

    print(f"✅ MP3 salvo: {os.path.basename(SAIDA)} ({os.path.getsize(SAIDA)} bytes)")
    print(f"   Ouça: /static/validacao_audio/{os.path.basename(SAIDA)}")
    print(f"\nNOTA: voice_id desta versão = {voz.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
