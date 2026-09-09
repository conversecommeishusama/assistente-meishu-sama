#!/usr/bin/env python3
"""Teste de reprodutibilidade/variabilidade do XTTS com a amostra oficial.

Contexto: na validação de 03/09, a MESMA fala 2 ("É o espírito de alguém que
morreu em um acidente de avião...") gerada com a MESMA amostra remasterizada
produziu DUAS sínteses com pitch diferente:
  - remaster_1.mp3 (17:06): f0 med ~159 Hz (mais grave/masculino)
  - meishu_remaster_2.mp3 (17:07): f0 med ~166 Hz
O usuário notou que a versão atual parece "menos masculina" que a que ele
aprovou. Hipótese: o XTTS é estocástico e o tom varia entre execuções, OU
mudou algo no pipeline (semente, versão, pós-processamento).

Este script sintetiza o MESMO texto 3x com a amostra oficial e mede o f0 de
cada repetição, para verificar se a variação entre execuções explica a
diferença de ~7 Hz observada.

Uso (CPU, no venv_xtts):
    venv_xtts/bin/python scripts/testar_variabilidade_xtts.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AMOSTRA = os.path.join(RAIZ, "amostras_voz", "amostra_meishu_oficial.wav")
SAIDA_DIR = os.path.join(RAIZ, "amostras_voz", "teste_variabilidade")
os.makedirs(SAIDA_DIR, exist_ok=True)

# Texto da fala 2 de validação (cortado no "avião" — como o áudio aprovado).
TEXTO = "É o espírito de alguém que morreu em um acidente de avião"

N_REPETICOES = 3


def sintetizar(texto: str, destino: str) -> None:
    from TTS.api import TTS
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
    tts.tts_to_file(text=texto, speaker_wav=AMOSTRA, language="pt",
                    file_path=destino)


def medir_f0(caminho: str) -> float:
    import librosa
    import numpy as np
    y, sr = librosa.load(caminho, sr=22050, mono=True)
    f0, voiced, _ = librosa.pyin(
        y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C5"),
        sr=sr, frame_length=2048)
    vals = f0[voiced & np.isfinite(f0)]
    return float(np.median(vals)) if len(vals) else float("nan")


def main() -> int:
    if not os.path.exists(AMOSTRA):
        print(f"ERRO: amostra não encontrada: {AMOSTRA}")
        return 1
    t0 = time.time()
    for i in range(1, N_REPETICOES + 1):
        destino = os.path.join(SAIDA_DIR, f"rep_{i}.wav")
        print(f"[{i}/{N_REPETICOES}] sintetizando...", flush=True)
        t1 = time.time()
        sintetizar(TEXTO, destino)
        f0 = medir_f0(destino)
        print(f"      OK em {time.time()-t1:.0f}s  f0 mediano = {f0:.1f} Hz  "
              f"({os.path.getsize(destino)} bytes)")
    print(f"\nTotal: {time.time()-t0:.0f}s. Áudios em {SAIDA_DIR}")
    print("Compare os f0 — se variarem ~7 Hz entre execuções, o XTTS é a causa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
