#!/usr/bin/env python3
"""Gate fail-closed Gokōwa §4.4-B — conteúdo PT, não só contagem.

Bloqueia fecho/promoção quando:
- diálogo contém japonês residual (CJK);
- Δ Interlocutor ≠ 0 (modo strict, default);
- travessões — no corpo;
- turno A4B com >25% caracteres CJK (JP colado pelo rebuild).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from apply_gokowa_collection_layout import GOKOWA_ORDER  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from qa_dialogue_annotation import parse_qa_turns  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORK_PT = ROOT / "reports/livros_trabalho/pt"
WORK_JP = ROOT / "reports/livros_trabalho/jp"
PROD_PT = ROOT / "textos_portugues"
SEG = ROOT / "reports/livros_trabalho/segmentacao_manual"
QUEUE_PATH = SEG / "GOKOWA_GATE_QUEUE.json"

CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
DASH_LINE = re.compile(r"^\s*[—―–\-]\s+\S")
def _dialogue_paragraphs(body: str) -> list[tuple[str, str]]:
    """Parágrafos A4B (label + texto), ignorando metadados partidos."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    out: list[tuple[str, str]] = []
    meta_keys = ("entry_id:", "title_jp:", "title_pt:", "paired_id:", "source_file:", "sort_date:")
    for para in paras:
        if para.startswith("Interlocutor:"):
            text = para[len("Interlocutor:") :].strip()
            if any(text.startswith(k) for k in meta_keys):
                continue
            out.append(("Interlocutor", text))
        elif para.startswith("Meishu-Sama:"):
            text = para[len("Meishu-Sama:") :].strip()
            if any(text.startswith(k) for k in meta_keys):
                continue
            out.append(("Meishu-Sama", text))
    return out


@dataclass
class GateResult:
    file: str
    ok: bool
    errors: list[str]
    warnings: list[str]
    jp_interlocutor: int = 0
    pt_interlocutor: int = 0
    pt_meishu: int = 0
    delta_i: int = 0
    cjk_dialogue_lines: int = 0
    jp_turns_in_pt: int = 0
    dash_lines: int = 0


def _line_cjk_residual(line: str) -> bool:
    if not CJK_RE.search(line):
        return False
    stripped = re.sub(r"\([^)]*\)", "", line)
    stripped = re.sub(r'"[^"]*"', "", stripped)
    stripped = re.sub(r"'[^']*'", "", stripped)
    return bool(CJK_RE.search(stripped))


def _cjk_ratio(text: str) -> float:
    if not text.strip():
        return 0.0
    cjk = len(CJK_RE.findall(text))
    letters = len(re.findall(r"\w", text, flags=re.UNICODE))
    return cjk / max(letters, 1)


def _extract_body(pt_text: str) -> str:
    if "=== ARTIGO ===" in pt_text:
        _, blocks = split_file(pt_text)
        return "\n".join(parse_article(b).content for b in blocks)
    if "---" in pt_text:
        return pt_text.split("---", 1)[-1]
    return pt_text


def gate_content(filename: str, pt_text: str, jp_text: str, *, strict_delta: bool = True) -> GateResult:
    errors: list[str] = []
    warnings: list[str] = []
    body = _extract_body(pt_text)

    jp_body = _extract_body(jp_text) if jp_text else ""
    ji = (
        sum(1 for t in parse_qa_turns(jp_body, lang="jp", profile="gokowa_roku_qa") if t.kind == "interlocutor")
        if jp_body
        else 0
    )
    pi = body.count("Interlocutor:")
    pm = body.count("Meishu-Sama:")
    delta = pi - ji

    dash_lines = sum(1 for ln in body.splitlines() if DASH_LINE.match(ln))
    if dash_lines:
        errors.append(f"travessões no corpo: {dash_lines}")

    cjk_lines = 0
    jp_turns = 0
    for label, text in _dialogue_paragraphs(body):
        line = f"{label}: {text}"
        if _line_cjk_residual(line):
            cjk_lines += 1
            errors.append(f"CJK em {label}: {text[:80]}…")
        elif _cjk_ratio(text) > 0.25:
            jp_turns += 1
            errors.append(f"turno predominantemente JP ({label}, ratio={_cjk_ratio(text):.2f})")

    if strict_delta and delta != 0:
        errors.append(f"Δ Interlocutor={delta} (JP={ji} PT={pi}); exige Δ=0")
    elif abs(delta) > 2:
        errors.append(f"Δ Interlocutor={delta} fora de tolerância")

    if pm and pi and pm / pi < 0.85:
        warnings.append(f"M/I={pm/pi:.3f} < 0.85")

    prod = PROD_PT / filename
    if prod.is_file() and jp_turns + cjk_lines > 0:
        warnings.append("CJK presente; confirmar contra textos_portugues/")

    ok = len(errors) == 0
    return GateResult(
        file=filename,
        ok=ok,
        errors=errors[:20],
        warnings=warnings,
        jp_interlocutor=ji,
        pt_interlocutor=pi,
        pt_meishu=pm,
        delta_i=delta,
        cjk_dialogue_lines=cjk_lines,
        jp_turns_in_pt=jp_turns,
        dash_lines=dash_lines,
    )


def gate_file(path: Path, *, strict_delta: bool = True) -> GateResult:
    name = path.name
    jp_path = WORK_JP / name
    pt_text = path.read_text(encoding="utf-8")
    jp_text = jp_path.read_text(encoding="utf-8") if jp_path.is_file() else ""
    return gate_content(name, pt_text, jp_text, strict_delta=strict_delta)


def load_queue() -> dict:
    if QUEUE_PATH.is_file():
        return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    return {
        "at": None,
        "policy": "one_volume_per_chat; gate exit 0 before approved",
        "volumes": [{"file": fn, "status": "pending", "errors": []} for fn in GOKOWA_ORDER],
    }


def save_queue(data: dict) -> None:
    data["at"] = datetime.now(timezone.utc).isoformat()
    SEG.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def refresh_queue(results: list[GateResult]) -> None:
    q = load_queue()
    by_name = {r.file: r for r in results}
    for vol in q.get("volumes", []):
        fn = vol["file"]
        if fn not in by_name:
            continue
        r = by_name[fn]
        vol["status"] = "passed" if r.ok else "failed"
        vol["errors"] = r.errors[:5]
        vol["delta_i"] = r.delta_i
        vol["cjk_dialogue_lines"] = r.cjk_dialogue_lines
    # first failed = current work item
    q["current"] = next((v["file"] for v in q["volumes"] if v["status"] != "passed"), None)
    save_queue(q)


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate fail-closed Gokōwa linha a linha (conteúdo PT)")
    ap.add_argument("--file", help="Um ficheiro (basename)")
    ap.add_argument("--all", action="store_true", help="Todos os 20 Gokōwa")
    ap.add_argument("--refresh-queue", action="store_true", help="Actualizar GOKOWA_GATE_QUEUE.json")
    ap.add_argument("--relaxed-delta", action="store_true", help="Permitir |Δ|≤2 (legacy); default strict Δ=0")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    strict = not args.relaxed_delta
    paths: list[Path] = []
    if args.file:
        paths = [WORK_PT / args.file]
    elif args.all:
        paths = [WORK_PT / fn for fn in GOKOWA_ORDER]
    else:
        ap.error("use --file or --all")

    results = [gate_file(p, strict_delta=strict) for p in paths if p.is_file()]
    if args.refresh_queue:
        refresh_queue(results)

    if args.json:
        print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
    else:
        for r in results:
            mark = "PASS" if r.ok else "FAIL"
            print(f"{mark} {r.file}: I={r.pt_interlocutor}/{r.jp_interlocutor} Δ={r.delta_i} CJK={r.cjk_dialogue_lines}")
            for e in r.errors[:8]:
                print(f"  ! {e}")

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
