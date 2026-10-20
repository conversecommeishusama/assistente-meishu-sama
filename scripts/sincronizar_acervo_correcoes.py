#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verifica (e propaga) as correções dos itens para os dois corpus PT.

O acervo PT guarda o bloco de cada artigo de periódico como
`titulo_pt + fonte_pt + texto_pt`. Quando os itens são corrigidos (auditoria),
o `.txt` fica desatualizado.

O método reconstrói a cadeia de estados de cada item a partir dos backups de
`backups_auditoria/` (cada backup é o estado ANTERIOR a uma correção) e aplica
a cada `.txt` as transições antigo→novo. Vale para `textos_portugues/` e
`textos_leitura_colaborativa/` — cada um recebe as transições sobre o **seu
próprio** texto.

**Falha alto.** Antes, uma transição impossível de aplicar era apenas somada a
um contador chamado «já ausentes» e o script saía com 0 — foi assim que 14
correções se perderam entre 13 e 14/10/2026. Agora:

* `já aplicadas` — a forma nova já está lá (comparação sem espaços, porque
  `\\n` e `\\n\\n` variam entre item e acervo);
* `variantes` — parágrafo presente com outra forma (quebra/marcador);
* `PERDIDAS` — não encontrado de nenhuma forma: **é o que importa**;
* `recusadas` — a aplicação criaria aspas repetidas ou parágrafo duplicado
  (aconteceu a 20/10: 8 kB repetidos na Kyusei; revertido).

Sai com código 1 se houver PERDIDAS ou recusadas, a menos que `--tolerar`.
A reparação autoritativa é `scripts/reconciliar_acervo_itens.py`.

Uso:
    python scripts/sincronizar_acervo_correcoes.py            # dry-run
    python scripts/sincronizar_acervo_correcoes.py --aplicar
    python scripts/sincronizar_acervo_correcoes.py --tolerar  # só relatório
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_auditoria"
ACERVO = RAIZ / "textos_portugues"
LEITURA = RAIZ / "textos_leitura_colaborativa"
VEIC_ARQ = {
    "Tijotengoku": "Tijotengoku.txt",
    "Hikari": "Hikari.txt",
    "Eiko": "Eiko.txt",
    "Kyusei": "Kyusei.txt",
}

TIPOS_AUDITORIA = {
    "lacuna", "media", "baixa", "suntetsu", "meshiya", "inv", "stripEN", "pan",
    "r3", "marc_r3", "nota_r3", "marc", "purif", "titulo", "inversao_causa",
    "dedup", "nota", "uniformizar", "r4", "marcins", "marcdel", "r3b",
    "rotulos_fala", "termo_obscuro", "inserir_marcadores", "r5", "r5b",
    "goshintai", "r6", "r6b", "r6c", "fix_auditoria_r6",
}


def backups_do_item(item: str) -> list[Path]:
    """Backups do item, ordenados por data de modificação (mais antigo primeiro)."""
    achados = []
    for p in BACKUPS.glob(f"{item}_*.json"):
        rotulo = p.name[len(item) + 1:].rsplit("_", 1)[0]  # ex.: media, suntetsu
        if rotulo in TIPOS_AUDITORIA or rotulo.startswith(tuple(TIPOS_AUDITORIA)):
            achados.append(p)
    return sorted(achados, key=lambda p: p.stat().st_mtime)


def transicoes(item: str, atual: dict) -> list[tuple[str, str, str]]:
    """Transições (campo, valor_antigo, valor_novo) desde o estado mais antigo.

    Para `texto_pt`, o diff é feito ao nível do PARÁGRAFO, de modo que se
    produzem apenas os parágrafos realmente alterados — necessário porque o
    `.txt` pode ter uma versão do artigo mais antiga noutras partes.
    """
    estados = []
    for p in backups_do_item(item):
        estados.append(json.loads(p.read_text(encoding="utf-8")))
    estados.append(atual)

    out: list[tuple[str, str, str]] = []
    for ant, nov in zip(estados, estados[1:]):
        for campo in ("titulo_pt", "fonte_pt"):
            a, n = (ant.get(campo) or ""), (nov.get(campo) or "")
            if a and n and a != n:
                out.append((campo, a, n))
        a, n = (ant.get("texto_pt") or ""), (nov.get("texto_pt") or "")
        if a and n and a != n:
            out.extend(diff_paragrafos(a, n))
        # um parágrafo que já foi aplicado e depois alterado outra vez não pode
        # ser reconstruído; nesse caso acrescenta-se a transição completa
    return out


def diff_paragrafos(antigo: str, novo: str) -> list[tuple[str, str, str]]:
    """Pares (old, new) de parágrafos alterados entre duas versões."""
    import difflib

    pa = [p for p in re.split(r"\n\s*\n", antigo)]
    pn = [p for p in re.split(r"\n\s*\n", novo)]
    sm = difflib.SequenceMatcher(None, pa, pn, autojunk=False)
    out: list[tuple[str, str, str]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        velho = "\n\n".join(pa[i1:i2]).strip()
        novo_t = "\n\n".join(pn[j1:j2]).strip()
        if not velho:
            # parágrafo totalmente novo: anexado ao parágrafo anterior
            ancora = pa[i1 - 1].strip() if i1 > 0 else ""
            if ancora:
                out.append(("texto_pt", ancora, f"{ancora}\n\n{novo_t}"))
            else:
                out.append(("texto_pt", "###INICIO###", novo_t))
            continue
        if not novo_t:
            out.append(("texto_pt", velho, ""))
            continue
        out.append(("texto_pt", velho, novo_t))
    return out


def sem_espaco(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def em_sincronia(flat_corpus: str, final: str, minimo: float = 0.98) -> bool:
    """O texto final do item está representado no ficheiro?

    Compara por parágrafos: o corpo não tem de aparecer como um bloco contíguo
    (o acervo tem marcadores e quebras diferentes), mas quase todos os
    parágrafos têm de estar lá.

    `final` é o texto CRU do item — normaliza-se aqui, bloco a bloco;
    recebê-lo já sem espaços colapsaria tudo num bloco só. Corta em qualquer
    quebra de linha porque alguns itens separam parágrafos com um `\n` simples
    e, sem isto, dois parágrafos fundidos dariam um bloco inexistente no acervo.
    """
    blocos = [sem_espaco(p) for p in re.split(r"\n+", final or "")]
    blocos = [p for p in blocos if len(p) >= 40]
    if not blocos:
        return sem_espaco(final) in flat_corpus
    achados = sum(1 for p in blocos if p in flat_corpus)
    return achados / len(blocos) >= minimo


def paragrafos_iguais_seguidos(t: str) -> int:
    ps = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", t)]
    return sum(1 for a, b in zip(ps, ps[1:]) if a and a == b)


def seguro(antes: str, depois: str, extra: str = "") -> str:
    """Devolve o motivo da recusa, ou "" se a transição for segura.

    As correcções vieram de diffs entre backups do item; aplicadas a um `.txt`
    que já divergiu, algumas produzem artefactos — foi o que aconteceu a
    20/10: aspas a mais em títulos e 8 kB de parágrafos repetidos na Kyusei.
    """
    if depois.count('""') > antes.count('""'):
        return "duplicaria aspas"
    if paragrafos_iguais_seguidos(depois) > paragrafos_iguais_seguidos(antes):
        return "duplicaria parágrafo"
    if extra and extra.strip() and extra.strip() in antes:
        return "conteúdo já presente no ficheiro"
    return ""


def variante(texto: str, antigo: str) -> bool:
    """O parágrafo existe no ficheiro mas com outra forma (quebra, marcador)?

    Depois da reconciliação, o que resta não são omissões: é o mesmo parágrafo
    com formatação diferente (o tradutor fundiu ou dividiu, e a normalização de
    marcadores acrescentou `(Pergunta)`, `**título**`). Tratar isso como
    perda de conteúdo tornaria o gate inútil.
    """
    flat = re.sub(r"\s+", "", texto)
    a = re.sub(r"\s+", "", antigo)
    if len(a) < 80:
        return a in flat or (len(a) >= 40 and a[:40] in flat)
    meio = len(a) // 2
    return (a[:80] in flat or a[-80:] in flat
            or a[max(0, meio - 40):meio + 40] in flat)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--tolerar", action="store_true",
                    help="sair com 0 mesmo havendo transições não aplicadas")
    args = ap.parse_args()
    tolerar = args.tolerar

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pendentes: list[str] = []
    graves: list[str] = []

    # transições por veículo, calculadas uma vez a partir dos itens
    por_veiculo: dict[str, list[tuple[str, str, str, str]]] = {}
    FINAL: dict[str, str] = {}
    for f in sorted(ITENS.glob("*.json")):
        if f.name.startswith("."):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        item = f.stem
        veic = d.get("veiculo")
        if veic not in VEIC_ARQ:
            continue
        FINAL[item] = d.get("texto_pt") or ""
        por_veiculo.setdefault(veic, []).extend(
            (item, *t) for t in transicoes(item, d))

    totais: dict[str, dict[str, int]] = {}
    plano: dict[tuple[str, str], str] = {}
    for destino, rotulo in ((ACERVO, "producao"), (LEITURA, "leitura")):
        contagem = {"aplicadas": 0, "ja": 0, "nao": 0, "amb": 0, "var": 0}
        for veic, arq in VEIC_ARQ.items():
            caminho = destino / arq
            if not caminho.exists():
                continue
            original = caminho.read_text(encoding="utf-8")
            texto = original
            flat: str | None = sem_espaco(texto)

            for item, item_campo, antigo, novo in por_veiculo.get(veic, []):
                if antigo == novo:
                    continue
                # Se o texto final auditado do item já está inteiro no
                # ficheiro, o item está em sincronia e as transições
                # intermédias não dizem nada (a cadeia A→B→C com C aplicado
                # faria B parecer perdido).
                final = FINAL.get(item, "")
                if final and flat and em_sincronia(flat, final):
                    contagem["ja"] += 1
                    continue
                if antigo == "###INICIO###":
                    contagem["amb"] += 1
                    graves.append(f"{item}.{item_campo}: parágrafo novo no início "
                                  f"sem âncora [{rotulo}]")
                    continue
                # IDEMPOTÊNCIA: o estado final pode já estar lá. Compara-se
                # sem espaços porque `\n` e `\n\n` variam entre item e acervo.
                # Não se exige que a forma antiga não exista: ela pode
                # legitimamente sobreviver noutro artigo.
                if novo and sem_espaco(novo) in sem_espaco(texto):
                    contagem["ja"] += 1
                    continue
                n = texto.count(antigo)
                extra = novo[len(antigo):] if novo.startswith(antigo) else ""
                if n == 1:
                    cand = texto.replace(antigo, novo, 1)
                    motivo = seguro(texto, cand, extra)
                    if motivo:
                        contagem["amb"] += 1
                        graves.append(f"{item}.{item_campo}: recusada — {motivo} "
                                      f"[{rotulo}]")
                        continue
                    texto = cand
                    contagem["aplicadas"] += 1
                    continue
                if n == 2:
                    antigo2, novo2 = f"\n{antigo}\n", f"\n{novo}\n"
                    if texto.count(antigo2) == 1:
                        cand = texto.replace(antigo2, novo2, 1)
                        motivo = seguro(texto, cand, extra)
                        if motivo:
                            contagem["amb"] += 1
                            graves.append(f"{item}.{item_campo}: recusada — "
                                          f"{motivo} [{rotulo}]")
                            continue
                        texto = cand
                        contagem["aplicadas"] += 1
                        continue
                    contagem["amb"] += 1
                    graves.append(f"{item}.{item_campo}: 2 ocorrências "
                                  f"(ambíguo) [{rotulo}]")
                    continue
                if n == 0:
                    if variante(texto, antigo):
                        contagem["var"] += 1
                        continue
                    contagem["nao"] += 1
                    pendentes.append(f"{item}.{item_campo}: antigo não "
                                     f"encontrado ({len(antigo)}c) [{rotulo}]")
                    continue
                contagem["amb"] += 1
                graves.append(f"{item}.{item_campo}: {n} ocorrências "
                              f"(ambíguo) [{rotulo}]")

            if texto != original:
                if args.aplicar:
                    shutil.copy2(caminho,
                                 BACKUPS / f"{arq}.bak_sync_{rotulo}_{stamp}")
                    caminho.write_text(texto, encoding="utf-8")
                print(f"  {arq} [{rotulo}]: {len(original)} -> {len(texto)} "
                      f"({len(texto) - len(original):+d})")
                plano[(rotulo, arq)] = texto
        totais[rotulo] = contagem

    for rotulo, c in totais.items():
        print(f"{rotulo:9} aplicadas={c['aplicadas']:>4} | já aplicadas={c['ja']:>4} "
              f"| variantes={c['var']:>4} | PERDIDAS={c['nao']:>3} "
              f"| recusadas/ambíguas={c['amb']:>3}")

    nao_total = sum(c["nao"] for c in totais.values())

    if pendentes:
        print("\nALERTA — transições que o .txt não permite aplicar "
              "(o acervo pode estar a servir texto não corrigido):")
        for p in pendentes[:60]:
            print("   -", p)
        if len(pendentes) > 60:
            print(f"   ... +{len(pendentes) - 60}")
    if graves:
        print("\nALERTA — transições ambíguas ou sem âncora:")
        for p in graves[:40]:
            print("   -", p)
        if len(graves) > 40:
            print(f"   ... +{len(graves) - 40}")

    if not args.aplicar:
        print("(use --aplicar para gravar)")

    # FALHAR ALTO: uma transição que não se aplica significa que o acervo está
    # a servir texto que já não é o auditado. Antes isto era só um aviso e o
    # script saía com 0 — foi assim que 14 correcções se perderam em 13–14/10.
    if nao_total or graves:
        print(f"\nERRO: {nao_total} transições não encontradas + "
              f"{len(graves)} ambíguas. Rever com "
              "`scripts/reconciliar_acervo_itens.py` antes de publicar.")
        if not tolerar:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
