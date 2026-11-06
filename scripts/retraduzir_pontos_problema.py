#!/usr/bin/env python3
"""Retraduz os pontos problemáticos do Gokōwa-roku (Suplemento) com o executor
corrigido (trava de glossário + contexto A + sujeito B + reconstrução).

Os pontos vêm do relatório do Claude (artifact ef63776f) — Parte 2 (texto
publicado, 41 erros) e Parte 1 (retradução, 65 erros). Cada ponto é localizado
no JP por fragmento e retraduzido com o pipeline corrigido.

Uso:
    python3 scripts/retraduzir_pontos_problema.py --todos
    python3 scripts/retraduzir_pontos_problema.py --parcial   # amostra de teste
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraducao_completa_gokowa import retraduzir, extrair_falas, JP, PT  # noqa: E402

OUT = RAIZ / "reports" / "amostragem_semantica_gokowa" / "pontos_problema"
SAIDA = OUT / "retraducao_pontos_problema.json"

# Pontos da Parte 2 (texto publicado) — localizados por fragmento JP
# Formato: (nome, fragmento_jp, quem_esperado)
PONTOS = [
    ("#449 omissão 龍神系", "龍神系の婦人は結婚せぬほうがよろしい", "Interlocutor"),
    ("#200 inversão culpa marido", "また子供の死は多くの場合実の不品行に原因", "Meishu-Sama"),
    ("#317 inversão hierarquia Ohikari", "弟子が先生を", "Interlocutor"),
    ("#934 inversão suástica", "ナチスは黒にはすっかいに", "Meishu-Sama"),
    ("#886 inversão saniwa", "霊の正邪を見分けるのは審神者", "Meishu-Sama"),
    ("#304 nome Mokichi", "茂吉というのをとった", "Meishu-Sama"),
    ("#139 Miroku Lodge", "ミロクロッジ", "Interlocutor"),
    ("#786 numérico 6 shaku", "無縁仏はそこへ小さくは三尺四方", "Meishu-Sama"),
    ("#404 Odawara cortado", "小田原の「小」は小さい型", "Meishu-Sama"),
    ("#85 Aomori 3ª pessoa", "青森から来た講習生", "Interlocutor"),
    ("#61 fala absorvida", "今月二日より御治療しましたところ", "Interlocutor"),
    # Parte 1 (retradução DeepSeek) — erros mais graves a revalidar
    ("#230 inversão espírito maligno", "眉間を占領すれば", "Meishu-Sama"),
    ("#508 ouro/prata", "金は火、銀は水", "Meishu-Sama"),
    ("#8 Nakayama 3ª pessoa", "あれはこのごろあまり作りませんね", "Meishu-Sama"),
    ("#518 mestre Osaka", "自分は先生に背いた", "Interlocutor"),
    ("#744 fala mal 1ª pessoa", "話が下手なのは言葉でゆかず", "Meishu-Sama"),
    ("#812 lado paterno", "これは父方です", "Meishu-Sama"),
]


def localizar_indice(fragmento: str, falas: list) -> int | None:
    for i, (quem, txt) in enumerate(falas):
        if fragmento in txt:
            return i
    return None


def main() -> None:
    parcial = "--parcial" in sys.argv
    falas_jp = extrair_falas(JP.read_text(encoding="utf-8"))
    falas_pt = extrair_falas(PT.read_text(encoding="utf-8"))
    n = min(len(falas_jp), len(falas_pt))

    OUT.mkdir(parents=True, exist_ok=True)
    resultados = []
    if SAIDA.exists():
        try:
            resultados = json.loads(SAIDA.read_text(encoding="utf-8"))
        except Exception:
            resultados = []
    feitos = {r["nome"] for r in resultados}

    # valida a lista de fragmentos (quais localizam no JP)
    print("=== Localização dos pontos no JP ===")
    nao_localizados = []
    for nome, frag, quem in PONTOS:
        idx = localizar_indice(frag, falas_jp)
        if idx is None:
            nao_localizados.append((nome, frag))
            print(f"  ❌ {nome}: não localizado ('{frag[:30]}...')")
        else:
            print(f"  ✅ {nome}: índice {idx}")

    if nao_localizados:
        print(f"\n⚠️  {len(nao_localizados)} pontos não localizados (serão pulados)")
        print("   Estes: ", [n for n, _ in nao_localizados])

    alvos = PONTOS if not parcial else PONTOS[:6]
    for nome, frag, quem in alvos:
        if nome in feitos:
            print(f"⏭️  {nome}: já feito")
            continue
        idx = localizar_indice(frag, falas_jp)
        if idx is None:
            continue

        jp = falas_jp[idx][1]
        pt_atual = falas_pt[idx][1] if idx < len(falas_pt) else ""
        # contexto = últimas 5 falas anteriores (para resolver anáforas/inversões
        # com bom espaço conversacional; mais contexto não prejudica a qualidade)
        ctx = ""
        if idx > 0:
            inicio_ctx = max(0, idx - 5)
            partes_ctx = []
            for j in range(inicio_ctx, idx):
                partes_ctx.append(f"[{falas_jp[j][0]}] {falas_jp[j][1]}")
            ctx = "\n".join(partes_ctx)

        print(f"\n{'='*60}")
        print(f"=== {nome} (índice {idx}) ===")
        print(f"JP: {jp[:90]}...")
        print(f"PT ATUAL: {pt_atual[:90]}...")
        print("Retraduzindo (executor corrigido)...", flush=True)
        novo = retraduzir(jp, quem, max_retries=12, contexto_anterior=ctx)
        print(f"PT NOVO: {novo[:150]}")
        resultados.append({
            "nome": nome,
            "indice_jp": idx,
            "fragmento": frag,
            "quem": quem,
            "jp": jp,
            "pt_atual": pt_atual,
            "pt_novo": novo,
        })
        # checkpoint a cada 3
        if len(resultados) % 3 == 0:
            SAIDA.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")

    SAIDA.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSalvo: {SAIDA} ({len(resultados)} pontos retraduzidos)")


if __name__ == "__main__":
    main()
