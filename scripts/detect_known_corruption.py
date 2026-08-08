#!/usr/bin/env python3
"""Detector de corrupção conhecida — Fase 1 (varredura, não corrige nada).

Varre reports/livros_trabalho/pt/*.txt (e periodicos_trabalho/pt/ se existir)
à procura de dois padrões reais encontrados em 2026-07-03:

1. Travessão embutido a meio de parágrafo já rotulado Interlocutor:/Meishu-Sama:
   — marca um turno que devia ter sido separado e não foi (achado em
   19480101-御光話録（補）.txt: 47 ocorrências). O gate (gate_gokowa_linha.py)
   só deteta travessão no INÍCIO da linha, não embutido — este detector cobre
   esse ponto cego.
2. Ficheiro de trabalho PT muito maior que a fonte de produção equivalente em
   textos_portugues/ (achado em 19490208-御光話録3号.txt: 377 KB de trabalho vs
   46 KB em produção — sintoma de retradução repetida sem convergir, inflando
   o ficheiro a cada tentativa).

Não corrige nada — só reporta. Ver reports/livros_trabalho/segmentacao_manual/
CORRUPTION_SCAN.json para o resultado.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORK_PT = ROOT / "reports/livros_trabalho/pt"
PROD_PT = ROOT / "textos_portugues"

DASH_RE = re.compile(r"[—―–]")
INLINE_DASH_RE = re.compile(r"\S\s*[—―–]\s*\S")

# Ficheiros claramente maiores que a produção por razão legítima (ex.: A4B
# acrescenta rótulos "Interlocutor:"/"Meishu-Sama:" a cada turno, o que por
# si só já infla ~15-25% sobre um dash-format puro). Só sinalizar acima disto.
SIZE_RATIO_WARN = 1.6
SIZE_RATIO_SEVERE = 3.0


def _extract_body(text: str) -> str:
    if "=== ARTIGO ===" in text:
        _, blocks = split_file(text)
        return "\n".join(parse_article(b).content for b in blocks)
    if "---" in text:
        return text.split("---", 1)[-1]
    return text


@dataclass
class FileFinding:
    filename: str
    inline_dash_count: int
    inline_dash_paragraphs: int
    work_size: int
    prod_size: int | None
    size_ratio: float | None
    severity: str
    notes: list[str]


def scan_inline_dashes(body: str) -> tuple[int, int]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    total = 0
    paras_hit = 0
    for para in paras:
        if not (para.startswith("Interlocutor:") or para.startswith("Meishu-Sama:")):
            continue
        n = len(INLINE_DASH_RE.findall(para))
        if n:
            total += n
            paras_hit += 1
    return total, paras_hit


def scan_file(pt_path: Path) -> FileFinding:
    name = pt_path.name
    text = pt_path.read_text(encoding="utf-8", errors="replace")
    body = _extract_body(text)
    dash_count, dash_paras = scan_inline_dashes(body)

    work_size = pt_path.stat().st_size
    prod_path = PROD_PT / name
    prod_size = prod_path.stat().st_size if prod_path.is_file() else None
    ratio = (work_size / prod_size) if prod_size else None

    notes: list[str] = []
    severity = "ok"
    if dash_count:
        severity = "warn"
        notes.append(f"{dash_count} travessão(ões) embutido(s) em {dash_paras} parágrafo(s) já rotulado(s)")
    if ratio is not None and ratio >= SIZE_RATIO_SEVERE:
        severity = "severe"
        notes.append(f"ficheiro de trabalho {ratio:.1f}x maior que produção — possível inflação por retradução repetida")
    elif ratio is not None and ratio >= SIZE_RATIO_WARN:
        if severity == "ok":
            severity = "warn"
        notes.append(f"ficheiro de trabalho {ratio:.1f}x maior que produção — confirmar se é conteúdo genuíno")

    return FileFinding(
        filename=name,
        inline_dash_count=dash_count,
        inline_dash_paragraphs=dash_paras,
        work_size=work_size,
        prod_size=prod_size,
        size_ratio=round(ratio, 2) if ratio is not None else None,
        severity=severity,
        notes=notes,
    )


def main() -> int:
    files = sorted(WORK_PT.glob("*.txt"))
    results = [scan_file(p) for p in files]
    severe = [r for r in results if r.severity == "severe"]
    warn = [r for r in results if r.severity == "warn"]

    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_files": len(results),
        "severe_count": len(severe),
        "warn_count": len(warn),
        "findings": [asdict(r) for r in results if r.severity != "ok"],
    }
    out_path = ROOT / "reports/livros_trabalho/segmentacao_manual/CORRUPTION_SCAN.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{len(results)} ficheiros varridos; {len(severe)} severe, {len(warn)} warn")
    for r in severe:
        print(f"SEVERE {r.filename}: {'; '.join(r.notes)}")
    for r in warn:
        print(f"warn   {r.filename}: {'; '.join(r.notes)}")
    print(f"Relatório: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
