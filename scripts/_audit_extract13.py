#!/usr/bin/env python3
"""Extrai JP+PT de 13 artigos específicos para auditoria manual (só leitura)."""
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
from apply_manual_livros_segmentacao import Boundary, split_by_anchors  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402

TARGETS = [
    ("19480101-御光話録（補）", 31),
    ("19490710-御光話録10号", 3),
    ("19491025-自観叢書第7篇『基仏と観音教』", 10),
    ("19500921-地上天国出来るまで", 0),
    ("19510810-或る日の公判スケッチ", 1),
    ("19511215-御教え集4号", 5),
    ("19520615-御垂示録10号", 0),
    ("19521115-御垂示録15号", 0),
    ("19530315-御垂示録18号", 1),
    ("19530615-御教え集22号", 2),
    ("19531001-浄霊法講座（二）『浄霊法講座』2号", 8),
    ("19540315-御教え集31号", 6),
    ("19550615-浄 霊法講座（九）（頭　部）  『浄霊法講座』9号", 18),
]

SPEC_DIR = Path("reports/livros_trabalho/segmentacao_manual")
JP_DIR = Path("reports/livros_trabalho/jp")
PT_DIR = Path("livros_publicacao_pt_revisado")
OUT_DIR = Path("/tmp/claude-0/-var-www-goshinsho/cc3c4724-3e2b-4393-a540-2bff425f3372/scratchpad/audit13")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def find_spec(stem: str) -> Path:
    exact = SPEC_DIR / f"{stem}.txt.json"
    if exact.is_file():
        return exact
    matches = [
        p for p in glob.glob(str(SPEC_DIR / "*.txt.json"))
        if stem.replace(" ", "").replace("　", "") in Path(p).name.replace(" ", "").replace("　", "").replace("\xa0", "")
    ]
    if len(matches) == 1:
        return Path(matches[0])
    raise FileNotFoundError(f"spec não encontrado para {stem!r}: {matches}")


def find_text(dir_: Path, stem: str) -> Path:
    exact = dir_ / f"{stem}.txt"
    if exact.is_file():
        return exact
    matches = [
        p for p in glob.glob(str(dir_ / "*.txt"))
        if stem.replace(" ", "").replace("　", "") in Path(p).name.replace(" ", "").replace("　", "").replace("\xa0", "")
        and not Path(p).name.endswith((".bak", ".json"))
        and ".bak" not in Path(p).name
    ]
    if len(matches) == 1:
        return Path(matches[0])
    raise FileNotFoundError(f"texto não encontrado para {stem!r} em {dir_}: {matches}")


def main():
    index_lines = []
    for stem, idx in TARGETS:
        spec_path = find_spec(stem)
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        bounds = [Boundary.from_article(a) for a in spec["articles"]]
        jp_path = find_text(JP_DIR, stem)
        pt_path = find_text(PT_DIR, stem)
        jp_text = jp_path.read_text(encoding="utf-8")
        pt_text = pt_path.read_text(encoding="utf-8")
        jp_header, jp_blocks = split_file(jp_text)
        pt_header, pt_blocks = split_file(pt_text)

        # JP working files carry the "=== ARTIGO ===" header; use its content.
        if len(jp_blocks) == 1:
            jp_body_full = parse_article(jp_blocks[0]).content
        elif len(jp_blocks) > 1:
            jp_body_full = None  # already segmented, handled below
        else:
            jp_body_full = jp_text

        # Published PT files are plain clean text with NO "=== ARTIGO ===" header.
        if len(pt_blocks) == 1:
            pt_body_full = parse_article(pt_blocks[0]).content
        elif len(pt_blocks) > 1:
            pt_body_full = None
        else:
            pt_body_full = pt_text

        if jp_body_full is not None and pt_body_full is not None:
            jp_anchors = [b.jp_anchor for b in bounds]
            pt_anchors = [b.pt_anchor for b in bounds]
            jp_chunks = split_by_anchors(jp_body_full, jp_anchors, label="JP")
            pt_chunks = split_by_anchors(pt_body_full, pt_anchors, label="PT")
            n = len(bounds)
            if idx >= n:
                raise IndexError(f"{stem}: idx {idx} >= {n} artigos")
            jp_body = jp_chunks[idx]
            pt_body = pt_chunks[idx]
        else:
            # already segmented into individual === ARTIGO === blocks
            if idx >= len(jp_blocks) or idx >= len(pt_blocks):
                raise IndexError(f"{stem}: idx {idx} fora de alcance (jp={len(jp_blocks)} pt={len(pt_blocks)})")
            jp_art = parse_article(jp_blocks[idx])
            pt_art = parse_article(pt_blocks[idx])
            jp_body = jp_art.content
            pt_body = pt_art.content

        b = bounds[idx]
        out_name = f"{stem}__idx{idx}.txt".replace("/", "_")
        out_path = OUT_DIR / out_name
        with out_path.open("w", encoding="utf-8") as f:
            f.write(f"ARQUIVO: {stem}\n")
            f.write(f"INDICE: {idx}\n")
            f.write(f"title_jp (spec): {b.title_jp}\n")
            f.write(f"title_pt (spec): {b.title_pt}\n")
            f.write(f"jp_anchor: {b.jp_anchor[:200]}\n")
            f.write(f"pt_anchor: {b.pt_anchor[:200]}\n")
            f.write("\n=== JP ===\n")
            f.write(jp_body)
            f.write("\n\n=== PT ===\n")
            f.write(pt_body)
        print(f"OK  {stem} idx={idx} -> {out_path}  (jp_len={len(jp_body)} pt_len={len(pt_body)})")
        index_lines.append(str(out_path))

    (OUT_DIR / "_INDEX.txt").write_text("\n".join(index_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
