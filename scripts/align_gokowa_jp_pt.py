#!/usr/bin/env python3
"""Alinhamento estrutural JP↔PT para ficheiros Gokōwa-roku, por proporção de
comprimento (técnica de alinhamento bilingue tipo Gale-Church), para detectar
com precisão fusões (N turnos JP → 1 parágrafo PT) e sobre-divisões (1 turno
JP → N parágrafos PT) que a contagem simples (Δ Interlocutor) não localiza.

Não traduz nem decide sozinho — produz um mapa de alinhamento com apontamentos
para revisão/correcção estrutural (relabel e/ou split) linha a linha.

Uso:
    venv/bin/python scripts/align_gokowa_jp_pt.py --file NOME.txt [--json]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from qa_dialogue_annotation import parse_qa_turns  # noqa: E402

WORK = work_root("livros_acervo")

# Razão média de expansão JP->PT (caracteres). Calibrada empiricamente a
# partir de ficheiros já verificados linha a linha (Suplemento, nº1). Usada
# só como prior de custo no alinhamento — não como asserção rígida.
MEAN_RATIO = 2.3
VARIANCE = 0.6  # desvio padrão do log da razão, estilo Gale-Church


def _split_paragraphs(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]


@dataclass
class JpTurn:
    kind: str
    text: str

    @property
    def n(self) -> int:
        return len(self.text)


@dataclass
class PtPara:
    label: str  # "I" | "M" | "?"
    text: str

    @property
    def n(self) -> int:
        return len(self.text)


def load_jp_turns(filename: str) -> list[JpTurn]:
    jp_path = WORK / "jp" / filename
    _, jp_blocks = split_file(jp_path.read_text(encoding="utf-8"))
    jp_body = parse_article(jp_blocks[0]).content
    turns = parse_qa_turns(jp_body, lang="jp", profile="gokowa_roku_qa")
    return [JpTurn(t.kind, t.text) for t in turns if t.kind in ("interlocutor", "meishu")]


def load_pt_paras(filename: str) -> list[PtPara]:
    pt_path = WORK / "pt" / filename
    _, pt_blocks = split_file(pt_path.read_text(encoding="utf-8"))
    pt_body = parse_article(pt_blocks[0]).content
    paras = _split_paragraphs(pt_body)
    out = []
    for p in paras:
        if p.startswith("Interlocutor:"):
            out.append(PtPara("I", p[len("Interlocutor:") :].strip()))
        elif p.startswith("Meishu-Sama:"):
            out.append(PtPara("M", p[len("Meishu-Sama:") :].strip()))
        # ignora parágrafos sem rótulo (títulos/datas) — não são turnos de diálogo
    return out


def _cost(jp_len_sum: int, pt_len_sum: int) -> float:
    if jp_len_sum <= 0 or pt_len_sum <= 0:
        return 25.0
    r = math.log(pt_len_sum / (jp_len_sum * MEAN_RATIO))
    return (r * r) / (2 * VARIANCE * VARIANCE)


# Categorias de alinhamento permitidas: (nº turnos JP, nº parágrafos PT)
CATS = [(1, 1), (1, 2), (2, 1), (1, 3), (3, 1)]
CAT_PENALTY = {(1, 1): 0.0, (1, 2): 2.0, (2, 1): 2.0, (1, 3): 4.0, (3, 1): 4.0}


def align(jp: list[JpTurn], pt: list[PtPara]) -> list[dict]:
    """DP de alinhamento por proporção de comprimento — permite fusão/divisão."""
    n, m = len(jp), len(pt)
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    bt: list[list[tuple | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] == INF:
                continue
            for (dj_j, di_i) in CATS:
                nj, ni = i + dj_j, j + di_i
                if nj > n or ni > m:
                    continue
                jp_sum = sum(t.n for t in jp[i:nj])
                pt_sum = sum(p.n for p in pt[j:ni])
                c = dp[i][j] + _cost(jp_sum, pt_sum) + CAT_PENALTY[(dj_j, di_i)]
                if c < dp[nj][ni]:
                    dp[nj][ni] = c
                    bt[nj][ni] = (i, j, dj_j, di_i)
    if dp[n][m] == INF:
        return []
    # backtrack
    path = []
    i, j = n, m
    while (i, j) != (0, 0):
        prev = bt[i][j]
        if prev is None:
            return []
        pi, pj, dj_j, di_i = prev
        path.append({"jp_range": (pi, i), "pt_range": (pj, j)})
        i, j = pi, pj
    path.reverse()
    return path


def build_report(filename: str) -> dict:
    jp = load_jp_turns(filename)
    pt = load_pt_paras(filename)
    path = align(jp, pt)

    pointers = []
    for seg in path:
        j0, j1 = seg["jp_range"]
        p0, p1 = seg["pt_range"]
        jp_kinds = [jp[k].kind for k in range(j0, j1)]
        pt_labels = [pt[k].label for k in range(p0, p1)]
        expect = "I" if len(set(jp_kinds)) == 1 and jp_kinds[0] == "interlocutor" else (
            "M" if len(set(jp_kinds)) == 1 else "MIX"
        )
        ok = (len(jp_kinds) == 1 and len(pt_labels) == 1 and pt_labels[0] == expect)
        item = {
            "jp_idx": [j0, j1],
            "pt_idx": [p0, p1],
            "jp_kinds": jp_kinds,
            "pt_labels": pt_labels,
            "expect": expect,
            "ok": ok,
            "jp_preview": jp[j0].text[:60].replace("\n", " "),
            "pt_preview": pt[p0].text[:60].replace("\n", " "),
        }
        pointers.append(item)

    problems = [p for p in pointers if not p["ok"]]
    return {
        "file": filename,
        "jp_turns": len(jp),
        "pt_paras": len(pt),
        "segments": len(path),
        "problems": len(problems),
        "pointers": pointers,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only-problems", action="store_true")
    args = ap.parse_args()

    report = build_report(args.file)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"{report['file']}: JP turns={report['jp_turns']} PT paras={report['pt_paras']} "
          f"segments={report['segments']} problems={report['problems']}")
    for p in report["pointers"]:
        if args.only_problems and p["ok"]:
            continue
        mark = "OK " if p["ok"] else "!! "
        print(f"{mark}jp{p['jp_idx']} {p['jp_kinds']} <-> pt{p['pt_idx']} {p['pt_labels']} "
              f"(esperado={p['expect']})")
        print(f"     JP: {p['jp_preview']}")
        print(f"     PT: {p['pt_preview']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
