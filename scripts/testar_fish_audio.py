#!/usr/bin/env python3
"""Teste de clonagem de voz na Fish Audio com a amostra kikivoice.

Objetivo: verificar (1) se o modelo S2.1 (free) suporta bem o PORTUGUÊS do
BRASIL e (2) se a voz clonada a partir da amostra kikivoice fica boa — para
comparar com o XTTS atual.

O que faz:
1. Cria um modelo de voz persistente (voice clone) a partir da amostra kikivoice.
2. Gera o MESMO trecho de teste usado na validação XTTS:
   "É o espírito de alguém que morreu em um acidente de avião..."
3. Salva em static/validacao_audio/teste_voz_fish_kikivoice.mp3 (+ wav).

Uso:
    .venv/bin/python scripts/testar_fish_audio.py [--texto "..."]
    (a chave é lida de GOSHINSHO_FISH_AUDIO_API_KEY no .env ou env FISH_API_KEY)

Modelo usado: s2.1-pro-free (US$ 0). Se não estiver mais ativo, trocar p/ s2.1-pro.
"""
from __future__ import annotations

import os
import sys

# Carrega o .env (para GOSHINSHO_FISH_AUDIO_API_KEY) sem expor a chave.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AMOSTRA = os.path.join(RAIZ, "amostras_voz", "amostra_meishu_kikivoice.wav")
SAIDA_MP3 = os.path.join(RAIZ, "static", "validacao_audio", "teste_voz_fish_kikivoice.mp3")
SAIDA_WAV = os.path.join(RAIZ, "static", "validacao_audio", "teste_voz_fish_kikivoice.wav")

# Texto de teste (mesmo da validação XTTS — fala 2 do Suplemento).
TEXTO_TESTE = ("É o espírito de alguém que morreu em um acidente de avião")

MODELO = "s2.1-pro-free"  # US$ 0 (se não vigora mais, usar "s2.1-pro")


def obter_chave() -> str:
    chave = os.environ.get("GOSHINSHO_FISH_AUDIO_API_KEY") or os.environ.get("FISH_API_KEY", "")
    if not chave:
        print("ERRO: chave não encontrada. Rode antes:")
        print("  bash scripts/definir_chave_fishaudio.sh")
        sys.exit(1)
    return chave


def main() -> int:
    if not os.path.exists(AMOSTRA):
        print(f"ERRO: amostra não encontrada: {AMOSTRA}")
        return 1

    chave = obter_chave()
    from fishaudio import FishAudio
    client = FishAudio(api_key=chave)

    print("=== Fish Audio — teste de clonagem (voz Meishu-Sama) ===")
    print(f"Modelo: {MODELO}")
    print(f"Amostra: {os.path.basename(AMOSTRA)}")
    print(f"Texto: {TEXTO_TESTE!r}\n")

    # 1. Cria modelo de voz persistente a partir da amostra.
    print("[1/3] Clonando voz a partir da amostra kikivoice...")
    with open(AMOSTRA, "rb") as f:
        voz = client.voices.create(
            title="Meishu-Sama (kikivoice)",
            voices=[f.read()],
            description="Clone da voz do Meishu-Sama a partir da amostra kikivoice",
            visibility="private",
        )
    print(f"      voice_id: {voz.id}  (state: {getattr(voz, 'state', '?')})")

    # 2. Gera o áudio com a voz clonada.
    print("[2/3] Gerando áudio (pt-BR)...")
    try:
        audio = client.tts.convert(
            text=TEXTO_TESTE,
            reference_id=voz.id,
            format="mp3",
            model=MODELO,
        )
        with open(SAIDA_MP3, "wb") as f:
            f.write(audio)
        print(f"      MP3 salvo: {SAIDA_MP3} ({os.path.getsize(SAIDA_MP3)} bytes)")
    except Exception as exc:
        print(f"      ERRO no modelo free ({MODELO}): {exc}")
        print("      Tentando com s2.1-pro (pago)...")
        audio = client.tts.convert(
            text=TEXTO_TESTE, reference_id=voz.id, format="mp3", model="s2.1-pro"
        )
        with open(SAIDA_MP3, "wb") as f:
            f.write(audio)

    # 3. Gera também em WAV (qualidade) para análise de pitch.
    print("[3/3] Gerando WAV (p/ análise)...")
    try:
        wav = client.tts.convert(
            text=TEXTO_TESTE, reference_id=voz.id, format="wav", sample_rate=44100,
            model=MODELO,
        )
        with open(SAIDA_WAV, "wb") as f:
            f.write(wav)
        print(f"      WAV salvo: {SAIDA_WAV}")
    except Exception as exc:
        print(f"      (WAV não gerado: {exc})")

    print("\n✅ Pronto! Ouça: /static/validacao_audio/teste_voz_fish_kikivoice.mp3")
    print("   (página de comparação será criada em seguida)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
