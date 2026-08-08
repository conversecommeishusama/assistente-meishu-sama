#!/usr/bin/env python3
"""Teste de diálogo multi-turno com MUDANÇA DE ASSUNTO no meio -- pedido do
usuário em 2026-07-26 para verificar se uma pergunta genuinamente fora do
tema (não relacionada às perguntas anteriores da mesma conversa) ainda
consegue recuperar os trechos certos, ou se o histórico da conversa
"puxa" a busca para o assunto anterior. Roda pt_direct e jp_direct -- os
dois modos realmente em produção (pt_first foi descontinuado em 2026-07-26,
não testar mais) -- na MESMA sequência de turnos, histórico isolado por modo.

Uso: python3 scripts/benchmark_dialogo_topico_fora.py <saida.json>
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
from goshinsho.services.jp_retrieval import jp_only_pool  # noqa: E402

TURNOS = [
    "O que é Johrei?",
    "Como ele é aplicado na prática?",
    "Mudando de assunto: o que Meishu-Sama ensina sobre a arte e sua importância espiritual?",
    "E quanto à pintura Sumi-e especificamente?",
    "Voltando ao Johrei: existe alguma contraindicação?",
    "Pode resumir tudo que conversamos até agora nesta conversa?",
]

MODES = [
    ("pt_direct", pt_only_pool),
    ("jp_direct", jp_only_pool),
]


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "reports" / "resultado_dialogo_topico_fora.json"
    data = {}
    for nome, pool_fn in MODES:
        history: list[dict] = []
        turnos_resultado = []
        for idx, pergunta in enumerate(TURNOS, start=1):
            t0 = time.perf_counter()
            try:
                resposta = answer_v2(pergunta, history, language="Português", base_pool_fn=pool_fn)
                elapsed = round(time.perf_counter() - t0, 1)
                turnos_resultado.append({"turno": idx, "pergunta": pergunta, "resposta": resposta, "elapsed_s": elapsed})
            except Exception as exc:  # noqa: BLE001
                elapsed = round(time.perf_counter() - t0, 1)
                resposta = ""
                turnos_resultado.append({"turno": idx, "pergunta": pergunta, "erro": str(exc), "elapsed_s": elapsed})
            print(f"[{nome}] turno {idx}/{len(TURNOS)}: {elapsed}s", flush=True)
            history.append({"role": "user", "content": pergunta})
            history.append({"role": "assistant", "content": resposta})
        data[nome] = turnos_resultado
        Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"gravado em {out_path}")


if __name__ == "__main__":
    main()
