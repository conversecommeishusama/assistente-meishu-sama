#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove o ECO do japonês original dentro do `texto_pt` (defeito de tradução).

Defeito observado em 8 itens de 質問応答 (Tijotengoku): o texto japonês de cada
bloco de Pergunta/Resposta foi reproduzido no PT **antes** da tradução, além dos
cabeçalhos `（お伺）`/`（御垂示）`. A tradução correta está logo depois — então o
reparo é remover as linhas em japonês, sem retraduzir.

Regra de remoção de uma linha:
  - >= 60% de caracteres japoneses e quase nenhuma letra latina; E
  - o núcleo kanji/kana já existe no `texto_jp` (é eco), OU
    a linha é prosa japonesa pura (>=10 chars JP, zero latinas).

Tudo é registrado em `reports/reparo_eco_jp_log.json` para conferência.

Uso:
    .venv/bin/python scripts/reparar_eco_jp_periodicos.py [--dry-run]
"""
from __future__ import annotations

import glob
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
LOG = RAIZ / "reports" / "reparo_eco_jp_log.json"

DRY = "--dry-run" in sys.argv
MIN_JP = 20

JP = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
LAT = re.compile(r"[A-Za-zÀ-ÿ]")


def core(s: str) -> str:
    """Só kanji/kana (remove pontuação, dígitos, espaços)."""
    return re.sub(r"[^\u3040-\u30ff\u4e00-\u9fff]", "", s)


def eh_eco(linha: str, src_core: str) -> tuple[bool, str]:
    nj = len(JP.findall(linha))
    nl = len(LAT.findall(linha))
    if nj < 2 or nj / max(1, nj + nl) < 0.6:
        return False, "nao_jp"
    c = core(linha)
    if c and c in src_core:
        return True, "eco_exato"
    if nj >= 10 and nl == 0:
        return True, "jp_prosa_pura"
    return False, "sem_casamento"


def normalizar_brancos(txt: str) -> str:
    txt = re.sub(r"[ \t]+\n", "\n", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


def main() -> int:
    arquivos = sorted(glob.glob(str(ITENS / "*.json")))
    ts = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    back = ITENS.parent / f"itens_backup_reparo_eco_{ts}"
    log: dict = {}
    total_rem = 0
    itens_afetados = 0

    for f in arquivos:
        d = json.load(open(f, encoding="utf-8"))
        pt = d.get("texto_pt") or ""
        src = core(d.get("texto_jp") or "")
        if not pt or not src:
            continue
        # Só itens com eco GRANDE (>=20 chars JP). Os de resíduo pequeno são
        # termos legítimos citados no PT (ex.: 舌代, 腐食) — não se toca.
        if len(JP.findall(pt)) < MIN_JP:
            continue
        # Item marcado para retradução: não reparar (será regerado inteiro).
        if d.get("retraduzir"):
            print(f"!! ignorado (marcado p/ retraduzir): {Path(f).name}")
            continue

        removidas, motivos = [], []
        mantidas = []
        for linha in pt.split("\n"):
            ok, motivo = eh_eco(linha, src)
            if ok:
                removidas.append(linha)
                motivos.append(motivo)
            else:
                mantidas.append(linha)

        if not removidas:
            continue

        novo = normalizar_brancos("\n".join(mantidas))
        # nunca deixar o texto ficar vazio nem perder >40% do corpo
        if len(novo) < 0.6 * len(pt):
            print(f"!! ABORTADO (perda excessiva): {Path(f).name}")
            continue

        itens_afetados += 1
        total_rem += len(removidas)
        log[Path(f).name] = {
            "linhas_removidas": len(removidas),
            "chars_pt_antes": len(pt),
            "chars_pt_depois": len(novo),
            "jp_antes": len(JP.findall(pt)),
            "jp_depois": len(JP.findall(novo)),
            "removidas": [
                {"motivo": m, "linha": ln[:160]} for ln, m in zip(removidas, motivos)
            ],
        }

        if DRY:
            print(
                f"[DRY] {Path(f).name}: -{len(removidas)} linhas | "
                f"JP {len(JP.findall(pt))}→{len(JP.findall(novo))}"
            )
            continue

        back.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, back / Path(f).name)
        d["texto_pt"] = novo
        d["reparo_eco_jp"] = {
            "data": ts,
            "linhas_removidas": len(removidas),
            "backup": str(back.relative_to(RAIZ)),
        }
        Path(f).write_text(
            json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(
            f"{Path(f).name}: -{len(removidas)} linhas | "
            f"JP {log[Path(f).name]['jp_antes']}→{log[Path(f).name]['jp_depois']}"
        )

    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{'[DRY] ' if DRY else ''}itens afetados: {itens_afetados} | "
          f"linhas removidas: {total_rem}")
    if not DRY and itens_afetados:
        print(f"backup: {back}")
    print(f"log: {LOG.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
