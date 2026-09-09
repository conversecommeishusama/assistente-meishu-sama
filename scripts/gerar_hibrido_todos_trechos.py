#!/usr/bin/env python3
"""Gera a versão HÍBRIDA (v2+v3) em TODOS os trechos testados.

Tag híbrida combina as características aprovadas:
  v2: standard Brazilian Portuguese, precise articulation
  v3: clear diction, no foreign accent, careful speech
  → "[standard Brazilian Portuguese, clear diction, no foreign accent,
      precise articulation, careful speech] "

Mesma voz (kikivoice remasterizada), speed 0.75.

Uso:
    .venv/bin/python scripts/gerar_hibrido_todos_trechos.py
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
TAG = "[standard Brazilian Portuguese, clear diction, no foreign accent, precise articulation, careful speech] "

TRECHOS = [
    ("A_aviao", "É o espírito de alguém que morreu em um acidente de avião"),
    ("B_L43_arte", (
        "Eu também gosto de obras de arte, mas as antigas é que são as "
        "verdadeiramente novas. As recentes não têm novidade genuína alguma. "
        "Na música também deve haver esse aspecto. É algo verdadeiramente "
        "misterioso. Eu não consigo entender o jazz. Afinal, é para dançar. "
        "Não é possível apreciar a música em si."
    )),
    ("C_L17_musica", (
        "Ficou muito bem-feita, tem um estilo de gagaku. É muito melhor do que "
        "o budismo, por exemplo. A música budista não tem vitalidade; é como se "
        "algo arrastasse a gente para o mundo espiritual. Afinal, deve ser porque "
        "quem a executa são os monges. Na música ocidental, o Messias, de Handel, "
        "é superior. Mesmo nesse nível, é uma obra notável. Também há uma de "
        "Mendelssohn."
    )),
    ("D_G12L21_caracteres", (
        "Isso mesmo. Ou seja, até mesmo os caracteres impressos possuem luz. "
        "Pode parecer estranho dizer que possuem luz, mas até agora a luz era "
        "quase inexistente, mas gradualmente a luz está surgindo."
    )),
    ("E_L37_koto", (
        "Também na música, os japoneses deveriam reconhecer as qualidades do Japão. "
        "Na música japonesa, o koto é o melhor; algo tão magnífico o Ocidente não tem. "
        "A música japonesa é estática; a ocidental é dinâmica. Aí está a diferença. "
        "O Ocidente também tem muitas canções de ninar, mas nenhuma cumpre tão bem "
        "as condições de uma canção de ninar quanto a do Japão. Quando se ouve a do "
        "Japão, dá sono; mas com a do Ocidente, mesmo quando a gente está a ponto de "
        "pegar no sono, acaba acordando. Seria bom se uma música magnífica surgisse "
        "do Japão."
    )),
]


def main() -> int:
    chave = os.environ.get("GOSHINSHO_FISH_AUDIO_API_KEY") or os.environ.get("FISH_API_KEY", "")
    if not chave:
        print("ERRO: chave não encontrada")
        return 1

    from fishaudio import FishAudio
    client = FishAudio(api_key=chave)

    print(f"=== Gerando versão HÍBRIDA (v2+v3) em {len(TRECHOS)} trechos ===")
    print(f"Voz: kikivoice remaster | Speed: {SPEED}")
    print(f"Tag: {TAG.strip()}\n")

    for nome, texto in TRECHOS:
        print(f"[*] {nome} ({len(texto)} chars)...")
        try:
            audio = client.tts.convert(
                text=TAG + texto,
                reference_id=VOICE_ID,
                format="mp3",
                speed=SPEED,
                model=MODELO,
            )
            destino = os.path.join(RAIZ, "static", "validacao_audio",
                                   f"teste_hibrido_{nome}.mp3")
            with open(destino, "wb") as f:
                f.write(audio)
            print(f"      ✅ {os.path.basename(destino)} ({os.path.getsize(destino)} bytes)")
        except Exception as e:
            print(f"      ❌ ERRO: {e}")

    print("\n✅ Pronto! Versão híbrida gerada em todos os trechos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
