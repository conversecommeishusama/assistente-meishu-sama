#!/usr/bin/env python3
"""Valida a exceção controlada adicionada à regra 10 (`SYSTEM_PROMPT`/
`SYSTEM_PROMPT_JP` em `goshinsho/services/agentic_search.py`, sessão
2026-07-30): quando dois trechos de arquivos diferentes parecem
conflitantes mas nenhum afirma o limite de escopo que os reconciliaria,
o modelo pode oferecer essa reconciliação, DEPOIS de separar os temas,
rotulada como "Inferência:" -- nunca fundida com a explicação.

Disciplina anti-tutela: controle primeiro (caso câncer, onde NÃO deve
haver reconciliação nem elo -- nenhum dos trechos deixa um "gap" de
escopo que sustente isso), caso-alvo por último (plano espiritual --
o motivo real da mudança).

Uso:
    venv/bin/python3 scripts/pilot_agentic_v6_excecao_reconciliacao.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import os

os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv()

from goshinsho.services.agentic_search import responder_agentico_deepseek


def rodar(pergunta: str) -> dict:
    t0 = time.time()
    r = responder_agentico_deepseek(pergunta)
    r["tempo_total_script"] = round(time.time() - t0, 1)
    return r


def resumo(r: dict) -> str:
    flags = []
    if r.get("esgotou_orcamento_busca"):
        flags.append("ESGOTOU TETO DE SEGURANÇA")
    if r.get("parou_por_estagnacao"):
        flags.append("PAROU POR ESTAGNAÇÃO")
    if r.get("vazamento_sintaxe_ferramenta"):
        flags.append("VAZAMENTO DE SINTAXE")
    if r.get("citacoes_suspeitas"):
        flags.append(f"CITAÇÕES SUSPEITAS: {r['citacoes_suspeitas']}")
    return (
        f"  rodadas={r.get('rodadas_busca')} tempo={r.get('tempo_total_script')}s "
        f"custo=${r.get('custo', 0):.4f} flags={flags or 'nenhuma'}"
    )


def main() -> None:
    resultados = {}

    print("=== CONTROLE: câncer (não deve haver reconciliação/elo -- regra 10 continua proibindo fusão) ===")
    r_controle = rodar(
        "É verdade que o câncer verdadeiro tem origem espiritual E também é causado pela toxina da carne animal? "
        "Como essas duas explicações se relacionam?"
    )
    print(resumo(r_controle))
    print(r_controle["resposta"])
    print()
    resultados["controle_cancer"] = r_controle

    print("=== ALVO: mudar de plano espiritual na mesma reencarnação ===")
    r_alvo = rodar("Segundo Meishu-Sama é possível mudar de plano espiritual na mesma reencarnação?")
    print(resumo(r_alvo))
    print(r_alvo["resposta"])
    print()
    resultados["alvo_plano_espiritual"] = r_alvo

    out_path = PROJECT_ROOT / "reports" / "piloto_agentico_v6_excecao_reconciliacao.json"
    out_path.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Salvo em {out_path}")


if __name__ == "__main__":
    main()
