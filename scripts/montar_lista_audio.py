#!/usr/bin/env python3
"""Monta a lista de obras com áudio em falta, para o lote de pré-geração.

Por que existe (2026-10-23):
    `pre_gerar_lote_orais.py --todos` varre TODAS as 137 obras da leitura, o
    que inclui material institucional (Manual, Guia, Doutrina, HAKONE) e os
    periódicos que misturam artigos do Meishu-Sama com texto da instituição
    (Tijotengoku, Kyusei, Relatos de Milagres). Narrar esses ficheiros na voz
    clonada dele atribui-lhe texto que não é dele.

    A política de autoria já existe e é do serviço, não deste script:
    `sincronizar_audios.NAO_MEISHU` + `filtrar_obras('escrita')`. Reutiliza-se
    essa regra em vez de a reescrever — três cópias divergentes da mesma regra
    foi o que deixou 1.784 áudios inacessíveis em 2026-10-22.

    O resultado é a lista de `--lista` do lote, e as contagens por obra (ordem
    decrescente de pendência) para se saber o que está a ser gerado.

Uso:
    # Âmbito aprovado (escritos do Meishu, sem institucional) → data/tts_lista_escrita.txt
    .venv/bin/python scripts/montar_lista_audio.py

    # Todos os textos, incluindo periódicos e institucional
    .venv/bin/python scripts/montar_lista_audio.py --tipo todos --incluir-institucional \
        --saida data/tts_lista_todos.txt

    # Só mostrar (não escrever ficheiro)
    .venv/bin/python scripts/montar_lista_audio.py --mostrar
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys

RAIZ = "/var/www/goshinsho"
sys.path.insert(0, RAIZ)
os.environ.setdefault("GOSHINSHO_TTS_CACHE", os.path.join(RAIZ, "data/tts_cache"))

from goshinsho.services import leitura_service, tts_service  # noqa: E402


def _carregar_sincronizador():
    """Importa `sincronizar_audios` sem executar o main (reutiliza a política)."""
    caminho = os.path.join(RAIZ, "scripts", "sincronizar_audios.py")
    spec = importlib.util.spec_from_file_location("sincronizar_audios", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def contar(obras) -> list[tuple[int, int, str]]:
    """[(faltando, com_audio, arquivo)] — mesma segmentação do front."""
    sa = _carregar_sincronizador()
    quebrar = sa.glf.quebrar_como_front
    linhas: list[tuple[int, int, str]] = []
    for o in obras:
        arq = o["arquivo"]
        texto = leitura_service.obter_texto(arq)
        if not texto:
            continue
        falta = ok = 0
        for trecho in quebrar(texto):
            if tts_service._trecho_sem_fala(trecho):
                continue
            if tts_service.caminho_em_cache(trecho):
                ok += 1
            else:
                falta += 1
        linhas.append((falta, ok, arq))
    linhas.sort(reverse=True)
    return linhas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tipo", choices=["oral", "escrita", "todos"], default="escrita")
    ap.add_argument("--incluir-institucional", action="store_true",
                    help="Não aplica a exclusão de periódicos/material institucional.")
    ap.add_argument("--saida", default=os.path.join(RAIZ, "data", "tts_lista_escrita.txt"),
                    help="Ficheiro de lista (uma obra por linha).")
    ap.add_argument("--mostrar", action="store_true", help="Só mostrar; não escrever.")
    args = ap.parse_args()

    sa = _carregar_sincronizador()
    obras = sa.filtrar_obras(args.tipo, None, args.incluir_institucional)
    linhas = contar(obras)

    total_falta = sum(l[0] for l in linhas)
    total_ok = sum(l[1] for l in linhas)
    com_pendencia = [l for l in linhas if l[0] > 0]

    print(f"Âmbito: tipo={args.tipo} institucional={'sim' if args.incluir_institucional else 'nao'}")
    print(f"Obras no âmbito: {len(linhas)} | com pendência: {len(com_pendencia)}")
    print(f"Trechos com áudio: {total_ok} | pendentes: {total_falta}")
    for falta, ok, arq in com_pendencia:
        print(f"  {falta:6d} em falta   {ok:6d} ok   {arq}")

    if not args.mostrar:
        os.makedirs(os.path.dirname(args.saida), exist_ok=True)
        with open(args.saida, "w", encoding="utf-8") as f:
            for _falta, _ok, arq in com_pendencia:
                f.write(arq + "\n")
        print(f"\nLista escrita em {args.saida} ({len(com_pendencia)} obras)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
