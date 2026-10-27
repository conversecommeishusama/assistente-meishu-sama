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


def contar(obras) -> list[dict]:
    """Contagens por obra, separando o que é dele do que não é.

    A separação não é cosmética: trecho de terceiros sai pelo edge em ~1 s,
    trecho dele exige XTTS (~30 s). Como a correção pedida é "tirar a voz dele
    do que não é dele", a fila é ordenada para os de terceiros saírem
    primeiro — sem isso, 3 440 trechos caros de Tijotengoku atrasariam em mais
    de um dia os 2 553 testemunhos que se resolvem numa hora.
    """
    from goshinsho.services import autoria_service

    linhas: list[dict] = []
    for o in obras:
        arq = o["arquivo"]
        texto = leitura_service.obter_texto(arq)
        if not texto:
            continue
        ok = falta_dele = falta_outro = 0
        for trecho, autor in autoria_service.trechos_com_autor(arq, texto):
            if tts_service._trecho_sem_fala(trecho):
                continue
            if tts_service.caminho_em_cache(trecho, arquivo=arq):
                ok += 1
            elif autor == autoria_service.OUTRO:
                falta_outro += 1
            else:
                falta_dele += 1
        linhas.append({"arquivo": arq, "ok": ok, "dele": falta_dele,
                       "outro": falta_outro,
                       "falta": falta_dele + falta_outro})
    linhas.sort(key=lambda x: (-x["outro"], -x["falta"]))
    return linhas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tipo", default="escrita",
                    help="oral | escrita | todos, ou uma combinação separada "
                         "por vírgulas (ex.: 'oral,escrita'). 2026-10-28: a "
                         "combinação existe porque o pedido do usuário foi "
                         "'tudo o que faltar dos escritos e dos orais' — um "
                         "tipo de cada vez deixava sempre metade de fora.")
    ap.add_argument("--incluir-institucional", action="store_true",
                    help="Não aplica a exclusão de periódicos/material institucional.")
    ap.add_argument("--saida", default=os.path.join(RAIZ, "data", "tts_lista_escrita.txt"),
                    help="Ficheiro de lista (uma obra por linha).")
    ap.add_argument("--mostrar", action="store_true", help="Só mostrar; não escrever.")
    args = ap.parse_args()

    tipos = [t.strip() for t in args.tipo.split(",") if t.strip()]
    invalidos = [t for t in tipos if t not in ("oral", "escrita", "todos")]
    if invalidos:
        ap.error(f"tipo inválido: {', '.join(invalidos)}")

    sa = _carregar_sincronizador()
    obras: list = []
    vistos: set = set()
    for tipo in tipos:
        for o in sa.filtrar_obras(tipo, None, args.incluir_institucional):
            arq = o["arquivo"] if isinstance(o, dict) else o
            if arq in vistos:
                continue
            vistos.add(arq)
            obras.append(o)
    linhas = contar(obras)

    total_falta = sum(l["falta"] for l in linhas)
    total_ok = sum(l["ok"] for l in linhas)
    falta_outro = sum(l["outro"] for l in linhas)
    falta_dele = sum(l["dele"] for l in linhas)
    com_pendencia = [l for l in linhas if l["falta"] > 0]

    print(f"Âmbito: tipo={args.tipo} institucional={'sim' if args.incluir_institucional else 'nao'}")
    print(f"Obras no âmbito: {len(linhas)} | com pendência: {len(com_pendencia)}")
    print(f"Trechos com áudio: {total_ok} | pendentes: {total_falta}")
    # 2026-10-28: o rótulo dizia "XTTS, ~30 s" porque era o único provedor da
    # voz clonada. Com a chave Fish instalada, o caminho por omissão é a voz
    # APROVADA — e o tempo por trecho é da chamada remota, não do daemon local.
    # Um rótulo errado aqui já fez alguém estimar dias onde havia horas.
    print(f"   voz dele (aprovada/Fish; XTTS só sem chave): {falta_dele}")
    print(f"   narrador (edge, ~1 s cada):  {falta_outro}")
    for l in com_pendencia:
        print(f"  {l['falta']:6d} em falta ({l['dele']:5d} dele + {l['outro']:5d} narrador)"
              f"   {l['ok']:6d} ok   {l['arquivo']}")

    if not args.mostrar:
        os.makedirs(os.path.dirname(args.saida), exist_ok=True)
        with open(args.saida, "w", encoding="utf-8") as f:
            for l in com_pendencia:
                f.write(l["arquivo"] + "\n")
        print(f"\nLista escrita em {args.saida} ({len(com_pendencia)} obras)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
