#!/usr/bin/env python3
"""Rotulagem §4.4-B Gokōwa-roku — JP linha a linha → contagem/formato → PT.

Etapa A: classificar turnos no JP (pergunta vs resposta) — fonte de verdade.
Etapa B: confirmar com contagem (―― vs Interlocutor) e formato (M/I, I→I).
Etapa C: aplicar rótulos no PT na mesma ordem, sem reordenar texto.
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

from acervo_work_paths import work_root, article_sep  # noqa: E402
from apply_gokowa_collection_layout import GOKOWA_ORDER  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from qa_dialogue_annotation import parse_qa_turns  # noqa: E402

WORK = work_root("livros_acervo")
SEG = WORK / "segmentacao_manual"
ARTICLE_SEP = article_sep()
CORPUS = Path("textos_portugues")
"""Fonte de verdade da produção (mesma pasta usada por restore_gokowa_from_prod.py).
Não usar snapshots datados de reports/translation_review/*: ficam desactualizados
e podem faltar conteúdo já promovido a textos_portugues/."""

JP_Q_MARK = re.compile(r"^[—―–\-]{1,2}\s*|^（お伺）")
JP_INDENT = re.compile(r"^[\u3000]")
KIND_LABEL = {"interlocutor": "Interlocutor", "meishu": "Meishu-Sama", "header": "header", "narration": "narration"}


@dataclass
class JpLineAudit:
    line_no: int
    raw: str
    inferred_kind: str
    marker: str


def audit_jp_lines(jp_content: str) -> list[JpLineAudit]:
    """Etapa A — classificação linha a linha do JP (apoio à leitura editorial)."""
    turns = parse_qa_turns(jp_content, lang="jp", profile="gokowa_roku_qa")
    turn_by_first_line: dict[int, str] = {}
    for t in turns:
        for i, ln in enumerate(jp_content.splitlines()):
            if ln.strip() and ln.strip() in t.text[: len(ln.strip()) + 20]:
                if i not in turn_by_first_line:
                    turn_by_first_line[i] = t.kind
                    break

    rows: list[JpLineAudit] = []
    mode = "narration"
    for i, raw in enumerate(jp_content.splitlines(), start=1):
        s = raw.strip()
        if not s:
            continue
        marker = ""
        if JP_Q_MARK.match(s):
            kind, marker = "interlocutor", "――/（お伺）"
        elif JP_INDENT.match(raw):
            kind, marker = "meishu", "　(resposta)"
        elif s.startswith("［") or re.match(r"^[一二三四五六七八九十百\d]+月", s):
            kind, marker = "header", "data/sessão"
        elif i - 1 in turn_by_first_line:
            kind = turn_by_first_line[i - 1]
        else:
            kind = mode if mode in ("meishu", "interlocutor") else "narration"
        if kind in ("interlocutor", "meishu"):
            mode = kind
        rows.append(JpLineAudit(i, s[:120], kind, marker))
    return rows


def jp_turn_map(jp_content: str) -> list[dict]:
    """Mapa de turnos JP para Etapa A–B (conferência antes do PT)."""
    turns = parse_qa_turns(jp_content, lang="jp", profile="gokowa_roku_qa")
    out: list[dict] = []
    for n, t in enumerate(turns, start=1):
        if t.kind not in ("interlocutor", "meishu", "header"):
            continue
        out.append(
            {
                "seq": n,
                "kind": t.kind,
                "label_pt": KIND_LABEL.get(t.kind, t.kind),
                "preview": t.text[:100].replace("\n", " "),
            }
        )
    return out


def _split_paragraphs(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]


def _strip_dialogue_label(para: str) -> str:
    for prefix in ("Interlocutor:", "Meishu-Sama:"):
        if para.startswith(prefix):
            return para[len(prefix) :].strip()
    return para.strip()


def _is_dialogue_para(para: str) -> bool:
    return para.startswith("Interlocutor:") or para.startswith("Meishu-Sama:")


def _format_turn(kind: str, text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    if kind == "interlocutor":
        return f"Interlocutor: {text}"
    return f"Meishu-Sama: {text}"


MAX_SAFE_DIALOGUE_MISMATCH = 8
"""Tolerância absoluta de Δ(turnos) entre JP e PT abaixo da qual confiamos no
alinhamento posicional global. Acima disto, o PT tipicamente tem conteúdo
ausente/deslocado (ex.: início do livro nunca migrado do corpus) e o
walk posicional inverte sistematicamente todos os rótulos a partir do
primeiro turno sem correspondência — corrupção pior do que não fazer nada.
Ver reports/livros_trabalho (caso 19480101-御光話録（補）.txt, Δ=-137)."""


def relabel_body_jp_guided(jp_content: str, pt_content: str) -> tuple[str, dict]:
    """Etapa C — aplica rótulos PT conforme mapa JP; não reordena texto.

    Estrutural: recusa-se a relabelar (fail-closed) quando a contagem de
    turnos de diálogo JP vs PT diverge além de MAX_SAFE_DIALOGUE_MISMATCH,
    em vez de assumir correspondência posicional 1:1 desde o turno 0.
    Isso vale para qualquer ficheiro, não é uma excepção por nome.
    """
    jp_turns = parse_qa_turns(jp_content, lang="jp", profile="gokowa_roku_qa")
    jp_dialogue = [t for t in jp_turns if t.kind in ("interlocutor", "meishu")]

    paras = _split_paragraphs(pt_content)
    pt_dialogue_count = sum(1 for p in paras if _is_dialogue_para(p))
    delta_dialogue = pt_dialogue_count - len(jp_dialogue)

    meta = {
        "jp_dialogue": len(jp_dialogue),
        "pt_dialogue": pt_dialogue_count,
        "delta_dialogue": delta_dialogue,
    }

    if abs(delta_dialogue) > MAX_SAFE_DIALOGUE_MISMATCH:
        meta["skipped"] = True
        meta["skip_reason"] = (
            f"|Δturnos|={abs(delta_dialogue)} > {MAX_SAFE_DIALOGUE_MISMATCH}: "
            "alinhamento posicional global não é seguro (PT provavelmente com "
            "conteúdo ausente/deslocado); requer reconciliação de conteúdo ou "
            "revisão semântica linha a linha antes de rotular."
        )
        meta["aligned"] = 0
        return pt_content.strip() + "\n", meta

    out: list[str] = []
    di = 0
    for para in paras:
        if not _is_dialogue_para(para):
            out.append(para)
            continue
        text = _strip_dialogue_label(para)
        if di < len(jp_dialogue):
            out.append(_format_turn(jp_dialogue[di].kind, text))
            di += 1
        else:
            out.append(para)

    meta["skipped"] = False
    meta["aligned"] = di
    return "\n\n".join(out).strip() + "\n", meta


def _a4b_stats(body: str) -> dict:
    paras = _split_paragraphs(body)
    i = sum(1 for p in paras if p.startswith("Interlocutor:"))
    m = sum(1 for p in paras if p.startswith("Meishu-Sama:"))
    ii = sum(
        1
        for n in range(len(paras) - 1)
        if paras[n].startswith("Interlocutor:") and paras[n + 1].startswith("Interlocutor:")
    )
    dash = sum(1 for ln in body.splitlines() if re.match(r"^\s*[—―–\-]\s", ln))
    return {"interlocutor": i, "meishu": m, "i_i_blocks": ii, "dash": dash}


def _jp_q(jp_content: str) -> int:
    turns = parse_qa_turns(jp_content, lang="jp", profile="gokowa_roku_qa")
    return sum(1 for t in turns if t.kind == "interlocutor")


def _corpus_body(filename: str) -> str | None:
    """Lê o corpo completo de textos_portugues/ preservando todo o conteúdo
    (incluindo prosa/prefácio antes da primeira marca de diálogo), usando o
    mesmo parser de artigos que o resto do pipeline — sem descartar linhas
    por um scan ingénuo até à primeira marca de travessão."""
    path = CORPUS / filename
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    try:
        _, blocks = split_file(text)
    except Exception:
        return None
    if not blocks:
        return None
    return "\n\n".join(parse_article(b).content for b in blocks).strip() + "\n"


def _normalize_corpus_to_a4b(body: str) -> str:
    """Converte travessões do corpus em parágrafos A4B preliminares."""
    from convert_gokowa_dialogue_a4b import convert_body_text  # noqa: WPS433

    return convert_body_text(body)


def _pick_pt_body(filename: str, pt_art_content: str, *, use_corpus: bool) -> tuple[str, str]:
    """Escolhe a fonte PT a rotular.

    Estrutural (sem excepção por nome de ficheiro): quando use_corpus está
    activo, tenta sempre textos_portugues/ (fonte de produção mais completa/
    actual) e só recorre ao PT já presente em livros_trabalho/ se a fonte de
    produção não existir. A segurança contra corrupção fica a cargo do guard
    de Δ em relabel_body_jp_guided, não de excepções ad hoc aqui.
    """
    if not use_corpus:
        return pt_art_content, "livros"
    corp = _corpus_body(filename)
    if not corp:
        return pt_art_content, "livros"
    if "—" in corp or corp.strip().startswith(("—", "——")):
        return _normalize_corpus_to_a4b(corp), "corpus_dash"
    return corp, "corpus_a4b"


def audit_file(filename: str) -> dict:
    """Etapas A+B: mapa JP linha a linha + métricas de confirmação."""
    jp_path = WORK / "jp" / filename
    pt_path = WORK / "pt" / filename
    _, jp_blocks = split_file(jp_path.read_text(encoding="utf-8"))
    jp_body = "\n".join(parse_article(b).content for b in jp_blocks)
    pt_body = ""
    if pt_path.is_file():
        _, pt_blocks = split_file(pt_path.read_text(encoding="utf-8"))
        pt_body = "\n".join(parse_article(b).content for b in pt_blocks)

    lines = [asdict(r) for r in audit_jp_lines(jp_body)]
    turns = jp_turn_map(jp_body)
    jpq = sum(1 for t in turns if t["kind"] == "interlocutor")
    jpm = sum(1 for t in turns if t["kind"] == "meishu")
    st = _a4b_stats(pt_body) if pt_body else {"interlocutor": 0, "meishu": 0, "i_i_blocks": 0, "dash": 0}
    return {
        "file": filename,
        "jp_lines_audited": len(lines),
        "jp_turns": turns,
        "jp_interlocutor": jpq,
        "jp_meishu": jpm,
        "pt_interlocutor": st["interlocutor"],
        "pt_meishu": st["meishu"],
        "delta_q": st["interlocutor"] - jpq,
        "m_i_ratio": round(st["meishu"] / st["interlocutor"], 3) if st["interlocutor"] else 0,
        "i_i_blocks": st["i_i_blocks"],
        "sample_lines": lines[:20],
    }


def process_file(filename: str, *, dry_run: bool = False, use_corpus: bool = False) -> dict:
    jp_path = WORK / "jp" / filename
    pt_path = WORK / "pt" / filename
    jp_raw = jp_path.read_text(encoding="utf-8")
    pt_raw = pt_path.read_text(encoding="utf-8")
    file_pre, pt_blocks = split_file(pt_raw)
    _, jp_blocks = split_file(jp_raw)

    new_blocks: list[str] = []
    sources: list[str] = []
    skips: list[dict] = []
    for jb, pb in zip(jp_blocks, pt_blocks, strict=False):
        jp_art = parse_article(jb)
        pt_art = parse_article(pb)
        src_body, src = _pick_pt_body(filename, pt_art.content, use_corpus=use_corpus)
        sources.append(src)
        new_content, rel_meta = relabel_body_jp_guided(jp_art.content, src_body)
        if rel_meta.get("skipped"):
            skips.append(rel_meta)
        pre = [f"{k}: {v}" for k, v in pt_art.fields.items()] + ["---"]
        block = "\n".join(pre)
        if pt_art.meta:
            block += "\n" + pt_art.meta + "\n\n"
        else:
            block += "\n\n"
        block += new_content
        new_blocks.append(block)

    out = file_pre.rstrip() + f"\n{ARTICLE_SEP}\n" + f"\n{ARTICLE_SEP}\n".join(new_blocks)
    if not dry_run:
        pt_path.write_text(out, encoding="utf-8")

    jp_body = "\n".join(parse_article(b).content for b in jp_blocks)
    pt_body = "\n\n".join(parse_article(b).content for b in new_blocks)
    st = _a4b_stats(pt_body)
    jpq = _jp_q(jp_body)
    delta = st["interlocutor"] - jpq
    mi = st["meishu"] / st["interlocutor"] if st["interlocutor"] else 0
    ok = (
        abs(delta) <= 2
        and st["dash"] == 0
        and mi >= 0.85
        and st["i_i_blocks"] <= 5
    )
    status = "ok" if ok else "warn"
    if skips:
        status = "skipped_mismatch"
    return {
        "file": filename,
        "source": sources[0] if sources else "?",
        "jp_q": jpq,
        "pt_i": st["interlocutor"],
        "pt_m": st["meishu"],
        "delta": delta,
        "m_i_ratio": round(mi, 3),
        "i_i_blocks": st["i_i_blocks"],
        "dash": st["dash"],
        "status": status,
        "skip_reasons": [s["skip_reason"] for s in skips] if skips else [],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Rotulagem §4.4-B — JP linha a linha → PT")
    ap.add_argument("--file", action="append")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--audit-jp", action="store_true", help="Etapa A–B: mapa JP + métricas, sem alterar PT")
    ap.add_argument(
        "--use-corpus",
        action="store_true",
        help=(
            "Etapa C: rederivar o PT a partir de textos_portugues/ (produção) em vez de "
            "usar o PT já presente em livros_trabalho/. Acção explícita e pouco frequente "
            "(reconstrução), não o comportamento por omissão — o padrão é relabelar só o "
            "que já existe em livros_trabalho/pt/."
        ),
    )
    ap.add_argument("--no-corpus", action="store_true", help=argparse.SUPPRESS)  # retrocompat.: já é o padrão
    ap.add_argument("--update-spec", action="store_true")
    args = ap.parse_args()

    files = args.file or GOKOWA_ORDER

    if args.audit_jp:
        audits = [audit_file(fn) for fn in files]
        out = SEG / "GOKOWA_JP_TURN_AUDIT.json"
        out.write_text(
            json.dumps({"at": datetime.now(timezone.utc).isoformat(), "audits": audits}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        for a in audits:
            ok = abs(a["delta_q"]) <= 2 and a["m_i_ratio"] >= 0.85
            m = "✓" if ok else "!"
            print(
                f"{m} {a['file']}: JP I={a['jp_interlocutor']} M={a['jp_meishu']} "
                f"PT I={a['pt_interlocutor']} M={a['pt_meishu']} Δ={a['delta_q']}"
            )
        print(f"Mapa: {out}")
        return 0

    results = [
        process_file(fn, dry_run=args.dry_run, use_corpus=args.use_corpus) for fn in files
    ]

    report = {
        "at": datetime.now(timezone.utc).isoformat(),
        "method": "A:jp_turns B:metrics C:relabel_pt_in_place",
        "results": results,
    }
    (SEG / "GOKOWA_LABEL_AUDIT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if args.update_spec and not args.dry_run:
        for r in results:
            sp = SEG / f"{r['file']}.json"
            if not sp.exists():
                continue
            spec = json.loads(sp.read_text(encoding="utf-8"))
            spec["profile"] = "gokowa_roku_qa"
            if r["status"] == "ok":
                spec["approved"] = True
                spec["editor_notes"] = (
                    f"Rotulagem §4.4-B JP-guiada {datetime.now(timezone.utc).strftime('%Y-%m-%d')}. "
                    f"Fonte={r['source']}; JP Q={r['jp_q']}, PT I={r['pt_i']} M={r['pt_m']}, "
                    f"M/I={r['m_i_ratio']}."
                )
            elif r["status"] == "skipped_mismatch":
                spec["approved"] = False
                spec["editor_notes"] = (
                    "Rotulagem JP-guiada RECUSADA (fail-closed): "
                    + " | ".join(r["skip_reasons"])
                )
            else:
                spec["approved"] = False
                spec["editor_notes"] = (
                    f"Pendente rotulagem JP-guiada: Δ={r['delta']}, M/I={r['m_i_ratio']}, "
                    f"I→I={r['i_i_blocks']}."
                )
            sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fails = [r for r in results if r["status"] != "ok"]
    for r in results:
        m = "✓" if r["status"] == "ok" else "!"
        print(
            f"{m} {r['file']}: src={r['source']} JP={r['jp_q']} I={r['pt_i']} M={r['pt_m']} "
            f"Δ={r['delta']} M/I={r['m_i_ratio']} I→I={r['i_i_blocks']}"
        )
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
