#!/usr/bin/env python3
"""Valida o mecanismo de estagnação (§3.9) implementado em
`goshinsho/services/agentic_search.py` -- corta a busca cedo quando N
rodadas consecutivas não trazem nenhum fragmento de texto genuinamente
novo, sem reintroduzir um teto fixo temático.

Disciplina anti-tutela (`feedback_nao_validar_fix_do_bug`): NUNCA validar um
fix só com o caso exato que motivou a correção. Por isso, nesta ordem:

1. Caso A (controle): pergunta claramente ausente do corpus (fora do
   escopo temporal/temático, sem relação com reencarnação/inferno
   animal/espírito secundário) -- esperado: poucas rodadas, sem chegar
   perto do teto de segurança (40), admite não achar.
2. Caso B (controle): tema doutrinário rico, exige busca legítima em
   profundidade -- esperado: o mecanismo de estagnação NÃO deve cortar
   cedo demais; deve continuar enquanto houver conteúdo novo relevante.
3. Só depois: reconfirmar os turnos 3 e 4 originais do piloto v3 (mesma
   sequência de chat), turno 3 exigindo é possível mudar de plano
   espiritual (antes ia até 40 rodadas/125s/$0,204), turno 4 não pode
   regredir (achou tabela completa de correspondência animal/característica
   em 9 rodadas antes desta mudança).

Uso:
    venv/bin/python3 scripts/pilot_agentic_v4_estagnacao.py
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


def rodar_pergunta_isolada(pergunta: str) -> dict:
    t0 = time.time()
    r = responder_agentico_deepseek(pergunta)
    r["tempo_total_script"] = round(time.time() - t0, 1)
    return r


def resumo(r: dict) -> str:
    flags = []
    if r.get("esgotou_orcamento_busca"):
        flags.append("ESGOTOU TETO DE SEGURANÇA (40)")
    if r.get("parou_por_estagnacao"):
        flags.append("PAROU POR ESTAGNAÇÃO")
    if r.get("vazamento_sintaxe_ferramenta"):
        flags.append("VAZAMENTO DE SINTAXE")
    if r.get("citacoes_suspeitas"):
        flags.append(f"CITAÇÕES SUSPEITAS: {r['citacoes_suspeitas']}")
    flag_str = f" [{', '.join(flags)}]" if flags else ""
    return f"{r['rodadas']} rodadas, {r['tempo']}s, ${r['custo']:.5f}{flag_str}"


def main():
    resultado: dict = {"data": time.strftime("%Y-%m-%d %H:%M:%S"), "controles": {}, "turnos_reconfirmados": {}}

    print("=" * 80)
    print("CASO A (controle) -- pergunta claramente ausente do corpus")
    print("=" * 80)
    pergunta_a = "O que Meishu-Sama disse sobre as viagens à Lua e a exploração espacial?"
    print(f"Pergunta: {pergunta_a}")
    r_a = rodar_pergunta_isolada(pergunta_a)
    print(f"  -> {resumo(r_a)}")
    print(f"  Resposta (300 chars): {r_a['resposta'][:300]!r}")
    resultado["controles"]["caso_a_ausente"] = {"pergunta": pergunta_a, **r_a}

    print()
    print("=" * 80)
    print("CASO B (controle) -- tema doutrinário rico, exige busca em profundidade")
    print("=" * 80)
    pergunta_b = "Explique a doutrina de Miroku (五六七) e a chegada da Era de Miroku segundo Meishu-Sama."
    print(f"Pergunta: {pergunta_b}")
    r_b = rodar_pergunta_isolada(pergunta_b)
    print(f"  -> {resumo(r_b)}")
    print(f"  Resposta (300 chars): {r_b['resposta'][:300]!r}")
    resultado["controles"]["caso_b_rico"] = {"pergunta": pergunta_b, **r_b}

    print()
    print("=" * 80)
    print("Reconfirmação dos turnos 3/4 originais (mesma sequência de chat do piloto v3)")
    print("=" * 80)
    perguntas_v3 = [
        "cancer",
        "hora das bruxas ou calada da noite",
        "Segundo Meishu-Sama é possível mudar de plano espiritual na mesma reencarnação?",
        "Meishu-Sama cita no ensinamento sobre o inferno do mundo dos animais que cada um desse inferno vai a pessoa que tem a característica correspondente, seria possível fazer uma correlação dessas características com o espírito secundário daquela pessoa?",
    ]
    historico: list[dict] = []
    turnos = []
    for i, pergunta in enumerate(perguntas_v3, 1):
        print(f"\n[Turno {i}] {pergunta[:70]}")
        r = responder_agentico_deepseek(pergunta, historico)
        print(f"  -> {resumo(r)}")
        if i in (3, 4):
            print(f"  Resposta (400 chars): {r['resposta'][:400]!r}")
        turnos.append({"turno": i, "pergunta": pergunta, **r})
        historico.append({"role": "user", "content": pergunta})
        historico.append({"role": "assistant", "content": r["resposta"]})
    resultado["turnos_reconfirmados"]["sequencia_v3"] = turnos

    out_path = PROJECT_ROOT / "reports" / "agentic_search_orcamento" / "VALIDACAO.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultado salvo em: {out_path}")

    # Checagens automáticas de sanidade (não falha o script, só avisa)
    print()
    print("=" * 80)
    print("Checagens de sanidade")
    print("=" * 80)
    if r_a["rodadas"] < 40 and not r_a.get("esgotou_orcamento_busca"):
        print(f"OK: Caso A não chegou perto do teto de segurança ({r_a['rodadas']} rodadas)")
    else:
        print(f"ATENÇÃO: Caso A usou {r_a['rodadas']} rodadas -- revisar")

    turno3 = turnos[2]
    turno4 = turnos[3]
    if turno3["rodadas"] < 40 and not turno3.get("esgotou_orcamento_busca"):
        print(f"OK: Turno 3 não foi até o teto de segurança ({turno3['rodadas']} rodadas, era 40 antes do fix)")
    else:
        print(f"FALHOU: Turno 3 ainda foi até o teto de segurança ({turno3['rodadas']} rodadas)")
    if turno4["rodadas"] >= 6:
        print(f"OK: Turno 4 continuou buscando em profundidade ({turno4['rodadas']} rodadas, era 9 antes do fix)")
    else:
        print(f"ATENÇÃO: Turno 4 parou cedo demais ({turno4['rodadas']} rodadas) -- pode ter regredido")


if __name__ == "__main__":
    main()
