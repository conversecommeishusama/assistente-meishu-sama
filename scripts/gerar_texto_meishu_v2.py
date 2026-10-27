#!/usr/bin/env python3
"""Gera o áudio de UMA obra usando o daemon XTTS persistente.

Atalho manual para uma obra: os trechos XTTS (voz do Meishu-Sama) vão para o
spool do `daemon_xtts.py` (que mantém o modelo carregado — lançar um subprocess
por trecho recarregaria 2 GB a cada vez) e os trechos do narrador são gerados
directo pelo edge-tts (~1 s).

⚠️ Este ficheiro ERA uma segunda implementação do laço de geração, e divergiu:

  · tinha a sua própria `_sanitizar()` — sem pronúncias nem remoção de macrons,
    mas com a MESMA chave de cache do `tts_service`, por isso o mesmo trecho
    saía diferente conforme tivesse sido gerado aqui ou no app;
  · chamava `sintetizar()` sem `arquivo`, ignorando a autoria (texto de
    terceiros saía na voz clonada);
  · engolia as excepções (`except Exception: pass`) e saía com 0.

Desde 2026-10-27 delega no worker do lote, que é a única implementação. Se
precisar de mudar o comportamento, mude `gerar_texto_worker_v2.py` — não
duplique aqui.

Uso:
  <venv_prod>/bin/python scripts/gerar_texto_meishu_v2.py "<arquivo.txt>"
  # ou, para a lista completa e em paralelo:
  <venv_prod>/bin/python scripts/pre_gerar_lote_orais.py --lista <lista.txt>
"""
from __future__ import annotations

import os
import sys

RAIZ = "/var/www/goshinsho"
SPOOL = os.path.join(RAIZ, "data", "tts_spool")

sys.path.insert(0, os.path.join(RAIZ, "scripts"))
from gerar_texto_worker_v2 import processar_obra  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: gerar_texto_meishu_v2.py '<arquivo.txt>'", file=sys.stderr)
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

    spool = os.environ.get("XTTS_SPOOL") or SPOOL
    os.makedirs(spool, exist_ok=True)
    # Devolve 0 só se tudo saiu; 1 se algum trecho ficou sem áudio (o relatório
    # fica em data/tts_falhas/).
    return processar_obra(caminho, spool, tts_service)


if __name__ == "__main__":
    sys.exit(main())
