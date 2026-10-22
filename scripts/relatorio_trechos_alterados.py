#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Relatório dos TRECHOS que mudaram entre duas versões de uma obra.

Por que existe (2026-10-22):
    `scripts/sincronizar_audios.py` diz quantos trechos estão sem áudio, mas
    junta duas coisas muito diferentes:
      (a) trechos que MUDARAM (ou nasceram) com a última edição do texto;
      (b) trechos que nunca chegaram a ser gerados (pré-geração incompleta).
    Ao actualizar o acervo de produção é preciso saber **exactamente** o que
    mudou — são esses os áudios a refazer; os de (b) seguem o plano normal de
    pré-geração.

Chave de comparação: o próprio texto do trecho (a chave do cache de áudio é o
sha256 de `provedor|rate|texto`). Comparar por chave — e nunca por índice —
é o que evita o bug histórico de "índices deslizam e os trechos ficam mudos".

Uso:
    # Pares descobertos automaticamente (.bak_promocao_* mais recente × actual)
    .venv/bin/python scripts/relatorio_trechos_alterados.py

    # Um par explícito
    .venv/bin/python scripts/relatorio_trechos_alterados.py \\
        --antigo "textos_leitura_colaborativa/Eiko.txt.bak_promocao_X" \\
        --novo   "textos_leitura_colaborativa/Eiko.txt"

    # Exportar a lista dos trechos novos para ficheiro
    .venv/bin/python scripts/relatorio_trechos_alterados.py --json /tmp/novos.json

    # Comparar com o acervo que estava em produção (backup completo)
    .venv/bin/python scripts/relatorio_trechos_alterados.py \
        --dir-antigo backups/acervo_producao_20261022T133647Z/textos_leitura_colaborativa

Saída: relatório legível + código 0. Só lê; não gera áudio nem altera texto.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("GOSHINSHO_TTS_CACHE", str(RAIZ / "data/tts_cache"))

from goshinsho.services import tts_service  # noqa: E402


def _spec_glf():
    """Importa `quebrar_como_front` do gerador — a segmentação do front."""
    p = RAIZ / "scripts" / "gerar_lote_fish.py"
    s = importlib.util.spec_from_file_location("glf", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


glf = _spec_glf()
CACHE = Path(tts_service._cache_dir())


def chave(trecho: str) -> str:
    """Chave de cache do áudio, com o mesmo critério do sincronizador."""
    falante = tts_service._identificar_falante(trecho)
    if falante == "outro" or (falante == "" and tts_service._eh_metadado(trecho)):
        return tts_service._chave_cache("edge:pt-BR-AntonioNeural", trecho, "+0%")
    return tts_service._chave_cache(
        f"fish:{tts_service.FISH_MEISHU_CACHE}", trecho, "+0%")


def tem_audio(tr: str) -> bool:
    if tts_service._trecho_sem_fala(tr):
        return True  # não é narrável: não conta como pendência
    return (CACHE / (chave(tr) + ".mp3")).exists()


def trechos_de(caminho: Path) -> list[str]:
    return glf.quebrar_como_front(caminho.read_text(encoding="utf-8",
                                                   errors="replace"))


def pares_automaticos(dir_antigo: Path | None = None) -> list[tuple[Path, Path]]:
    """(antigo, actual) — de um directório de backup ou dos `.bak_promocao_*`.

    Com `dir_antigo` (ex.: `backups/acervo_producao_<stamp>/textos_leitura_colaborativa`),
    compara o ACERVO QUE ESTAVA EM PRODUÇÃO com o actual: é esta a lista que
    interessa para refazer áudio, porque não mistura promoções de outras datas.

    Sem ele, usa o `.bak_promocao_*` mais recente de cada ficheiro (útil para
    ver só o efeito da última promoção, ficheiro a ficheiro).
    """
    LC = RAIZ / "textos_leitura_colaborativa"
    if dir_antigo is not None:
        pares = []
        for actual in sorted(LC.glob("*.txt")):
            if ".bak" in actual.name:
                continue
            antigo = dir_antigo / actual.name
            if antigo.is_file():
                pares.append((antigo, actual))
        return pares

    por_nome: dict[str, Path] = {}
    for bak in LC.glob("*.bak_promocao_*"):
        original = re.sub(r"\.bak_promocao_.*$", "", bak.name)
        if (por_nome.get(original) is None
                or bak.name > por_nome[original].name):
            por_nome[original] = bak
    pares = []
    for nome, bak in sorted(por_nome.items()):
        actual = LC / nome
        if actual.is_file():
            pares.append((bak, actual))
    return pares


def compara(antigo: Path, actual: Path, novos_json: list) -> dict:
    a = trechos_de(antigo)
    b = trechos_de(actual)
    # multiconjunto: um trecho repetido no texto tem de ser contado uma vez por
    # ocorrência (o áudio é o mesmo, mas a posição conta).
    ca: dict[str, int] = {}
    for t in a:
        ca[t] = ca.get(t, 0) + 1
    cb: dict[str, int] = {}
    for t in b:
        cb[t] = cb.get(t, 0) + 1

    novos, removidos = [], []
    for t, n in cb.items():
        falta = n - ca.get(t, 0)
        if falta > 0:
            novos.append((t, falta))
    for t, n in ca.items():
        falta = n - cb.get(t, 0)
        if falta > 0:
            removidos.append((t, falta))

    novos_sem_audio = [(t, n) for t, n in novos if not tem_audio(t)]
    removidos_orfãos = [(t, n) for t, n in removidos if tem_audio(t)]

    for t, n in novos_sem_audio:
        novos_json.append({"arquivo": actual.name, "ocorrencias": n,
                           "trecho": t})

    return {
        "titulo": actual.stem,
        "antigos": len(a), "actuais": len(b),
        "inalterados": len(a) - sum(n for _, n in removidos),
        "novos": sum(n for _, n in novos),
        "novos_sem_audio": sum(n for _, n in novos_sem_audio),
        "removidos": sum(n for _, n in removidos),
        "removidos_com_audio": sum(n for _, n in removidos_orfãos),
        "exemplos_novos": [t for t, _ in novos_sem_audio[:3]],
        "exemplos_removidos": [t for t, _ in removidos_orfãos[:2]],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--antigo", help="ficheiro de backup (versão anterior)")
    ap.add_argument("--novo", help="ficheiro actual")
    ap.add_argument("--dir-antigo",
                    help="directório com a versão anterior de todas as obras "
                         "(ex.: backups/acervo_producao_<stamp>/textos_leitura_colaborativa)")
    ap.add_argument("--json", help="gravar a lista de trechos novos aqui")
    args = ap.parse_args()

    if args.antigo or args.novo:
        if not (args.antigo and args.novo):
            print("--antigo e --novo têm de ser usados juntos", file=sys.stderr)
            return 2
        pares = [(Path(args.antigo), Path(args.novo))]
    else:
        pares = pares_automaticos(Path(args.dir_antigo) if args.dir_antigo else None)

    if not pares:
        print("nenhum par (.bak_promocao_* × actual) encontrado")
        return 0

    print(f"Cache: {CACHE}")
    print(f"Pares: {len(pares)}\n")
    print(f'{"obra":<48} {"ant":>6} {"act":>6} {"novos":>6} {"sem áudio":>9} '
          f'{"remov":>6} {"órfãos":>7}')
    print("-" * 96)

    novos_json: list[dict] = []
    resumos = []
    for antigo, actual in pares:
        r = compara(antigo, actual, novos_json)
        resumos.append(r)
        if r["novos"] or r["removidos"]:
            print(f'{r["titulo"][:47]:<48} {r["antigos"]:>6} {r["actuais"]:>6} '
                  f'{r["novos"]:>6} {r["novos_sem_audio"]:>9} '
                  f'{r["removidos"]:>6} {r["removidos_com_audio"]:>7}')
            for ex in r["exemplos_novos"]:
                print(f'      + {ex[:100]}')
            for ex in r["exemplos_removidos"]:
                print(f'      - {ex[:100]}')

    total_novos = sum(r["novos"] for r in resumos)
    total_sem = sum(r["novos_sem_audio"] for r in resumos)
    total_rem = sum(r["removidos"] for r in resumos)
    total_orf = sum(r["removidos_com_audio"] for r in resumos)
    print("-" * 96)
    print(f"Trechos novos ..................: {total_novos}")
    print(f"  já com áudio (reaproveitado) .: {total_novos - total_sem}")
    print(f"  SEM áudio → a gerar ..........: {total_sem}")
    print(f"Trechos removidos ..............: {total_rem}")
    print(f"  com áudio agora órfão ........: {total_orf}")

    if args.json:
        Path(args.json).write_text(
            json.dumps(novos_json, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"\nlista gravada em {args.json} ({len(novos_json)} trechos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
