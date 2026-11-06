#!/usr/bin/env python3
"""Compara objetivamente pares de áudios de validação da voz Meishu-Sama.

Objetivo: descobrir quais arquivos são o MESMO áudio (mesma fala, mesmo
conteúdo) — apenas re-encodados/copiados — e quais são sínteses DIFERENTES.

Método: para cada par, alinha por correlação cruzada no domínio do tempo
(após decodificar p/ 16kHz mono) e mede o erro médio absoluto normalizado
(MAE) e a correlação de Pearson no melhor alinhamento:
  - MAE baixo + correlação ~1.0  → mesmo áudio (re-encode/cópia)
  - correlação alta mas MAE médio → mesma fala, síntese ligeiramente diferente
  - correlação baixa             → falas/conteúdos diferentes

Uso:
    /var/www/goshinsho/.venv/bin/python scripts/comparar_audios_validacao.py
"""
from __future__ import annotations

import os

import librosa
import numpy as np

RAIZ = "/var/www/goshinsho"

# Pares suspeitos de serem o mesmo áudio/fala entre as duas séries remaster
# e entre a "atual" (22kHz) e a "remaster".
PARES = [
    # mesma fala, séries diferentes (17:05-06 amostras_voz vs 17:07 static)
    ("amostras_voz/validacao/remaster_0.mp3", "static/validacao_audio/meishu_remaster_1.mp3"),
    ("amostras_voz/validacao/remaster_1.mp3", "static/validacao_audio/meishu_remaster_2.mp3"),
    ("amostras_voz/validacao/remaster_2.mp3", "static/validacao_audio/meishu_remaster_3.mp3"),
    # mesma fala, "atual" (22kHz) vs remaster (referência da página comparar)
    ("static/validacao_audio/meishu_1.mp3", "static/validacao_audio/meishu_remaster_1.mp3"),
    ("static/validacao_audio/meishu_2.mp3", "static/validacao_audio/meishu_remaster_2.mp3"),
    ("static/validacao_audio/meishu_3.mp3", "static/validacao_audio/meishu_remaster_3.mp3"),
    # meishu_fala (amostras_voz/validacao, originais) vs as cópias em static
    ("amostras_voz/validacao/meishu_fala_010.mp3", "static/validacao_audio/meishu_1.mp3"),
    ("amostras_voz/validacao/meishu_fala_042.mp3", "static/validacao_audio/meishu_2.mp3"),
    ("amostras_voz/validacao/meishu_fala_051.mp3", "static/validacao_audio/meishu_3.mp3"),
    ("amostras_voz/validacao/meishu_fala_010.mp3", "amostras_voz/validacao/remaster_0.mp3"),
    ("amostras_voz/validacao/meishu_fala_042.mp3", "amostras_voz/validacao/remaster_1.mp3"),
    ("amostras_voz/validacao/meishu_fala_051.mp3", "amostras_voz/validacao/remaster_2.mp3"),
]


def _carregar(caminho: str) -> np.ndarray:
    p = os.path.join(RAIZ, caminho)
    y, _ = librosa.load(p, sr=16000, mono=True)
    return y


def comparar(a: str, b: str) -> tuple[float, float, int, int]:
    x = _carregar(a)
    y = _carregar(b)
    n = min(len(x), len(y))
    if n < 1000:
        return float("nan"), float("nan"), len(x), len(y)
    x, y = x[:n], y[:n]
    # correlação cruzada p/ achar o melhor deslocamento (±0,2s)
    maxlag = int(0.2 * 16000)
    xc = np.correlate(x - x.mean(), y - y.mean(), mode="full")
    lag = int(np.argmax(xc) - (len(x) - 1))
    lag = max(-maxlag, min(maxlag, lag))
    if lag > 0:
        xx, yy = x[lag:], y[: len(x) - lag]
    elif lag < 0:
        xx, yy = x[: len(x) + lag], y[-lag:]
    else:
        xx, yy = x, y
    m = min(len(xx), len(yy))
    xx, yy = xx[:m], yy[:m]
    if m < 1000:
        return float("nan"), float("nan"), len(x), len(y)
    corr = float(np.corrcoef(xx, yy)[0, 1])
    mae = float(np.mean(np.abs(xx - yy)))
    return corr, mae, len(x), len(y)


def main() -> int:
    print(f"{'par':<78} {'corr':>7} {'mae':>8} {'n1':>7} {'n2':>7}  veredito")
    print("-" * 120)
    for a, b in PARES:
        pa = os.path.join(RAIZ, a)
        pb = os.path.join(RAIZ, b)
        if not (os.path.exists(pa) and os.path.exists(pb)):
            print(f"{a}  vs  {b}\n{'':<76} (arquivo ausente)")
            continue
        corr, mae, n1, n2 = comparar(a, b)
        if corr != corr:
            veredito = "n/d"
        elif corr > 0.99 and mae < 0.02:
            veredito = "MESMO áudio (cópia/re-encode)"
        elif corr > 0.90:
            veredito = "mesma fala, síntese varia"
        elif corr > 0.75:
            veredito = "provável mesma fala, bem diferente"
        else:
            veredito = "conteúdos diferentes"
        print(f"{a}  vs  {b}")
        print(f"{'':<3}corr={corr:.4f}  mae={mae:.4f}  n1={n1}  n2={n2}  → {veredito}")
    return 0


if __name__ == "__main__":
    main()
