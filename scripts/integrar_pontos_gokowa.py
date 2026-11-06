#!/usr/bin/env python3
"""Integra os pontos retraduzidos no texto publicado do Gokōwa-roku (Suplemento).

Lê reports/amostragem_semantica_gokowa/pontos_problema/retraducao_pontos_problema.json
e substitui os trechos correspondentes em
livros_publicacao_pt_revisado/19480101 - Gokōwa-roku (Suplemento).txt.

Estratégia: cada ponto tem `pt_atual` (texto atual na publicação) e `pt_novo`
(retradução). Como cada `pt_atual` aparece exatamente 1x no texto publicado,
substituímos por conteúdo. Faz backup antes.

Uso:
    python3 scripts/integrar_pontos_gokowa.py
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

PUBLICADO = RAIZ / "livros_publicacao_pt_revisado" / "19480101 - Gokōwa-roku (Suplemento).txt"
RESULTADOS = RAIZ / "reports" / "amostragem_semantica_gokowa" / "pontos_problema" / "retraducao_pontos_problema.json"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    if not RESULTADOS.exists():
        print(f"❌ Sem resultados: {RESULTADOS}")
        return

    pontos = json.loads(RESULTADOS.read_text(encoding="utf-8"))
    pontos = [p for p in pontos if p.get("pt_novo")]
    print(f"Pontos com retradução: {len(pontos)}")

    texto = PUBLICADO.read_text(encoding="utf-8")
    original = texto

    # backup
    stamp = time.strftime("%Y%m%dT%H%M%SZ")
    backup = PUBLICADO.with_name(PUBLICADO.name + f".bak_integracao_{stamp}")
    shutil.copy2(PUBLICADO, backup)
    print(f"Backup: {backup.name}")

    integrados = 0
    nao_encontrados = 0
    report = []

    for p in pontos:
        nome = p.get("nome", "?")
        pt_atual = p.get("pt_atual") or ""
        pt_novo = p.get("pt_novo") or ""

        if not pt_atual or not pt_novo:
            print(f"  ⚠️ {nome}: sem pt_atual ou pt_novo")
            nao_encontrados += 1
            continue

        n_pt_atual = norm(pt_atual)
        n_pt_novo = norm(pt_novo)

        # ocorrência bruta no texto
        ocorr_bruta = texto.count(pt_atual)
        if ocorr_bruta == 1:
            texto = texto.replace(pt_atual, pt_novo)
            integrados += 1
            report.append((nome, "raw", pt_atual[:60]))
            print(f"  ✅ {nome}: substituído (raw)")
            continue
        if ocorr_bruta > 1:
            print(f"  ⚠️ {nome}: {ocorr_bruta} ocorrências brutas — pulado")
            nao_encontrados += 1
            continue

        # não achou bruto: tentar por linha normalizada
        lines = texto.splitlines(keepends=True)
        alvo = None
        for i, ln in enumerate(lines):
            if n_pt_atual in norm(ln):
                alvo = i
                break
        if alvo is None:
            print(f"  ❌ {nome}: não encontrado")
            nao_encontrados += 1
            continue

        linha = lines[alvo]
        n_linha = norm(linha)
        if n_linha == n_pt_atual:
            lines[alvo] = pt_novo.rstrip("\n") + "\n"
        else:
            if pt_atual in linha:
                lines[alvo] = linha.replace(pt_atual, pt_novo)
            else:
                print(f"  ⚠️ {nome}: corresponde normalizado mas não bruto — revisão")
                nao_encontrados += 1
                continue
        texto = "".join(lines)
        integrados += 1
        report.append((nome, "line", pt_atual[:60]))
        print(f"  ✅ {nome}: substituído (linha {alvo+1})")

    PUBLICADO.write_text(texto, encoding="utf-8")

    print("\n=== Resumo ===")
    print(f"Integrados: {integrados} | Não encontrados: {nao_encontrados}")
    print(f"Tamanho antes: {len(original)} | depois: {len(texto)}")

    rel = RAIZ / "reports" / "amostragem_semantica_gokowa" / "pontos_problema" / f"integracao_relatorio_{stamp}.json"
    rel.write_text(json.dumps({"integrados": integrados, "nao_encontrados": nao_encontrados, "itens": report},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Relatório: {rel}")


if __name__ == "__main__":
    main()
