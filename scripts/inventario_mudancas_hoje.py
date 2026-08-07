"""Inventaria TODA mudança feita hoje no corpus português.

Determinação do usuário (2026-08-08): verificar semanticamente tudo o que foi
feito hoje, sem exceção, e dimensionar o problema corretamente antes de
decidir o que fazer.

Compara `livros_publicacao_pt_revisado/` (atual) contra `textos_portugues/`
(promovido em 06/08, não tocado hoje -- é o estado íntegro de referência).

Não presume quais termos mudaram: pega toda diferença de parágrafo, para que
mudança que eu não lembre ou não tenha percebido também apareça.

Saída: reports/varredura_padronizacao/INVENTARIO_HOJE.json
       um registro por trecho alterado, com o artigo a que pertence, o texto
       antes e depois, e o japonês correspondente -- pronto para a leitura.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

ATUAL = RAIZ / "livros_publicacao_pt_revisado"
LIMPO = RAIZ / "textos_portugues"
JP_DIR = RAIZ / "reports/livros_trabalho/jp"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
SAIDA = RAIZ / "reports/varredura_padronizacao/INVENTARIO_HOJE.json"


def artigos(caminho: Path, campo: str, obra: str) -> list[str]:
    spec_path = SPEC_DIR / f"{obra}.json"
    if not spec_path.exists() or not caminho.exists():
        return []
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    texto = clean_body(caminho.read_text(encoding="utf-8", errors="replace"))
    arts = spec.get("articles", [])
    anc = [a.get(campo, "") for a in arts]
    if len(arts) <= 1 or not all(anc):
        return [texto]
    try:
        pedacos = split_by_anchors(texto, anc, label=obra)
    except ValueError:
        return [texto]
    return pedacos if len(pedacos) == len(arts) else [texto]


def artigo_do_trecho(trecho: str, arts: list[str]) -> int:
    """Em que artigo cai este trecho? Usa uma âncora textual curta."""
    chave = re.sub(r"\s+", " ", trecho).strip()[:60]
    if len(chave) < 15:
        return -1
    for i, a in enumerate(arts):
        if chave in re.sub(r"\s+", " ", a):
            return i
    return -1


def main() -> None:
    registros = []
    resumo = Counter()
    for p in sorted(ATUAL.glob("*.txt")):
        obra = p.name
        lp = LIMPO / obra
        if not lp.exists():
            continue
        atual = p.read_text(encoding="utf-8")
        limpo = lp.read_text(encoding="utf-8", errors="replace")
        if atual == limpo:
            continue

        la = [x for x in limpo.split("\n\n")]
        lb = [x for x in atual.split("\n\n")]
        sm = difflib.SequenceMatcher(None, la, lb, autojunk=False)
        mudancas = [(i1, i2, j1, j2) for tag, i1, i2, j1, j2 in sm.get_opcodes()
                    if tag in ("replace", "insert", "delete")]
        if not mudancas:
            continue

        arts_pt = artigos(p, "pt_anchor", obra)
        arts_jp = artigos(JP_DIR / obra, "jp_anchor", obra)
        resumo[obra] = len(mudancas)

        for i1, i2, j1, j2 in mudancas:
            antes = "\n\n".join(la[i1:i2]).strip()
            depois = "\n\n".join(lb[j1:j2]).strip()
            if antes == depois:
                continue
            idx = artigo_do_trecho(depois or antes, arts_pt)
            registros.append({
                "obra": obra, "artigo": idx,
                "antes": antes[:2500], "depois": depois[:2500],
                "jp": (arts_jp[idx][:3000] if 0 <= idx < len(arts_jp) else ""),
            })

    SAIDA.write_text(json.dumps(registros, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(registros)} trechos alterados em {len(resumo)} obras")
    for obra, n in resumo.most_common(14):
        print(f"  {n:>5}  {obra[:58]}")
    sem_artigo = sum(1 for r in registros if r["artigo"] < 0)
    sem_jp = sum(1 for r in registros if not r["jp"])
    print(f"\n{sem_artigo} trechos sem artigo identificado, {sem_jp} sem japonês pareado")
    print(f"saída em {SAIDA}")


if __name__ == "__main__":
    main()
