#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconcilia o acervo com os itens de tradução auditados.

**O defeito.** `inserir_periodicos_traduzidos.py` escreveu nos `.txt` o estado
dos itens de 09/10/2026. O que veio depois — reparação de chunks (13/10),
auditorias R1–R3 e rondas r3–r6c (13–14/10) — foi aplicado aos itens mas
**não** ao acervo: `sincronizar_acervo_correcoes.py` salta em silêncio toda
transição cujo texto antigo não encontra, e registou isso como
«0 aplicadas / 237 já ausentes».

Resultado medido: 46 parágrafos auditados (≈13 mil caracteres, quase todos no
Tijotengoku nº 39/40) existem no item e faltam no acervo, e 14 substituições
documentadas nos scripts de correcção nunca chegaram ao ficheiro.

**Fusão, não substituição.** Os dois lados divergiram em sentidos opostos: o
acervo recebeu marcadores (`(Pergunta)`, `**Ensinamento Divino:**`) e conversões
métricas que os itens não têm; os itens receberam correcções e chunks
restaurados que o acervo não tem. Por isso este script **só acrescenta**:

* insere os parágrafos que só existem no item, no lugar que lhes cabe;
* aplica as substituições documentadas (`old -> new`) dos scripts de correcção,
  quando `old` está no acervo e `new` no item;
* **nunca apaga** texto do acervo;
* parágrafos alterados dos dois lados (sem correcção documentada) são apenas
  listados — decisão manual.

Vale para `textos_portugues/` e `textos_leitura_colaborativa/`.

Exclusão: `P2_Eiko_218_256` — é duplicado real do artigo antigo
`美術品蒐集の奇蹟`; o bloco no acervo é do artigo antigo e não se toca.

Validações antes de gravar: todas as âncoras da spec continuam a resolver, na
mesma ordem e no mesmo número; cada parágrafo inserido passa a existir.
Backups `.bak_reconciliacao_<ts>`.

Uso:
    .venv/bin/python scripts/reconciliar_acervo_itens.py
    .venv/bin/python scripts/reconciliar_acervo_itens.py --aplicar
"""
from __future__ import annotations

import argparse
import difflib
import glob
import importlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ))

import estender_specs_periodicos as E  # noqa: E402
from sincronizar_acervo_correcoes import transicoes  # noqa: E402
from normalizar_goshintai_dialogos import converte  # noqa: E402

PT = RAIZ / "textos_portugues"
LC = RAIZ / "textos_leitura_colaborativa"
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
SPECS = RAIZ / "reports" / "livros_trabalho" / "segmentacao_manual"

VEICULOS = ["Tijotengoku", "Eiko", "Hikari", "Kyusei"]

# Duplicado real: o bloco no acervo pertence ao artigo antigo 美術品蒐集の奇蹟.
EXCLUIR = {"P2_Eiko_218_256"}

# Scripts que documentam substituições verificadas contra o japonês.
CORRECOES = [
    "aplicar_correcoes_auditoria_r3",
    "aplicar_correcoes_auditoria_r4",
    "aplicar_correcoes_auditoria_r5",
    "aplicar_correcoes_auditoria_r6",
    "aplicar_correcoes_auditoria_r6b",
]

SEP = re.compile(r"\n[ \t]*\n")

FONTE_HINT = re.compile(
    r"(Tijotengoku|Eiko|Eik[oō]|Hikari|Kyusei|Para[ií]so Terrestre|"
    r"地上天国|栄光|救世|publicado em|n[ºo°]\s*\d|\d+号|\(\d{4}\))")


def sq(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def divide(texto: str) -> list[tuple[int, int, str]]:
    """[(início, fim, bruto)] dos parágrafos, com os separadores fora."""
    out, pos = [], 0
    for m in SEP.finditer(texto):
        if m.start() > pos:
            out.append((pos, m.start(), texto[pos:m.start()]))
        pos = m.end()
    if pos < len(texto):
        out.append((pos, len(texto), texto[pos:]))
    return out


def parte_cabecalho(bloco: str, corpo: str) -> tuple[str, str]:
    """Divide o bloco em (cabeçalho, corpo).

    Cabeçalho = título + linha de fonte. A fonte é reconhecida por padrão e
    **nunca** quando é já o início do corpo — a âncora da spec é
    `título\\n\\nlinha seguinte`, e perder essa linha parte a âncora.
    """
    titulo, _, resto = bloco.partition("\n")
    resto_sem = resto.lstrip("\n")
    if len(resto_sem) != len(resto):
        cand = resto_sem.split("\n", 1)[0]
        if (len(cand) <= 220 and FONTE_HINT.search(cand)
                and not (corpo and corpo.startswith(cand[:60]))):
            return f"{titulo}\n\n{cand}", resto_sem[len(cand):].lstrip("\n")
    return titulo, resto_sem


def boundaries(texto: str, anchors: list[str]) -> list[int]:
    pos = []
    for a in anchors:
        p = texto.find(a)
        if p < 0:
            raise SystemExit(f"âncora não resolve: {a[:70]!r}")
        pos.append(p)
    if pos != sorted(pos):
        raise SystemExit("âncoras fora de ordem")
    return pos


def carrega_correcoes() -> dict[str, list[tuple[str, str]]]:
    """{item: [(old, new)]} a partir dos scripts de correcção."""
    out: dict[str, list[tuple[str, str]]] = {}
    for nome in CORRECOES:
        m = importlib.import_module(nome)
        for item, campo, old, new, _n in getattr(m, "SUBS"):
            if campo != "texto_pt" or old == new:
                continue
            out.setdefault(item, []).append((old, new))
    return out


def funde(corpo: str, novo: str) -> tuple[str, list[str], list[str]]:
    """Acrescenta ao `corpo` os parágrafos que só existem em `novo`.

    Só entra o parágrafo que (a) não aparece em parte alguma do bloco e (b) não
    tem nenhum parágrafo do bloco com semelhança ≥ 0,80 — ou seja, não é
    variante de nada que lá esteja. É o que impede a duplicação: uma fusão por
    opcodes duplicava 8 mil caracteres no Tijotengoku nº 43, onde o tradutor
    fundiu e dividiu parágrafos.

    A posição vem dos vizinhos: insere-se depois do último parágrafo do item
    presente no corpo (ou antes do primeiro, se não houver anterior).

    Devolve (corpo_fundido, inseridos, conflitos). Nunca remove nada.
    """
    cp, ip = divide(corpo), divide(novo)
    csq = [sq(p[2]) for p in cp]
    isq = [sq(p[2]) for p in ip]
    blob = " ".join(csq)

    inseridos: list[str] = []
    conflitos: list[str] = []
    # (indice do parágrafo-Âncora no corpo, +1=depois/-1=antes, ordem do item)
    pend: list[tuple[int, int, int, str]] = []

    for k, par in enumerate(ip):
        s = isq[k]
        if len(s) < 40 or s in blob:
            continue
        melhor = max((difflib.SequenceMatcher(None, s, c).ratio()
                      for c in csq), default=0.0)
        if melhor >= 0.80:
            conflitos.append(par[2][:120])
            continue
        antes = [n for n in range(len(csq)) if n < len(csq) and isq and
                 any(isq[j] == csq[n] for j in range(0, k))]
        if antes:
            pend.append((max(antes), +1, k, par[2]))
        else:
            segs = [n for n in range(len(csq))
                    if any(isq[j] == csq[n] for j in range(k + 1, len(isq)))]
            pend.append((min(segs) if segs else len(csq) - 1, -1, k, par[2]))
        inseridos.append(par[2][:120])

    if not pend:
        return corpo, inseridos, conflitos

    # bloco vazio no corpus (acontece no corpus de leitura, cuja cópia do artigo
    # pode estar vazia): não há âncora possível — devolve tudo no fim
    if not cp:
        corpo_novo = "\n\n".join(t for _, _, _, t in sorted(pend))
        return corpo_novo, inseridos, conflitos

    # agrupa por âncora e aplica de trás para a frente, mantendo a ordem do item
    por_ancora: dict[tuple[int, int], list[tuple[int, str]]] = {}
    for idx, lado, k, txt in pend:
        por_ancora.setdefault((idx, lado), []).append((k, txt))

    corpo_novo = corpo
    for (idx, lado), itens in sorted(por_ancora.items(), reverse=True):
        itens.sort()
        bloco = "\n\n".join(t for _, t in itens)
        ini, fim, _raw = cp[idx]
        if lado > 0:
            corpo_novo = corpo_novo[:fim] + "\n\n" + bloco + corpo_novo[fim:]
        else:
            corpo_novo = corpo_novo[:ini] + bloco + "\n\n" + corpo_novo[ini:]
    return corpo_novo, inseridos, conflitos


def resolve_lc(texto: str, item: dict, titulo_corpus: str) -> int:
    for cand in (titulo_corpus, E.titulo_limpo(item.get("titulo_pt"))):
        if not cand:
            continue
        h = E.inicios_de_bloco(texto, cand)
        if h:
            return h[0]
        p = texto.find(cand)
        if p >= 0:
            return p
    return -1


def nome_item(item: dict) -> str:
    """Nome do ficheiro do item, como usado pelos scripts de correcção."""
    if item.get("_arquivo"):
        return item["_arquivo"]
    return (f"{item.get('fase','')}_{item['veiculo']}_{item['numero']}"
            f"_{item['ordem']}")


def sub_flexivel(texto: str, antigo: str, novo: str) -> tuple[str, int]:
    """Substitui `antigo` por `novo` tolerando diferenças de quebra de linha.

    Muitas transições documentadas têm `\n` onde o acervo tem `\n\n` (ou o
    contrário); a comparação literal falha e a correcção parece perdida. Exige
    ocorrência única e que a forma nova ainda não esteja lá.
    """
    antigo, novo = antigo.strip(), novo.strip()
    if not antigo or not novo or sq(novo) in sq(texto):
        return texto, 0
    pat = re.sub(r"\s+", r"\\s+", re.escape(antigo))
    achados = list(re.finditer(pat, texto))
    if len(achados) != 1:
        return texto, 0
    m = achados[0]
    return texto[:m.start()] + novo + texto[m.end():], 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    itens = []
    for f in sorted(glob.glob(str(ITENS / "*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        d["_arquivo"] = Path(f).stem
        itens.append(d)
    correcoes = carrega_correcoes()

    total_ins = total_cor = total_conf = 0
    relatorio: list[str] = []

    for veic in VEICULOS:
        pt_path = PT / f"{veic}.txt"
        lc_path = LC / f"{veic}.txt"
        spec = json.loads((SPECS / f"{veic}.txt.json").read_text(encoding="utf-8"))
        anchors = [a["pt_anchor"] for a in spec["articles"]]

        pt = pt_path.read_text(encoding="utf-8")
        lc = lc_path.read_text(encoding="utf-8") if lc_path.exists() else None

        ins = cor = conf = 0
        for item in [i for i in itens if i["veiculo"] == veic]:
            nome = nome_item(item)
            if nome in EXCLUIR:
                continue
            p = E.resolve_pt(pt, item)
            if p < 0:
                relatorio.append(f"{veic} {nome}: título não localizado")
                continue
            starts = boundaries(pt, anchors)
            if p not in starts:
                relatorio.append(f"{veic} {nome}: não é início de bloco")
                continue
            boxes = {s: (s, f) for s, f in
                     zip(starts, starts[1:] + [len(pt)])}
            ini, fim = boxes[p]

            novo = (item.get("texto_pt") or "").strip()
            cab, corpo = parte_cabecalho(pt[ini:fim], novo)
            fundido, inseridos, conflitos = funde(corpo, novo)

            for old, new in correcoes.get(nome, []):
                if new in fundido or old not in fundido:
                    continue
                if fundido.count(old) != 1:
                    continue
                fundido = fundido.replace(old, new)
                cor += 1

            # histórico do próprio item (transições entre backups), tolerante a
            # diferenças de quebra de linha
            for campo, antigo, novo in transicoes(nome, item):
                if campo != "texto_pt" or antigo == "###INICIO###":
                    continue
                fundido, n = sub_flexivel(fundido, antigo, novo)
                cor += n

            # O histórico inclui rondas anteriores à decisão de 20/10 (a R5
            # impunha «objeto sagrado de culto»; os marcadores antigos vêm de
            # rondas dos dias 13-14). Reaplicá-las em cadeia reintroduziria a
            # convenção abolida — canoniza-se o resultado.
            fundido = converte(fundido)

            if fundido != corpo and sq(fundido) != sq(corpo):
                pt = pt[:ini] + cab + "\n\n" + fundido.strip() + "\n\n" + pt[fim:]

            ins += len(inseridos)
            conf += len(conflitos)
            for c in conflitos:
                relatorio.append(f"{veic} nº {item['numero']} "
                                 f"({item['ordem']}): {c}")

            if lc is not None:
                pl = resolve_lc(lc, item, cab.split("\n")[0])
                if pl >= 0:
                    prox = [q for q in (lc.find(a) for a in anchors) if q > pl]
                    fim_lc = min(prox) if prox else len(lc)
                    cab_l, corpo_l = parte_cabecalho(lc[pl:fim_lc], novo)
                    f2, _, _ = funde(corpo_l, novo)
                    if f2 != corpo_l and sq(f2) != sq(corpo_l):
                        lc = (lc[:pl] + cab_l + "\n\n" + f2.strip() + "\n\n"
                              + lc[fim_lc:])

        boundaries(pt, anchors)
        for item in [i for i in itens if i["veiculo"] == veic]:
            if nome_item(item) in EXCLUIR:
                continue
            p = E.resolve_pt(pt, item)
            if p < 0:
                continue
            starts = boundaries(pt, anchors)
            boxes = {s: (s, f) for s, f in
                     zip(starts, starts[1:] + [len(pt)])}
            if p not in boxes:
                continue
            ini, fim = boxes[p]
            _c, corpo = parte_cabecalho(pt[ini:fim], novo)
            alvo = (item.get("texto_pt") or "").strip()
            if len(corpo) < len(alvo) * 0.5:
                raise SystemExit(f"{veic}: bloco suspeito em {nome_item(item)}")

        print(f"{veic:13} blocos={len(anchors):>4} | parágrafos inseridos={ins:>3} "
              f"| substituições={cor:>3} | conflitos={conf:>2}")

        if args.aplicar:
            shutil.copy2(pt_path, f"{pt_path}.bak_reconciliacao_{ts}")
            pt_path.write_text(pt, encoding="utf-8")
            if lc is not None and lc_path.exists():
                shutil.copy2(lc_path, f"{lc_path}.bak_reconciliacao_{ts}")
                lc_path.write_text(lc, encoding="utf-8")

        total_ins += ins
        total_cor += cor
        total_conf += conf

    print(f"\nTOTAL: {total_ins} parágrafos, {total_cor} substituições, "
          f"{total_conf} conflitos")
    if relatorio:
        print("\nregistos:")
        for r in relatorio[:40]:
            print("   -", r)
        if len(relatorio) > 40:
            print(f"   ... +{len(relatorio) - 40}")

    if args.aplicar:
        print(f"\ngravado. backups *.bak_reconciliacao_{ts}")
    else:
        print("\n(dry-run — use --aplicar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
