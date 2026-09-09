#!/usr/bin/env python3
"""Análise acústica comparativa das amostras/áudios da voz Meishu-Sama.

Mede, para cada arquivo de áudio:
  - f0 (pitch) médio/mediana via pyin (librosa) — só em trechos sonoros
  - centroide espectral médio (Hz) — proxy de "brilho"/timbre
  - rolloff 85% (Hz) — concentração de energia
  - RMS médio (volume)

Objetivo: dar evidência objetiva sobre qual versão soa "mais masculina"
(pitch mais grave) e qual tem timbre mais limpo/rico.

Uso:
    /var/www/goshinsho/.venv/bin/python scripts/analisar_pitch_amostras.py
"""
from __future__ import annotations

import os
import sys

import librosa
import numpy as np

RAIZ = "/var/www/goshinsho"

ARQUIVOS = [
    # amostras de referência (wav)
    "amostras_voz/S290226_hawai.mp3",            # original 1952
    "amostras_voz/amostra_meishu_30s.wav",       # 1ª extração
    "amostras_voz/amostra_meishu_30s_limpa.wav", # limpa 22kHz (antiga)
    "amostras_voz/amostra_meishu_remaster.wav",  # remaster (17:02)
    "amostras_voz/amostra_meishu_oficial.wav",   # = remaster (oficial)
    "amostras_voz/amostra_meishu_kikivoice.wav", # kikivoice (nova)
    # validação "versão atual" (22kHz) — 03/09 16:52
    "static/validacao_audio/meishu_1.mp3",
    "static/validacao_audio/meishu_2.mp3",
    "static/validacao_audio/meishu_3.mp3",
    # validação "remasterizada aprovada" — 03/09 17:07
    "static/validacao_audio/meishu_remaster_1.mp3",
    "static/validacao_audio/meishu_remaster_2.mp3",
    "static/validacao_audio/meishu_remaster_3.mp3",
    # primeira série remaster — 03/09 17:05-06 (amostras_voz/validacao)
    "amostras_voz/validacao/remaster_0.mp3",
    "amostras_voz/validacao/remaster_1.mp3",
    "amostras_voz/validacao/remaster_2.mp3",
    # teste comparativo 08/09 (atual vs kikivoice)
    "static/validacao_audio/teste_voz_atual.mp3",
    "static/validacao_audio/teste_voz_kikivoice.mp3",
    # testes de pitch antigos
    "amostras_voz/teste_voz_gokowa_pitch0.mp3",
    "amostras_voz/teste_voz_gokowa_pitch-3.mp3",
]


def medir(caminho: str) -> dict | None:
    p = os.path.join(RAIZ, caminho)
    if not os.path.exists(p):
        return None
    y, sr = librosa.load(p, sr=22050, mono=True)
    if len(y) < sr * 0.3:  # < 0.3s, sem análise confiável
        return None
    # --- f0 (pyin) só onde há voz ---
    try:
        f0, voiced_flag, _ = librosa.pyin(
            y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C5"),
            sr=sr, frame_length=2048)
        f0_vals = f0[voiced_flag]
        f0_ok = f0_vals[np.isfinite(f0_vals)]
        f0_med = float(np.median(f0_ok)) if len(f0_ok) else float("nan")
        f0_mean = float(np.mean(f0_ok)) if len(f0_ok) else float("nan")
        f0_p25 = float(np.percentile(f0_ok, 25)) if len(f0_ok) else float("nan")
        f0_p75 = float(np.percentile(f0_ok, 75)) if len(f0_ok) else float("nan")
    except Exception:
        f0_med = f0_mean = f0_p25 = f0_p75 = float("nan")
    # --- espectro ---
    try:
        S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
        freqs = librosa.fft_frequencies(sr=sr)
        cent = float(np.mean(librosa.feature.spectral_centroid(S=S, sr=sr)))
        roll = float(np.mean(librosa.feature.spectral_rolloff(S=S, sr=sr, roll_percent=0.85)))
        bw = float(np.mean(librosa.feature.spectral_bandwidth(S=S, sr=sr)))
    except Exception:
        cent = roll = bw = float("nan")
    rms = float(np.sqrt(np.mean(y ** 2)))
    return {
        "arq": caminho,
        "dur_s": round(len(y) / sr, 2),
        "f0_med": round(f0_med, 1),
        "f0_mean": round(f0_mean, 1),
        "f0_p25": round(f0_p25, 1),
        "f0_p75": round(f0_p75, 1),
        "centroide_hz": round(cent, 0),
        "rolloff_hz": round(roll, 0),
        "bandwidth_hz": round(bw, 0),
        "rms": round(rms, 4),
    }


def main() -> int:
    print(f"{'arquivo':<48} {'dur':>6} {'f0med':>7} {'f0mean':>7} "
          f"{'f0p25':>7} {'f0p75':>7} {'cent':>7} {'roll':>7} {'bw':>7} {'rms':>7}")
    print("-" * 120)
    for caminho in ARQUIVOS:
        r = medir(caminho)
        if r is None:
            print(f"{caminho:<48}  (ausente ou muito curto)")
            continue
        print(f"{r['arq']:<48} {r['dur_s']:>6} {r['f0_med']:>7} {r['f0_mean']:>7} "
              f"{r['f0_p25']:>7} {r['f0_p75']:>7} {r['centroide_hz']:>7.0f} "
              f"{r['rolloff_hz']:>7.0f} {r['bandwidth_hz']:>7.0f} {r['rms']:>7.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
