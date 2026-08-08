#!/usr/bin/env python3
"""Pipeline lote Gokōwa-roku: layout §4.4 + alinhamento JP + §4.4-B + spec + gate."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root, article_sep  # noqa: E402
from apply_gokowa_collection_layout import GOKOWA_ORDER, process_file as apply_layout  # noqa: E402
from convert_gokowa_dialogue_a4b import convert_file as convert_a4b  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from qa_dialogue_annotation import parse_qa_turns  # noqa: E402
from rebuild_gokowa_pt_inline import rebuild  # noqa: E402

WORK = work_root("livros_acervo")
SEG = WORK / "segmentacao_manual"
ARTICLE_SEP = article_sep()
PER = Path("reports/periodicos_trabalho/pt")
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
SESSION_PT_RE = re.compile(
    r"^(\[\d{1,2} de [^\]]+\]|\*\*\d{1,2}.+\*\*|\d{1,2}(?:º)? de .+)$",
    re.I,
)

# 11号: snapshot P2 contamina JP; periodicos é fonte limpa
PERIODICOS_ONLY = {"19490821-御光話録11号.txt"}


def _jp_q_count(jp_text: str) -> int:
    _, blocks = split_file(jp_text)
    body = "\n".join(parse_article(b).content for b in blocks)
    turns = parse_qa_turns(body, lang="jp", profile="gokowa_roku_qa")
    return sum(1 for t in turns if t.kind == "interlocutor")


def _line_has_residual_cjk(line: str) -> bool:
    """CJK intencional (glossário entre parênteses ou caractere citado entre aspas) não conta."""
    if not CJK_RE.search(line):
        return False
    stripped = re.sub(r"\([^)]*\)", "", line)
    stripped = re.sub(r'"[^"]*"', "", stripped)
    stripped = re.sub(r"'[^']*'", "", stripped)
    return bool(CJK_RE.search(stripped))


def _body_cjk_lines(text: str) -> int:
    body = text.split("---", 1)[-1] if "---" in text else text
    return sum(1 for ln in body.splitlines() if _line_has_residual_cjk(ln))


def _pt_i_count(pt_text: str) -> int:
    return sum(1 for ln in pt_text.splitlines() if ln.startswith("Interlocutor:"))


def _parse_a4b_body(body: str) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    kind = None
    buf: list[str] = []
    for ln in body.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith("Interlocutor:"):
            if kind and buf:
                turns.append((kind, " ".join(buf).strip()))
            kind = "interlocutor"
            buf = [s[len("Interlocutor:") :].strip()]
        elif s.startswith("Meishu-Sama:"):
            if kind and buf:
                turns.append((kind, " ".join(buf).strip()))
            kind = "meishu"
            buf = [s[len("Meishu-Sama:") :].strip()]
        elif kind:
            buf.append(s)
    if kind and buf:
        turns.append((kind, " ".join(buf).strip()))
    return turns


def _trim_to_jp_pairs(pt_path: Path, jpq: int) -> int:
    """Reduz pares Q/A PT ao número de perguntas JP (funde excesso no último Meishu)."""
    raw = pt_path.read_text(encoding="utf-8")
    if ARTICLE_SEP not in raw:
        parts = raw.split("---", 1)
        if len(parts) < 2:
            return 0
        head, body = parts[0] + "---", parts[1]
    else:
        pre, blocks = split_file(raw)
        new_blocks = []
        total_trimmed = 0
        for block in blocks:
            art = parse_article(block)
            turns = _parse_a4b_body(art.content)
            pairs: list[tuple[str, str]] = []
            q, a = "", ""
            for kind, text in turns:
                if kind == "interlocutor":
                    if q:
                        pairs.append((q, a))
                    q, a = text, ""
                else:
                    a = (a + " " + text).strip() if a else text
            if q:
                pairs.append((q, a))
            if len(pairs) <= jpq:
                new_blocks.append(block)
                continue
            kept = pairs[:jpq]
            extra = pairs[jpq:]
            merge = " ".join(a for _, a in extra if a).strip()
            if merge and kept:
                q0, a0 = kept[-1]
                kept[-1] = (q0, (a0 + " " + merge).strip())
            out_lines: list[str] = []
            for qq, aa in kept:
                out_lines.append(f"Interlocutor: {qq}\n\nMeishu-Sama: {aa}\n")
            pre_lines = [f"{k}: {v}" for k, v in art.fields.items()] + ["---"]
            blk = "\n".join(pre_lines)
            if art.meta:
                blk += "\n" + art.meta + "\n\n"
            else:
                blk += "\n\n"
            blk += "\n".join(out_lines).strip() + "\n"
            new_blocks.append(blk)
            total_trimmed += len(pairs) - jpq
        out = pre.rstrip() + f"\n{ARTICLE_SEP}\n" + f"\n{ARTICLE_SEP}\n".join(new_blocks)
        pt_path.write_text(out, encoding="utf-8")
        return total_trimmed

    turns = _parse_a4b_body(body)
    pairs: list[tuple[str, str]] = []
    q, a = "", ""
    for kind, text in turns:
        if kind == "interlocutor":
            if q:
                pairs.append((q, a))
            q, a = text, ""
        else:
            a = (a + " " + text).strip() if a else text
    if q:
        pairs.append((q, a))
    if len(pairs) <= jpq:
        return 0
    kept = pairs[:jpq]
    extra = pairs[jpq:]
    merge = " ".join(a for _, a in extra if a).strip()
    if merge and kept:
        q0, a0 = kept[-1]
        kept[-1] = (q0, (a0 + " " + merge).strip())
    prose_before = body.split("Interlocutor:")[0].strip()
    out_body = prose_before + "\n\n" if prose_before else ""
    for qq, aa in kept:
        out_body += f"Interlocutor: {qq}\n\nMeishu-Sama: {aa}\n\n"
    pt_path.write_text(head + out_body.strip() + "\n", encoding="utf-8")
    return len(pairs) - jpq


def _copy_periodicos(fn: str) -> None:
    src = PER / fn
    dst = WORK / "pt" / fn
    if not src.exists():
        return
    src_text = src.read_text(encoding="utf-8")
    dst_text = dst.read_text(encoding="utf-8") if dst.exists() else src_text
    file_pre = dst_text.split("=== ARTIGO ===")[0].rstrip() + "\n\n"
    _, src_blocks = split_file(src_text)
    dst_art = parse_article(split_file(dst_text)[1][0]) if dst.exists() else parse_article(src_blocks[0])
    src_body = parse_article(src_blocks[0]).content
    pre = [f"{k}: {v}" for k, v in dst_art.fields.items()] + ["---"]
    block = "\n".join(pre)
    if dst_art.meta:
        block += "\n" + dst_art.meta + "\n\n"
    else:
        block += "\n\n"
    block += src_body.replace("Gosuiji-roku", "Gokōwa-roku").strip() + "\n"
    dst.write_text(file_pre + "=== ARTIGO ===\n" + block, encoding="utf-8")


def _fix_spec_anchors(fn: str) -> None:
    spec_path = SEG / f"{fn}.json"
    if not spec_path.exists():
        return
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    body = (WORK / "pt" / fn).read_text(encoding="utf-8").split("---", 1)[-1]
    headers: list[str] = []
    for ln in body.splitlines():
        s = ln.strip()
        if SESSION_PT_RE.match(s):
            headers.append(s.strip("*"))
        elif re.match(r"^Gokōwa-roku", s) and "publicado" in s:
            headers.insert(0, s)
    hi = 0
    for art in spec.get("articles", []):
        if art.get("kind") == "preface":
            if headers:
                art["pt_anchor"] = headers[0]
            continue
        prefix = art.get("pt_prefix") or art.get("title_pt", "")
        found = None
        for h in headers:
            core = h.strip("[]")
            if core.startswith(prefix) or prefix in core:
                found = h if h.startswith("[") else core
                break
        if not found and hi < len(headers):
            found = headers[hi]
            hi += 1
        if found:
            art["pt_anchor"] = found
            art["notes"] = ""
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def process_one(fn: str, *, skip_approved: bool = True, approve: bool = False) -> dict:
    spec_path = SEG / f"{fn}.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path.exists() else {}
    jp_path = WORK / "jp" / fn
    pt_path = WORK / "pt" / fn
    jp_text = jp_path.read_text(encoding="utf-8")
    jpq = _jp_q_count(jp_text)
    supplement = "（補）" in fn
    trimmed = 0
    approved = bool(spec.get("approved"))

    if approved and skip_approved:
        pt_text = pt_path.read_text(encoding="utf-8")
        ptq = _pt_i_count(pt_text)
        return {
            "file": fn,
            "status": "skip_approved",
            "jp_q": jpq,
            "pt_q": ptq,
            "delta": ptq - jpq,
            "cjk": _body_cjk_lines(pt_text),
            "trimmed": 0,
        }

    if supplement:
        ptq = _pt_i_count(pt_path.read_text(encoding="utf-8"))
        if ptq > jpq + 2:
            trimmed = _trim_to_jp_pairs(pt_path, jpq)
    elif not approved:
        if fn in PERIODICOS_ONLY:
            _copy_periodicos(fn)
        apply_layout(fn, dry_run=False)
        if fn not in PERIODICOS_ONLY:
            pt_path.write_text(rebuild(jp_text, pt_path.read_text(encoding="utf-8")), encoding="utf-8")
        convert_a4b(fn, dry_run=False)
        ptq = _pt_i_count(pt_path.read_text(encoding="utf-8"))
        if ptq > jpq + 2:
            trimmed = _trim_to_jp_pairs(pt_path, jpq)
        elif ptq < jpq - 2 and fn not in PERIODICOS_ONLY:
            pt_path.write_text(rebuild(jp_text, pt_path.read_text(encoding="utf-8")), encoding="utf-8")
            convert_a4b(fn, dry_run=False)
            ptq = _pt_i_count(pt_path.read_text(encoding="utf-8"))
            if ptq > jpq + 2:
                trimmed = _trim_to_jp_pairs(pt_path, jpq)

    pt_text = pt_path.read_text(encoding="utf-8")
    ptq = _pt_i_count(pt_text)
    delta = ptq - jpq
    cjk = _body_cjk_lines(pt_text)
    _fix_spec_anchors(fn)

    status = "ok" if abs(delta) <= 2 and cjk == 0 else "delta_warn"
    if approve and status == "ok":
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["approved"] = True
        spec["editor_notes"] = (
            f"Gate 100% lote Gokōwa-roku {datetime.now(timezone.utc).strftime('%Y-%m-%d')}. "
            f"§4.4-A + §4.4-B; JP Q={jpq}, PT Interlocutor={ptq}."
        )
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        status = "approved"

    return {"file": fn, "status": status, "jp_q": jpq, "pt_q": ptq, "delta": delta, "cjk": cjk, "trimmed": trimmed}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--approve", action="store_true")
    ap.add_argument("--force", action="store_true", help="revalidar mesmo com approved: true")
    ap.add_argument("--file", action="append")
    args = ap.parse_args()
    skip = not args.force
    results = [process_one(fn, skip_approved=skip, approve=args.approve) for fn in (args.file or GOKOWA_ORDER)]

    report = SEG / "GOKOWA_BATCH_GATE.json"
    report.write_text(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fails = [r for r in results if r["status"] not in ("ok", "approved", "skip_approved")]
    for r in results:
        m = "✓" if r["status"] in ("ok", "approved", "skip_approved") else "!"
        print(f"{m} {r['file']}: {r['status']} JP={r.get('jp_q')} PT={r.get('pt_q')} Δ={r.get('delta')} cjk={r.get('cjk',0)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
