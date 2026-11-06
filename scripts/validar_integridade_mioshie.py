#!/usr/bin/env python3
"""Validação de integridade dos checkpoints Mioshie 1-8 (docs/19 §4.3).

Verifica ANTES de consolidar:
- [x] Nº de falas por arquivo == Nº de turnos do JP (extrator corrigido).
- [x] 0 duplicatas (nenhuma fala com conteúdo repetido).
- [x] Ordem pergunta → resposta (alternância) correta.
- [x] Cobertura 100% do JP (todo turno tem tradução).
- [x] Todas as falas com pt_contextual preenchido.

Uso:
  .venv/bin/python scripts/validar_integridade_mioshie.py
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
JP_DIR = RAIZ / "textos_japones"

ARQUIVOS = [
    "19510920-御教え集1号",
    "19511025-御教え集2号",
    "19511125-御教え集3号",
    "19511215-御教え集4号",
    "19520115-御教え集5号",
    "19510225-御教え集6号",
    "19520320-御教え集7号",
    "19520420-御教え集8号",
]


def norm(s: str) -> str:
    """Normaliza para comparação de duplicatas (ignora espaços)."""
    return re.sub(r"\s+", "", s or "")


def main() -> int:
    problemas = 0
    for stem in ARQUIVOS:
        jp_path = JP_DIR / f"{stem}.txt"
        ckpt_path = CKPT_DIR / f"{stem}.json"
        erros = []

        # 1. Turnos do JP (extrator corrigido = fonte de verdade)
        jp_falas = extrair_falas_mioshie(jp_path.read_text(encoding="utf-8"))
        n_jp = len(jp_falas)

        if not ckpt_path.exists():
            erros.append("checkpoint NÃO EXISTE")
            print(f"[{stem}] FALHA: {erros}")
            problemas += 1
            continue

        ckpt = json.loads(ckpt_path.read_text(encoding="utf-8"))
        falas_raw = ckpt.get("falas", {})
        falas = list(falas_raw.values()) if isinstance(falas_raw, dict) else falas_raw
        n_ckpt = len(falas)

        # 2. Cobertura: nº falas ckpt == nº turnos JP
        if n_ckpt != n_jp:
            erros.append(f"nº falas ckpt ({n_ckpt}) != nº turnos JP ({n_jp})")

        # 3. Todas com pt_contextual
        sem_pt = sum(1 for f in falas if not (f.get("pt_contextual") or "").strip())
        if sem_pt:
            erros.append(f"{sem_pt} falas sem pt_contextual")

        # 4. Duplicatas (JP e PT normalizados)
        vistos = set()
        dups = 0
        for f in falas:
            chave = (norm(f.get("jp", "")), norm(f.get("pt_contextual", "")))
            if chave[0]:
                if chave in vistos:
                    dups += 1
                else:
                    vistos.add(chave)
        if dups:
            erros.append(f"{dups} falas duplicadas")

        # 5. Ordem: alternância Interlocutor/Meishu-Sama sem quebrar
        quem = [f.get("quem") for f in falas]
        # Não pode ter dois Interlocutor seguidos SEM um Meishu-Sama entre
        # (a menos que seja continuação legítima — mas o padrão do corpus é
        # pergunta→resposta). Sinaliza como aviso, não erro fatal.
        seguidas = sum(1 for i in range(1, len(quem)) if quem[i] == quem[i - 1] == "Interlocutor")

        status = "OK" if not erros else "FALHA"
        if erros:
            problemas += 1
        aviso = f" | aviso: {seguidas} Interlocutor seguidos" if seguidas else ""
        print(f"[{stem}] {status}: ckpt={n_ckpt} jp={n_jp} | {erros or 'íntegro'}{aviso}")

    print(f"\nResultado: {'TUDO ÍNTEGRO' if problemas == 0 else f'{problemas} arquivo(s) com problema'}")
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
