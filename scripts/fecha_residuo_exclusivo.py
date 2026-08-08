"""Fecha o resíduo dos termos cuja forma desviante é EXCLUSIVA daquele japonês.

Nem toda troca precisa de leitura ocorrência a ocorrência. Estes quatro têm
uma propriedade que os outros não têm: nada além da chave japonesa produz a
forma portuguesa desviante.

    御屏風観音  -> "Kannon do biombo"   (nenhum outro termo vira isso)
    教修       -> "curso de iniciação"
    観音力     -> "poder de Kannon"
    邪神       -> "deuses malignos"     (悪霊 é "espíritos malignos", outra
                                         palavra; 正神 é "divindades corretas")

Contraste com os que NÃO entram aqui e continuam exigindo leitura, porque a
forma desviante tem gêmeo em japonês:

    祝詞 x 祈り/祈願   -> os dois viram "oração"
    野菜 x 植物        -> os dois viram "vegetal"
    浄霊 x 浄化        -> os dois viram "purificação"
    地上天国 x 天国    -> os dois viram "Paraíso ..."

A garantia continua sendo o japonês: a troca só ocorre no artigo cujo japonês
traz a chave, e dentro da janela daquele artigo. Nada de find-replace no
arquivo.

Uso:
    python3 scripts/fecha_residuo_exclusivo.py            # diagnóstico
    python3 scripts/fecha_residuo_exclusivo.py --aplicar
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import reaplica_semantico as R  # noqa: E402
from aplica_no_artigo import janelas  # noqa: E402
from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

# (chave japonesa, [(regex do desvio, substituto)]) -- a ordem importa: as
# formas com preposição contraída vêm antes das simples.
REGRAS: list[tuple[str, list[tuple[str, str]]]] = [
    ("御屏風観音", [
        (r"\bda Kannon do biombo\b", "de Byōbu Kannon"),
        (r"\bà Kannon do biombo\b", "a Byōbu Kannon"),
        (r"\bna Kannon do biombo\b", "em Byōbu Kannon"),
        (r"\bpela Kannon do biombo\b", "por Byōbu Kannon"),
        (r"\ba imagem de Kannon do biombo\b", "Byōbu Kannon"),
        (r"\ba Kannon do biombo\b", "Byōbu Kannon"),
        (r"\bA Kannon do biombo\b", "Byōbu Kannon"),
        (r"\bo biombo com a imagem de Kannon(-Sama)?\b", "Byōbu Kannon"),
        (r"\bKannon do biombo\b", "Byōbu Kannon"),
    ]),
    ("教修", [
        (r"\bcurso de iniciação \(Kyoshu\)", "curso (aula) de preparação para receber o Ohikari (kyoshu)"),
        (r"\bcurso de iniciação\b", "curso (aula) de preparação para receber o Ohikari (kyoshu)"),
    ]),
    ("観音力", [
        (r"\bo poder de Kannon\b", "o Poder Kannon"),
        (r"\bpoder de Kannon\b", "Poder Kannon"),
    ]),
    ("邪神", [
        (r"\bdeuses malignos\b", "Divindades malignas"),
        (r"\bdeus maligno\b", "Divindade maligna"),
        (r"\bDeuses malignos\b", "Divindades malignas"),
        (r"\bDeus maligno\b", "Divindade maligna"),
    ]),
]

# Contextos em que a forma desviante NÃO vem da chave -- confirmados lendo o
# japonês: 念彼観音力 tem forma própria, e a glosa já feita não se toca.
NAO_TOCAR = [
    re.compile(r"\(Kannon do biombo\)"),          # glosa de Byōbu Kannon
    re.compile(r"nenpi Kannon riki"),             # translitera 念彼観音力
    re.compile(r"Graça do Poder Kannon"),
]


def protegido(trecho: str, ini: int) -> bool:
    janela = trecho[max(0, ini - 40): ini + 40]
    return any(rx.search(janela) for rx in NAO_TOCAR)


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    conta: Counter = Counter()
    pulados: list[str] = []

    for p in sorted(R.PT_FONTE.glob("*.txt")):
        obra = p.name
        ajp = R.artigos(R.JP_DIR / obra, "jp_anchor", obra)
        if not ajp:
            continue
        bruto = p.read_text(encoding="utf-8")
        js = janelas(obra, bruto)
        if js is None or len(js) != len(ajp):
            continue
        novo, mudou = bruto, False

        # de trás para frente: mexer no fim não desloca o começo
        for i in range(len(js) - 1, -1, -1):
            jp = ajp[i]
            ini, fim = js[i]
            trecho = novo[ini:fim]
            antes = trecho
            for chave, subs in REGRAS:
                if chave not in jp:
                    continue
                for rx, dest in subs:
                    def troca(m: re.Match) -> str:
                        if protegido(trecho, m.start()):
                            return m.group()
                        conta[chave] += 1
                        return dest
                    trecho = re.sub(rx, troca, trecho)
            if trecho != antes:
                novo = novo[:ini] + trecho + novo[fim:]
                mudou = True

        if not mudou:
            continue
        if aplicar:
            p.with_suffix(f".txt.bak_pre_residuo_{carimbo}").write_text(
                bruto, encoding="utf-8")
            p.write_text(novo, encoding="utf-8")
            st = R.PT_STAGING / obra
            if st.exists():
                st.write_text(novo, encoding="utf-8")

    for k, v in conta.most_common():
        print(f"  {v:>4}  {k}")
    print(f"  total {sum(conta.values())}")
    if pulados:
        print("pulados:", *pulados, sep="\n  ")
    if not aplicar:
        print("\n(diagnóstico apenas -- rode com --aplicar)")
        return

    ruins = 0
    for p in sorted(R.PT_FONTE.glob("*.txt")):
        sp = R.SPEC_DIR / f"{p.name}.json"
        if not sp.exists():
            continue
        anc = [a.get("pt_anchor", "") for a in
               json.loads(sp.read_text(encoding="utf-8")).get("articles", [])]
        if len(anc) <= 1 or not all(anc):
            continue
        for base in (R.PT_FONTE, R.PT_STAGING):
            f = base / p.name
            if not f.exists():
                continue
            try:
                if len(split_by_anchors(clean_body(f.read_text(encoding="utf-8")),
                                        anc, label=p.name)) != len(anc):
                    raise ValueError("contagem")
            except ValueError as exc:
                print(f"  QUEBRADA {base.name}/{p.name}: {str(exc)[:90]}")
                ruins += 1
    print(f"verificação: {ruins} âncoras quebradas")


if __name__ == "__main__":
    main()
