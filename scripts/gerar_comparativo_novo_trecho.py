#!/usr/bin/env python3
"""Gera comparativo com OUTRO trecho (Gosuiji-roku nº 12, L21) usando as
DUAS vozes kikivoice já clonadas na Fish Audio, sem re-clonar:
  - kikivoice original:   bee1d7a9ae9f4b71ae6abcded75503a6
  - kikivoice remaster:   ac0db2ec3d054298ad1e8bd26848588b

Gera 2 MP3 (mesmo texto, speed 0.75) p/ o usuário comparar num trecho novo.

Uso:
    .venv/bin/python scripts/gerar_comparativo_novo_trecho.py
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(RAIZ, ".env"))

MODELO = "s2.1-pro-free"
SPEED = 0.75

VOZES = {
    "kikivoice_original": ("bee1d7a9ae9f4b71ae6abcded75503a6", "kikivoice original"),
    "kikivoice_remaster": ("ac0db2ec3d054298ad1e8bd26848588b", "kikivoice remasterizado"),
}

# Novo trecho — Gosuiji-roku nº 12, L21 (caracteres possuem luz).
TEXTO_NOVO = (
    "Isso mesmo. Ou seja, até mesmo os caracteres impressos possuem luz. "
    "Pode parecer estranho dizer que possuem luz, mas até agora a luz era "
    "quase inexistente, mas gradualmente a luz está surgindo."
)


def main() -> int:
    chave = os.environ.get("GOSHINSHO_FISH_AUDIO_API_KEY") or os.environ.get("FISH_API_KEY", "")
    if not chave:
        print("ERRO: chave Fish Audio não encontrada no .env")
        return 1

    from fishaudio import FishAudio
    client = FishAudio(api_key=chave)

    print("=== Comparativo Fish — novo trecho (Gosuiji-roku nº 12, L21) ===")
    print(f"Speed: {SPEED} | Modelo: {MODELO}\n")

    for nome, (voice_id, rotulo) in VOZES.items():
        print(f"[*] Gerando com {rotulo} ({voice_id[:8]}...)...")
        audio = client.tts.convert(
            text=TEXTO_NOVO,
            reference_id=voice_id,
            format="mp3",
            speed=SPEED,
            model=MODELO,
        )
        destino = os.path.join(RAIZ, "static", "validacao_audio",
                               f"teste_voz_fish_{nome}_G12L21_speed0.75.mp3")
        with open(destino, "wb") as f:
            f.write(audio)
        print(f"      ✅ {os.path.basename(destino)} ({os.path.getsize(destino)} bytes)")

    print("\n✅ Pronto! Dois áudios gerados com o mesmo trecho novo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
