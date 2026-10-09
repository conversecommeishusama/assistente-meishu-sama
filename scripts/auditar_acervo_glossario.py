#!/usr/bin/env python3
"""Auditoria do glossário sobre textos JÁ TRADUZIDOS (acervo e periódicos).

Regra de ouro desta auditoria: comparar cada par JP→PT **separadamente**
(título com título, corpo com corpo). A versão anterior concatenava
`titulo_jp + texto_jp` e comparava só com `texto_pt` — daí o falso positivo
massivo de `栄光` (nome do periódico Eikō): a palavra estava em `fonte_pt`
e `titulo_pt`, nunca no corpo.

Uso:
    python scripts/auditar_acervo_glossario.py --itens 'reports/traducao_periodicos/itens/*.json'
    python scripts/auditar_acervo_glossario.py --itens <glob> --saida reports/auditoria_glossario
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from glossario_core import auditar  # noqa: E402

# Campos comparados como PAR (JP → PT). `fonte_pt` é metadado editorial:
# não tem JP correspondente, então só recebe a checagem de proibições.
PARES = (
    ("titulo_jp", "titulo_pt"),
    ("texto_jp", "texto_pt"),
)
CAMPOS_PT_SOZINHOS = ("fonte_pt",)


def _achatar(rel: dict, secao: str, origem: str) -> list[dict]:
    """Transforma o relatório de `auditar` numa lista plana de achados."""
    linhas: list[dict] = []
    for p in rel["proibicoes"]:
        linhas.append({
            "origem": origem, "secao": secao, "camada": "proibicao",
            "termo": p["palavra"], "gravidade": p["gravidade"],
            "contexto": p["contexto"],
        })
    for m in rel["medidas"]:
        linhas.append({
            "origem": origem, "secao": secao, "camada": "medida",
            "termo": m["unidade_jp"], "gravidade": "medida",
            "contexto": m.get("conversao_aproximada", ""),
            "transliteracao": "|".join(m.get("transliteracao_presente", [])),
        })
    for v in rel["forma"]:
        linhas.append({
            "origem": origem, "secao": secao, "camada": "forma",
            "termo": v["termo_jp"], "gravidade": v["criticidade"],
            "contexto": " | ".join(v["formas"])[:200],
        })
    for v in rel["primeira_ocorrencia"]:
        linhas.append({
            "origem": origem, "secao": secao, "camada": "1a_ocorrencia",
            "termo": v["termo_jp"], "gravidade": "normal",
            "contexto": v["forma_completa"],
        })
    return linhas


def auditar_item(d: dict, origem: str) -> list[dict]:
    """Audita um item traduzido (registro com campos *_jp / *_pt)."""
    achados: list[dict] = []
    for campo_jp, campo_pt in PARES:
        jp, pt = d.get(campo_jp) or "", d.get(campo_pt) or ""
        if not jp or not pt:
            continue
        rel = auditar(jp, pt)
        if rel["total"]:
            achados += _achatar(rel, campo_pt, origem)
    # metadados em PT: só proibições (não há JP para casar forma)
    for campo in CAMPOS_PT_SOZINHOS:
        txt = d.get(campo) or ""
        if not txt:
            continue
        rel = auditar("", txt)
        if rel["proibicoes"]:
            achados += _achatar(rel, campo, origem)
    return achados


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--itens", required=True, help="glob dos arquivos JSON")
    ap.add_argument("--saida", default="reports/auditoria_glossario")
    ap.add_argument("--detalhar", action="store_true",
                    help="imprime os achados no terminal")
    args = ap.parse_args()

    arquivos = sorted(glob.glob(args.itens))
    if not arquivos:
        print(f"nenhum arquivo para o glob: {args.itens}")
        return 1
    print(f"itens encontrados: {len(arquivos)}")

    todos: list[dict] = []
    itens_com_achado = 0
    for f in arquivos:
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception as e:                      # noqa: BLE001
            print(f"  ! falha lendo {f}: {e}")
            continue
        achados = auditar_item(d, Path(f).name)
        if achados:
            itens_com_achado += 1
            todos += achados

    saida = RAIZ / args.saida
    saida.mkdir(parents=True, exist_ok=True)

    # ---- agregações -------------------------------------------------------
    por_camada = Counter(a["camada"] for a in todos)
    por_termo = Counter(f"{a['camada']}:{a['termo']}" for a in todos)
    # depois de calibrar, contamos ITENS distintos por termo (não ocorrências)
    itens_por_termo: dict[str, set] = defaultdict(set)
    for a in todos:
        itens_por_termo[f"{a['camada']}:{a['termo']}"].add(a["origem"])

    (saida / "achados.json").write_text(
        json.dumps(todos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with (saida / "achados.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "origem", "secao", "camada", "termo", "gravidade",
            "contexto", "transliteracao"])
        w.writeheader()
        for a in todos:
            w.writerow({**{"transliteracao": ""}, **a})

    top = sorted(itens_por_termo.items(), key=lambda x: -len(x[1]))

    linhas = [
        "# Auditoria do glossário — textos traduzidos",
        "",
        f"- itens auditados: **{len(arquivos)}**",
        f"- itens com algum achado: **{itens_com_achado}**",
        f"- achados no total: **{len(todos)}**",
        "",
        "## Por camada",
        "",
        "| camada | achados |",
        "|---|---|",
    ]
    for k, v in por_camada.most_common():
        linhas.append(f"| {k} | {v} |")
    linhas += ["", "## Termos mais recorrentes (nº de ITENS afetados)", "",
               "| termo | itens |", "|---|---|"]
    for k, v in top[:60]:
        linhas.append(f"| `{k}` | {len(v)} |")
    (saida / "RELATORIO.md").write_text("\n".join(linhas) + "\n",
                                        encoding="utf-8")

    print(f"\nitens com achado: {itens_com_achado}/{len(arquivos)}")
    print(f"achados: {len(todos)}")
    for k, v in por_camada.most_common():
        print(f"   {k:16} {v}")
    print("\nTermos mais recorrentes (nº de itens):")
    for k, v in top[:30]:
        print(f"   {len(v):4}  {k}")
    print(f"\ngravado em: {saida}")

    if args.detalhar:
        print("\n--- achados ---")
        for a in todos[:200]:
            print(f"  [{a['camada']}] {a['termo']} :: {a['contexto'][:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
