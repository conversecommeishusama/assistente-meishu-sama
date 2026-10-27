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

COLECOES_ORAIS = ["gokowa", "gosuiji", "mioshie"]


def _normalizar(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


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
    """⚠️ Já não decide nada — a autoria e o falante são do serviço.

    Fica só como documentação do que aqui se fazia: um teste de rótulo de fala
    que mandava para a voz clonada todo trecho sem rótulo, inclusive os de obra
    de terceiros (testemunhos assinados, por exemplo). Ver `preparar_texto`.
    """
    t = texto.lstrip()
    if re.match(r"^\s*(?:meishu[- ]sama|gr[ãa]o[- ]mestre|mestre)\s*:", t, re.IGNORECASE):
        return "meishu"
    if re.match(r"^\s*([^:]{2,40}):\s*", t):
        return "outro"
    return ""


def _sanitizar_xtts(texto: str) -> str:
    """Fragmento final da preparação do XTTS (fallback sem o app importável).

    ⚠️ NÃO é a preparação completa: falta a normalização de caracteres, as
    pronúncias e a remoção de macrons que o serviço aplica. Usar isto para
    gerar áudio com a chave de cache do serviço produz um ficheiro com o MESMO
    nome e conteúdo diferente do que o app geraria — foi o que aconteceu em
    2026-10-27, quando o worker do lote e este gerador tinham cada um a sua
    cópia. `preparar_texto()` abaixo usa a do serviço quando ela existe.
    """
    out = re.sub(r"^\s*[^:]{2,40}:\s*", "", texto)
    out = out.replace(";", ",").replace(":", ",")
    out = re.sub(r"\.(?=\s+[A-ZÀ-Ú])", ",", out)
    out = re.sub(r"\.\s*$", ",", out)
    out = re.sub(r"\s*\[[^\]]*\]\s*", " ", out)
    out = re.sub(r"\s*\([^)]*\)\s*", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _servico():
    """Importa o `tts_service` do repositório, ou None se não estiver aqui.

    Procura a raiz do repositório a partir do directório deste ficheiro (e um
    nível acima, para o caso de correr a partir de `data/pacote_gpu/`). Só assim
    há uma única fonte de verdade para a preparação do texto e para a autoria.
    """
    candidato = AQUI
    for _ in range(3):
        if os.path.isdir(os.path.join(candidato, "goshinsho", "services")):
            if candidato not in sys.path:
                sys.path.insert(0, candidato)
            try:
                from goshinsho.services import tts_service
                return tts_service
            except Exception:
                return None
        candidato = os.path.dirname(candidato)
    return None


def preparar_texto(texto: str, arquivo: str, servico) -> str | None:
    """Texto que o XTTS vai ler — a preparação do SERVIÇO, não uma cópia.

    Devolve None quando o trecho não é do Meishu-Sama (autoria) ou quando não
    sobra nada pronunciável. Antes, este gerador só olhava o rótulo de fala:
    testemunhos sem rótulo, dentro de obra de terceiros, eram gerados na voz
    clonada — trabalho perdido e ficheiros que o serviço nunca serve.
    """
    if servico is not None:
        try:
            if servico.provedor_canonico(texto, RATE, arquivo=arquivo)[0] != "xtts":
                return None
            return servico._preparar_texto_xtts(texto)
        except Exception as e:
            print(f"AVISO: falha na preparação do serviço ({e}) — a usar o "
                  f"fallback local, que NÃO aplica pronúncias nem macrons.",
                  file=sys.stderr, flush=True)
    return _sanitizar_xtts(texto)


def chave_cache(provedor_voz: str, texto: str, rate: str) -> str:
    raw = f"{provedor_voz}|{rate}|{texto}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# Versão da amostra de voz, IGUAL à canónica do serviço (`tts_service.
# VOZ_MEISHU_CACHE`). 2026-10-22: este gerador gravava sob "xtts:meishu" (sem
# versão) enquanto o app procurava "xtts:meishu:v2" — 1.784 áudios produzidos em
# Outubro (3 dias de CPU) ficaram invisíveis para o serviço. Ao trocar a amostra,
# mudar AQUI e no serviço, no mesmo commit.
VOZ_MEISHU_CACHE = "meishu:v2"


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

    # Uma só fonte de verdade para a preparação e a autoria (ver `preparar_texto`).
    servico = _servico()
    if servico is None:
        print("AVISO: `goshinsho.services.tts_service` não é importável a partir "
              "daqui. A preparação do texto e a autoria caem num fallback LOCAL "
              "que não é equivalente ao que o app gera — os mp3 terão o nome "
              "certo e o texto preparado de outra forma. Para evitar isso, "
              "corra este script a partir de uma cópia do repositório.",
              file=sys.stderr, flush=True)

    for nome in textos:
        with open(os.path.join(TEXTOS_DIR, nome)) as f:
            conteudo = f.read()
        trechos = quebrar_como_front(conteudo)
        t_txt = time.time()
        n_txt = 0
        for trecho in trechos:
            # Autoria + preparação: uma só decisão, a do serviço.
            # (Aqui havia um teste de rótulo de fala que gerava na voz clonada
            # todo trecho sem rótulo — inclusive os de obra de terceiros.)
            texto_tts = preparar_texto(trecho, nome, servico)
            if not texto_tts:
                continue
            chave = chave_cache(f"xtts:{VOZ_MEISHU_CACHE}", trecho, RATE)
            destino = os.path.join(SAIDA_DIR, f"{chave}.mp3")
            if os.path.exists(destino):
                total_pulados += 1
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
