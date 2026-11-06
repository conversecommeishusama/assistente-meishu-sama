#!/usr/bin/env python3
"""Adequação estrutural dos Mioshie-shū 1-8 (base JP).

O que faz:
1. Copia os arquivos consolidados novos (retraduzidos) de
   revisao_literaria/orais/ para o staging reports/livros_trabalho/pt/.
2. Reconcilias as `pt_anchor` das specs de segmentação com o texto novo,
   mantendo as `jp_anchor` (base JP) e a estrutura de sessões (title_pt/title_jp).
3. Valida cada spec com `split_by_anchors` (função de produção) nos dois lados.

Uso:
  .venv/bin/python scripts/adequacao_estrutural_mioshie.py [--dry-run]
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

SPEC_DIR = RAIZ / "reports" / "livros_trabalho" / "segmentacao_manual"
PT_STAGING = RAIZ / "reports" / "livros_trabalho" / "pt"
ORAIS = RAIZ / "revisao_literaria" / "orais"

# Mapa: nº edição -> arquivos (consolidado, spec)
NUMEROS = {
    1: "19510920", 2: "19511025", 3: "19511125", 4: "19511215",
    5: "19520115", 6: "19510225", 7: "19520320", 8: "19520420",
}


def achar_spec(n: int) -> Path | None:
    cands = list(SPEC_DIR.glob(f"*Mioshie-shū nº {n}.txt.json"))
    return cands[0] if cands else None


def achar_consolidado(n: int) -> Path | None:
    cands = list(ORAIS.glob(f"*Mioshie-shū nº {n}.txt"))
    return cands[0] if cands else None


def nova_pt_anchor(pt: str, jp_anchor: str, title_jp: str, kind: str) -> str:
    """Gera a nova pt_anchor com base no texto consolidado novo.

    Estratégia (determinística, base JP):
    - Para `preface`: usa o início do arquivo (primeira linha não vazia).
    - Para `session`: encontra a data da sessão (title_jp é a data japonesa)
      no texto PT — a data traduzida precede o primeiro turno da sessão.
      A âncora = "Interlocutor:" seguido do início do turno, ou a linha da
      data traduzida + próximo turno.
    """
    linhas = [l for l in pt.splitlines() if l.strip()]
    if kind == "preface" or not linhas:
        return linhas[0][:60] if linhas else ""

    # Converte a data JP do título para encontrar a linha de data no PT.
    # O consolidado tem linhas como "[1º de agosto]" ou "1 de agosto".
    jp_data = (title_jp or "").strip()
    # A data PT correspondente: procuramos uma linha que comece com data
    # (padrão "[Nº de mês]" ou "N de mês" ou "Nº de mês de YYYY").
    alvo = None
    for i, l in enumerate(linhas):
        if re.match(r"^(\[)?\d{1,2}(º)? de ", l):
            alvo = i
            # primeira data que aparece DEPOIS da âncora anterior já está
            # correta pois processamos em ordem; usamos a primeira data
            break
    if alvo is None:
        # fallback: usa o primeiro "Interlocutor:" após a metade? Não —
        # usa o primeiro turno do arquivo (conservador).
        for i, l in enumerate(linhas):
            if l.startswith("Interlocutor:"):
                return l[:80]
        return linhas[0][:80]
    # a data está em `alvo`; o turno da sessão é a próxima linha "Interlocutor:"
    for j in range(alvo, min(alvo + 6, len(linhas))):
        if linhas[j].startswith("Interlocutor:"):
            return linhas[j][:80]
    return linhas[alvo][:80]


def reconciliar_spec(spec_path: Path, pt_text: str, dry: bool) -> dict:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    arts = spec.get("articles", [])
    mudancas = 0
    for a in arts:
        # base JP inalterada
        jp_anchor = (a.get("jp_anchor") or "").strip()
        kind = a.get("kind") or ("preface" if a.get("title_pt") == "Prefácio" else "session")
        nova = nova_pt_anchor(pt_text, jp_anchor, a.get("title_jp", ""), kind)
        antiga = (a.get("pt_anchor") or "").strip()
        if nova and nova != antiga:
            a["pt_anchor"] = nova
            mudancas += 1
    if not dry and mudancas:
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"arquivo": spec_path.name, "artigos": len(arts), "mudancas": mudancas}


def validar_spec(spec_path: Path, pt_path: Path) -> bool:
    """Valida a spec com split_by_anchors (função de produção)."""
    try:
        from apply_manual_livros_segmentacao import load_boundary_file, Boundary, split_by_anchors, split_file, parse_article
        from acervo_work_paths import work_root
    except Exception as e:  # noqa: BLE001
        print(f"    [validar] import falhou: {e}", file=sys.stderr)
        return False
    try:
        spec = load_boundary_file(spec_path)
        fn = spec["filename"]
        bounds = [Boundary.from_article(a) for a in spec["articles"]]
        if not bounds:
            return False
        pt_text = pt_path.read_text(encoding="utf-8")
        # usa split_by_anchors diretamente no texto PT
        pt_anchors = [b.pt_anchor for b in bounds]
        if any(not a.strip() for a in pt_anchors):
            return False
        chunks = split_by_anchors(pt_text, pt_anchors, label="PT")
        return len(chunks) == len(bounds)
    except Exception as e:  # noqa: BLE001
        print(f"    [validar] {spec_path.name}: {e}", file=sys.stderr)
        return False


def main() -> int:
    dry = "--dry-run" in sys.argv
    print("=== Adequação estrutural Mioshie 1-8 ===" + (" (DRY-RUN)" if dry else ""))
    ok = 0
    for n in range(1, 9):
        spec_p = achar_spec(n)
        cons = achar_consolidado(n)
        if not spec_p or not cons:
            print(f"  nº {n}: faltando spec ou consolidado")
            continue
        pt_text = cons.read_text(encoding="utf-8")
        # 1. copia para staging (se não dry)
        dest = PT_STAGING / cons.name
        if not dry:
            shutil.copy2(cons, dest)
        # 2. reconcilia pt_anchor
        r = reconciliar_spec(spec_p, pt_text, dry)
        # 3. valida
        valido = validar_spec(spec_p, cons)
        status = "OK" if valido else "FALHA"
        if valido:
            ok += 1
        print(f"  nº {n}: {len(pt_text)} chars | {r['mudancas']} pt_anchor atualizadas | validação: {status}")
    print(f"\nResultado: {ok}/8 specs válidas" + (" (dry-run)" if dry else ""))
    return 0 if ok == 8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
