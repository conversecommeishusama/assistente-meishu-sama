"""Audita as propostas da 3ª passada (14 termos já decididos) antes de gravar.

Mesmas três verificações da 2ª passada, com o conjunto de termos desta rodada.
A primeira tentativa de gerar este arquivo por `sed` herdou as regras da 2ª e
rejeitou por engano `graça divina -> Graças Divinas`, que é exatamente a
decisão de 御霊徳 aqui -- daí ele ser escrito à mão.

Uso:
    python3 scripts/audita_reaplicacao3.py            # relatório
    python3 scripts/audita_reaplicacao3.py --podar    # grava sem as rejeitadas
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import reaplica_semantico as R  # noqa: E402

DESTINO = RAIZ / "reports/varredura_padronizacao/REAPLICACAO_SEMANTICA3.json"

# forma canônica no português -> chave que o japonês precisa trazer
# (o honorífico aparece em kanji e em hiragana: 御霊徳 e ご霊徳)
CANONICAS = [
    (re.compile(r"curso \(aula\) de prepara|curso de prepara|kyoshu"),
     re.compile(r"教\s*修")),
    (re.compile(r"Deus Supremo"), re.compile(r"主\s*神")),
    (re.compile(r"Amaterasu Ōmikami"), re.compile(r"天\s*照")),
    (re.compile(r"Raça de Yamato"), re.compile(r"大\s*和\s*民\s*族")),
    (re.compile(r"Poder Kannon"), re.compile(r"観\s*音\s*力")),
    (re.compile(r"Kanzeon-Bosatsu"), re.compile(r"観\s*世\s*音\s*菩\s*薩")),
    (re.compile(r"\bInari\b"), re.compile(r"稲\s*荷")),
    (re.compile(r"\bJohrei\b"), re.compile(r"浄\s*霊")),
    (re.compile(r"Mundo da Noite"), re.compile(r"夜\s*の\s*世\s*界")),
    (re.compile(r"Extinção do Budismo"), re.compile(r"仏\s*滅")),
    (re.compile(r"\bJikan\b"), re.compile(r"自\s*観")),
    (re.compile(r"divindades corretas"), re.compile(r"正\s*神")),
    (re.compile(r"encontro dos três Miroku"), re.compile(r"弥\s*勒\s*三\s*会")),
    (re.compile(r"Graças Divinas"), re.compile(r"[御ごお]\s*霊\s*徳")),
]

# termos com decisão própria e diferente: se forem REESCRITOS, rejeita
COMPOSTOS = [
    "Kannon de Mil Braços", "Byōbu Kannon", "Guse-Kannon", "Kannon-Sama",
    "método do Johrei", "Divindades malignas", "benefício material",
    "nuvens espirituais", "proteção divina", "Komyo-Nyorai", "Daikōmyō",
]


def audita() -> tuple[list[dict], Counter, list[tuple], list[tuple]]:
    dados = json.loads(DESTINO.read_text(encoding="utf-8"))
    cache: dict[str, list[str]] = {}
    contagem: Counter = Counter()
    rejeitadas: list[tuple] = []
    inspecionar: list[tuple] = []

    for r in dados:
        obra = r["obra"]
        if obra not in cache:
            cache[obra] = R.artigos(R.JP_DIR / obra, "jp_anchor", obra)
        arts = cache[obra]
        jp = arts[r["artigo"]] if r["artigo"] < len(arts) else ""
        mantidas = []
        for t in r.get("trocas", []):
            de, para = t["de"], t["para"]
            motivo = None

            if any(c in de and c not in para for c in COMPOSTOS):
                motivo = "composto com decisão própria foi reescrito"
            else:
                for rx_pt, rx_jp in CANONICAS:
                    tinha, tem = bool(rx_pt.search(de)), bool(rx_pt.search(para))
                    # Tirar a forma canônica NÃO é erro por si: o português
                    # pode tê-la aplicado onde o japonês não a sustenta. Caso
                    # real desta rodada -- "Johrei" onde o japonês diz 浄化
                    # (purificação), não 浄霊. E a presença da chave no artigo
                    # não decide, porque 結核の革命的療法 art114 tem 浄霊 7x e
                    # 浄化 17x. Por isso sinaliza para leitura, não rejeita.
                    if tinha and not tem:
                        contagem["mantida — remove forma canônica (inspecionada)"] += 1
                        inspecionar.append((obra, r["artigo"], de, para))
                        break
                    if tem and not tinha and not rx_jp.search(jp):
                        motivo = "sem apoio no japonês do artigo"
                        break

            if motivo:
                rejeitadas.append((motivo, obra, r["artigo"], de, para))
                contagem[f"REJEITADA — {motivo}"] += 1
                continue
            contagem["mantida"] += 1
            mantidas.append(t)
        r["trocas"] = mantidas

    return dados, contagem, rejeitadas, inspecionar


def main() -> None:
    dados, contagem, rejeitadas, inspecionar = audita()
    total = sum(len(r.get("trocas", [])) for r in dados)
    print(f"{len(dados)} artigos | {total} trocas mantidas | "
          f"{len(rejeitadas)} rejeitadas\n")
    for k, v in contagem.most_common():
        print(f"  {v:>5}  {k}")
    if rejeitadas:
        print("\nrejeitadas:")
        for motivo, obra, art, de, para in rejeitadas[:30]:
            print(f"  [{motivo}] {obra[:26]} art{art}")
            print(f"      {de[:62]!r}\n   -> {para[:62]!r}")
    if inspecionar:
        print("\nremovem a forma canônica -- confirmadas contra o japonês:")
        for obra, art, de, para in inspecionar:
            print(f"  {obra[:28]} art{art}: {de[:52]!r} -> {para[:52]!r}")
    if "--podar" in sys.argv:
        DESTINO.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        print(f"\nJSON podado: {total} trocas sobreviveram")
    else:
        print("\n(relatório apenas -- rode com --podar para gravar)")


if __name__ == "__main__":
    main()
