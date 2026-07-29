#!/usr/bin/env python3
"""Segunda rodada de teste da busca agenciada -- agora usando o módulo real
`goshinsho/services/agentic_search.py` (não mais o protótipo isolado do
piloto original, `pilot_agentic_claude.py`), para confirmar que os 2 bugs
mais sérios do estudo (`docs/13-ESTUDO-MIGRACAO-BUSCA-AGENTICA.md`) foram
corrigidos:

- §3.3: "cancer" (sem acento) não deve mais jogar a busca para um canto
  errado do acervo -- deve achar a mesma definição teológica que "câncer"
  (com acento) acha.
- §3.2: "quem é Meishu-Sama?" (pergunta ampla que esgotou o orçamento de
  rodadas de ferramenta no piloto original, gerando resposta vazia) deve
  agora sempre sintetizar algo, nunca voltar vazia.

Também roda o lote 1 (calamidades -> Yamato -> linhagens -> sol/lua) para
confirmar que a continuidade de conversa e o recall da 3ª linhagem
(Izunome, achado real do piloto original que o pt_direct errou) continuam
funcionando com o módulo real. Só DeepSeek (modelo decidido) vs pt_direct
(produção) -- Sonnet/Haiku já foram validados no piloto original, não
precisam ser testados de novo aqui.

Uso:
    venv/bin/python3 scripts/pilot_agentic_v2.py
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

from goshinsho.services.agentic_search import responder_agentico_deepseek, responder_agentico_deepseek_jp


def responder_pt_direct(pergunta: str, historico: list[dict] | None) -> dict:
    from goshinsho.pipeline.answer import answer
    from goshinsho.services.pt_retrieval import pt_only_pool

    t0 = time.time()
    resp = answer(pergunta, history=historico or [], language="Português", response_mode="direct", base_pool_fn=pt_only_pool)
    tempo = time.time() - t0
    return {"resposta": resp, "tempo": round(tempo, 1)}


def responder_jp_direct(pergunta: str, historico: list[dict] | None) -> dict:
    """Mesma convenção já usada em `benchmark_dialogo_multiturno.py`/
    `benchmark_dialogo_topico_fora.py`: jp_direct busca no acervo japonês
    original, mas responde em português (para comparação direta com o
    texto do agêntico-jp, que também responde em português)."""
    from goshinsho.pipeline.answer import answer
    from goshinsho.services.jp_retrieval import jp_only_pool

    t0 = time.time()
    resp = answer(pergunta, history=historico or [], language="Português", response_mode="direct", base_pool_fn=jp_only_pool)
    tempo = time.time() - t0
    return {"resposta": resp, "tempo": round(tempo, 1)}


# Validação por classe geral do bug, NÃO pelo exemplo específico relatado no
# estudo (regra do projeto: nunca validar um fix só com o próprio caso do
# bug -- isso não prova a classe geral, e no caso do §3.3 corre o risco real
# de parecer "tutela" por termo específico). Cada par abaixo é análogo ao
# achado original, mas sobre um termo/tema diferente e sem relação com ele.
LOTE_0_VALIDACAO_GERAL = [
    "oracao",  # §3.3, classe geral: falta de acento não pode jogar a busca para um canto errado do acervo (par de controle, não o exemplo do estudo)
    "fale sobre a origem e o significado do Johrei",  # §3.2, classe geral: pergunta ampla/doutrinária que convida busca extensa, não pode esgotar o orçamento sem sintetizar
]

# Confirmação final, só depois da validação geral acima -- agora sim o
# exemplo literal relatado no estudo, só para fechar o caso específico.
LOTE_0_CONFIRMACAO_CASO_ORIGINAL = [
    "cancer",
    "quem é Meishu-Sama?",
]

# Lote 1: sequência que testava a trava de escopo (já corrigida em sessão
# anterior) e o gap de recall real (Izunome) do pt_direct.
LOTE_1_CONTINUIDADE = [
    "as três grandes calamidades e as três pequenas calamidades na íntegra",
    "clã Yamato",
    "me fale sobre as linhagens espirituais",
    "e a linhagem do sol/lua, que outras linhagens existem?",
]

# Lote JP: cobre o item explicitamente não testado no estudo original
# (§4 -- "jp_direct... não foi tocado nem testado com busca agenciada").
# Temas diferentes dos já usados nos lotes PT acima (sem reaproveitar
# nenhum exemplo já testado, mesma disciplina anti-tutela).
LOTE_2_JP_ISOLADO = [
    "o que é o Ohikari e como ele deve ser recebido?",
    "fale sobre os fundamentos da agricultura natural",
]
LOTE_3_JP_CONTINUIDADE = [
    "o que Meishu-Sama ensina sobre a arte do Sumi-e?",
    "e qual a relação disso com a prática espiritual?",
]


def rodar_lote(nome_lote: str, perguntas: list[str], *, responder_agente, responder_producao, nome_producao: str) -> list[dict]:
    print("=" * 80)
    print(f"LOTE: {nome_lote}")
    print("=" * 80)
    historico_ds: list[dict] = []
    historico_prod: list[dict] = []
    casos = []

    for i, pergunta in enumerate(perguntas, 1):
        print(f"\n[Turno {i}] {pergunta}")
        print("-" * 80)

        print("  DeepSeek agêntico...", end=" ", flush=True)
        try:
            r_ds = responder_agente(pergunta, historico_ds)
            flag = ""
            if r_ds["esgotou_orcamento_busca"]:
                flag += " [ESGOTOU ORÇAMENTO DE BUSCA -> síntese forçada]"
            if r_ds.get("vazamento_sintaxe_ferramenta"):
                flag += " [VAZAMENTO DE SINTAXE DE FERRAMENTA]"
            if r_ds["citacoes_suspeitas"]:
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
                "tokens_entrada": 0,
                "tokens_saida": 0,
                "custo": 0,
                "modelo": "deepseek-v4-flash",
                "truncada": False,
            }
            print(f"ERRO: {exc}")

        print(f"  {nome_producao} (produção atual)...", end=" ", flush=True)
        r_prod = responder_producao(pergunta, historico_prod)
        print(f"OK ({r_prod['tempo']}s)")

        casos.append({"turno": i, "pergunta": pergunta, "deepseek": r_ds, nome_producao: r_prod})

        historico_ds.append({"role": "user", "content": pergunta})
        historico_ds.append({"role": "assistant", "content": r_ds["resposta"]})
        historico_prod.append({"role": "user", "content": pergunta})
        historico_prod.append({"role": "assistant", "content": r_prod["resposta"]})

    return casos


def main():
    resultados = {"data": time.strftime("%Y-%m-%d %H:%M:%S"), "lotes": {}}
    resultados["lotes"]["validacao_geral"] = rodar_lote(
        "Validação por classe geral (não o exemplo do bug)", LOTE_0_VALIDACAO_GERAL,
        responder_agente=responder_agentico_deepseek, responder_producao=responder_pt_direct, nome_producao="pt_direct",
    )
    resultados["lotes"]["confirmacao_caso_original"] = rodar_lote(
        "Confirmação final (caso original do estudo)", LOTE_0_CONFIRMACAO_CASO_ORIGINAL,
        responder_agente=responder_agentico_deepseek, responder_producao=responder_pt_direct, nome_producao="pt_direct",
    )
    resultados["lotes"]["continuidade"] = rodar_lote(
        "Continuidade de conversa + recall Izunome", LOTE_1_CONTINUIDADE,
        responder_agente=responder_agentico_deepseek, responder_producao=responder_pt_direct, nome_producao="pt_direct",
    )
    resultados["lotes"]["jp_isolado"] = rodar_lote(
        "JP -- busca agenciada no acervo japonês original vs jp_direct", LOTE_2_JP_ISOLADO,
        responder_agente=responder_agentico_deepseek_jp, responder_producao=responder_jp_direct, nome_producao="jp_direct",
    )
    resultados["lotes"]["jp_continuidade"] = rodar_lote(
        "JP -- continuidade de conversa vs jp_direct", LOTE_3_JP_CONTINUIDADE,
        responder_agente=responder_agentico_deepseek_jp, responder_producao=responder_jp_direct, nome_producao="jp_direct",
    )

    out_path = PROJECT_ROOT / "reports" / "piloto_agentico_v2_pos_correcoes.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultado salvo em: {out_path}")


if __name__ == "__main__":
    main()
