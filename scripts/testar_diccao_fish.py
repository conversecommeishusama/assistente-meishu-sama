#!/usr/bin/env python3
"""Testa se tags de linguagem natural do Fish S2.1 reduzem o sotaque japonês
e melhoram a dicção, mantendo a mesma voz clonada (kikivoice remasterizada).

O usuário notou que a voz clonada tem sotaque japonês que atrapalha palavras
como "caracteres". O S2.1 aceita tags como [clear], [neutral accent], etc.
Este script gera o MESMO trecho com a MESMA voz, variando a instrução:

  v0: texto puro (baseline)
  v1: [neutral accent, clear enunciation]
  v2: [standard Brazilian Portuguese, precise articulation]
  v3: [clear diction, no foreign accent]

Uso:
    .venv/bin/python scripts/testar_diccao_fish.py
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(RAIZ, ".env"))

MODELO = "s2.1-pro-free"
SPEED = 0.75
VOICE_ID = "ac0db2ec3d054298ad1e8bd26848588b"  # kikivoice remasterizado

# Texto curto focado na palavra problemática + uma frase.
TEXTO_BASE = (
    "Ou seja, até mesmo os caracteres impressos possuem luz. "
    "Pode parecer estranho dizer que possuem luz."
)

# Variações de instrução (tags de linguagem natural do S2).
VARIANTS = [
    ("v0_base", None),
    ("v1_neutral", "[neutral accent, clear enunciation] "),
    ("v2_brasileiro", "[standard Brazilian Portuguese, precise articulation] "),
    ("v3_diccao", "[clear diction, no foreign accent, careful speech] "),
]


def main() -> int:
    chave = os.environ.get("GOSHINSHO_FISH_AUDIO_API_KEY") or os.environ.get("FISH_API_KEY", "")
    if not chave:
        print("ERRO: chave não encontrada")
        return 1

    from fishaudio import FishAudio
    client = FishAudio(api_key=chave)

    print("=== Teste de dicção — Fish S2.1 (voz kikivoice remaster) ===")
    print(f"Speed: {SPEED}\n")

    for nome, tag in VARIANTS:
        texto = (tag or "") + TEXTO_BASE
        print(f"[*] {nome}: {tag or '(sem tag)'}")
        audio = client.tts.convert(
            text=texto,
            reference_id=VOICE_ID,
            format="mp3",
            speed=SPEED,
            model=MODELO,
        )
        destino = os.path.join(RAIZ, "static", "validacao_audio",
                               f"teste_diccao_fish_{nome}.mp3")
        with open(destino, "wb") as f:
            f.write(audio)
        print(f"      ✅ {os.path.basename(destino)} ({os.path.getsize(destino)} bytes)")

    print("\n✅ Pronto! Compare as variações.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
