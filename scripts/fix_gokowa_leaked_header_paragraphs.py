#!/usr/bin/env python3
"""Remove parágrafos de CABEÇALHO/METADADOS vazados para o corpo de diálogo,
rotulados erradamente como Interlocutor:/Meishu-Sama: no início dos ficheiros
Gokōwa-roku. Achado sistémico (não pontual): pipelines anteriores de
conversão/relabel deixaram, no topo de vários ficheiros, entre 1 e 4
parágrafos repetindo o título da edição (por vezes em formas diferentes:
"Gokōwa-roku nº N...", "Registro de Luz...", "Goshinsho nº N...",
"title_pt: ...", "Title: ...", uma linha solta "-") em vez de apenas UM
título limpo antes da primeira pergunta/resposta real.

Isto NÃO é o mesmo bug do fix_gokowa_header_label_corruption.py (que tratava
de linhas de metadados do cabeçalho oficial ---); aqui trata-se de
parágrafos inteiros de TÍTULO/METADADO que vazaram para dentro do CORPO,
consumindo posições de diálogo e distorcendo a contagem Δ Interlocutor —
em alguns casos compensando-se por coincidência e produzindo Δ=0 mesmo
com conteúdo corrompido (achado confirmado em ficheiro nº3).

Estratégia: detectar, a partir do início do corpo, uma sequência de
parágrafos que correspondam a padrões de título/metadado (curtos e sem
marcador de pergunta real), removê-los, e substituir por UMA única linha de
título limpa (usando o title_pt do spec de segmentação), preservando todo o
resto do corpo intacto.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root, article_sep  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from align_gokowa_jp_pt import _split_paragraphs  # noqa: E402

WORK = work_root("livros_acervo")
SPEC_DIR = Path("reports/livros_trabalho/segmentacao_manual")

TITLE_PAT = re.compile(r"Gok[oō]wa-roku|Registro de Luz|Goshinsho\s*n[ºo°]|Gosuiji-roku")
META_LEAK_PAT = re.compile(r"^(title_pt|title_jp|Title|Publication source|Date|Language|Collection ID)\s*:", re.I)
MAX_HEADER_LEN = 150


def _is_leaked_header_para(text: str) -> bool:
    stripped = text.strip()
    if stripped == "-":
        return True
    if META_LEAK_PAT.match(stripped):
        return True
    if TITLE_PAT.search(stripped) and len(stripped) < MAX_HEADER_LEN:
        return True
    return False


def _strip_label(para: str) -> tuple[str, str]:
    if para.startswith("Interlocutor:"):
        return "I", para[len("Interlocutor:"):].strip()
    if para.startswith("Meishu-Sama:"):
        return "M", para[len("Meishu-Sama:"):].strip()
    return "", para.strip()


def process_file(filename: str, *, dry_run: bool = False) -> dict:
    spec_path = SPEC_DIR / f"{filename}.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path.is_file() else {}

    pt_path = WORK / "pt" / filename
    raw = pt_path.read_text(encoding="utf-8")
    file_pre, blocks = split_file(raw)
    if len(blocks) != 1:
        return {"file": filename, "status": "skip_multi_block"}
    art = parse_article(blocks[0])
    body = art.content
    paras = _split_paragraphs(body)

    removed = []
    i = 0
    while i < len(paras) and i < 10:
        _label, text = _strip_label(paras[i])
        if _is_leaked_header_para(text):
            removed.append(paras[i])
            i += 1
            continue
        break

    if not removed:
        return {"file": filename, "status": "no_leak", "removed": 0}

    if len(removed) == 1:
        # única linha de título, sem duplicação — não há nada a consolidar;
        # não arriscar substituí-la por uma fonte de título menos fiável.
        return {"file": filename, "status": "single_no_dup", "removed": 0}

    # título canónico: preferir o campo "Title" do próprio cabeçalho ---
    # do ficheiro (fonte mais fiável que o spec, que pode não ter title_pt).
    title_pt = art.fields.get("Title") or spec.get("title_pt") or _strip_label(removed[0])[1]

    new_paras = paras[i:]
    new_body = title_pt + "\n\n" + "\n\n".join(new_paras)

    pre = [f"{k}: {v}" for k, v in art.fields.items()] + ["---"]
    block = "\n".join(pre)
    if art.meta:
        block += "\n" + art.meta + "\n\n"
    else:
        block += "\n\n"
    block += new_body.strip() + "\n"
    out = file_pre.rstrip() + f"\n{article_sep()}\n" + block

    if not dry_run:
        pt_path.write_text(out, encoding="utf-8")

    return {"file": filename, "status": "fixed", "removed": len(removed), "removed_preview": [r[:60] for r in removed]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append")
    ap.add_argument("--all-gokowa", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = args.file or []
    if args.all_gokowa:
        import glob

        files = sorted(
            Path(f).name.replace(".json", "")
            for f in glob.glob(str(SPEC_DIR / "*御光話録*.txt.json"))
        )
    for fn in files:
        r = process_file(fn, dry_run=args.dry_run)
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
