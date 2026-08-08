#!/usr/bin/env python3
"""Aplica correcções MECÂNICAS e seguras a partir do alinhamento JP↔PT:

- Segmentos 1 JP <-> 1 PT com rótulo errado: corrige o rótulo (mesmo texto).
- Segmentos 1 JP <-> 2 PT (sobre-divisão de um único turno em dois
  parágrafos): funde os dois parágrafos PT num só, com o rótulo correcto do
  turno JP único. Não reordena nem edita texto, só remove a quebra de
  parágrafo espúria e corrige o rótulo.

NÃO toca em segmentos "MIX" (N turnos JP fundidos num só parágrafo PT) — esses
exigem localizar o ponto exacto de divisão no texto PT já traduzido, o que
fica para revisão dedicada (mesmo método usado no Suplemento e ficheiro nº1).

Reescreve o corpo de diálogo preservando texto integral; título/data sem
rótulo mantidos como estão.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root, article_sep  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from align_gokowa_jp_pt import load_jp_turns, load_pt_paras, align, _split_paragraphs  # noqa: E402

WORK = work_root("livros_acervo")
ARTICLE_SEP = article_sep()
KIND_LABEL = {"interlocutor": "Interlocutor", "meishu": "Meishu-Sama"}


def process_file(filename: str, *, dry_run: bool = False) -> dict:
    jp = load_jp_turns(filename)
    pt = load_pt_paras(filename)
    path = align(jp, pt)

    pt_path = WORK / "pt" / filename
    pt_raw = pt_path.read_text(encoding="utf-8")
    file_pre, pt_blocks = split_file(pt_raw)
    if len(pt_blocks) != 1:
        raise SystemExit(f"{filename}: esperado 1 bloco de artigo, encontrados {len(pt_blocks)}")
    pt_art = parse_article(pt_blocks[0])
    body = pt_art.content
    all_paras = _split_paragraphs(body)
    # localizar índices dos parágrafos de diálogo dentro de all_paras
    dialog_idx = [i for i, p in enumerate(all_paras) if p.startswith("Interlocutor:") or p.startswith("Meishu-Sama:")]

    fixed_relabel = 0
    fixed_merge = 0
    skipped_mix = 0

    # novo corpo: percorre all_paras; quando encontra um bloco de diálogo
    # correspondente a um segmento MIX de fusão, funde-o.
    new_dialog_paras: list[str] = []
    for seg in path:
        j0, j1 = seg["jp_range"]
        p0, p1 = seg["pt_range"]
        n_jp = j1 - j0
        n_pt = p1 - p0
        texts = [pt[k].text for k in range(p0, p1)]
        kinds = [jp[k].kind for k in range(j0, j1)]

        if n_jp == 1 and n_pt == 1:
            expect = KIND_LABEL[kinds[0]]
            cur_label = pt[p0].label
            if (cur_label == "I") != (kinds[0] == "interlocutor"):
                fixed_relabel += 1
            new_dialog_paras.append(f"{expect}: {texts[0]}")
        elif n_jp == 1 and n_pt > 1:
            expect = KIND_LABEL[kinds[0]]
            merged = " ".join(t.strip() for t in texts)
            new_dialog_paras.append(f"{expect}: {merged}")
            fixed_merge += 1
        else:
            # MIX (N JP -> 1 PT) ou outra combinação: preserva parágrafo(s)
            # original(is) sem alteração, com o(s) rótulo(s) original(is),
            # para revisão dedicada.
            for k in range(p0, p1):
                new_dialog_paras.append(f"{'Interlocutor' if pt[k].label=='I' else 'Meishu-Sama'}: {pt[k].text}")
            skipped_mix += 1

    # reconstruir corpo: substitui a sequência de parágrafos de diálogo
    # pelos novos, mantendo título/data (parágrafos não-diálogo) nas mesmas
    # posições relativas antes do primeiro turno.
    non_dialog_prefix = [p for i, p in enumerate(all_paras) if i not in dialog_idx and i < dialog_idx[0]]
    new_body = "\n\n".join(non_dialog_prefix + new_dialog_paras)

    pre = [f"{k}: {v}" for k, v in pt_art.fields.items()] + ["---"]
    block = "\n".join(pre)
    if pt_art.meta:
        block += "\n" + pt_art.meta + "\n\n"
    else:
        block += "\n\n"
    block += new_body.strip() + "\n"

    out = file_pre.rstrip() + f"\n{ARTICLE_SEP}\n" + block

    if not dry_run:
        pt_path.write_text(out, encoding="utf-8")

    return {
        "file": filename,
        "relabeled": fixed_relabel,
        "merged_phantom_splits": fixed_merge,
        "skipped_mix_segments": skipped_mix,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for fn in args.file:
        r = process_file(fn, dry_run=args.dry_run)
        print(f"{'[dry-run] ' if args.dry_run else ''}{r['file']}: "
              f"relabel={r['relabeled']} merge_phantom={r['merged_phantom_splits']} "
              f"skip_mix={r['skipped_mix_segments']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
