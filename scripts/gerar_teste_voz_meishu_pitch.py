#!/usr/bin/env python3
"""Gera AMOSTRAS DE TESTE da voz de Meishu-Sama (XTTS v2) com correções:

1. SANITIZAÇÃO: remove/vocaliza corretamente a pontuação (evita que o XTTS
   leia "." como "ponto", ":" como "dois pontos", etc.).
2. PITCH MAIS GRAVE: a voz clonada saiu um pouco aguda/feminina; aplica um
   ajuste de pitch (atempo/semitons) via ffmpeg para deixar mais masculina.

Gera 2 arquivos para comparação:
  amostras_voz/teste_voz_gokowa_pitch0.mp3   (pitch original do XTTS)
  amostras_voz/teste_voz_gokowa_pitch-3.mp3  (3 semitons abaixo — mais grave)

Uso:
    venv_xtts/bin/python scripts/gerar_teste_voz_meishu_pitch.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

AMOSTRA = os.path.join(RAIZ, "amostras_voz", "amostra_meishu_30s.wav")
BASE = os.path.join(RAIZ, "amostras_voz", "teste_voz_gokowa")

# Trecho do Gokōwa-roku (Suplemento) — com pontuação que o XTTS tende a ler.
TEXTO_TESTE = (
    "Há alguma razão nisso. Não fique especulando sobre isso; "
    "entregue-se à natureza. Agora está começando o Grande Acerto de Contas. "
    "Ser salvo por Kannon-Sama é isto: pessoas cujo destino é perecer "
    "não têm como se salvar sem morrer de modo algum."
)

DEVICE = "cpu"

# Variações de pitch (semitons, negativo = mais grave) para comparar.
PITCHES = [0, -3]  # original e 3 semitons abaixo


def sanitizar(texto: str) -> str:
    """Prepara o texto para o XTTS ler sem vocalizar pontuação.

    O XTTS v2 tende a ler pontos finais/dois-pontos como "ponto", "dois
    pontos" etc. Estratégia: troca pontuação problemática por pausas que o
    XTTS respeita (vírgula/ponto final mantidos como pausa natural, mas sem
    serem "falados"), e normaliza caracteres especiais.
    """
    out = texto
    # Vírgulas e ponto-e-vírgula: substitui por vírgula (pausa curta) —
    # o XTTS não vocaliza vírgula.
    out = out.replace(";", ",")
    # Dois-pontos: vira pausa (vírgula) para não ler "dois pontos".
    out = out.replace(":", ",")
    # Ponto final: o XTTS às vezes lê "ponto". Mantém o ponto mas garante
    # espaço depois (já há). Pode-se usar reticências para pausa maior,
    # mas manteremos o ponto — em testes o XTTS costuma tratá-lo como pausa.
    # (Se ainda ler, o fallback é trocar por vírgula — deixamos configurável.)
    # Parênteses: remove conteúdo que são anotações editoriais [entre chaves].
    out = re.sub(r"\s*\[[^\]]*\]\s*", " ", out)  # [nota editorial]
    out = re.sub(r"\s*\([^)]*\)\s*", " ", out)   # (nota)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def aplicar_pitch(entrada: str, saida: str, semitons: int) -> None:
    """Ajusta o pitch do áudio com ffmpeg (atempo preserva a velocidade).

    Nota: o XTTS grava um WAV com extensão .mp3; por isso SEMPRE re-encoda
    para MP3 real (libmp3lame), mesmo com semitons=0.
    """
    import math
    fator = 2 ** (semitons / 12.0)
    if semitons == 0:
        # Sem mudança de pitch — apenas converte para MP3 real.
        cmd = [
            "ffmpeg", "-y", "-i", entrada,
            "-c:a", "libmp3lame", "-q:a", "2", saida,
        ]
    else:
        # Para baixar o pitch mantendo a duração: sobe o sample rate e
        # compensa com atempo. ratio = fator (negativo → mais grave).
        ratio = fator
        cmd = [
            "ffmpeg", "-y", "-i", entrada,
            "-af", f"asetrate=24000*{ratio:.6f},aresample=24000,atempo={1/ratio:.6f}",
            "-c:a", "libmp3lame", "-q:a", "2", saida,
        ]
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> int:
    if not os.path.exists(AMOSTRA):
        print(f"ERRO: amostra não encontrada: {AMOSTRA}")
        return 1

    texto_limpo = sanitizar(TEXTO_TESTE)
    print("=== Texto enviado ao XTTS (sanitizado) ===")
    print(f"  {texto_limpo}")
    print()

    t0 = time.time()
    print("[1/3] Carregando XTTS v2...")
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

    # Gera o áudio base (pitch original) uma única vez.
    base_mp3 = BASE + "_base.mp3"
    if not os.path.exists(base_mp3):
        t1 = time.time()
        print("[2/3] Sintetizando (pitch original)...")
        try:
            tts.tts_to_file(
                text=texto_limpo,
                speaker_wav=AMOSTRA,
                language="pt",
                file_path=base_mp3,
            )
        except Exception as exc:
            print(f"ERRO ao sintetizar: {exc}")
            return 1
        print(f"      síntese em {time.time()-t1:.0f}s")

    # Gera as variações de pitch.
    for semitons in PITCHES:
        saida = f"{BASE}_pitch{semitons}.mp3"
        print(f"[3/3] Aplicando pitch {semitons:+d} semitons → {os.path.basename(saida)}")
        aplicar_pitch(base_mp3, saida, semitons)
        print(f"      OK ({os.path.getsize(saida)} bytes)")

    print()
    print("OUÇA e compare:")
    for semitons in PITCHES:
        print(f"  - {os.path.basename(BASE)}_pitch{semitons}.mp3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
