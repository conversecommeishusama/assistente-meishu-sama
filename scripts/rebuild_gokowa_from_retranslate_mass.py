#!/usr/bin/env python3
"""Reconstrói o corpo PT de um ficheiro gokowa a partir da retradução em
massa crua (reports/translation_review/retranslate_mass/20260619T142344Z),
que antecede o protocolo/glossário finais mas já usa a terminologia certa
(Ohikari, Elo Espiritual, Johrei, Daijo/Shojo — verificado manualmente) e,
ao contrário da produção actual, não perdeu turnos de diálogo.

Preserva o cabeçalho estrutural (metadados, entry_id, pairing) já existente
em textos_portugues/<file> — só substitui o corpo de diálogo.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PROD = ROOT / "textos_portugues"
RETRA = (
    ROOT
    / "reports/translation_review/retranslate_mass/20260619T142344Z/corpus/textos_portugues"
)
BACKUP_DIR = ROOT / "reports/livros_trabalho/segmentacao_manual/pt_backup_pre_retranslate_mass"
RESTORE_SCRIPT = SCRIPTS / "restore_gokowa_from_prod.py"

DATE_HDR_RE = re.compile(r"\*\*(\d{1,2}(?:º)? de [^*]+?)\*\*")
FIRST_TURN_RE = re.compile(r"[—―–]{1,2}\s?")


BODY_START_RE = re.compile(r"^(\[[^\]]+\]|[—―–]{1,2}\s?)", re.M)


def split_header_body(prod_text: str) -> tuple[str, str]:
    """Cabeçalho = tudo antes do 1º '[data]' ou do 1º turno '— ...'."""
    m = BODY_START_RE.search(prod_text)
    if not m:
        raise ValueError("não encontrei início do corpo ('[data]' ou '— ') no ficheiro de produção")
    return prod_text[: m.start()], prod_text[m.start() :]


def reflow_retranslate_body(raw: str) -> str:
    date_m = DATE_HDR_RE.search(raw)
    turn_m = FIRST_TURN_RE.search(raw)
    if not date_m and not turn_m:
        raise ValueError("não encontrei cabeçalho de data nem turno '—' na retradução em massa")
    # Usa o que aparecer primeiro: cabeçalho de data em negrito, ou o 1º turno
    # (títulos sem data em negrito, ex. datas por extenso, caem neste 2º caso).
    if date_m and (not turn_m or date_m.start() <= turn_m.start()):
        start = date_m.start()
    else:
        start = turn_m.start()
    body = raw[start:]
    # "**28 de outubro (quinta-feira)**" -> "\n\n[28 de outubro (quinta-feira)]\n\n"
    body = DATE_HDR_RE.sub(lambda mm: f"\n\n[{mm.group(1)}]\n\n", body)
    # Alguns ficheiros preservam o travessão japonês colado ao texto (ex.
    # "――Diz-se..."), sem o espaço que convert_gokowa_dialogue_a4b.py exige
    # para reconhecer início de turno (Q_MARK_RE = r"^[—―–\-]{1,2}\s+").
    body = re.sub(r"([—―–]{1,2})(?=\S)", r"\1 ", body)
    return body.strip() + "\n"


def rebuild_one(name: str, *, dry_run: bool = False) -> int:
    prod_path = PROD / name
    retra_path = RETRA / name
    if not prod_path.is_file():
        print(f"FAIL {name}: sem textos_portugues", file=sys.stderr)
        return 1
    if not retra_path.is_file():
        print(f"FAIL {name}: sem par em retranslate_mass", file=sys.stderr)
        return 1

    prod_text = prod_path.read_text(encoding="utf-8")
    retra_raw = retra_path.read_text(encoding="utf-8")

    header, _old_body = split_header_body(prod_text)
    try:
        new_body = reflow_retranslate_body(retra_raw)
    except ValueError as exc:
        print(f"FAIL {name}: {exc}", file=sys.stderr)
        return 1

    new_text = header + new_body

    if dry_run:
        print(f"DRY-RUN {name}: {len(prod_text)} -> {len(new_text)} chars")
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(prod_path, BACKUP_DIR / name)
    prod_path.write_text(new_text, encoding="utf-8")

    r = subprocess.run(
        [sys.executable, str(RESTORE_SCRIPT), "--file", name],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip(), file=sys.stderr)
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    return rebuild_one(args.file, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
