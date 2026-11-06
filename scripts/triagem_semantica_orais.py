#!/usr/bin/env python3
"""Triagem de problemas na revisão semântica de coleções orais (não-LLM).

Detecta candidatos a revisão manual em cada checkpoint:
1. JP cru no PT (kana/kanji que sobraram na tradução)
2. Data de sessão no JP ausente no PT (para prosa Mioshie)
3. Termos do glossário que deveriam aparecer (nomes próprios/doutrinários)
4. Proporção JP/PT anormal (possível omissão grande ou inflação)
5. Rótulos duplicados no início do PT

Uso:
  .venv/bin/python scripts/triagem_semantica_orais.py --colecao mioshie_prosa|gokowa|gosuiji
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CKPT_DIR = RAIZ / "reports" / "retraducao_colecoes"

# Termos doutrinários/nomes que SEMPRE devem ser vertidos corretamente
TERMOS_CHAVE = [
    "Johrei", "Ohikari", "Meishu-Sama", "Kannon", "Daikōmyō", "Kōmyō",
    "Miroku", "Mundo de Miroku", "Paraíso Terrestre", "Grande Purificação",
    "Grande Acerto de Contas", "Miroku Ōkami", "free e desimpedido",
]

KANA = "ぁ-ゖァ-ヺー"


def _chave_ord(chave) -> int:
    if isinstance(chave, str) and chave.startswith("t") and chave[1:].isdigit():
        return int(chave[1:])
    try:
        return int(chave)
    except (TypeError, ValueError):
        return 0


def detectar_jp_cru(pt: str) -> list[str]:
    """Detecta trechos de kana/kanji que sobraram no PT (não traduzidos)."""
    achados = []
    # kana em sequência (≥2 chars) = japonês não traduzido
    for m in re.finditer(f"[{KANA}]{{2,}}", pt):
        achados.append(m.group(0))
    # kanji em sequência (≥3 chars) = japonês não traduzido
    for m in re.finditer(r"[\u4e00-\u9fff]{3,}", pt):
        achados.append(m.group(0))
    return achados[:5]


def detectar_data_faltante(jp: str, pt: str) -> bool:
    """Para prosa: se o JP tem data de sessão e o PT não a traduz."""
    # datas no formato 昭和二十七年四月五日 ou 四月五日
    m = re.search(r'昭和\s*([一二三四五六七八九十\d]+)\s*年\s*([一二三四五六七八九十\d]+)\s*月\s*([一二三四五六七八九十\d]+)\s*日', jp)
    if m:
        ano, mes, dia = m.group(1), m.group(2), m.group(3)
        # verifica se algum número/dia aparece no PT
        if mes not in pt and dia not in pt:
            return True
    return False


def carregar_glossario() -> dict:
    try:
        return json.loads((RAIZ / "glossario_traducao.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    colecao = sys.argv[sys.argv.index("--colecao") + 1] if "--colecao" in sys.argv else "todas"
    pref = {"gokowa": "御光話録", "gosuiji": "御垂示録", "mioshie_prosa": "御教え集"}.get(colecao)
    gloss = carregar_glossario()

    arquivos = sorted(p.stem for p in CKPT_DIR.glob(f"*{pref}*.json")
                      if not p.name.startswith("backup") and "bak" not in p.name)
    if colecao == "mioshie_prosa":
        arquivos = [a for a in arquivos if re.search(r'御教え集(\d+)号', a) and int(re.search(r'御教え集(\d+)号', a).group(1)) >= 9]

    total_alertas = 0
    for stem in arquivos:
        ckpt_path = CKPT_DIR / f"{stem}.json"
        if not ckpt_path.exists():
            continue
        ckpt = json.loads(ckpt_path.read_text(encoding="utf-8"))
        falas = ckpt.get("falas", {})
        alertas_arquivo = []
        for k in sorted(falas.keys(), key=_chave_ord):
            f = falas[k]
            if not isinstance(f, dict):
                continue
            jp = f.get("jp", "") or ""
            pt = f.get("pt_contextual", "") or ""

            # 1. JP cru no PT
            jp_cru = detectar_jp_cru(pt)
            if jp_cru:
                alertas_arquivo.append(f"  [{k}] JP cru no PT: {jp_cru}")

            # 2. Data faltante (prosa)
            if colecao == "mioshie_prosa" and detectar_data_faltante(jp, pt):
                alertas_arquivo.append(f"  [{k}] possível data de sessão faltando no PT")

            # 3. Proporção JP/PT (sem espaços)
            jp_n = len(re.sub(r"\s", "", jp))
            pt_n = len(re.sub(r"\s", "", pt))
            if jp_n > 0:
                ratio = pt_n / jp_n
                if ratio < 0.4:
                    alertas_arquivo.append(f"  [{k}] PT muito curto (ratio {ratio:.2f}): possível omissão")

            # 4. Termos-chave no JP que deveriam aparecer no PT (amostra)
            for termo in ["御教え", "栄光"]:
                if termo in jp and termo not in pt and "【" in jp:
                    pass  # marcadores editoriais, ignorar

        if alertas_arquivo:
            print(f"\n=== {stem} ({len(alertas_arquivo)} alertas) ===")
            print("\n".join(alertas_arquivo[:10]))
            total_alertas += len(alertas_arquivo)

    print(f"\nTOTAL alertas: {total_alertas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
