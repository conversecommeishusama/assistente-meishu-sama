#!/usr/bin/env python3
"""Piloto: gera as falas de UM texto (Gosuiji-roku nº 12) no cache do app
via Fish Audio, replicando EXATAMENTE o que o front envia ao servidor.

Isso valida o alinhamento de chave de ponta a ponta: os MP3 ficam no
data/tts_cache com o nome que o app vai procurar quando o usuário clicar
para ouvir.

A transformação replicada (do static/js/leitura_tts.js):
  1. quebrar o texto em trechos (parágrafos → frases, blocos até ~700)
  2. para cada trecho, aplicarPronuncias() (troca Meishu→Meichu etc.)
  3. sanitizarParaTTS() (remove kanji, converte aspas japonesas etc.)
  4. enviar ao servidor: sintetizar(texto_processado, voz='meishu', rate='+0%')

Uso:
    /var/www/goshinsho/.venv/bin/python scripts/piloto_fish_1texto.py
"""
from __future__ import annotations

import os
import re
import sys

RAIZ = "/var/www/goshinsho"
sys.path.insert(0, RAIZ)
os.environ.setdefault("GOSHINSHO_TTS_CACHE", os.path.join(RAIZ, "data/tts_cache"))

# Texto piloto: Gosuiji-roku nº 12 (mesmo usado nos testes de voz).
ARQUIVO = "/var/www/goshinsho/textos_leitura_colaborativa/19520825 - Gosuiji-roku nº 12.txt"

# --- PRONUNCIAS (cópia EXATA do leitura_tts.js) ---
PRONUNCIAS = [
    ["Meishu-Sama", "Meichu-Sama"], ["Meishu Sama", "Meichu Sama"], ["Meishu", "Meichu"],
    ["Johrei", "Jyorei"], ["Ohikari", "Oricari"], ["Ohikari-Sama", "Oricari-Sama"],
    ["Gokōwa-roku", "Gocoua-roku"], ["Gokowa-roku", "Gocoua-roku"],
    ["Mioshie-shū", "Miochie-shu"], ["Mioshie", "Miochie"], ["Daikōmyō", "Daicomio"],
    ["Kōmyō", "Comio"], ["Nyorai", "Niorai"], ["Jikan", "Jicã"], ["Tijotengoku", "Tijotengoku"],
    ["Shinsei", "Chinsei"], ["Hannya", "Rania"], ["Shukumei", "Chukumei"], ["Shinrei", "Chinrei"],
    ["Ōmikami", "Omicami"], ["Omikami", "Omicami"],
]


def sanitizar(texto: str) -> str:
    out = texto
    out = out.replace("（", "(").replace("）", ")")
    out = out.replace("「", '"').replace("」", '"')
    out = out.replace("『", '"').replace("』", '"')
    out = out.replace("【", "[").replace("】", "]")
    out = re.sub(r"[〜～]", " ", out)
    out = re.sub(r"[\u4e00-\u9fff]+", "", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\(\s*\)", "", out)
    return out.strip()


def aplicar_pronuncias(texto: str) -> str:
    out = texto
    for termo, pron in PRONUNCIAS:
        out = re.sub(re.escape(termo), pron, out, flags=re.IGNORECASE)
    return sanitizar(out)


def quebrar_como_front(texto: str) -> list[str]:
    """Segmenta como o front (parágrafos → frases, blocos até ~700 chars)."""
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


def main() -> int:
    if not os.path.exists(ARQUIVO):
        print(f"ERRO: arquivo não encontrado: {ARQUIVO}")
        return 1

    from goshinsho.services import tts_service

    with open(ARQUIVO, encoding="utf-8") as f:
        conteudo = f.read()

    trechos = quebrar_como_front(conteudo)
    print(f"=== Piloto Fish — {os.path.basename(ARQUIVO)} ===")
    print(f"{len(trechos)} trechos no total\n")

    n_meishu = 0
    n_interlocutor = 0
    n_cache = 0
    n_gerado = 0
    n_erro = 0

    for i, trecho in enumerate(trechos, 1):
        # Aplica a transformação que o front faz ANTES de enviar.
        texto_front = trecho  # v7: front envia texto CRU
        if not texto_front:
            continue
        # Chama o servidor (mesma rota do app). Ele decide o falante e o provedor.
        try:
            caminho = tts_service.sintetizar(texto_front, voz="meishu", rate="+0%")
        except Exception as exc:
            print(f"  [{i}] ERRO: {str(exc)[:80]}")
            n_erro += 1
            continue

        nome = os.path.basename(caminho)
        # Classifica (pelo rótulo original) só p/ estatística.
        if re.match(r"^\s*(?:meishu[- ]sama|meichu[- ]sama|gr[ãa]o[- ]mestre|mestre)\s*:", trecho, re.IGNORECASE) \
           or not re.match(r"^\s*[^:]{2,40}:\s*", trecho):
            n_meishu += 1
        else:
            n_interlocutor += 1

        # Detecta se veio do cache (já existia) ou foi gerado agora.
        # O sintetizar retorna o caminho; se o arquivo foi criado agora,
        # o mtime é recente — mas simplificamos: verificamos se é Fish
        # pelo prefixo da chave (fish:) é difícil pós-hash; contamos só sucesso.
        n_gerado += 1
        if i % 20 == 0 or i == len(trechos):
            print(f"  ...{i}/{len(trechos)} processados ({n_gerado} ok, {n_erro} erros)")

    print(f"\n=== Resumo ===")
    print(f"Trechos Meishu (Fish/edge-tts quando Interlocutor): {n_meishu}")
    print(f"Trechos Interlocutor (edge/Antônio): {n_interlocutor}")
    print(f"OK gerados/encontrados no cache: {n_gerado}")
    print(f"Erros: {n_erro}")
    print(f"\nCache em: {tts_service._cache_dir()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
