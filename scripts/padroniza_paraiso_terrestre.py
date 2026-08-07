"""Padroniza 地上天国 como "Paraíso Terrestre" no acervo.

Decisão do usuário (2026-08-07): as duas formas são válidas, mas a IMMB usa
"Paraíso Terrestre" como padrão, e padronizar ajuda a busca.

Estado antes:

    Paraíso na Terra           1016   <- forma dominante hoje
    Paraíso Terrestre             3
    Paraíso Terreno               2
    Reino Celestial na Terra      1

Duas ressalvas que a troca precisa respeitar:

1. CITAÇÃO DE PERIÓDICO. 地上天国 é também o nome de um dos periódicos do
   acervo, citado como fonte em 116 lugares na forma "Paraíso na Terra nº X".
   Nome de publicação é outra decisão -- e note que os demais periódicos são
   citados por transliteração ("Eikō nº 167"), não por tradução. Fica
   intocado até o usuário decidir.
2. ÂNCORAS. 140 âncoras de segmentação em 20 obras contêm o termo e precisam
   mudar junto com o texto, senão a segmentação quebra.

Não há problema de concordância: "Paraíso" é masculino nas duas formas.

Uso:
    python3 scripts/padroniza_paraiso_terrestre.py            # não grava
    python3 scripts/padroniza_paraiso_terrestre.py --aplicar
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

BASES = [RAIZ / "livros_publicacao_pt_revisado", RAIZ / "reports/livros_trabalho/pt"]
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"

ALVO = "Paraíso Terrestre"
# Não toca quando o termo abre uma citação de periódico ("... nº 12",
# "... n. 12", "... , publicado em ...").
CITACAO = re.compile(r"^\s*(n[ºo°.]|,\s*publicad|\s*\()", re.IGNORECASE)

VARIANTES = [
    re.compile(r"Para[íi]so\s+na\s+Terra", re.IGNORECASE),
    re.compile(r"Para[íi]so\s+Terreno", re.IGNORECASE),
    re.compile(r"Reino\s+Celestial\s+na\s+Terra", re.IGNORECASE),
]


def transforma(texto: str) -> tuple[str, int, int]:
    trocas = citacoes = 0

    def repl(m: re.Match) -> str:
        nonlocal trocas, citacoes
        depois = texto[m.end(): m.end() + 20]
        if CITACAO.match(depois):
            citacoes += 1
            return m.group()
        trocas += 1
        alvo = ALVO
        if m.group()[0].islower():
            alvo = alvo[0].lower() + alvo[1:]
        return alvo

    for rx in VARIANTES:
        texto = rx.sub(repl, texto)
    return texto, trocas, citacoes


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    total = preservadas = 0
    por_obra: dict[str, int] = {}

    for base in BASES:
        for p in sorted(base.glob("*.txt")):
            texto = p.read_text(encoding="utf-8")
            novo, n, c = transforma(texto)
            if not n:
                continue
            if base is BASES[0]:
                por_obra[p.name] = n
                total += n
                preservadas += c
            if aplicar:
                if base is BASES[0]:
                    p.with_suffix(f".txt.bak_pre_paraiso_{carimbo}").write_text(
                        texto, encoding="utf-8")
                p.write_text(novo, encoding="utf-8")

    print(f"{total} ocorrências trocadas em {len(por_obra)} obras")
    print(f"{preservadas} citações de periódico preservadas")
    for obra, n in sorted(por_obra.items(), key=lambda x: -x[1])[:8]:
        print(f"  {n:>4}  {obra[:56]}")

    if not aplicar:
        print("\n(diagnóstico apenas — rode com --aplicar)")
        return

    print("\nâncoras...")
    ajust = ruins = 0
    for obra in por_obra:
        spec_path = SPEC_DIR / f"{obra}.json"
        if not spec_path.exists():
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        arts = spec.get("articles", [])
        anc = [a.get("pt_anchor", "") for a in arts]
        if len(anc) <= 1 or not all(anc):
            continue
        texto = clean_body((BASES[0] / obra).read_text(encoding="utf-8"))
        original = spec_path.read_text(encoding="utf-8")
        mudou = False
        for a in arts:
            alvo = a.get("pt_anchor", "")
            if alvo in texto:
                continue
            novo_anc = transforma(alvo)[0]
            if novo_anc != alvo and novo_anc in texto:
                a["pt_anchor"] = novo_anc
                if a.get("title_pt"):
                    a["title_pt"] = transforma(a["title_pt"])[0]
                mudou = True
                ajust += 1
        if mudou:
            spec_path.with_suffix(f".json.bak_pre_paraiso_{carimbo}").write_text(
                original, encoding="utf-8")
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
            anc = [a["pt_anchor"] for a in arts]
        for base in BASES:
            f = base / obra
            if not f.exists():
                continue
            try:
                c = split_by_anchors(clean_body(f.read_text(encoding="utf-8")), anc, label=obra)
                if len(c) != len(anc):
                    raise ValueError("contagem")
            except ValueError as exc:
                print(f"  QUEBROU {base.name}/{obra}: {exc}")
                ruins += 1
    print(f"  {ajust} âncoras atualizadas, {ruins} quebradas")


if __name__ == "__main__":
    main()
