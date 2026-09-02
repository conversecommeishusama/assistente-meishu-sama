#!/usr/bin/env python3
"""Gera uma AMOSTRA DE TESTE da voz clonada de Meishu-Sama (XTTS v2) falando
português, a partir da amostra de áudio histórico em japonês.

Uso:
    python3 scripts/gerar_teste_voz_meishu.py
Saída:
    amostras_voz/teste_voz_meishu_pt.mp3  (frase curta em português)
"""
from __future__ import annotations

import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

AMOSTRA = os.path.join(RAIZ, "amostras_voz", "amostra_meishu_30s.wav")
SAIDA = os.path.join(RAIZ, "amostras_voz", "teste_voz_meishu_gokowa.mp3")

# Trecho autêntico do Gokōwa-roku (Suplemento, 1948-01-01) — fala de
# Meishu-Sama sobre o Grande Acerto de Contas (texto em português).
TEXTO_TESTE = (
    "Há alguma razão nisso. Não fique especulando sobre isso; "
    "entregue-se à natureza. Agora está começando o Grande Acerto de Contas. "
    "Ser salvo por Kannon-Sama é isto: pessoas cujo destino é perecer "
    "não têm como se salvar sem morrer de modo algum."
)

# Dispositivo: CPU (o servidor não tem GPU).
DEVICE = "cpu"


def main() -> int:
    if not os.path.exists(AMOSTRA):
        print(f"ERRO: amostra não encontrada: {AMOSTRA}")
        return 1

    t0 = time.time()
    print(f"[1/3] Carregando XTTS v2 (modelo ~1.8 GB, primeira vez demora)...")
    try:
        from TTS.api import TTS
    except Exception as exc:
        print(f"ERRO ao importar TTS: {exc}")
        return 1

    try:
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(DEVICE)
    except Exception as exc:
        print(f"ERRO ao carregar o modelo: {exc}")
        return 1
    print(f"      modelo carregado em {time.time()-t0:.0f}s")

    t1 = time.time()
    print("[2/3] Clonando voz a partir da amostra e sintetizando em português...")
    try:
        tts.tts_to_file(
            text=TEXTO_TESTE,
            speaker_wav=AMOSTRA,
            language="pt",
            file_path=SAIDA,
        )
    except Exception as exc:
        print(f"ERRO ao sintetizar: {exc}")
        return 1

    print(f"      síntese concluída em {time.time()-t1:.0f}s")
    print(f"[3/3] Salvo em: {SAIDA}")
    print(f"      Tamanho: {os.path.getsize(SAIDA)} bytes")
    print("\nOUÇA este arquivo para avaliar a voz.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
