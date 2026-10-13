#!/usr/bin/env python3
"""Reforça a regra de 1ª ocorrência do glossário nos periódicos traduzidos.

Regra (glossario_regras.json -> primeira_ocorrencia): na PRIMEIRA menção do termo
em cada artigo, usar a forma completa (com a glosa); depois, a forma curta.

Este script percorre os itens traduzidos e, quando a forma curta aparece no PT e o
item ainda NÃO contém a forma completa, expande a primeira ocorrência.

Uso:
    python scripts/reforcar_primeira_ocorrencia_periodicos.py            # dry-run
    python scripts/reforcar_primeira_ocorrencia_periodicos.py --aplicar  # grava
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

ITENS_DIR = PROJECT_ROOT / "reports" / "traducao_periodicos" / "itens"
RELATORIO = PROJECT_ROOT / "reports" / "primeira_ocorrencia_periodicos.json"

# Guardas: se o texto em volta da forma curta indicar outro sentido, não mexer.
GUARDAS: dict[str, str] = {
    "destino": r"pr[ée]-?determinad|predestinad|shukumei|imut[áa]vel|fixado",
    "benefício": r"espiritual|divino|Virtude",
    "tabuleta": r"funer|memoria|de madeira|branca",
}

# Termos que só devem ser expandidos quando o par contrastante aparece no artigo.
EXIGE_TERMO_JP: dict[str, str] = {
    # "destino mutável" só faz sentido quando 宿命 (destino pré-determinado) coocorre.
    "運命": "宿命",
}

# Termos cuja expansão automática é insegura (exigem decisão frase a frase).
REVISAO_MANUAL = {"運命"}

# Alvo específico (regex) para formas curtas ambíguas.
ALVO_ESPECIFICO: dict[str, str] = {
    # "Norito" sozinho também traduz 祝詞; exigir o qualificador Amatsu.
    "Norito": r"Amatsu\s+Norito",
}

LETRA = r"A-Za-zÀ-ÖØ-öø-ÿ"


# Vocábulos que interrompem a concordância de número (preposições/artigos).
PARADAS = {"de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "com", "e", "a", "o", "as", "os"}


def _plural_palavra(p: str) -> str:
    if p.endswith("s"):
        return p
    if p.endswith(("al", "el", "ol", "ul")):
        return p[:-1] + "is"
    if p.endswith("m"):
        return p[:-1] + "ns"
    if p.endswith(("r", "z", "n")):
        return p + "es"
    return p + "s"


def _pluralizar(forma: str) -> str:
    """Pluraliza os vocábulos concordantes antes de qualquer parêntese."""
    cabeca, _, cauda = forma.partition(" (")
    palavras = cabeca.split()
    if not palavras:
        return forma
    for i, p in enumerate(palavras):
        if p.lower() in PARADAS:
            break
        palavras[i] = _plural_palavra(p)
    return " ".join(palavras) + ((" (" + cauda) if cauda else "")


def _curta_para_completa(curta: str, completa: str) -> str | None:
    """Expande a forma curta para a completa quando a completa contém a curta."""
    if curta == completa:
        return None
    if completa.startswith(curta):
        return completa
    # completa embrulha a curta com glosa, ex.: "tabuleta mortuária (ihai)"
    if curta.lower() in completa.lower():
        return completa
    # curta é transliteração dentro de parênteses da completa, ex.:
    # completa "Papel Sagrado (Goreishi)" / curta "Goreishi" -> expandir
    if curta.lower() in completa.lower():
        return completa
    return None


def _localizar(pt: str, curta: str) -> re.Match[str] | None:
    """Primeira ocorrência "limpa" da forma curta (sem casar dentro de palavra)."""
    alvo = ALVO_ESPECIFICO.get(curta)
    if alvo:
        padrao = alvo
    else:
        # aceita o plural regular logo após a forma curta
        padrao = rf"(?<![{LETRA}]){re.escape(curta)}s?(?![{LETRA}])"
    for m in re.finditer(padrao, pt, flags=re.IGNORECASE):
        if m.start() and pt[m.start() - 1] in "[(":
            continue  # já está glosado entre colchetes/parênteses
        if pt[m.end() : m.end() + 2].startswith(" ["):
            continue  # a glosa já segue o termo, ex.: \"benefício [a graça]\"
        ini = max(0, m.start() - 80)
        fim = min(len(pt), m.end() + 80)
        guarda = GUARDAS.get(curta)
        if guarda and re.search(guarda, pt[ini:fim], flags=re.IGNORECASE):
            continue
        return m
    return None


def processar(pasta: Path, aplicar: bool) -> list[dict]:
    regras = json.loads((PROJECT_ROOT / "glossario_regras.json").read_text(encoding="utf-8"))
    primeira = regras.get("primeira_ocorrencia", {})

    achados: list[dict] = []
    for arquivo in sorted(pasta.glob("*.json")):
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        jp = dados.get("texto_jp") or ""
        pt = dados.get("texto_pt") or ""
        if not jp or not pt:
            continue

        novo = pt
        mudou = False
        for termo, formas in primeira.items():
            completa = formas.get("completa", "")
            curta = formas.get("curta", "")
            if not completa or not curta or termo not in jp:
                continue
            exigido = EXIGE_TERMO_JP.get(termo)
            if exigido and exigido not in jp:
                continue
            expansao = _curta_para_completa(curta, completa)
            if not expansao:
                continue
            if termo in REVISAO_MANUAL:
                continue
            # já tem a forma completa (singular ou plural)?
            if expansao in novo or _pluralizar(expansao) in novo:
                continue
            m = _localizar(novo, curta)
            if not m:
                continue
            # plural: "benefícios" -> "benefícios materiais"
            casou_plural = m.group(0).endswith("s")
            texto = _pluralizar(expansao) if casou_plural else expansao
            achados.append(
                {
                    "arquivo": arquivo.name,
                    "termo": termo,
                    "curta": curta,
                    "completa": texto,
                    "antes": novo[max(0, m.start() - 45) : m.end() + 45],
                }
            )
            novo = novo[: m.start()] + texto + novo[m.end() :]
            mudou = True

        if mudou and aplicar:
            dados["texto_pt"] = novo
            arquivo.write_text(
                json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
            )
    return achados


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true", help="grava as alterações")
    ap.add_argument("--pasta", default=str(ITENS_DIR))
    args = ap.parse_args()

    pasta = Path(args.pasta)
    achados = processar(pasta, args.aplicar)
    RELATORIO.write_text(
        json.dumps(
            {"aplicado": args.aplicar, "total": len(achados), "itens": achados},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"{'APLICADO' if args.aplicar else 'DRY-RUN'}: {len(achados)} expansões")
    for a in achados[:40]:
        print(f"  {a['arquivo']:32s} {a['termo']:8s} {a['curta']!r} -> {a['completa']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
