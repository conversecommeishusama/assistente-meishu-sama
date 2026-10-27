#!/usr/bin/env python3
"""Worker de pré-geração de áudio (voz Meishu-Sama) para UM texto da Leitura.

Gera todos os trechos de um texto (como o front os envia ao /api/tts) com a
voz 'meishu' — que decide: Meishu-Sama → XTTS local, Interlocutor → Antônio
(edge-tts). Usa o MESMO tts_service da rota /api/tts, então respeita o cache
(GOSHINSHO_TTS_CACHE) e não regenera o que já existe.

Uso:
    <venv_prod>/bin/python scripts/gerar_texto_meishu.py "<nome do arquivo .txt>"

Saída: os MP3 ficam no cache (data/tts_cache). Escreve o progresso em stderr.
"""
from __future__ import annotations

import os
import re
import sys
import time

RAIZ = "/var/www/goshinsho"


def quebrar_como_front(texto: str) -> list[str]:
    """Reproduz a segmentação do leitura_tts.js (quebrarEmFrases)."""
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
    if len(sys.argv) < 2:
        print("uso: gerar_texto_meishu.py '<arquivo.txt>'", file=sys.stderr)
        return 2
    nome = sys.argv[1]
    caminho = os.path.join(RAIZ, "textos_leitura_colaborativa", nome)
    if not os.path.exists(caminho):
        print(f"arquivo não encontrado: {caminho}", file=sys.stderr)
        return 1

    sys.path.insert(0, RAIZ)
    os.chdir(RAIZ)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, ".env"))
    from goshinsho.services import tts_service

    with open(caminho) as f:
        texto = f.read()
    trechos = quebrar_como_front(texto)

    # Pré-computa o nome do arquivo de cache de cada trecho para pular os que
    # já existem (o cache é por provedor+voz+texto+rate).
    # 2026-10-27: esta pré-computação era uma QUARTA cópia da regra de
    # roteamento (junto com provedor_canonico, caminho_em_cache e o worker do
    # lote) e não passava `arquivo`, por isso ignorava a autoria: texto de
    # terceiros saía na voz clonada. Agora usa o serviço.
    def _ja_existe(t: str) -> bool:
        return tts_service.caminho_em_cache(t, arquivo=nome) is not None

    pendentes = [t for t in trechos if not _ja_existe(t)]

    print(f"[{nome}] {len(trechos)} trechos, {len(pendentes)} a gerar", file=sys.stderr)
    t0 = time.time()
    n_ok = 0
    n_erro = 0
    for i, trecho in enumerate(trechos):
        # Já está no cache? (pode ter sido gerado por outro worker)
        if _ja_existe(trecho):
            continue
        try:
            tts_service.sintetizar(trecho, voz="meishu", arquivo=nome)
            n_ok += 1
            if n_ok % 5 == 0:
                print(f"  [{nome}] {i+1}/{len(trechos)} (+{n_ok}) {time.time()-t0:.0f}s", file=sys.stderr)
        except Exception as e:
            n_erro += 1
            print(f"  [{nome}] ERRO trecho {i}: {str(e)[:100]}", file=sys.stderr)
            time.sleep(1)

    print(f"[{nome}] FIM: {n_ok} gerados, {n_erro} erros, em {time.time()-t0:.0f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
