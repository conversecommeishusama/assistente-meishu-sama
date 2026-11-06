#!/usr/bin/env python3
"""Prepara 6 lotes de auditoria para os agentes Claude, a partir do arquivo
retraducao_gokowa_para_auditoria.json (pares JP/PT alinhados).

Para as falas corrigidas na integração (pontos_problema), substitui o PT pela
versão final integrada no texto publicado.

Saída:
  reports/amostragem_semantica_gokowa/lotes_claude/lote_N.json  (N=1..6)
  reports/amostragem_semantica_gokowa/lotes_claude/prompt_N.md (instruções por lote)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

AUDITORIA = RAIZ / "reports" / "amostragem_semantica_gokowa" / "retraducao_gokowa_para_auditoria.json"
PONTOS = RAIZ / "reports" / "amostragem_semantica_gokowa" / "pontos_problema" / "retraducao_pontos_problema.json"
PUBLICADO = RAIZ / "livros_publicacao_pt_revisado" / "19480101 - Gokōwa-roku (Suplemento).txt"
SAIDA = RAIZ / "reports" / "amostragem_semantica_gokowa" / "lotes_claude"

N_LOTES = 6


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)

    # 1. Carrega auditoria (pares JP/PT)
    aud = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    falas = aud["falas"]
    # falas é dict {str: {...}}
    itens = []
    for k in sorted(falas, key=lambda x: int(x)):
        f = falas[k]
        itens.append({
            "indice": f.get("indice"),
            "quem": f.get("quem"),
            "jp": f.get("jp", ""),
            "pt_retraduzido": f.get("pt_contextual") or f.get("pt") or "",
            "status": f.get("status"),
        })

    # 2. Atualiza PT das falas corrigidas a partir do texto publicado
    texto_pub = PUBLICADO.read_text(encoding="utf-8")
    linhas_pub = texto_pub.splitlines()

    pontos = json.loads(PONTOS.read_text(encoding="utf-8"))
    pontos = [p for p in pontos if p.get("pt_novo")]
    print(f"Pontos corrigidos a aplicar: {len(pontos)}")

    # mapeia indice_jp -> texto corrigido (pt_novo normalizado)
    corrigidos = {}
    for p in pontos:
        idx = str(p.get("indice_jp"))
        corrigidos[idx] = norm(p.get("pt_novo", ""))

    # 3. Divide em 6 lotes
    total = len(itens)
    tam = (total + N_LOTES - 1) // N_LOTES
    lotes = [itens[i:i + tam] for i in range(0, total, tam)]

    # 4. Escreve lotes e prompts
    for n, lote in enumerate(lotes, 1):
        # marcar falas corrigidas
        for it in lote:
            idx = str(it["indice"])
            if idx in corrigidos:
                it["corrigida"] = True
                it["pt_retraduzido"] = corrigidos[idx]
            else:
                it.setdefault("corrigida", False)

        arquivo_lote = SAIDA / f"lote_{n}.json"
        arquivo_lote.write_text(json.dumps({
            "lote": n,
            "total_falas": len(lote),
            "intervalo_indices": [lote[0]["indice"], lote[-1]["indice"]],
            "falas": lote,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        n_corrigidas = sum(1 for it in lote if it["corrigida"])
        print(f"Lote {n}: {len(lote)} falas (índices {lote[0]['indice']}-{lote[-1]['indice']}), corrigidas={n_corrigidas}")

    # 5. Prompt base (mesmo padrão do INSTRUCOES_PARA_CLAUDE.md, ajustado por lote)
    prompt_base = RAIZ / "reports" / "amostragem_semantica_gokowa" / "INSTRUCOES_PARA_CLAUDE.md"
    base = prompt_base.read_text(encoding="utf-8")
    for n in range(1, N_LOTES + 1):
        prompt = SAIDA / f"prompt_{n}.md"
        lote_file = SAIDA / f"lote_{n}.json"
        # reescrever com referência ao arquivo do lote
        texto = (
            "# Auditoria de Tradução — Lote {n}\n\n"
            "Este lote é parte da auditoria do Gokōwa-roku (Suplemento), "
            "dividido em 6 lotes paralelos. Revise APENAS as falas deste lote.\n\n"
            "Arquivo do lote: `lote_{n}.json`\n\n"
            "---\n\n"
        ).format(n=n)
        texto += base
        # corrigir referências ao arquivo único
        texto = texto.replace("retraducao_gokowa_para_auditoria.json", f"lote_{n}.json")
        prompt.write_text(texto, encoding="utf-8")
        print(f"Prompt {n}: {prompt.name}")

    print(f"\nTotal falas: {total} | lotes: {len(lotes)} | por lote: {tam}")


if __name__ == "__main__":
    main()
