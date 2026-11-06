#!/usr/bin/env python3
"""Retraduz APENAS as falas novas (respostas perdidas) dos Mioshie.

Motivação: o extrator corrigido (extrair_falas_mioshie) agora captura as
respostas do Meishu-Sama que o bug anterior descartava. As perguntas
(Interlocutor) já estão traduzidas no checkpoint. Este script:

1. Extrai falas com o extrator CORRIGIDO.
2. Identifica quais falas ainda NÃO têm pt_contextual no checkpoint (novas).
3. Agrupa SÓ as novas em trechos de ~2000 chars.
4. Retraduz (2 etapas: contínua + rotulação) com o executor.
5. Mescla no checkpoint, PRESERVANDO as falas já traduzidas.

Uso:
  .venv/bin/python scripts/retraduzir_respostas_mioshie.py <arquivo_jp>
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

from retraduzir_colecao import extrair_falas_mioshie  # noqa: E402
from retraduzir_trechos import (  # noqa: E402
    agrupar_em_trechos,
    montar_trecho,
    montar_trecho_rotulado,
    traduzir_continuo,
    rotular_falas,
    relatorio_glossario_falas,
    adquirir_lock,
    liberar_lock,
)

OUT = RAIZ / "reports" / "retraducao_colecoes"
LIMITE_TRECHO = 2000


def norm(s: str) -> str:
    s = re.sub(r"（[^）]{1,120}）", " ", s)
    return re.sub(r"[\s、]", "", s)


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: .venv/bin/python scripts/retraduzir_respostas_mioshie.py <arquivo_jp>")
        return 1
    arquivo = sys.argv[1]
    arq_path = Path(arquivo)

    if not adquirir_lock(arq_path):
        print(f"[{arq_path.name}] LOCK: outro processo está processando — saindo")
        return 0

    texto = arq_path.read_text(encoding="utf-8")
    falas = extrair_falas_mioshie(texto)  # extrator CORRIGIDO
    ckpt = OUT / f"{arq_path.stem}.json"

    dados = {}
    if ckpt.exists():
        try:
            dados = json.loads(ckpt.read_text(encoding="utf-8"))
        except Exception:
            dados = {}
    if "falas" not in dados:
        dados["falas"] = {}

    # Mapa de JP já traduzidos (normalizado -> chave)
    ck_jps = {}
    for k, v in dados["falas"].items():
        if isinstance(v, dict) and v.get("pt_contextual"):
            ck_jps[norm(v.get("jp", ""))] = k

    # Identificar falas novas (sem tradução no checkpoint)
    novas_indices = []
    for i, (quem, jp) in enumerate(falas):
        chave = norm(jp)
        casa = any(chave[:25] in cj or cj[:25] in chave for cj in ck_jps)
        if not casa:
            novas_indices.append(i)

    if not novas_indices:
        print(f"[{arq_path.name}] nenhuma fala nova — arquivo já íntegro")
        liberar_lock(arq_path)
        return 0

    # Agrupar SÓ as novas em trechos
    falas_novas = [(falas[i][0], falas[i][1]) for i in novas_indices]
    trechos_novos = agrupar_em_trechos(falas_novas, limite=LIMITE_TRECHO)
    print(f"[{arq_path.name}] {len(falas)} falas totais | {len(novas_indices)} novas "
          f"→ {len(trechos_novos)} trechos")

    # Mapear índices novos -> posição no falas_novas
    idx_novo_para_fala = {n: novas_indices[n] for n in range(len(novas_indices))}

    for n_trecho, indices_rel in enumerate(trechos_novos):
        indices_abs = [idx_novo_para_fala[n] for n in indices_rel]
        print(f"  [trecho {n_trecho+1}/{len(trechos_novos)}] falas {indices_abs[0]}-"
              f"{indices_abs[-1]} ({len(montar_trecho(falas_novas, indices_rel))} chars)...",
              flush=True)
        inicio = time.time()

        pt_continuo = traduzir_continuo(falas_novas, indices_rel)
        if not pt_continuo:
            print(f"    ERRO: tradução contínua falhou — pulando trecho", flush=True)
            continue

        trecho_str = montar_trecho(falas_novas, indices_rel)
        traducoes = rotular_falas(trecho_str, pt_continuo, indices_rel)
        if traducoes is None:
            print(f"    ERRO: rotulação falhou — pulando trecho", flush=True)
            continue

        relatorio = relatorio_glossario_falas(falas_novas, indices_rel, traducoes)
        for n, i_abs in zip(indices_rel, indices_abs):
            dados["falas"][str(i_abs)] = {
                "indice": i_abs,
                "quem": falas[i_abs][0],
                "jp": falas[i_abs][1],
                "pt_contextual": traducoes.get(str(n), ""),
                "status": "retraduzido",
                "trecho": n_trecho,
            }
        dados.setdefault("relatorios_glossario", {})[str(n_trecho)] = relatorio
        tempo = time.time() - inicio
        OUT.mkdir(parents=True, exist_ok=True)
        ckpt.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    -> {tempo:.1f}s | {len(indices_abs)} falas | rel. glossário: {len(relatorio)}",
              flush=True)

    n_ok = sum(1 for f in dados["falas"].values() if isinstance(f, dict) and f.get("pt_contextual"))
    print(f"[{arq_path.stem}] {n_ok}/{len(falas)} falas com pt_contextual")
    liberar_lock(arq_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
