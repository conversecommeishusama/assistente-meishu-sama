"""Triagem dos três pareceres nas pilhas definidas pelo usuário (2026-08-10).

    DS1 = DS2 = Claude          -> pilha A: aplica automático
    DS1 = DS2 ≠ Claude          -> pilha B: eu escrevo o contraponto e a
                                   palavra final é do DeepSeek
    DS1 ≠ DS2                   -> pilha C: vai para o usuário
    os três diferentes          -> pilha C

O desenho tira o Claude da posição de juiz em causa própria: na pilha B ele
argumenta, não decide. Isso responde ao problema que o usuário levantou -- quem
desempata Claude contra DeepSeek não pode ser o Claude.

A pilha C junta dois casos que o usuário tratou separadamente mas que têm a
mesma natureza: quando os DOIS DeepSeek discordam entre si (8% dos casos, medido
em 2026-08-10), é sinal de dificuldade real, e não de ruído -- dois DeepSeek
independentes concordam em 92%.

    python3 scripts/triagem.py               # o quadro
    python3 scripts/triagem.py --pilha B     # lista uma pilha
    python3 scripts/triagem.py --grupos      # a pilha C agrupada por tipo
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

import auditoria as A  # noqa: E402

DS1 = RAIZ / "reports/varredura_padronizacao/AUDITORIA_DEEPSEEK.json"
DS2 = RAIZ / "reports/varredura_padronizacao/AUDITORIA_DEEPSEEK2.json"


def _le(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def pilhas() -> dict[str, list[str]]:
    c, d1, d2 = A.carrega(), _le(DS1), _le(DS2)
    out: dict[str, list[str]] = {"A": [], "B": [], "C": []}
    for k in d1:
        if k not in d2 or k not in c:
            continue
        v1, v2, vc = d1[k]["veredito"], d2[k]["veredito"], c[k]["veredito"]
        if "erro" in (v1, v2, vc) or "?" in (v1, v2, vc):
            continue
        if v1 != v2:
            out["C"].append(k)
        elif v1 == vc:
            out["A"].append(k)
        else:
            out["B"].append(k)
    return out


TIPOS = [
    ("âncora de segmentação", r"âncora|ancora"),
    ("nome próprio ou topônimo", r"lê-se|romaniz|nome próprio|topônimo|furigana"),
    ("glossário", r"glossári|forma fixa|forma canônica"),
    ("turno de diálogo", r"turno|Interlocutor|Meishu-Sama:"),
    ("número, data ou unidade", r"\bnúmero\b|unidade|décimo|milhar|bilh|contagem de"),
    ("sujeito ou agente", r"sujeito|agente|inverte|invertid"),
    ("omissão ou acréscimo", r"omit|acrescent|suprimi|inventad"),
    ("convenção (decisão do usuário)", r"convenç|depende dele|decisão do usuário|bíblic"),
]


def tipo(nota: str) -> str:
    for nome, pat in TIPOS:
        if re.search(pat, nota, re.I):
            return nome
    return "outros"


def main() -> None:
    p = pilhas()
    c, d1, d2 = A.carrega(), _le(DS1), _le(DS2)
    tot = sum(len(v) for v in p.values())
    if "--pilha" in sys.argv:
        alvo = sys.argv[sys.argv.index("--pilha") + 1].upper()
        for k in p[alvo][:60]:
            print(f"\n{k}")
            print(f"  DS1    [{d1[k]['veredito']:<9}] {d1[k]['nota'][:104]}")
            print(f"  DS2    [{d2[k]['veredito']:<9}] {d2[k]['nota'][:104]}")
            print(f"  Claude [{c[k]['veredito']:<9}] {c[k]['nota'][:104]}")
        return
    if "--grupos" in sys.argv:
        g = defaultdict(list)
        for k in p["C"]:
            g[tipo(d1[k]["nota"] + " " + c[k]["nota"])].append(k)
        print("PILHA C agrupada — é o que vai para o usuário decidir em lote\n")
        for nome, ks in sorted(g.items(), key=lambda x: -len(x[1])):
            print(f"  {len(ks):>4}  {nome}")
        return
    print(f"{tot:,} achados com os três pareceres\n")
    print(f"  A  {len(p['A']):>5}  {len(p['A'])/max(1,tot):5.0%}  os três de acordo — aplica automático")
    print(f"  B  {len(p['B']):>5}  {len(p['B'])/max(1,tot):5.0%}  DS1=DS2 ≠ Claude — contraponto meu, palavra final do DeepSeek")
    print(f"  C  {len(p['C']):>5}  {len(p['C'])/max(1,tot):5.0%}  DS1 ≠ DS2 ou três diferentes — vai para o usuário")
    if p["A"]:
        print(f"\n  na pilha A, o que seria aplicado: "
              f"{dict(Counter(d1[k]['veredito'] for k in p['A']))}")


if __name__ == "__main__":
    main()
