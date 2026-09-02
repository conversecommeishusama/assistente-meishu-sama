#!/usr/bin/env python3
"""Gera AMOSTRAS DE TESTE (v2) com três correções pedidas pelo usuário:

1. MANTER pitch0 (sem mudança de pitch no pós-processamento).
2. CORRIGIR "fala ponto": testa duas sanitizações do texto:
     - v1: ponto final ". " -> ", " (vírgula = pausa curta, não vocaliza)
     - v2: ponto final ". " -> "... " (reticências = pausa maior)
3. REDUZIR RUÍDO da amostra original (ffmpeg afftdn + highpass) antes de
   clonar — a gravação de 1952 tem ruído de fundo que degrada o clone.

Gera (para comparar):
  amostras_voz/teste_voz_gokowa_v1_virgula.mp3   (amostra limpa + vírgulas)
  amostras_voz/teste_voz_gokowa_v2_reticencias.mp3 (amostra limpa + reticências)

Uso:
    venv_xtts/bin/python scripts/gerar_teste_voz_v2.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

AMOSTRA_ORIGINAL = os.path.join(RAIZ, "amostras_voz", "amostra_meishu_30s.wav")
AMOSTRA_LIMPA = os.path.join(RAIZ, "amostras_voz", "amostra_meishu_30s_limpa.wav")

TEXTO_ORIGINAL = (
    "Há alguma razão nisso. Não fique especulando sobre isso; "
    "entregue-se à natureza. Agora está começando o Grande Acerto de Contas. "
    "Ser salvo por Kannon-Sama é isto: pessoas cujo destino é perecer "
    "não têm como se salvar sem morrer de modo algum."
)

DEVICE = "cpu"


def limpar_amostra() -> str:
    """Reduz ruído de fundo da amostra com ffmpeg (afftdn + highpass)."""
    if not os.path.exists(AMOSTRA_LIMPA):
        print("[0/4] Reduzindo ruído da amostra original...")
        cmd = [
            "ffmpeg", "-y", "-i", AMOSTRA_ORIGINAL,
            # highpass corta rumble < 70 Hz; afftdn remove ruído estacionário.
            "-af", "highpass=f=70,afftdn=nf=-35",
            "-ar", "22050", "-ac", "1", AMOSTRA_LIMPA,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"      amostra limpa salva: {os.path.basename(AMOSTRA_LIMPA)}")
    return AMOSTRA_LIMPA


def sanitizar_base(texto: str) -> str:
    """Sanitização comum: tira ';' e ':' (vira pausa) e notas editoriais."""
    out = texto
    out = out.replace(";", ",")
    out = out.replace(":", ",")
    out = re.sub(r"\s*\[[^\]]*\]\s*", " ", out)  # [nota editorial]
    out = re.sub(r"\s*\([^)]*\)\s*", " ", out)   # (nota)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def sanitizar_v1(texto: str) -> str:
    """Ponto final ". " -> ", " (vírgula). NÃO deve ler 'ponto'."""
    out = sanitizar_base(texto)
    # Só os pontos seguidos de espaço (fim de frase), preserva reticências.
    out = re.sub(r"\.(?=\s+[A-ZÀ-Ú])", ",", out)
    out = re.sub(r"\.\s*$", ",", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def sanitizar_v2(texto: str) -> str:
    """Ponto final -> reticências "... " (pausa maior, não vocaliza)."""
    out = sanitizar_base(texto)
    out = re.sub(r"\.(?=\s+[A-ZÀ-Ú])", "...", out)
    out = re.sub(r"\.\s*$", "...", out)
    out = re.sub(r"\.{4,}", "...", out)  # normaliza múltiplas
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def quebrar_segmentos(texto: str, limite: int = 200) -> list[str]:
    """Quebra o texto em segmentos <= limite chars, em fronteiras de vírgula
    ou espaço, para respeitar o limite do XTTS por língua (PT ~203 chars).

    O XTTS v2 TRUNCA áudio acima do limite por chamada — por isso dividimos.
    """
    if len(texto) <= limite:
        return [texto]
    segs: list[str] = []
    atual = ""
    # Quebra em vírgulas/pontos/reticências (pausas naturais).
    partes = re.split(r"(?<=[,;:.…])\s+", texto)
    for parte in partes:
        if len(atual) + len(parte) + 1 <= limite:
            atual = (atual + " " + parte).strip() if atual else parte
        else:
            if atual:
                segs.append(atual.strip())
            # Se uma única parte ainda é longa, quebra por espaço.
            if len(parte) > limite:
                palavras = parte.split()
                atual = ""
                for palavra in palavras:
                    if len(atual) + len(palavra) + 1 <= limite:
                        atual = (atual + " " + palavra).strip() if atual else palavra
                    else:
                        segs.append(atual.strip())
                        atual = palavra
            else:
                atual = parte
    if atual.strip():
        segs.append(atual.strip())
    return segs


def sintetizar_segmentos(tts, texto: str, amostra: str, destino_final: str) -> None:
    """Sintetiza por segmentos <=200 chars e concatena em um MP3 final."""
    import subprocess as sp

    segs = quebrar_segmentos(texto)
    temporarios: list[str] = []
    try:
        for i, seg in enumerate(segs):
            tmp = os.path.join(RAIZ, "amostras_voz", f"_tmp_seg_{i}.wav")
            tts.tts_to_file(text=seg, speaker_wav=amostra, language="pt", file_path=tmp)
            temporarios.append(tmp)
            print(f"      segmento {i+1}/{len(segs)} OK ({len(seg)} chars)")
        # Concatena com ffmpeg (lista de arquivos).
        lista = os.path.join(RAIZ, "amostras_voz", "_tmp_lista.txt")
        with open(lista, "w") as f:
            for tmp in temporarios:
                f.write(f"file '{tmp}'\n")
        sp.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista,
             "-c:a", "libmp3lame", "-q:a", "2", destino_final],
            check=True, capture_output=True,
        )
        print(f"      concatenado → {os.path.basename(destino_final)}")
    finally:
        for tmp in temporarios:
            try:
                os.remove(tmp)
            except OSError:
                pass
        try:
            os.remove(os.path.join(RAIZ, "amostras_voz", "_tmp_lista.txt"))
        except OSError:
            pass


def main() -> int:
    if not os.path.exists(AMOSTRA_ORIGINAL):
        print(f"ERRO: amostra não encontrada: {AMOSTRA_ORIGINAL}")
        return 1

    amostra = limpar_amostra()

    t0 = time.time()
    print("[1/4] Carregando XTTS v2...")
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

    casos = [
        ("v1_virgula", sanitizar_v1(TEXTO_ORIGINAL), "teste_voz_gokowa_v1_virgula.mp3"),
        ("v2_reticencias", sanitizar_v2(TEXTO_ORIGINAL), "teste_voz_gokowa_v2_reticencias.mp3"),
    ]

    for nome, texto, arquivo in casos:
        destino = os.path.join(RAIZ, "amostras_voz", arquivo)
        print(f"\n[2/4] {nome}: sintetizando em segmentos ({len(texto)} chars)...")
        try:
            sintetizar_segmentos(tts, texto, amostra, destino)
        except Exception as exc:
            print(f"      ERRO: {exc}")
            continue
        print(f"      OK: {os.path.basename(destino)} ({os.path.getsize(destino)} bytes)")

    print("\nOUÇA e compare (ambos com amostra sem ruído e pitch original):")
    for _, _, arquivo in casos:
        print(f"  - {arquivo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
