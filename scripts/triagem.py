"""Triagem no sistema de três agentes DeepSeek — o padrão desde 2026-08-10.

    DS1 e DS2 auditam tudo, independentes.
    O DESAFIADOR examina todo caso em que os dois concordam, procurando a razão
    para os dois estarem errados juntos.

    DS1 = DS2 e o desafiador SUSTENTA   -> pilha A: aplica
    DS1 = DS2 e o desafiador DERRUBA    -> pilha C: vai para o usuário
    DS1 ≠ DS2                            -> pilha C: vai para o usuário

Por que este desenho, e não o anterior de Claude como terceira opinião:

O Claude julgava 60 casos por hora contra 385 do DeepSeek — três dias para os
4.350 restantes, prazo que o usuário recusou. O trabalho dele está arquivado em
`reports/arquivo_auditoria_claude/` (1.114 pareceres e 116 decisões pós-
contraponto) e continua consultável.

O desafiador ocupa aquele lugar por um motivo medido, não por conveniência: dois
DeepSeek independentes concordam entre si em 92% — convergem porque compartilham
o modo de ler —, e o risco real da pilha A é justamente o erro que os dois
cometem juntos. Auditar uma terceira vez reproduziria a convergência; pedir
explicitamente «por que os dois podem estar errados» não. No teste cego sobre 17
casos de consenso, ele sustentou 14 e derrubou 3, acertando nos 3 a posição a
que o Claude tinha chegado por outro caminho — sem tê-la visto.

    python3 scripts/triagem.py
    python3 scripts/triagem.py --pilha C
    python3 scripts/triagem.py --grupos
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import auditoria as A  # noqa: E402  (só para dossiê e lista de procedentes)

R = RAIZ / "reports/varredura_padronizacao"
DS1 = R / "AUDITORIA_DEEPSEEK.json"
DS2 = R / "AUDITORIA_DEEPSEEK2.json"
DES = R / "DESAFIADOR.json"
VALIDOS = ("aprovado", "recusado", "reformar")


def _le(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def pilhas() -> dict[str, list[str]]:
    d1, d2, ds = _le(DS1), _le(DS2), _le(DES)
    out: dict[str, list[str]] = {"A": [], "C": [], "aguardando": []}
    for k in d1:
        if k not in d2:
            continue
        v1, v2 = d1[k]["veredito"], d2[k]["veredito"]
        if v1 not in VALIDOS or v2 not in VALIDOS:
            continue
        if v1 != v2:
            out["C"].append(k)
        elif k not in ds or "erro" in ds[k]:
            out["aguardando"].append(k)      # falta o desafiador passar
        elif ds[k]["derruba"]:
            out["C"].append(k)
        else:
            out["A"].append(k)
    return out


def veredito(k: str) -> str:
    return _le(DS1)[k]["veredito"]


TIPOS = [
    ("âncora de segmentação", r"âncora|ancora"),
    ("nome próprio ou topônimo", r"lê-se|romaniz|nome próprio|topônimo|furigana"),
    ("glossário", r"glossári|forma fixa|forma canônica"),
    ("turno de diálogo", r"turno|Interlocutor|Meishu-Sama:"),
    ("número, data ou unidade", r"\bnúmero\b|unidade|décimo|milhar|bilh|idade|ano de"),
    ("sujeito ou agente", r"sujeito|agente|inverte|invertid|polaridade"),
    ("omissão ou acréscimo", r"omit|acrescent|suprimi|inventad"),
    ("convenção — decisão sua", r"convenç|depende dele|decisão do usuário|bíblic"),
]


def tipo(nota: str) -> str:
    for nome, pat in TIPOS:
        if re.search(pat, nota, re.I):
            return nome
    return "outros"


def main() -> None:
    p = pilhas()
    d1, ds = _le(DS1), _le(DES)

    if "--pilha" in sys.argv:
        alvo = sys.argv[sys.argv.index("--pilha") + 1].upper()
        d2 = _le(DS2)
        for k in p[alvo][:60]:
            print(f"\n{k}")
            print(f"  DS1 [{d1[k]['veredito']:<9}] {d1[k]['nota'][:100]}")
            print(f"  DS2 [{d2[k]['veredito']:<9}] {d2[k]['nota'][:100]}")
            if k in ds and "erro" not in ds[k]:
                m = "DERRUBOU" if ds[k]["derruba"] else "sustentou"
                print(f"  desafiador [{m}] {ds[k]['razao'][:100]}")
        return

    if "--grupos" in sys.argv:
        g = defaultdict(list)
        for k in p["C"]:
            nota = d1[k]["nota"] + " " + (ds.get(k, {}).get("razao", ""))
            g[tipo(nota)].append(k)
        print("PILHA C agrupada — o que vai para a sua mesa, por tipo\n")
        for nome, ks in sorted(g.items(), key=lambda x: -len(x[1])):
            print(f"  {len(ks):>4}  {nome}")
        return

    dec = len(p["A"]) + len(p["C"])
    tot = dec + len(p["aguardando"])
    print(f"{tot:,} achados com DS1 e DS2; {dec:,} já triados\n")
    print(f"  A  {len(p['A']):>5}  os dois de acordo e o desafiador sustentou — aplica")
    print(f"  C  {len(p['C']):>5}  desafiador derrubou, ou DS1 ≠ DS2 — sua mesa")
    print(f"     {len(p['aguardando']):>5}  aguardando o desafiador")
    if p["A"]:
        c = Counter(veredito(k) for k in p["A"])
        print(f"\n  na pilha A: {c.get('aprovado',0)} a aplicar, "
              f"{c.get('reformar',0)} a reformular, {c.get('recusado',0)} sem ação")


if __name__ == "__main__":
    main()
