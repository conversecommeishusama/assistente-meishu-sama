#!/usr/bin/env python3
"""Redivide o Eiko.txt (fonte de verdade atualizada) nos 3 volumes (25/26/27).

Proposta confirmada pelo usuário (2026-08-14): divisão por ANO da Era Showa,
sem dividir nenhum ano entre volumes, equilibrando o tamanho (~1/3 cada):

  Volume I   -> anos 15, 24, 25, 26   (~124 artigos, ~527k chars)
  Volume II  -> ano 27                 (~127 artigos, ~555k chars)
  Volume III -> anos 28, 29            (~118 artigos, ~556k chars)

Os artigos são extraídos do Eiko.txt (livros_publicacao_pt_revisado), agrupados
por ano, e cada volume é montado mantendo a ORDEM ORIGINAL dos artigos dentro
do arquivo-fonte. Depois reescreve os MANIFESTO.json dos 3 volumes com as novas
datas/caracteres.

Uso:
    python3 scripts/redividir_eiko.py            # executa
    python3 scripts/redividir_eiko.py --dry-run  # só mostra
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path("/var/www/goshinsho")
EIKO_FONTE = ROOT / "livros_publicacao_pt_revisado" / "Eiko.txt"
PUB = ROOT / "publicacao_livros"

# Mapeamento volume -> anos (proposta confirmada)
DIVISAO = {
    "25_Eiko__Volume_I": {15, 24, 25, 26},
    "26_Eiko__Volume_II": {27},
    "27_Eiko__Volume_III": {28, 29},
}


def extrair_artigos() -> list[dict]:
    """Extrai artigos do Eiko.txt: cada um com número, ano, e conteúdo."""
    texto = EIKO_FONTE.read_text(encoding="utf-8")
    linhas = texto.splitlines()

    artigos = []
    inicio_atual = None
    num_atual = None
    ano_atual = None

    def _buscar_ano(linha: str) -> int | None:
        m = re.search(r"ano (\d+) da Era Showa", linha)
        if m:
            return int(m.group(1))
        # formato "26º ano" (ordinal)
        m = re.search(r"(\d+)[º°] ano", linha)
        if m:
            return int(m.group(1))
        return None

    for i, linha in enumerate(linhas):
        m = re.match(r"^Eik[oō] nº (\d+)", linha)
        if m:
            if inicio_atual is not None:
                conteudo = "\n".join(linhas[inicio_atual:i])
                artigos.append({
                    "num": num_atual,
                    "ano": ano_atual,
                    "conteudo": conteudo,
                    "tamanho": len(conteudo),
                })
            inicio_atual = i
            num_atual = int(m.group(1))
            ano_atual = _buscar_ano(linha)
            # busca o ano nas primeiras linhas do artigo se não estiver no título
            if ano_atual is None:
                for j in range(i, min(i + 8, len(linhas))):
                    ano_atual = _buscar_ano(linhas[j])
                    if ano_atual is not None:
                        break
    # último artigo
    if inicio_atual is not None:
        conteudo = "\n".join(linhas[inicio_atual:])
        artigos.append({
            "num": num_atual,
            "ano": ano_atual,
            "conteudo": conteudo,
            "tamanho": len(conteudo),
        })
    return artigos


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    artigos = extrair_artigos()
    print(f"Eiko.txt: {len(artigos)} artigos extraídos")

    # Artigos sem ano identificado
    sem_ano = [a for a in artigos if a["ano"] is None]
    if sem_ano:
        print(f"⚠️  {len(sem_ano)} artigos sem ano identificado (serão colocados no Volume I):")
        for a in sem_ano:
            print(f"    nº {a['num']}: {a['conteudo'].splitlines()[0][:60]}")

    # Agrupar por ano (ordem de aparição preservada)
    for vol_nome, anos in DIVISAO.items():
        selecionados = [a for a in artigos if (a["ano"] in anos)]
        # artigos sem ano -> Volume I (com anos 15-26, período inicial)
        if "25_Eiko__Volume_I" == vol_nome:
            selecionados = [a for a in artigos if (a["ano"] is None or a["ano"] in anos)]
        # ordenar pela ordem do arquivo original (índice de aparição)
        ordem = {id(a): idx for idx, a in enumerate(artigos)}
        selecionados.sort(key=lambda a: ordem[id(a)])

        conteudo_total = "\n\n".join(a["conteudo"] for a in selecionados)
        chars = sum(a["tamanho"] for a in selecionados)
        print(f"\n{vol_nome}: {len(selecionados)} artigos, {chars:,} chars")
        anos_contidos = sorted({a["ano"] for a in selecionados if a["ano"] is not None})
        print(f"  anos: {anos_contidos}")

        if dry_run:
            continue

        vol_dir = PUB / vol_nome
        vol_dir.mkdir(parents=True, exist_ok=True)
        destino = vol_dir / "01_Eiko.txt"
        destino.write_text(conteudo_total + "\n", encoding="utf-8")

        # Atualizar MANIFESTO
        mf = vol_dir / "MANIFESTO.json"
        if mf.exists():
            data = json.loads(mf.read_text(encoding="utf-8"))
            data["arquivos"] = [{
                "arquivo_destino": "01_Eiko.txt",
                "fonte": "livros_publicacao_pt_revisado/Eiko.txt (redivisão por ano)",
                "caracteres": chars,
            }]
            data["caracteres_totais"] = chars
            data["nota"] = f"Redivisão por ano da Era Showa ({anos_contidos[0]}-{anos_contidos[-1]}) — proposta confirmada 2026-08-14"
            mf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if dry_run:
        print("\n(dry-run — sem --dry-run para executar)")
    else:
        print("\nRedivisão Eiko concluída.")


if __name__ == "__main__":
    main()
