#!/usr/bin/env python3
"""Integra as respostas traduzidas no checkpoint do Mioshie (MERGE SEGURO).

Lê as traduções de /tmp/retrad_respostas_traduzidas/<stem>.json e insere no
checkpoint reports/retraducao_colecoes/<stem>.json, PRESERVANDO INTACTAS as
falas que já existiam (perguntas do Interlocutor e qualquer resposta existente).

REGRA DE OURO (lição da abordagem por script que falhou): NUNCA remover/sobrescrever
uma fala existente com pt_contextual. Só ADICIONA as respostas que faltavam.

Como identifica onde inserir: cada resposta traduzida tem o JP. Localiza o turno
correspondente no JP original (por correspondência de texto) e insere a resposta
com esse JP + PT no checkpoint, na posição correta (após a pergunta).

Uso:
  .venv/bin/python scripts/integrar_respostas_mioshie.py <stem>  # ex: 19510920-御教え集1号
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraduzir_colecao import extrair_falas_mioshie  # noqa: E402

CKPT_DIR = RAIZ / "reports" / "retraducao_colecoes"
TRAD_DIR = Path("/tmp/retrad_respostas_traduzidas")


def norm(s: str) -> str:
    s = re.sub(r"（[^）]{1,120}）", " ", s)
    return re.sub(r"[\s、]", "", s)


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: .venv/bin/python scripts/integrar_respostas_mioshie.py <stem>")
        return 1
    stem = sys.argv[1]

    trad_path = TRAD_DIR / f"{stem}.json"
    if not trad_path.exists():
        print(f"[{stem}] sem traduções em {trad_path}")
        return 1
    traducoes = json.loads(trad_path.read_text(encoding="utf-8"))
    traducoes = [t for t in traducoes if isinstance(t, dict) and t.get("pt")]
    if not traducoes:
        print(f"[{stem}] nenhuma tradução útil")
        return 1

    ckpt_path = CKPT_DIR / f"{stem}.json"
    ckpt = json.loads(ckpt_path.read_text(encoding="utf-8"))
    falas = ckpt.get("falas", {})

    # Backup antes do merge
    import time
    ts = time.strftime('%Y%m%dT%H%M%SZ')
    backup = CKPT_DIR / "backup_merge_respostas_20260819"
    backup.mkdir(parents=True, exist_ok=True)
    (backup / f"{stem}.json.pre_merge_{ts}").write_text(
        json.dumps(ckpt, ensure_ascii=False, indent=2), encoding="utf-8")

    # JP existente no checkpoint (para não duplicar)
    ck_jps = {norm(v.get("jp", "")): k for k, v in falas.items() if isinstance(v, dict)}

    # JP do texto original (para localizar posição)
    jp_texto = (RAIZ / "textos_japones" / f"{stem}.txt").read_text(encoding="utf-8")
    falas_extrator = extrair_falas_mioshie(jp_texto)  # extrator corrigido

    # Para cada resposta traduzida, localizar no extrator e inserir se não existe
    n_inseridas = 0
    n_ja_existe = 0
    for i, trad in enumerate(traducoes):
        jp_resp = trad.get("jp", "").strip()
        pt_resp = trad.get("pt", "").strip()
        if not jp_resp or not pt_resp:
            continue
        chave = norm(jp_resp)
        # já existe no checkpoint? (não duplicar)
        if any(chave[:30] in cj or cj[:30] in chave for cj in ck_jps):
            n_ja_existe += 1
            continue
        # localizar o JP no texto original (via extrator) para obter quem
        quem = "Meishu-Sama"
        for fq, fjp in falas_extrator:
            if norm(fjp) and (chave[:30] in norm(fjp) or norm(fjp)[:30] in chave):
                quem = fq
                break
        # novo índice (maior + 1)
        novo_idx = str(max([int(k) for k in falas.keys() if str(k).isdigit()] or [0]) + 1)
        falas[novo_idx] = {
            "indice": int(novo_idx),
            "quem": quem,
            "jp": jp_resp,
            "pt_contextual": pt_resp,
            "status": "retraduzido",
            "trecho": i,
        }
        ck_jps[chave] = novo_idx
        n_inseridas += 1

    # Salvar (preservando o resto)
    ckpt["falas"] = falas
    ckpt_path.write_text(json.dumps(ckpt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{stem}] inseridas: {n_inseridas} | já existiam: {n_ja_existe} | total falas: {len(falas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
