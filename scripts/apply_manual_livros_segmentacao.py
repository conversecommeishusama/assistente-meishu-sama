#!/usr/bin/env python3
"""Aplica segmentação manual JP-first a livros monolíticos.

Fronteiras definidas em reports/livros_trabalho/segmentacao_manual/<ficheiro>.json
(campo jp_anchor por artigo; pt_anchor após pareamento manual).

Não infere cortes — só valida ordem, cobertura e emite blocos === ARTIGO ===.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root  # noqa: E402
from fix_periodicos_work_headers import Article, format_article, parse_article, split_file  # noqa: E402

MANUAL_DIR_NAME = "segmentacao_manual"


@dataclass
class Boundary:
    kind: str
    title_jp: str
    jp_anchor: str
    pt_anchor: str = ""
    title_pt: str = ""
    pt_prefix: str = ""
    notes: str = ""

    @classmethod
    def from_article(cls, art: dict) -> "Boundary":
        """Constrói a partir de um dict de artigo do spec, ignorando campos
        extra do schema mais recente (segment_index, structural_chunk_id,
        topics, entities, etc.) que a reconciliação linha-a-linha não usa."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in art.items() if k in known})


def load_boundary_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_anchor(body: str, anchor: str, start: int, label: str) -> int:
    anchor = anchor.strip()
    if not anchor:
        raise ValueError(f"{label}: anchor vazio")
    pos = body.find(anchor, start)
    if pos < 0:
        first = anchor.strip().splitlines()[0]
        if "\n" in anchor.strip():
            raise ValueError(
                f"{label}: anchor multiline não encontrado a partir de {start}: {anchor[:80]!r}"
            )
        if len(first) >= 6:
            pos = body.find(first, start)
    if pos < 0:
        raise ValueError(f"{label}: anchor não encontrado: {anchor[:80]!r}")
    return pos


def split_by_anchors(body: str, anchors: list[str], *, label: str) -> list[str]:
    if not anchors:
        return [body.strip()] if body.strip() else []
    positions: list[int] = []
    cursor = 0
    for i, anc in enumerate(anchors):
        pos = _find_anchor(body, anc, cursor, f"{label}[{i + 1}]")
        if positions and pos < positions[-1]:
            raise ValueError(f"{label}: anchors fora de ordem no índice {i + 1}")
        positions.append(pos)
        cursor = pos + max(1, len(anc.strip().splitlines()[0]))
    chunks: list[str] = []
    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(body)
        chunks.append(body[pos:end].strip())
    return chunks


def build_multi(
    file_header: str,
    base_jp: Article,
    base_pt: Article,
    jp_chunks: list[str],
    pt_chunks: list[str],
    bounds: list[Boundary],
) -> tuple[str, str]:
    if len(jp_chunks) != len(pt_chunks) or len(jp_chunks) != len(bounds):
        raise ValueError(
            f"contagens: jp={len(jp_chunks)} pt={len(pt_chunks)} bounds={len(bounds)}"
        )
    base_id = base_jp.fields.get("entry_id", "acervo")
    paired = base_jp.fields.get("paired_id", "")
    sort_date = base_jp.fields.get("sort_date", "")
    source = base_jp.fields.get("source_file", "")

    jp_blocks = [file_header.rstrip()]
    pt_blocks = [file_header.rstrip()]

    for i, (b, jp_body, pt_body) in enumerate(zip(bounds, jp_chunks, pt_chunks, strict=True), start=1):
        seg_id = f"{base_id}__art{i:03d}"
        title_jp = b.title_jp or b.jp_anchor.splitlines()[0][:120]
        if b.title_pt and b.title_pt != title_jp:
            title_pt = b.title_pt
        elif len(bounds) > 1:
            suffix = title_jp.split(" — ")[-1][:60]
            title_pt = f"{base_pt.fields.get('title_pt', title_jp)} — {suffix}"
        else:
            title_pt = b.title_pt or base_pt.fields.get("title_pt", title_jp)
        if b.pt_prefix:
            pt_body = b.pt_prefix.rstrip() + "\n\n" + pt_body.lstrip()

        jp_fields = {**base_jp.fields, "entry_id": seg_id, "title_jp": title_jp}
        pt_fields = {
            **base_pt.fields,
            "entry_id": seg_id,
            "paired_id": paired,
            "source_file": source,
            "sort_date": sort_date,
            "title_jp": title_jp,
            "title_pt": title_pt,
        }
        jp_blocks.append(format_article(jp_fields, base_jp.meta if i == 1 else "", jp_body))
        pt_blocks.append(format_article(pt_fields, base_pt.meta if i == 1 else "", pt_body))

    return "\n".join(jp_blocks) + "\n", "\n".join(pt_blocks) + "\n"


def apply_file(spec_path: Path, work_dir: Path, *, dry_run: bool = False) -> dict:
    spec = load_boundary_file(spec_path)
    fn = spec["filename"]
    bounds = [Boundary.from_article(a) for a in spec["articles"]]
    if not bounds:
        raise ValueError(f"{fn}: lista articles vazia")

    jp_path = work_dir / "jp" / fn
    pt_path = work_dir / "pt" / fn
    jp_text = jp_path.read_text(encoding="utf-8")
    pt_text = pt_path.read_text(encoding="utf-8")
    jp_header, jp_blocks = split_file(jp_text)
    _, pt_blocks = split_file(pt_text)
    if len(jp_blocks) != 1 or len(pt_blocks) != 1:
        raise ValueError(f"{fn}: esperado 1 bloco monolítico (jp={len(jp_blocks)} pt={len(pt_blocks)})")

    jp_art = parse_article(jp_blocks[0])
    pt_art = parse_article(pt_blocks[0])

    jp_anchors = [b.jp_anchor for b in bounds]
    pt_anchors = [b.pt_anchor for b in bounds]
    if any(not a for a in pt_anchors):
        missing = [i + 1 for i, a in enumerate(pt_anchors) if not a.strip()]
        raise ValueError(f"{fn}: pt_anchor em falta nos artigos {missing}")

    jp_chunks = split_by_anchors(jp_art.content, jp_anchors, label="JP")
    pt_chunks = split_by_anchors(pt_art.content, pt_anchors, label="PT")

    out_jp, out_pt = build_multi(jp_header, jp_art, pt_art, jp_chunks, pt_chunks, bounds)

    result = {
        "filename": fn,
        "articles": len(bounds),
        "jp_chars": [len(c) for c in jp_chunks],
        "pt_chars": [len(c) for c in pt_chunks],
        "approved": spec.get("approved", False),
    }

    if not dry_run:
        jp_path.write_text(out_jp, encoding="utf-8")
        pt_path.write_text(out_pt, encoding="utf-8")
        spec["applied_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        spec["apply_result"] = result
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return result


def init_manifest(work_dir: Path, manual_dir: Path) -> None:
    jp_dir = work_dir / "jp"
    files = sorted(p.name for p in jp_dir.glob("*.txt"))
    manifest = {
        "method": "manual_jp_first",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": [],
    }
    for fn in files:
        spec_path = manual_dir / f"{fn}.json"
        status = "pending"
        if spec_path.is_file():
            spec = load_boundary_file(spec_path)
            if spec.get("approved"):
                status = "approved"
            elif spec.get("applied_at"):
                status = "applied"
            elif spec.get("articles"):
                has_pt = all(a.get("pt_anchor", "").strip() for a in spec["articles"])
                status = "pt_paired" if has_pt else "jp_marked"
        manifest["files"].append({"filename": fn, "status": status, "spec": str(spec_path.name)})
    (manual_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Aplica segmentação manual livros_acervo")
    p.add_argument("--file", help="Nome do ficheiro .txt")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--init-manifest", action="store_true", help="Regenera manifest.json")
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    manual_dir = wr / MANUAL_DIR_NAME
    manual_dir.mkdir(parents=True, exist_ok=True)

    if args.init_manifest:
        init_manifest(wr, manual_dir)
        print(manual_dir / "manifest.json")
        return 0

    if not args.file:
        p.error("--file é obrigatório (ou use --init-manifest)")

    spec_path = manual_dir / f"{args.file}.json"
    if not spec_path.is_file():
        print(f"Spec não encontrado: {spec_path}", file=sys.stderr)
        return 1
    if not load_boundary_file(spec_path).get("approved"):
        print(f"AVISO: {args.file} não está approved=true — use --dry-run ou aprove antes.", file=sys.stderr)
        if not args.dry_run:
            return 1

    result = apply_file(spec_path, wr, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
