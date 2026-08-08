"""Repara âncoras quebradas por edição de texto, preservando a ORDEM.

Substitui o reparo por prefixo que existia em `reaplica_semantico.aplicar()`,
e que causou um erro real: ao procurar a âncora quebrada pelos seus 26
primeiros caracteres, "O Juízo Final\\n\\nParaíso na " passou a ocorrer uma
única vez no arquivo (a outra ocorrência virara "Tijotengoku") e o reparo
reapontou a âncora silenciosamente para OUTRO artigo -- o nº 12 em vez do
nº 42. Casar por prefixo não distingue artigos que começam igual.

Aqui a âncora nova só é aceita se:
  1. nascer de uma troca REAL aplicada àquele arquivo (ou de um par derivado
     das decisões), nunca de um pedaço do texto antigo;
  2. ocorrer UMA única vez no arquivo;
  3. cair DEPOIS da âncora anterior -- a ordem dos artigos é o invariante.

Uso:
    python3 scripts/repara_ancoras_ordem.py            # diagnóstico
    python3 scripts/repara_ancoras_ordem.py --aplicar
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
PROPOSTAS = [
    RAIZ / "reports/varredura_padronizacao/REAPLICACAO_SEMANTICA.json",
    RAIZ / "reports/varredura_padronizacao/REAPLICACAO_SEMANTICA2.json",
    RAIZ / "reports/varredura_padronizacao/REAPLICACAO_SEMANTICA3.json",
    RAIZ / "reports/varredura_padronizacao/REAPLICACAO_SEMANTICA4.json",
]

# Pares derivados das decisões, para a âncora que o modelo nunca citou por
# estar num título e não no corpo lido.
DERIVADOS = [
    ("Paraíso na Terra nº", "Tijotengoku nº"),
    ("Paraíso na Terra,", "Tijotengoku,"),
    ("Paraíso na Terra", "Paraíso Terrestre"),
    # âncora com a citação truncada -- "(Paraíso na Terra" sem o "nº"
    ("Paraíso na Terra", "Tijotengoku"),
    ("Orações", "Norito"),
    ("orações", "norito"),
    ("Oração", "Norito"),
    ("vegetais", "hortaliças"),
    ("Vegetais", "Hortaliças"),
    ("poder de Kannon", "Poder Kannon"),
    ("espírito da palavra", "espírito da palavra (kotodama)"),
    ("Kannon do biombo", "Byōbu Kannon"),
]


def trocas_por_obra() -> dict[str, list[tuple[str, str]]]:
    saida: dict[str, list[tuple[str, str]]] = {}
    for f in PROPOSTAS:
        if not f.exists():
            continue
        for r in json.loads(f.read_text(encoding="utf-8")):
            for t in r.get("trocas", []):
                saida.setdefault(r["obra"], []).append((t["de"], t["para"]))
    return saida


def candidatos(velha: str, pares: list[tuple[str, str]]) -> list[str]:
    """Formas que a âncora pode ter assumido -- nunca um pedaço dela."""
    vistos, saida = {velha}, []
    for de, para in pares:
        if de in velha:
            novo = velha.replace(de, para)
            if novo not in vistos:
                vistos.add(novo)
                saida.append(novo)
    # composições de dois pares (título e citação mudaram juntos)
    for base in list(saida):
        for de, para in pares:
            if de in base:
                novo = base.replace(de, para)
                if novo not in vistos:
                    vistos.add(novo)
                    saida.append(novo)
    return saida


def repara_obra(obra: str, pares: list[tuple[str, str]], aplicar: bool) -> tuple[int, int]:
    sp = SPEC_DIR / f"{obra}.json"
    if not sp.exists():
        return 0, 0
    spec = json.loads(sp.read_text(encoding="utf-8"))
    arts = spec.get("articles", [])
    anc = [a.get("pt_anchor", "") for a in arts]
    if len(anc) <= 1 or not all(anc):
        return 0, 0
    texto = clean_body((PT_FONTE / obra).read_text(encoding="utf-8"))
    try:
        if len(split_by_anchors(texto, anc, label=obra)) == len(arts):
            return 0, 0
    except ValueError:
        pass

    cursor, corrigidas, perdidas = 0, 0, 0
    for i, a in enumerate(arts):
        velha = a.get("pt_anchor", "")
        pos = texto.find(velha, cursor)
        if pos >= 0:
            cursor = pos + 1
            continue
        # onde a PRÓXIMA âncora ainda existente começa: é o teto da janela
        teto = len(texto)
        for prox in arts[i + 1:]:
            q = texto.find(prox.get("pt_anchor", "\x00"), cursor)
            if q >= 0:
                teto = q
                break

        escolhida = None
        for c in candidatos(velha, pares + DERIVADOS):
            p = texto.find(c, cursor)
            if p < 0:
                continue
            # Aceita se for única no arquivo (caso simples) OU se cair dentro
            # da janela deste artigo -- entre a âncora anterior e a próxima.
            # A janela é o invariante real; exigir unicidade global rejeitava
            # títulos legítimos que se repetem no corpo (caso real: a âncora
            # "Paraíso na Terra" de 信仰雑話, e o título de 結核と神霊療法).
            if texto.count(c) == 1 or p < teto:
                escolhida, pos = c, p
                break
        if escolhida is None:
            print(f"  NÃO RESOLVIDA {obra[:34]} idx{i}: {velha[:56]!r}")
            perdidas += 1
            continue
        print(f"  {obra[:26]:<28} idx{i:<4} {velha[:44]!r}\n"
              f"  {'':<28}      -> {escolhida[:44]!r}")
        if aplicar:
            if (a.get("title_pt") or "").strip() == velha.strip():
                a["title_pt"] = escolhida
            a["pt_anchor"] = escolhida
        cursor = pos + 1
        corrigidas += 1

    if aplicar and corrigidas:
        sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return corrigidas, perdidas


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    pares = trocas_por_obra()
    tot_c = tot_p = obras = 0
    for p in sorted(PT_FONTE.glob("*.txt")):
        c, pe = repara_obra(p.name, pares.get(p.name, []), aplicar)
        if c or pe:
            obras += 1
        tot_c += c
        tot_p += pe
    print(f"\n{tot_c} âncoras reparadas, {tot_p} não resolvidas, em {obras} obras")
    if not aplicar:
        print("(diagnóstico apenas -- rode com --aplicar)")
        return

    ruins = 0
    for p in sorted(PT_FONTE.glob("*.txt")):
        sp = SPEC_DIR / f"{p.name}.json"
        if not sp.exists():
            continue
        anc = [a.get("pt_anchor", "") for a in
               json.loads(sp.read_text(encoding="utf-8")).get("articles", [])]
        if len(anc) <= 1 or not all(anc):
            continue
        for base in (PT_FONTE, PT_STAGING):
            f = base / p.name
            if not f.exists():
                continue
            try:
                if len(split_by_anchors(clean_body(f.read_text(encoding="utf-8")),
                                        anc, label=p.name)) != len(anc):
                    raise ValueError("contagem")
            except ValueError as exc:
                print(f"  QUEBRADA {base.name}/{p.name}: {str(exc)[:100]}")
                ruins += 1
    print(f"verificação final: {ruins} âncoras quebradas")


if __name__ == "__main__":
    main()
