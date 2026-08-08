#!/usr/bin/env python3
"""Revisão paralela JP/PT — triagem rigorosa de todo o acervo livros (Etapa A).

Não substitui leitura editorial; regista flags por trecho para revisão profunda.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import ROOT, work_root  # noqa: E402
from apply_manual_livros_segmentacao import Boundary, load_boundary_file, split_by_anchors  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from livros_segmentacao_pairing import jp_session_needles, split_pt_chunks  # noqa: E402
from retranslate_qa import sanitize_pt_translation  # noqa: E402

QA_PROFILES = frozenset({"gokowa_roku_qa", "gokowa_roku_ho", "ochishiji_roku", "mioshie_shu"})

MANUAL_DIR = "segmentacao_manual"
SNAPSHOT_ROOT = ROOT / "reports/acervo_revision/snapshots/livros_acervo"

CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uF900-\uFAFF]")
JP_DATE_RE = re.compile(r"^([一二三四五六七八九十百\d]+)月([一二三四五六七八九十百\d]+)日")
JP_KOZA_RE = re.compile(r"^[\s　]*第([一二三四五六七八九十\d]+)講座")
JP_HEN_RE = re.compile(r"^（([一二三四五六七八九十百\d]+)）")
JP_PRAYER_RE = re.compile(r"^(五赞歌|賛歌|讃歌|祈祷|お祈|御祈祷| Psalm|Salmo)", re.I)
JP_CHAPTER_RE = re.compile(r"^(第[一二三四五六七八九十百\d]+[章篇節]|Chapter\s+[IVXLC\d]+)", re.I)
JP_ARTICLE_TITLE_RE = re.compile(r"^【[^】]{2,40}】$")
PT_TRUNC_RE = re.compile(r"(\.\.\.|…|\[truncado\]|\[incomplete\])", re.I)

ISSUE_SUBDIVIDE = "subdivisao_possivel"
ISSUE_NO_PT = "pt_ausente"
ISSUE_ALIGN = "desalinhamento"
ISSUE_INCOMPLETE = "pt_incompleto"
ISSUE_CJK = "cjk_no_pt"
ISSUE_PARA = "paragrafação"
ISSUE_TITLE = "titulo_cabecalho"
ISSUE_DUP = "duplicacao"
ISSUE_ORDER = "ordem_suspeita"
ISSUE_ANCHOR = "anchor_invalido"
ISSUE_META = "metadados"
ISSUE_OTHER = "outro"


@dataclass
class TrechoReview:
    index: int
    title_jp: str
    kind: str
    jp_chars: int
    pt_chars: int
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    severity: str = "ok"  # ok | warn | fail


@dataclass
class FileReview:
    filename: str
    profile: str
    articles_total: int
    trechos: list[TrechoReview]
    file_issues: list[str] = field(default_factory=list)


def _body(path: Path) -> str:
    _, blocks = split_file(path.read_text(encoding="utf-8"))
    if not blocks:
        return path.read_text(encoding="utf-8")
    parts = [parse_article(b).content for b in blocks if parse_article(b).content.strip()]
    return "\n\n".join(parts)


def _article_bodies(path: Path) -> list[str]:
    _, blocks = split_file(path.read_text(encoding="utf-8"))
    return [parse_article(b).content.strip() for b in blocks]


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _internal_split_candidates(jp: str) -> list[tuple[str, str]]:
    """Marcadores JP internos que sugerem mais subdivisões."""
    found: list[tuple[str, str]] = []
    for i, line in enumerate(jp.splitlines()):
        s = line.strip()
        if not s:
            continue
        for pat, label in (
            (JP_DATE_RE, "data_sessao"),
            (JP_KOZA_RE, "koza_licao"),
            (JP_HEN_RE, "jikan_secao"),
            (JP_PRAYER_RE, "oracao_salmo"),
            (JP_CHAPTER_RE, "capitulo"),
            (JP_ARTICLE_TITLE_RE, "titulo_colchetes"),
        ):
            if pat.match(s):
                found.append((label, s[:60]))
                break
    return found


def _cjk_spans(pt: str) -> list[str]:
    # Usa o mesmo sanitizador do QA de tradução (retranslate_qa) antes de
    # procurar CJK residual: isso exclui a exceção pedagógica do protocolo
    # (§5.1b) — glosa curta de kanji entre parênteses, ex. "kyō" (教) — que,
    # sem esta normalização, era sinalizada como falso positivo e travava o
    # trecho num ciclo infinito de autofix.
    cleaned = sanitize_pt_translation(pt).text
    spans: list[str] = []
    for m in CJK_RE.finditer(cleaned):
        start = max(0, m.start() - 20)
        end = min(len(cleaned), m.end() + 20)
        spans.append(cleaned[start:end].replace("\n", " "))
    return spans[:5]


def _needle_hits(chunk: str, needles: list[str]) -> tuple[int, int]:
    ok = 0
    for n in needles:
        n = n.strip()
        if len(n) < 8:
            continue
        if n in chunk or chunk.find(n[: min(40, len(n))]) >= 0:
            ok += 1
    return ok, len([n for n in needles if len(n.strip()) >= 8])


def _count_numbered_poems(text: str) -> tuple[int, int | None]:
    last: int | None = None
    count = 0
    for line in text.splitlines():
        m = re.match(r"^(\d+),\s", line.strip())
        if m:
            count += 1
            last = int(m.group(1))
    return count, last


def _anchor_corrupt(anchor: str) -> bool:
    a = anchor.strip()
    if len(a) < 12:
        return False
    if a[0].islower() or a[0] in "óãíúéàê":
        return True
    if re.match(r"^(lhosa|erialismo|latente|óxima)\b", a, re.I):
        return True
    return False


def _shinko_article_titles(jp: str) -> list[str]:
    div = "─" * 10
    page_re = re.compile(r"全集著述篇")
    lines = jp.splitlines()
    titles: list[str] = []
    for i, line in enumerate(lines):
        if div not in line or len(line.strip()) < 20:
            continue
        for j in range(i + 1, min(i + 8, len(lines))):
            s = lines[j].strip()
            if (
                2 <= len(s) <= 30
                and not page_re.search(s)
                and not s.startswith("─")
                and "昭和" not in s
                and not s.isdigit()
                and not s.startswith("『信仰")
            ):
                titles.append(s)
                break
    return titles


def _search_snapshots(filename: str, needle: str) -> list[str]:
    if len(needle) < 12:
        return []
    hits: list[str] = []
    for snap in sorted(SNAPSHOT_ROOT.glob("*/livros_trabalho/pt/" + filename)):
        try:
            body = _body(snap)
        except Exception:
            continue
        if needle in body or body.find(needle[:40]) >= 0:
            hits.append(snap.parent.parent.name)
    return hits[:3]


def _para_alignment(jp: str, pt: str) -> tuple[bool, str]:
    jp_p = _paragraphs(jp)
    pt_p = _paragraphs(pt)
    if not jp_p or not pt_p:
        return True, ""
    ratio = len(pt_p) / len(jp_p)
    if ratio < 0.45 or ratio > 2.2:
        return False, f"parágrafos JP={len(jp_p)} PT={len(pt_p)} ratio={ratio:.2f}"
    return True, ""


def review_trecho(
    idx: int,
    b: Boundary,
    jp_c: str,
    pt_c: str,
    *,
    filename: str,
    profile: str = "",
) -> TrechoReview:
    tr = TrechoReview(
        index=idx,
        title_jp=b.title_jp,
        kind=b.kind,
        jp_chars=len(jp_c),
        pt_chars=len(pt_c),
    )
    issues = tr.issues
    notes = tr.notes

    if not pt_c.strip():
        issues.append(ISSUE_NO_PT)
        tr.severity = "fail"
        return tr

    internal = _internal_split_candidates(jp_c)
    if len(internal) >= 2 and b.kind in ("monolith", "chapter", "section"):
        issues.append(ISSUE_SUBDIVIDE)
        notes.append(f"JP interno: {len(internal)} marcadores ({', '.join(sorted(set(l for l, _ in internal)))})")

    if len(jp_c) > 200 and len(pt_c) < len(jp_c) * 0.35:
        issues.append(ISSUE_INCOMPLETE)
        notes.append(f"PT {len(pt_c)} chars vs JP {len(jp_c)} ({100*len(pt_c)/len(jp_c):.0f}%)")

    if PT_TRUNC_RE.search(pt_c[-400:] if len(pt_c) > 400 else pt_c):
        issues.append(ISSUE_INCOMPLETE)
        notes.append("marcador truncamento no PT")

    needles = jp_session_needles(jp_c)[:6]
    hits, total = _needle_hits(pt_c, needles)
    if total >= 2 and hits == 0:
        issues.append(ISSUE_ALIGN)
        notes.append(f"agulhas JP não encontradas no chunk PT ({total} testadas)")
    elif total >= 3 and hits < total // 2:
        issues.append(ISSUE_ALIGN)
        notes.append(f"só {hits}/{total} agulhas JP no PT")

    cjk = _cjk_spans(pt_c)
    if cjk:
        issues.append(ISSUE_CJK)
        notes.extend(f"CJK: …{s}…" for s in cjk[:3])

    ok_para, para_note = _para_alignment(jp_c, pt_c)
    if not ok_para and profile not in QA_PROFILES:
        issues.append(ISSUE_PARA)
        notes.append(para_note)

    if profile in QA_PROFILES and jp_c.strip() and pt_c.strip():
        try:
            from qa_dialogue_annotation import verify_qa_alignment  # noqa: WPS433

            qa_warn = verify_qa_alignment(jp_c, pt_c, profile=profile)
            if qa_warn:
                issues.append(ISSUE_ALIGN)
                notes.extend(qa_warn[:3])
        except Exception:
            pass

    if b.pt_anchor and len(b.pt_anchor) > 10:
        if b.pt_anchor.strip() not in pt_c and pt_c.find(b.pt_anchor[:40].strip()) < 0:
            issues.append(ISSUE_ANCHOR)
            notes.append(f"pt_anchor não encontrado: {b.pt_anchor[:50]!r}")
        if _anchor_corrupt(b.pt_anchor):
            issues.append(ISSUE_ALIGN)
            notes.append(f"pt_anchor corrupto (meio de frase): {b.pt_anchor[:50]!r}")

    jp_poems, jp_last = _count_numbered_poems(jp_c)
    pt_poems, pt_last = _count_numbered_poems(pt_c)
    if jp_poems >= 20 and pt_poems < jp_poems * 0.85:
        issues.append(ISSUE_INCOMPLETE)
        notes.append(f"poemas/hinos numerados JP={jp_poems} PT={pt_poems} (último JP={jp_last} PT={pt_last})")

    if b.title_pt and b.title_jp and b.title_pt == b.title_jp and not CJK_RE.search(b.title_jp):
        pass
    elif b.title_pt and CJK_RE.search(b.title_pt):
        issues.append(ISSUE_TITLE)
        notes.append("title_pt contém CJK")

    if issues and tr.severity == "ok":
        tr.severity = "fail" if any(
            x in issues
            for x in (ISSUE_NO_PT, ISSUE_ALIGN, ISSUE_INCOMPLETE, ISSUE_CJK)
        ) else "warn"

    if ISSUE_INCOMPLETE in issues and jp_c.strip():
        tail = jp_c.strip()[-80:]
        snaps = _search_snapshots(filename, tail)
        if snaps:
            notes.append(f"snapshot com cauda JP: {snaps[0]}")

    return tr


def review_file(spec_path: Path, wr: Path) -> FileReview | None:
    spec = load_boundary_file(spec_path)
    fn = spec.get("filename") or spec_path.stem.replace(".txt", "")
    if not fn.endswith(".txt"):
        fn += ".txt" if ".txt" not in fn else ""
    jp_path, pt_path = wr / "jp" / fn, wr / "pt" / fn
    fr = FileReview(
        filename=fn,
        profile=spec.get("profile", "?"),
        articles_total=len(spec.get("articles", [])),
        trechos=[],
    )
    if not jp_path.is_file():
        fr.file_issues.append("jp_ausente")
        return fr
    if not pt_path.is_file():
        fr.file_issues.append("pt_ausente_ficheiro")
        return fr

    bounds = [Boundary.from_article(a) for a in spec["articles"]]
    jp_articles = _article_bodies(jp_path)
    pt_articles = _article_bodies(pt_path)

    if len(jp_articles) == len(pt_articles) == len(bounds) and len(bounds) > 1:
        jp_chunks, pt_chunks = jp_articles, pt_articles
    else:
        jp_body = _body(jp_path)
        pt_body = _body(pt_path)
        jp_chunks = split_by_anchors(jp_body, [b.jp_anchor for b in bounds], label="JP")
        try:
            pt_chunks = split_pt_chunks(pt_body, jp_chunks, bounds, profile=fr.profile)
        except Exception as e:
            fr.file_issues.append(f"pairing_erro: {e}")
            pt_chunks = split_by_anchors(pt_body, [b.pt_anchor for b in bounds], label="PT")

        if len(jp_chunks) != len(pt_chunks):
            fr.file_issues.append(f"chunks_jp={len(jp_chunks)} pt={len(pt_chunks)}")

    for i, (b, jc, pc) in enumerate(zip(bounds, jp_chunks, pt_chunks, strict=False)):
        fr.trechos.append(review_trecho(i + 1, b, jc, pc, filename=fn, profile=fr.profile))

    if fr.articles_total == 1 and fr.trechos:
        jp_body = _body(jp_path)
        pt_body = _body(pt_path)
        internal = _internal_split_candidates(jp_body)
        jp_poems, _ = _count_numbered_poems(jp_body)
        if len(internal) >= 3:
            fr.file_issues.append(ISSUE_SUBDIVIDE)
            fr.file_issues.append(f"monólito com {len(internal)} marcadores internos JP")
        shinko_titles = _shinko_article_titles(jp_body) if "信仰雑話" in fn else []
        if len(shinko_titles) >= 10:
            fr.file_issues.append(ISSUE_SUBDIVIDE)
            fr.file_issues.append(f"信仰雑話: ~{len(shinko_titles)} artigos JP, spec=1")
        if jp_poems >= 50 and fr.profile == "monolith":
            pt_poems, _ = _count_numbered_poems(pt_body)
            if pt_poems < jp_poems * 0.85:
                fr.file_issues.append(ISSUE_INCOMPLETE)
                fr.file_issues.append(f"monólito poético: JP={jp_poems} PT={pt_poems}")

    return fr


def main() -> int:
    p = argparse.ArgumentParser(description="Revisão paralela JP/PT — Etapa A")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--file", type=str, default="")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    manual = wr / MANUAL_DIR
    out = args.out or manual / "REVISAO_PARALELA_REPORT.json"

    specs = [manual / f"{args.file}.json"] if args.file else sorted(
        p for p in manual.glob("*.json") if not p.name.startswith(("BATCH", "AUDIT", "REVISAO"))
    )

    reviews: list[dict] = []
    stats = {"files": 0, "trechos": 0, "fail": 0, "warn": 0, "ok": 0}

    for sp in specs:
        if not sp.is_file():
            continue
        fr = review_file(sp, wr)
        if not fr:
            continue
        stats["files"] += 1
        for t in fr.trechos:
            stats["trechos"] += 1
            stats[t.severity] = stats.get(t.severity, 0) + 1
        reviews.append(asdict(fr))

    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage": "A_triagem_rigorosa",
        "stats": stats,
        "files": reviews,
    }
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out)
    print(
        f"files={stats['files']} trechos={stats['trechos']} "
        f"ok={stats.get('ok',0)} warn={stats.get('warn',0)} fail={stats.get('fail',0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
