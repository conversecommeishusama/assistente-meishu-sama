#!/usr/bin/env python3
"""Gera os áudios da voz Meishu-Sama (XTTS) numa máquina com GPU.

Roda na máquina GPU sob demanda (RunPod/Vast/etc.). Lê os 83 textos orais,
segmenta como o front, e gera cada trecho com o XTTS na GPU (device cuda,
~20-50x mais rápido que CPU). Escreve os MP3 em ./saida/ com nomes por hash
(iguais ao cache do servidor: sha256 de "provedor:voz|rate|texto").

Uso:
  python3 gerar_gpu.py [--todos] [--device cuda]

Depois, copie ./saida/*.mp3 para /var/www/goshinsho/data/tts_cache/ no servidor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
TEXTOS_DIR = os.path.join(AQUI, "textos")
AMOSTRA = os.path.join(AQUI, "amostra_meishu.wav")
SAIDA_DIR = os.path.join(AQUI, "saida")
MODELO = "tts_models/multilingual/multi-dataset/xtts_v2"
RATE = "+0%"

# Versão da amostra de voz (MESMA do tts_service.py → VOZ_MEISHU_CACHE).
# Incluída na chave do cache para forçar regeneração quando a amostra mudar.
# v1 = amostra antiga (30s_limpa); v2 = remasterizada (oficial, aprovada).
VOZ_MEISHU_CACHE = "meishu:v2"

COLECOES_ORAIS = ["gokowa", "gosuiji", "mioshie"]


def _normalizar(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


# Tabela de pronúncias — MESMA do tts_service.py (PRONUNCIAS_TTS) e do antigo
# leitura_tts.js. Ao alterar uma, altere todas.
PRONUNCIAS_TTS: list[tuple[str, str]] = [
    ("Meishu-Sama", "Meichu-Sama"),
    ("Meishu Sama", "Meichu Sama"),
    ("Meishu", "Meichu"),
    ("Johrei", "Jyorei"),
    ("Ohikari-Sama", "Oricari-Sama"),
    ("Ohikari", "Oricari"),
    ("Gokōwa-roku", "Gocoua-roku"),
    ("Gokowa-roku", "Gocoua-roku"),
    ("Mioshie-shū", "Miochie-shu"),
    ("Mioshie", "Miochie"),
    ("Daikōmyō", "Daicomio"),
    ("Kōmyō", "Comio"),
    ("Nyorai", "Niorai"),
    ("Jikan", "Jicã"),
    ("Tijotengoku", "Tijotengoku"),
    ("Shinsei", "Chinsei"),
    ("Hannya", "Rania"),
    ("Shukumei", "Chukumei"),
    ("Shinrei", "Chinrei"),
    ("Ōmikami", "Omicami"),
    ("Omikami", "Omicami"),
]

_MACRON_MAP = str.maketrans({
    "ā": "a", "ē": "e", "ī": "i", "ō": "o", "ū": "u",
    "Ā": "A", "Ē": "E", "Ī": "I", "Ō": "O", "Ū": "U",
})


def _normalizar_caracteres(texto: str) -> str:
    out = (texto or "")
    out = out.replace("（", "(").replace("）", ")")
    out = out.replace("「", '"').replace("」", '"')
    out = out.replace("『", '"').replace("』", '"')
    out = out.replace("【", "[").replace("】", "]")
    out = re.sub(r"[〜～]", " ", out)
    out = re.sub(r"[\u4e00-\u9fff]+", "", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\(\s*\)", "", out)
    return out.strip()


def _aplicar_pronuncias(texto: str) -> str:
    out = texto or ""
    for termo, pron in PRONUNCIAS_TTS:
        out = re.sub(re.escape(termo), pron, out, flags=re.IGNORECASE)
    return out


def _remover_macrons(texto: str) -> str:
    return (texto or "").translate(_MACRON_MAP)


def listar_textos(todos: bool = False) -> list[str]:
    nomes = [f for f in os.listdir(TEXTOS_DIR) if f.endswith(".txt") and ".bak" not in f]
    if not todos:
        nomes = [f for f in nomes if any(c in _normalizar(f) for c in COLECOES_ORAIS)]
    nomes.sort()
    return nomes


def quebrar_como_front(texto: str) -> list[str]:
    trechos = []
    paragrafos = [re.sub(r"\s+", " ", p).strip()
                  for p in re.split(r"\n+", texto) if p.strip()]
    for par in paragrafos:
        partes = re.split(r"(?<=[.!?…])\s+", par)
        if len(partes) <= 1:
            trechos.append(par)
        else:
            bloco = ""
            for parte in partes:
                if len(bloco) + len(parte) + 1 > 700 and bloco:
                    trechos.append(bloco.strip())
                    bloco = parte
                else:
                    bloco = (bloco + " " + parte).strip() if bloco else parte
            if bloco:
                trechos.append(bloco.strip())
    return trechos


def _identificar_falante(texto: str) -> str:
    t = texto.lstrip()
    if re.match(r"^\s*(?:meishu[- ]sama|gr[ãa]o[- ]mestre|mestre)\s*:", t, re.IGNORECASE):
        return "meishu"
    if re.match(r"^\s*([^:]{2,40}):\s*", t):
        return "outro"
    return ""


def _sanitizar_xtts(texto: str) -> str:
    out = re.sub(r"^\s*[^:]{2,40}:\s*", "", texto)
    out = out.replace(";", ",").replace(":", ",")
    out = re.sub(r"\.(?=\s+[A-ZÀ-Ú])", ",", out)
    out = re.sub(r"\.\s*$", ",", out)
    out = re.sub(r"\s*\[[^\]]*\]\s*", " ", out)
    out = re.sub(r"\s*\([^)]*\)\s*", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def chave_cache(provedor_voz: str, texto: str, rate: str) -> str:
    raw = f"{provedor_voz}|{rate}|{texto}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _quebrar_segs(t: str, limite: int = 200) -> list[str]:
    if len(t) <= limite:
        return [t]
    segs, atual = [], ""
    for parte in re.split(r"(?<=[,;:.…])\s+", t):
        if len(atual) + len(parte) + 1 <= limite:
            atual = (atual + " " + parte).strip() if atual else parte
        else:
            if atual:
                segs.append(atual.strip())
            if len(parte) > limite:
                palavras, atual = parte.split(), ""
                for p in palavras:
                    if len(atual) + len(p) + 1 <= limite:
                        atual = (atual + " " + p).strip() if atual else p
                    else:
                        segs.append(atual.strip())
                        atual = p
            else:
                atual = parte
    if atual.strip():
        segs.append(atual.strip())
    return segs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    os.makedirs(SAIDA_DIR, exist_ok=True)
    if not os.path.exists(AMOSTRA):
        print(f"ERRO: amostra não encontrada: {AMOSTRA}", file=sys.stderr)
        return 1

    print(f"Carregando XTTS no device '{args.device}'...", file=sys.stderr, flush=True)
    t0 = time.time()
    from TTS.api import TTS
    tts = TTS(MODELO).to(args.device)
    print(f"Modelo carregado em {time.time()-t0:.0f}s", file=sys.stderr, flush=True)

    textos = listar_textos(todos=args.todos)
    total_gerados = 0
    total_pulados = 0
    t_inicio = time.time()

    for nome in textos:
        with open(os.path.join(TEXTOS_DIR, nome)) as f:
            conteudo = f.read()
        trechos = quebrar_como_front(conteudo)
        t_txt = time.time()
        n_txt = 0
        for trecho in trechos:
            falante = _identificar_falante(trecho)
            if falante == "outro":
                # Interlocutor -> edge-tts NAO roda aqui (sem edge na GPU?).
                # Vamos gerar edge localmente depois; aqui pulamos.
                # (Na verdade, geramos edge no servidor depois — rápido.)
                continue

            # 2026-09-05: a CHAVE usa o texto CRU + versão da amostra, MESMA
            # fórmula do tts_service (que recebe o texto cru do front). O texto
            # SINTETIZADO é o cru transformado (pronúncias + macrons + pontos
            # → vírgulas), idêntico ao que o servidor gera.
            chave = chave_cache(f"xtts:{VOZ_MEISHU_CACHE}", trecho, RATE)
            destino = os.path.join(SAIDA_DIR, f"{chave}.mp3")
            if os.path.exists(destino):
                total_pulados += 1
                continue

            # Prepara o texto para o XTTS (mesma lógica do servidor):
            # normaliza caracteres → pronúncias → remove macrons → sanitiza.
            texto_tts = _sanitizar_xtts(
                _remover_macrons(_aplicar_pronuncias(_normalizar_caracteres(trecho)))
            )
            if not texto_tts:
                continue
            # Gera (quebra em segs e concatena).
            segs = _quebrar_segs(texto_tts)
            tmp_files = []
            try:
                for i, seg in enumerate(segs):
                    tmp = os.path.join(SAIDA_DIR, f"_gpu_{os.getpid()}_{i}.wav")
                    tts.tts_to_file(text=seg, speaker_wav=AMOSTRA, language="pt",
                                    file_path=tmp)
                    tmp_files.append(tmp)
                lista = os.path.join(SAIDA_DIR, f"_gpu_lista_{os.getpid()}.txt")
                with open(lista, "w") as f:
                    for t in tmp_files:
                        f.write(f"file '{t}'\n")
                subprocess.run(
                    ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista,
                     "-c:a", "libmp3lame", "-q:a", "2", destino],
                    check=True, capture_output=True,
                )
                os.remove(lista)
                for t in tmp_files:
                    try:
                        os.remove(t)
                    except OSError:
                        pass
                total_gerados += 1
                n_txt += 1
            except Exception as e:
                print(f"ERRO trecho em {nome}: {str(e)[:120]}", file=sys.stderr)
                for t in tmp_files:
                    try:
                        os.remove(t)
                    except OSError:
                        pass
        print(f"[{nome}] +{n_txt} em {time.time()-t_txt:.0f}s (total {total_gerados})",
              file=sys.stderr, flush=True)

    print(f"\nFIM: {total_gerados} gerados, {total_pulados} já existiam, "
          f"em {(time.time()-t_inicio)/60:.1f} min", file=sys.stderr, flush=True)
    print(f"Áudios em: {SAIDA_DIR}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
