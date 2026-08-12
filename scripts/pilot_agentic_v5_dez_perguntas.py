#!/usr/bin/env python3
"""Quinta rodada de teste da busca agenciada -- 10 perguntas em sequência
única de chat (mesmo histórico entre uma pergunta e a próxima, tanto para
o agêntico quanto para o pt_direct), comparando DeepSeek agêntico (módulo
real, goshinsho/services/agentic_search.py, já com o novo formato por
tema + citação confirmatória) vs pt_direct (produção, mesmo novo formato
no modo direto).

Perguntas 1-4: mesmas do piloto v3 (câncer, hora das bruxas, plano
espiritual, correlação animal/espírito secundário).

Perguntas 5-10: 6 perguntas historicamente problemáticas, documentadas em
GOSHINSHO.md -- as 4 primeiras (5-8) reproduzem a sequência real que travava
o escopo em conversas longas (trava de escopo corrigida em 2026-07-29);
as últimas 2 (9-10) reproduzem o bug do marcador de fontes estruturado
("me forneça a fonte original na íntegra" puxando ensinamento errado,
também corrigido em 2026-07-29). Testar de novo agora serve para conferir
se o novo formato de resposta (por tema + citação confirmatória) não
reintroduziu nenhum desses problemas.

Uso:
    venv/bin/python3 scripts/pilot_agentic_v5_dez_perguntas.py
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


def responder_pt_direct(pergunta: str, historico: list[dict] | None) -> dict:
    from goshinsho.pipeline.answer import answer
    from goshinsho.services.pt_retrieval import pt_only_pool

    t0 = time.time()
    resp = answer(pergunta, history=historico or [], language="Português", response_mode="direct", base_pool_fn=pt_only_pool)
    tempo = time.time() - t0
    return {"resposta": resp, "tempo": round(tempo, 1)}


PERGUNTAS = [
    "cancer",
    "hora das bruxas ou calada da noite",
    "Segundo Meishu-Sama é possível mudar de plano espiritual na mesma reencarnação?",
    "Meishu-Sama cita no ensinamento sobre o inferno do mundo dos animais que cada um desse inferno vai a pessoa que tem a característica correspondente, seria possível fazer uma correlação dessas características com o espírito secundário daquela pessoa?",
    "as três grandes calamidades e as três pequenas calamidades, na íntegra",
    "clã Yamato",
    "me fale sobre as linhagens espirituais",
    "e a linhagem do sol/lua, que outras linhagens existem?",
    "fale sobre as fazendas modelo de agricultura natural",
    "me forneça a fonte original na íntegra",
]


def main():
    print("=" * 80)
    print("10 perguntas -- sequência única de chat, DeepSeek agêntico vs pt_direct")
    print("=" * 80)

    historico_ds: list[dict] = []
    historico_prod: list[dict] = []
    casos = []

    for i, pergunta in enumerate(PERGUNTAS, 1):
        print(f"\n[Turno {i}] {pergunta}")
        print("-" * 80)

        print("  DeepSeek agêntico...", end=" ", flush=True)
        try:
            r_ds = responder_agentico_deepseek(pergunta, historico_ds)
            flag = ""
            if r_ds.get("esgotou_orcamento_busca"):
                flag += " [ESGOTOU ORÇAMENTO DE BUSCA -> síntese forçada]"
            if r_ds.get("parou_por_estagnacao"):
                flag += " [PAROU POR ESTAGNAÇÃO]"
            if r_ds.get("vazamento_sintaxe_ferramenta"):
                flag += " [VAZAMENTO DE SINTAXE DE FERRAMENTA]"
            if r_ds.get("citacoes_suspeitas"):
                flag += f" [CITAÇÕES SUSPEITAS: {r_ds['citacoes_suspeitas']}]"
            print(f"OK ({r_ds['tempo']}s, {r_ds['rodadas']} rodadas, ${r_ds['custo']:.5f}){flag}")
        except Exception as exc:
            r_ds = {
                "resposta": f"(erro: {exc})",
                "tempo": 0,
                "rodadas": 0,
                "chamadas_ferramenta": [],
                "citacoes_suspeitas": [],
                "esgotou_orcamento_busca": False,
                "parou_por_estagnacao": False,
                "vazamento_sintaxe_ferramenta": False,
                "tokens_entrada": 0,
                "tokens_saida": 0,
                "custo": 0,
                "modelo": "deepseek-v4-flash",
                "truncada": False,
            }
            print(f"ERRO: {exc}")

        print("  pt_direct (produção, novo formato)...", end=" ", flush=True)
        try:
            r_prod = responder_pt_direct(pergunta, historico_prod)
            print(f"OK ({r_prod['tempo']}s)")
        except Exception as exc:
            r_prod = {"resposta": f"(erro: {exc})", "tempo": 0}
            print(f"ERRO: {exc}")

        casos.append({"turno": i, "pergunta": pergunta, "deepseek": r_ds, "pt_direct": r_prod})

        historico_ds.append({"role": "user", "content": pergunta})
        historico_ds.append({"role": "assistant", "content": r_ds["resposta"]})
        historico_prod.append({"role": "user", "content": pergunta})
        historico_prod.append({"role": "assistant", "content": r_prod["resposta"]})

    resultado = {"data": time.strftime("%Y-%m-%d %H:%M:%S"), "casos": casos}
    out_path = PROJECT_ROOT / "reports" / "piloto_agentico_v5_dez_perguntas.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultado salvo em: {out_path}")


if __name__ == "__main__":
    main()
