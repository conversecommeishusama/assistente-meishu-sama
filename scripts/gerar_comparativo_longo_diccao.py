#!/usr/bin/env python3
"""Comparativo com TEXTO LONGO (L37, 552 chars) das variações de dicção
na Fish Audio, mesma voz (kikivoice remasterizada).

O usuário achou que as tags de dicção melhoraram. Este teste usa um texto
bem mais longo p/ avaliar se a dicção se mantém consistente.

Uso:
    .venv/bin/python scripts/gerar_comparativo_longo_diccao.py
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

# Fala longa (L37, 552 chars) — música japonesa vs ocidental.
TEXTO_LONGO = (
    "Também na música, os japoneses deveriam reconhecer as qualidades do Japão. "
    "Na música japonesa, o koto é o melhor; algo tão magnífico o Ocidente não tem. "
    "A música japonesa é estática; a ocidental é dinâmica. Aí está a diferença. "
    "O Ocidente também tem muitas canções de ninar, mas nenhuma cumpre tão bem "
    "as condições de uma canção de ninar quanto a do Japão. Quando se ouve a do "
    "Japão, dá sono; mas com a do Ocidente, mesmo quando a gente está a ponto de "
    "pegar no sono, acaba acordando. Seria bom se uma música magnífica surgisse "
    "do Japão."
)

# Baseline (sem tag) + as tags que pareceram melhorar.
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

    print(f"=== Comparativo TEXTO LONGO (L37, {len(TEXTO_LONGO)} chars) ===")
    print(f"Voz: kikivoice remasterizada | Speed: {SPEED}\n")

    for nome, tag in VARIANTS:
        texto = (tag or "") + TEXTO_LONGO
        print(f"[*] {nome}: {tag or '(sem tag)'}")
        audio = client.tts.convert(
            text=texto,
            reference_id=VOICE_ID,
            format="mp3",
            speed=SPEED,
            model=MODELO,
        )
        destino = os.path.join(RAIZ, "static", "validacao_audio",
                               f"teste_diccao_fish_longo_{nome}.mp3")
        with open(destino, "wb") as f:
            f.write(audio)
        print(f"      ✅ {os.path.basename(destino)} ({os.path.getsize(destino)} bytes)")

    print("\n✅ Pronto! Texto longo gerado em todas as variações.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
