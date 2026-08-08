#!/usr/bin/env python3
"""Dois testes de diálogo multi-turno pedidos pelo usuário em 2026-07-18:
1. Conversa nova sobre oferendas ao Ohikari (3 perguntas interligadas,
   assunto nunca testado nesta sessão).
2. As reproduções do bug "na íntegra" já feitas manualmente ao longo da
   sessão (assuntos variados: agricultura natural, Johrei, câncer),
   reunidas aqui pra registro/dashboard.
Roda pt_first e pt_direct nos dois.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from goshinsho.pipeline.answer import answer as answer_v2  # noqa: E402
from goshinsho.services.pt_retrieval import pt_only_pool  # noqa: E402
from goshinsho.services.conversation_context import strip_source_marker  # noqa: E402

CONVERSAS = {
    "oferendas": [
        "O que Meishu-Sama fala sobre as oferendas para a Imagem da Luz Divina?",
        "O que ele acha de oferecer água, sal e arroz lavado?",
        "Qual seria a oferenda ideal?",
    ],
    "na_integra_agricultura": [
        "Quais são as fazendas modelo de agricultura natural que Meishu-Sama estabeleceu?",
        "Me forneça a fonte original na íntegra",
    ],
    "na_integra_johrei": [
        "O que é o Johrei?",
        "Me forneça a fonte original na íntegra",
    ],
    "na_integra_cancer": [
        "Meishu-Sama fala sobre câncer?",
        "Me forneça a fonte original na íntegra",
    ],
}

MODES = [
    ("pt_first", None),
    ("pt_direct", pt_only_pool),
]


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "reports" / "resultado_dialogo_ofertas_e_na_integra.json"
    data: dict = {}
    for nome_conversa, perguntas in CONVERSAS.items():
        data[nome_conversa] = {}
        for nome_modo, pool_fn in MODES:
            history: list[dict] = []
            turnos = []
            for idx, pergunta in enumerate(perguntas, start=1):
                t0 = time.perf_counter()
                try:
                    resposta = answer_v2(pergunta, history, language="Português", base_pool_fn=pool_fn)
                    elapsed = round(time.perf_counter() - t0, 1)
                    limpa = strip_source_marker(resposta)
                    turnos.append({"turno": idx, "pergunta": pergunta, "resposta": limpa, "elapsed_s": elapsed})
                except Exception as exc:  # noqa: BLE001
                    elapsed = round(time.perf_counter() - t0, 1)
                    resposta = ""
                    limpa = ""
                    turnos.append({"turno": idx, "pergunta": pergunta, "erro": str(exc), "elapsed_s": elapsed})
                print(f"[{nome_conversa}/{nome_modo}] turno {idx}/{len(perguntas)}: {elapsed}s", flush=True)
                history.append({"role": "user", "content": pergunta})
                history.append({"role": "assistant", "content": resposta})
            data[nome_conversa][nome_modo] = turnos
        Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"gravado em {out_path}")


if __name__ == "__main__":
    main()
