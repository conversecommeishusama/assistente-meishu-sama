"""Audita as propostas da 2ª passada antes de gravar.

Cada proposta é conferida contra o japonês do próprio artigo. Só sobrevive o
que o original sustenta. Três verificações, todas nascidas de caso real visto
nesta rodada:

REGRESSÃO -- a troca AFASTA da forma canônica em vez de aproximar. Caso real:
    "há muitas nuvens" -> "há muita nebulosidade", quando o japonês diz
    戦争のあとは曇りが多い, o 曇 doutrinário. Rejeitada.

SEM APOIO -- o japonês do artigo não traz a chave que justificaria a troca.
    Ex.: virar "proteção divina" num artigo sem 御守護 nenhum.

COMPOSTO -- a troca toca um termo que tem decisão própria e diferente
    (千手観音様, 御屏風観音様, 救世観音, 観世音菩薩, 観音力, 霊体の曇,
    御守り, 守護神, 御神徳). Rejeitada.

Remoção de "-Sama" é contada à parte e mantida: nos casos inspecionados o
japonês de fato traz 観音 sem 様 (観音に擬える, 観音力), então a troca é
fiel. Fica no relatório para o usuário saber que aconteceu.

Uso:
    python3 scripts/audita_reaplicacao2.py            # relatório
    python3 scripts/audita_reaplicacao2.py --podar    # grava o JSON sem as rejeitadas
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

DESTINO = RAIZ / "reports/varredura_padronizacao/REAPLICACAO_SEMANTICA2.json"

# forma canônica -> chave que o japonês precisa trazer
CANONICAS = [
    (re.compile(r"Kannon-Sama"), re.compile(r"観\s*音\s*様")),
    (re.compile(r"proteção divina|graça divina"), re.compile(r"御\s*守\s*護")),
    (re.compile(r"benefício[s]? material|benefícios materiais"), re.compile(r"御\s*利\s*益")),
    (re.compile(r"nuvens? espirituais?|nuvem espiritual"), re.compile(r"曇")),
]

# termos com decisão própria: se aparecem no trecho de origem, não se mexe
COMPOSTOS = [
    "Kannon de Mil Braços", "Byōbu Kannon", "Guse-Kannon", "Kanzeon-Bosatsu",
    "Poder Kannon", "nuvens do corpo espiritual", "Ohikari",
    "espírito protetor", "Graças Divinas", "virtude divina",
]


def audita() -> tuple[list[dict], Counter, list[tuple]]:
    dados = json.loads(DESTINO.read_text(encoding="utf-8"))
    cache: dict[str, list[str]] = {}
    contagem: Counter = Counter()
    rejeitadas: list[tuple] = []

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

            # só é problema se o composto foi REESCRITO -- aparecer intacto
            # no trecho não impede corrigir outra palavra da mesma frase
            tocou_composto = any(c in de and c not in para for c in COMPOSTOS)
            # remover o honorífico é caso à parte, tratado abaixo: nos casos
            # inspecionados o japonês traz 観音 sem 様 (観音に擬える, 観音力)
            so_tira_sama = ("Kannon-Sama" in de and "Kannon-Sama" not in para
                            and "Kannon" in para)

            if tocou_composto:
                motivo = "composto com decisão própria foi reescrito"
            elif not so_tira_sama:
                for rx_pt, rx_jp in CANONICAS:
                    tinha, tem = bool(rx_pt.search(de)), bool(rx_pt.search(para))
                    if tinha and not tem:
                        motivo = "regressão: afasta da forma canônica"
                        break
                    if tem and not tinha and not rx_jp.search(jp):
                        motivo = "sem apoio no japonês do artigo"
                        break

            if motivo:
                rejeitadas.append((motivo, obra, r["artigo"], de, para))
                contagem[f"REJEITADA — {motivo}"] += 1
                continue

            if so_tira_sama:
                contagem["mantida — remove -Sama (japonês sem 様)"] += 1
            else:
                contagem["mantida"] += 1
            mantidas.append(t)
        r["trocas"] = mantidas

    return dados, contagem, rejeitadas


def main() -> None:
    dados, contagem, rejeitadas = audita()
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
    if "--podar" in sys.argv:
        DESTINO.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        print(f"\nJSON podado: {total} trocas sobreviveram")
    else:
        print("\n(relatório apenas -- rode com --podar para gravar)")


if __name__ == "__main__":
    main()
