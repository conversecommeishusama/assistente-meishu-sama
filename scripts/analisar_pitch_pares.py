#!/usr/bin/env python3
"""Compara pitch/timbre entre as DUAS sínteses da mesma fala (remaster).

A fala 2 (remaster_1.mp3 vs meishu_remaster_2.mp3) tem a MESMA duração
(~5,16s) e o MESMO texto, mas correlação 0.71 → sínteses diferentes.
Objetivo: ver qual é "mais masculina" (f0 mais grave) e qual tem timbre
mais limpo — para reconstruir qual versão foi aprovada.

Também compara a fala 1 (remaster_0/meishu_remaster_1 são idênticos → única
versão) e fala 3 (remaster_2/meishu_remaster_3 idênticos).

Uso:
    /var/www/goshinsho/.venv/bin/python scripts/analisar_pitch_pares.py
"""
from __future__ import annotations

import os

import librosa
import numpy as np

RAIZ = "/var/www/goshinsho"

GRUPOS = {
    "fala1 (Fujiwara/Debune)": [
        "amostras_voz/validacao/remaster_0.mp3",
        "static/validacao_audio/meishu_remaster_1.mp3",
    ],
    "fala2 (espírito/acidente)": [
        "amostras_voz/validacao/remaster_1.mp3",        # 17:06
        "static/validacao_audio/meishu_remaster_2.mp3",  # 17:07 (na página)
        "static/validacao_audio/meishu_2.mp3",           # versão 22kHz (16:52)
    ],
    "fala3 (Amatsu Norito)": [
        "amostras_voz/validacao/remaster_2.mp3",
        "static/validacao_audio/meishu_remaster_3.mp3",
        "static/validacao_audio/meishu_3.mp3",           # versão 22kHz (16:52)
    ],
    "fala1b (Fujiwara, versão 22kHz)": [
        "static/validacao_audio/meishu_1.mp3",
    ],
}


def _analisar(caminho: str) -> dict:
    p = os.path.join(RAIZ, caminho)
    y, sr = librosa.load(p, sr=22050, mono=True)
    out = {"arq": caminho}
    # f0 com pyin
    try:
        f0, voiced, _ = librosa.pyin(
            y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C5"),
            sr=sr, frame_length=2048)
        vals = f0[voiced & np.isfinite(f0)]
        if len(vals):
            out["f0_med"] = float(np.median(vals))
            out["f0_mean"] = float(np.mean(vals))
            out["f0_p25"] = float(np.percentile(vals, 25))
        else:
            out["f0_med"] = out["f0_mean"] = out["f0_p25"] = float("nan")
    except Exception:
        out["f0_med"] = out["f0_mean"] = out["f0_p25"] = float("nan")
    # espectro (centroide)
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
    out["cent"] = float(np.mean(librosa.feature.spectral_centroid(S=S, sr=sr)))
    out["roll"] = float(np.mean(librosa.feature.spectral_rolloff(S=S, sr=sr, roll_percent=0.85)))
    out["dur"] = round(len(y) / sr, 2)
    out["rms"] = float(np.sqrt(np.mean(y ** 2)))
    return out


def main() -> int:
    for nome, arquivos in GRUPOS.items():
        print(f"\n=== {nome} ===")
        print(f"{'arquivo':<52} {'dur':>6} {'f0med':>7} {'f0mean':>7} {'f0p25':>7} {'cent':>7} {'roll':>7}")
        for a in arquivos:
            if not os.path.exists(os.path.join(RAIZ, a)):
                print(f"{a:<52}  (ausente)")
                continue
            r = _analisar(a)
            print(f"{r['arq']:<52} {r['dur']:>6} {r['f0_med']:>7.1f} {r['f0_mean']:>7.1f} "
                  f"{r['f0_p25']:>7.1f} {r['cent']:>7.0f} {r['roll']:>7.0f}")
    return 0


if __name__ == "__main__":
    main()
