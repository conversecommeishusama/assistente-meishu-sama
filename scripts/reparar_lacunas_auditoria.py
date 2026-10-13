#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repara lacunas apontadas pela auditoria (trecho JP sem tradução).

Usado quando a auditoria deteta que falta um trecho do japonês no português
(caso típico: o PT termina a meio, ou salta uma secção).

O trecho JP em falta é indicado por um ficheiro de texto; a inserção faz-se
antes de uma âncora do PT (ou no fim, se `--fim`).

Uso:
    python scripts/reparar_lacunas_auditoria.py \
        --item P3_Kyusei_51_304 \
        --jp-falta /tmp/jp_51_304_falta.txt \
        --fim
    python scripts/reparar_lacunas_auditoria.py \
        --item P1_Tijotengoku_40_72 \
        --jp-falta /tmp/jp_40_72_falta.txt \
        --ancora "(Pergunta)\n\nEu sou uma pessoa que" \
        --aplicar
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from traduzir_periodicos_meishu_sama import (  # noqa: E402
    divide_chunks, traduzir_com_alertas,
)

ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_auditoria"
SUBLIMITE = 1400


def traduzir_trecho(jp: str) -> str:
    partes = []
    for i, sub in enumerate(divide_chunks(jp, SUBLIMITE), 1):
        nova, _ = traduzir_com_alertas(sub, "Meishu-Sama (autor do artigo)")
        if not nova:
            raise RuntimeError(f"sub-bloco {i} voltou vazio")
        print(f"    sub {i}: {len(sub)}c -> {len(nova)}c", flush=True)
        partes.append(nova)
    return "\n\n".join(partes)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", required=True)
    ap.add_argument("--jp-falta", required=True)
    ap.add_argument("--ancora", help="inserir ANTES deste trecho do PT")
    ap.add_argument("--fim", action="store_true", help="inserir no fim do PT")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--pt-ja-traduzido",
                    help="ficheiro com a tradução já feita (evita repetir a API)")
    args = ap.parse_args()

    arq = ITENS / f"{args.item}.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    jp_artigo = d.get("texto_jp") or ""
    pt = d.get("texto_pt") or ""

    if args.pt_ja_traduzido:
        bloco = Path(args.pt_ja_traduzido).read_text(encoding="utf-8").strip()
        print(f"  tradução carregada de {args.pt_ja_traduzido} ({len(bloco)}c)")
    else:
        jp_falta = Path(args.jp_falta).read_text(encoding="utf-8")
        if jp_falta.strip() == "":
            print("  trecho JP vazio; nada a fazer")
            return 1
        bloco = traduzir_trecho(jp_falta)
        Path("/tmp/pt_falta_ultimo.txt").write_text(bloco, encoding="utf-8")

    if args.fim:
        novo = pt.rstrip() + "\n\n" + bloco
        onde = "fim"
    else:
        if not args.ancora:
            print("  é preciso --ancora ou --fim")
            return 2
        n = pt.count(args.ancora)
        if n != 1:
            print(f"  âncora ocorre {n}× (esperado 1); abortado")
            return 3
        i = pt.find(args.ancora)
        novo = pt[:i].rstrip() + "\n\n" + bloco + "\n\n" + pt[i:].lstrip()
        onde = f"antes de {args.ancora[:40]!r}"

    print(f"  PT {len(pt)} -> {len(novo)} (+{len(novo) - len(pt)}) | "
          f"ratio {len(novo) / max(len(jp_artigo), 1):.2f} | inserção: {onde}")

    if args.aplicar:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(arq, BACKUPS / f"{args.item}_lacuna_{stamp}.json")
        d["texto_pt"] = novo
        d.setdefault("reparos", []).append(
            {"tipo": "lacuna_auditoria", "data": stamp, "onde": onde}
        )
        arq.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        print("  gravado")
    else:
        print("  (dry-run; use --aplicar para gravar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
