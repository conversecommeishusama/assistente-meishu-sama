#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Insere as traduções dos periódicos (Meishu-Sama) no acervo PT.

Fonte : reports/traducao_periodicos/itens/*.json (415 artigos traduzidos)
Destino: textos_portugues/{Tijotengoku,Hikari,Eiko,Kyusei}.txt

Regras:
  - backup timestamped de cada .txt antes de escrever;
  - dedup por título (linha exata normalizada já presente no acervo → pula);
  - limpa títulos poluídos (nota "(Explicação: ...)" embutida → fica só a 1ª linha);
  - ordena por (ano, numero, ordem) dentro de cada veículo;
  - anexa ao fim, no formato: título \\n\\n fonte \\n\\n corpo.

Uso:
    .venv/bin/python scripts/inserir_periodicos_traduzidos.py [--dry-run]
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
ACERVO = RAIZ / "textos_portugues"

VEICULOS = ["Tijotengoku", "Hikari", "Eiko", "Kyusei"]

DRY = "--dry-run" in sys.argv


def norm(s: str) -> str:
    return re.sub(r"[\s\u3000]+", "", (s or "")).lower()


def _int(v, default=0):
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return default


def titulo_limpo(t: str) -> str:
    """Remove cauda de explicação/nota embutida no título (fica só a 1ª linha)."""
    return re.split(r"\n+", (t or "").strip(), maxsplit=1)[0].strip()


def main() -> None:
    itens = [json.load(open(f, encoding="utf-8")) for f in sorted(ITENS.glob("*.json"))]
    ts = datetime.now().strftime("%Y%m%dT%H%M%SZ")

    total_inseridos = 0
    total_pulados = 0

    for veiculo in VEICULOS:
        path = ACERVO / f"{veiculo}.txt"
        acervo = path.read_text(encoding="utf-8")
        linhas_existentes = {norm(l) for l in acervo.splitlines() if l.strip()}

        grupo = [d for d in itens if d.get("veiculo") == veiculo]
        grupo.sort(key=lambda d: (_int(d.get("ano")), _int(d.get("numero")), _int(d.get("ordem"))))

        blocos = []
        pulados = []
        for d in grupo:
            t = titulo_limpo(d.get("titulo_pt"))
            if norm(t) in linhas_existentes:
                pulados.append((d.get("numero"), d.get("ordem"), t))
                continue
            fonte = (d.get("fonte_pt") or "").strip() or f"{veiculo} ({d.get('ano')})"
            corpo = (d.get("texto_pt") or "").strip()
            blocos.append(f"{t}\n\n{fonte}\n\n{corpo}")

        if not blocos:
            print(f"{veiculo}: 0 novos (0 a inserir, {len(pulados)} pulados)")
            continue

        novo_txt = acervo.rstrip("\n") + "\n\n" + "\n\n".join(blocos) + "\n"

        if DRY:
            print(f"[DRY] {veiculo}: +{len(blocos)} artigos (pulados={len(pulados)}) → {path}")
        else:
            shutil.copy2(path, f"{path}.bak_insercao_periodicos_{ts}")
            path.write_text(novo_txt, encoding="utf-8")
            print(f"{veiculo}: +{len(blocos)} artigos | pulados={len(pulados)} | backup={path.name}.bak_insercao_periodicos_{ts}")

        total_inseridos += len(blocos)
        total_pulados += len(pulados)

    print(f"\nTOTAL: {total_inseridos} inseridos, {total_pulados} pulados (já presentes)")


if __name__ == "__main__":
    main()
