#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Varredura DIRIGIDA no acervo (JP + PT) para os 7 pontos pedidos pelo usuario
sobre o sofrimento dos espiritos no Inferno e o Culto aos Antepassados (Obon).

Uso:
    python scripts/_busca_7pontos_obon.py            # todos os pontos
    python scripts/_busca_7pontos_obon.py 1 4 5      # só os pontos indicados
"""
from __future__ import annotations

import pathlib
import re
import sys

RAIZ = pathlib.Path("/var/www/goshinsho")
PASTAS = {
    "JP": RAIZ / "textos_japones",
    "PT": RAIZ / "textos_leitura_colaborativa",
}

# ---------------------------------------------------------------------------
# Cada ponto tem uma lista de "grupos de gatilho". Um parágrafo é candidato
# quando casa com PELO MENOS UM gatilho de CADA grupo obrigatório.
# ---------------------------------------------------------------------------
PONTOS: dict[int, dict] = {
    1: {
        "titulo": "Fome/sede no Inferno; não podem se alimentar das oferendas; só no Obon",
        "jp": {
            "obrig": [
                [r"飢", r"饑", r"餓鬼", r"食物", r"食べ", r"食え", r"飲食"],
                [r"地獄", r"霊", r"祖霊", r"供養", r"お盆"],
            ],
        },
        "pt": {
            "obrig": [
                [r"fome", r"sede", r"faminto", r"aliment", r"comer", r"comida"],
                [r"[Ii]nferno", r"espírito", r"sufrág", r"[Oo]bon", r"antepassado"],
            ],
        },
    },
    2: {
        "titulo": "Méritos/virtudes dos descendentes só chegam quando o antepassado sai do Inferno",
        "jp": {
            "obrig": [
                [r"功徳", r"徳を積", r"善行", r"善い?事", r"供養"],
                [r"地獄", r"救われ", r"浮かば", r"成仏", r"昇天", r"浄化"],
            ],
        },
        "pt": {
            "obrig": [
                [r"virtude", r"mérito", r"acumul", r"boas ações", r"bem"],
                [r"[Ii]nferno", r"salv", r"purific", r"ascend", r"sufrág"],
            ],
        },
    },
    3: {
        "titulo": "Antepassados só se aproximam se forem convidados/chamados",
        "jp": {
            "obrig": [
                [r"招", r"呼(?:ば|ん|び|び寄)", r"勧請", r"お招き", r"招待", r"誘"],
                [r"霊", r"先祖", r"祖霊", r"仏壇", r"供養", r"盆", r"彼岸"],
            ],
        },
        "pt": {
            "obrig": [
                [r"convid", r"chamad", r"chamar", r"invoca", r"atrai", r"convoca"],
                [r"espírito", r"antepassado", r"ancestral", r"altar", r"sufrág"],
            ],
        },
    },
    4: {
        "titulo": "Única saída do Inferno: arrepender-se verdadeiramente dos pecados",
        "jp": {
            "obrig": [
                [r"反省", r"後悔", r"悔(?:い|い改)", r"懺悔", r"改心", r"悟(?:り|る|った)"],
                [r"地獄", r"霊", r"罪", r"救われ", r"浄め", r"上が"],
            ],
        },
        "pt": {
            "obrig": [
                [r"arrepend", r"remorso", r"contri", r"refletir", r"despert", r"redim", r"reconhec"],
                [r"[Ii]nferno", r"espírito", r"pecado", r"salv", r"purifica", r"subir"],
            ],
        },
    },
    5: {
        "titulo": "Antepassados no Inferno aguardam ansiosamente o Culto/Obon",
        "jp": {
            "obrig": [
                [r"待", r"楽しみ", r"望(?:んで|み)", r"首を長く"],
                [r"お盆", r"供養", r"先祖", r"祖霊", r"地獄", r"盆"],
            ],
        },
        "pt": {
            "obrig": [
                [r"aguard", r"esper", r"ansios", r"ansei", r"anela", r"ansiedade"],
                [r"[Oo]bon", r"sufrág", r"antepassado", r"[Ii]nferno", r"culto"],
            ],
        },
    },
    6: {
        "titulo": "Oferta monetária pode substituir as oferendas (de comida)",
        "jp": {
            "obrig": [
                [r"金", r"浄財", r"献金", r"供養料", r"お布施", r"賽銭", r"貨幣"],
                [r"供養", r"先祖", r"祖霊", r"霊", r"仏壇", r"お盆", r"捧げ"],
            ],
        },
        "pt": {
            "obrig": [
                [r"dinheiro", r"quantia", r"valor", r"monet", r"oferta de", r"óbolo", r"contribuiç"],
                [r"sufrág", r"oferenda", r"antepassado", r"espírito", r"[Oo]bon", r"altar"],
            ],
        },
    },
    7: {
        "titulo": "Antepassados do plano médio p/ cima ajudam a receber os que sofrem no Inferno",
        "jp": {
            "obrig": [
                [r"迎", r"案内", r"導(?:い|く|き)", r"助け", r"世話", r"手伝", r"協力"],
                [r"地獄", r"先祖", r"祖霊", r"霊", r"救(?:い|う)", r"浄(?:い|め)"],
                [r"中(?:位|以上|段)", r"幽世", r"霊界", r"段階", r"上", r"高位"],
            ],
        },
        "pt": {
            "obrig": [
                [r"receb", r"acolh", r"auxili", r"ajud", r"acompanh", r"conduz", r"guia"],
                [r"[Ii]nferno", r"antepassado", r"espírito", r"salv"],
                [r"intermediári", r"superior", r"hierarqu", r"nível", r"grau", r"elevado", r"médio"],
            ],
        },
    },
}

ROTULOS = ("――", "（お伺）", "御伺", "Interlocutor", "Pergunta", "Meishu-Sama")


def blocos(texto: str) -> list[str]:
    """Quebra em blocos por linha vazia, limpando espaços."""
    return [re.sub(r"\s+", " ", b).strip() for b in re.split(r"\n\s*\n", texto) if b.strip()]


def casa_grupos(bloco: str, grupos: list[list[str]]) -> bool:
    for grupo in grupos:
        if not any(re.search(p, bloco) for p in grupo):
            return False
    return True


def pontua(bloco: str, grupos: list[list[str]]) -> int:
    """Conta quantos gatilhos casam (para ordenar candidatos)."""
    n = 0
    for grupo in grupos:
        for p in grupo:
            n += len(re.findall(p, bloco))
    return n


def varrer(ponto: int, idioma: str, limite: int) -> list[tuple[int, str, str]]:
    cfg = PONTOS[ponto][idioma.lower()]
    grupos = cfg["obrig"]
    pasta = PASTAS[idioma]
    out: list[tuple[int, str, str]] = []
    for f in sorted(pasta.glob("*.txt")):
        if ".bak" in f.name:
            continue
        try:
            texto = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for b in blocos(texto):
            if len(b) < 40:
                continue
            if casa_grupos(b, grupos):
                out.append((pontua(b, grupos), f.name, b))
    out.sort(key=lambda x: -x[0])
    return out[:limite]


def main() -> int:
    quais = [int(a) for a in sys.argv[1:]] or list(PONTOS)
    for ponto in quais:
        for idioma in ("JP", "PT"):
            res = varrer(ponto, idioma, limite=6)
            print("\n" + "=" * 110)
            print(f"PONTO {ponto} [{idioma}] — {PONTOS[ponto]['titulo']}")
            print("=" * 110)
            if not res:
                print("  (nenhum candidato)")
            for score, nome, b in res:
                print(f"\n  ▸ {nome}   (score {score})")
                print(f"    {b[:900]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
