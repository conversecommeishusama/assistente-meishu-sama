#!/usr/bin/env python3
"""Gera uma versão comparativa na Fish Audio clonando a voz do Meishu-Sama
diretamente da amostra amostra_meishu_30s.wav (extração do áudio de 1952),
sem passar pelo kikivoice.

Gera o MESMO trecho do último teste (L43, speed 0.75) para o usuário comparar
com a versão baseada no kikivoice.

Uso:
    .venv/bin/python scripts/gerar_fish_amostra_30s.py
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(RAIZ, ".env"))

AMOSTRA = os.path.join(RAIZ, "amostras_voz", "amostra_meishu_30s.wav")
MODELO = "s2.1-pro-free"
SPEED = 0.75

# Mesmo trecho do último teste (L43 do Suplemento).
TEXTO = (
    "Eu também gosto de obras de arte, mas as antigas é que são as "
    "verdadeiramente novas. As recentes não têm novidade genuína alguma. "
    "Na música também deve haver esse aspecto. É algo verdadeiramente "
    "misterioso. Eu não consigo entender o jazz. Afinal, é para dançar. "
    "Não é possível apreciar a música em si."
)

SAIDA = os.path.join(RAIZ, "static", "validacao_audio",
                     "teste_voz_fish_amostra30s_L43_speed0.75.mp3")


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

    print("=== Fish Audio — clone da amostra_meishu_30s.wav (1952) ===")
    print(f"Amostra: {os.path.basename(AMOSTRA)}")
    print(f"Speed: {SPEED} | Modelo: {MODELO}\n")

    # 1. Clona a voz a partir da amostra de 30s (japonês, 1952).
    print("[1/2] Clonando voz a partir de amostra_meishu_30s.wav...")
    with open(AMOSTRA, "rb") as f:
        voz = client.voices.create(
            title="Meishu-Sama (amostra 30s 1952)",
            voices=[f.read()],
            description="Clone da voz do Meishu-Sama a partir do áudio de 1952 (30s)",
            visibility="private",
        )
    print(f"      voice_id: {voz.id}  (state: {getattr(voz, 'state', '?')})")

    # 2. Gera o trecho (L43) em speed 0.75.
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
