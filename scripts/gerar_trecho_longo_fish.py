#!/usr/bin/env python3
"""Gera um TRECHO LONGO na Fish Audio com a voz clonada do Meishu-Sama,
em velocidade reduzida (speed=0.75 — que o usuário aprovou).

Usa o voice_id persistente já criado no teste anterior
(bee1d7a9ae9f4b71ae6abcded75503a6) — evita re-clonar.

Uso:
    .venv/bin/python scripts/gerar_trecho_longo_fish.py [--speed 0.75]
"""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(RAIZ, ".env"))

# Voice_id persistente criado no teste (clone da amostra kikivoice).
VOICE_ID = "bee1d7a9ae9f4b71ae6abcded75503a6"
MODELO = "s2.1-pro-free"

# Texto: fala contínua do Meishu-Sama (Suplemento L43) — 260 chars.
TEXTO_LONGO = (
    "Eu também gosto de obras de arte, mas as antigas é que são as "
    "verdadeiramente novas. As recentes não têm novidade genuína alguma. "
    "Na música também deve haver esse aspecto. É algo verdadeiramente "
    "misterioso. Eu não consigo entender o jazz. Afinal, é para dançar. "
    "Não é possível apreciar a música em si."
)

# Texto: fala L17 (Suplemento) — 384 chars (ainda mais longa, opcional).
TEXTO_EXTRA = (
    "Ficou muito bem-feita, tem um estilo de gagaku. É muito melhor do que "
    "o budismo, por exemplo. A música budista não tem vitalidade; é como se "
    "algo arrastasse a gente para o mundo espiritual. Afinal, deve ser porque "
    "quem a executa são os monges. Na música ocidental, o Messias, de Handel, "
    "é superior. Mesmo nesse nível, é uma obra notável. Também há uma de "
    "Mendelssohn."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=float, default=0.75)
    ap.add_argument("--texto", choices=["L43", "L17"], default="L43")
    args = ap.parse_args()

    chave = os.environ.get("GOSHINSHO_FISH_AUDIO_API_KEY") or os.environ.get("FISH_API_KEY", "")
    if not chave:
        print("ERRO: chave Fish Audio não encontrada no .env")
        return 1

    texto = TEXTO_LONGO if args.texto == "L43" else TEXTO_EXTRA
    rotulo = "L43" if args.texto == "L43" else "L17"
    destino = os.path.join(RAIZ, "static", "validacao_audio",
                           f"teste_voz_fish_longo_{rotulo}_speed{args.speed:.2f}.mp3")

    from fishaudio import FishAudio
    client = FishAudio(api_key=chave)

    print(f"=== Fish Audio — trecho longo ({rotulo}, {len(texto)} chars) ===")
    print(f"Velocidade: {args.speed}x | Modelo: {MODELO}")
    print(f"Voz: {VOICE_ID}\n")

    print("[1/1] Gerando áudio...")
    audio = client.tts.convert(
        text=texto,
        reference_id=VOICE_ID,
        format="mp3",
        speed=args.speed,
        model=MODELO,
    )
    with open(destino, "wb") as f:
        f.write(audio)

    print(f"✅ MP3 salvo: {os.path.basename(destino)} ({os.path.getsize(destino)} bytes)")
    print(f"   Ouça: /static/validacao_audio/{os.path.basename(destino)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
