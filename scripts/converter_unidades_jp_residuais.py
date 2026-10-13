#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Converte unidades japonesas RESIDUAIS nos periódicos para o sistema métrico.

Decisão do usuário (glossario_regras.json → decisoes_usuario): converter SEMPRE
para o métrico, SEM transliterar a unidade (nada de "sun", "bu", "shaku").

O conversor automático de quantidades já tratou o grosso; este script trata os
casos que escaparam — sobretudo medidas de COMPRIMENTO escritas por extenso em
português ("um shaku", "cinco bu", "três sun"), que o regex de numeral+kanji não
apanha porque a unidade já vinha transliterada.

Cada substituição é CURADA e conferida contra o japonês de origem; o script
verifica que o trecho antigo ocorre exatamente UMA vez antes de gravar.

Equivalências (1 shaku = 30,3 cm; 1 sun = 3,03 cm; 1 bu = 0,303 cm):
    一尺=30 cm · 一寸=3 cm · 五分=1,5 cm · 二分=0,6 cm · 五、六寸=15-18 cm
    一寸平方=9 cm² · 七分=2,1 cm · 五尺=1,5 m

Uso:
    python scripts/converter_unidades_jp_residuais.py            # dry-run
    python scripts/converter_unidades_jp_residuais.py --aplicar
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_unidades"
RELATORIO = RAIZ / "reports" / "unidades_residuais_conversao.json"

# (item, trecho_antigo, trecho_novo, unidade_jp, observacao)
CONVERSOES: list[tuple[str, str, str, str, str]] = [
    # --- 厚さ五分くらい / 二、三分くらいの深さ ---------------------------------
    ("P1_Tijotengoku_12_20",
     "aderido numa espessura de uns cinco bu",
     "aderido numa espessura de cerca de 1,5 cm",
     "五分", ""),
    ("P1_Tijotengoku_12_20",
     "a uma profundidade de cerca de dois ou três bu",
     "a uma profundidade de cerca de 0,6 a 0,9 cm",
     "二、三分", ""),
    # --- 直径三寸くらいの光の玉 ------------------------------------------------
    ("P1_Tijotengoku_23_48",
     "uma esfera (jóia) de luz de cerca de três sun de diâmetro",
     "uma esfera (jóia) de luz de cerca de 9 cm de diâmetro",
     "三寸", ""),
    # --- 37_68: 一尺 / 五分 / 二分 / 一寸 / 五、六寸 ----------------------------
    ("P1_Tijotengoku_37_68",
     "uma secreção viscosa contínua de cerca de um shaku",
     "uma secreção viscosa contínua de cerca de 30 cm",
     "一尺", ""),
    ("P1_Tijotengoku_37_68",
     "deslocada cerca de metade (aproximadamente cinco bu)",
     "deslocada cerca de metade (aproximadamente 1,5 cm)",
     "五分", ""),
    ("P1_Tijotengoku_37_68",
     "o deslocamento era de cerca de dois bu",
     "o deslocamento era de cerca de 0,6 cm",
     "二分", ""),
    ("P1_Tijotengoku_37_68",
     "os brotos surjam viçosos com cerca de um sun",
     "os brotos surjam viçosos com cerca de 3 cm",
     "一寸", ""),
    ("P1_Tijotengoku_37_68",
     "a camada de folhas caídas era de cerca de cinco a seis sun",
     "a camada de folhas caídas era de cerca de 15 a 18 cm",
     "五、六寸", ""),
    # --- 一寸平方 -------------------------------------------------------------
    ("P1_Tijotengoku_46_77",
     "o inchaço se estendeu até cerca de um sun quadrado",
     "o inchaço se estendeu até cerca de 9 cm²",
     "一寸平方", ""),
    # --- 112_116: 一尺近くから数寸、更に一寸位 --------------------------------
    ("P2_Eiko_112_116",
     "e mesmo até cerca de um sun [cerca de 3 cm]",
     "e mesmo até cerca de 3 cm",
     "一寸位", "colchete redundante"),
    # --- 163_222: 藁も一二分位に切り ------------------------------------------
    ("P2_Eiko_163_222",
     "já cortando a palha em cerca de um ou dois bu",
     "já cortando a palha em cerca de 0,3 a 0,6 cm",
     "一二分", "um ou dois bu = 0,3-0,6 cm"),
    # --- 235_269: 五分位付いていた --------------------------------------------
    ("P2_Eiko_235_269",
     "um dano anterior de cerca de cinco bu [aproximadamente 1,5 cm]",
     "um dano anterior de cerca de 1,5 cm",
     "五分位", "colchete redundante"),
    # --- 250_280: 直径三振位の斑点（「振」は「寸」の誤りとみられる） -----------
    ("P2_Eiko_250_280",
     "uma mancha de cerca de três sun (aproximadamente 9 cm) de diâmetro",
     "uma mancha de cerca de 9 cm de diâmetro",
     "三寸", "parêntese redundante"),
    # --- 97_183: 五尺何寸の人間 -----------------------------------------------
    ("P2_Eiko_97_183",
     "Que um ser humano de cerca de 1,5 m e alguns sun [cerca de um metro e meio] acabe derrotado",
     "Que um ser humano de cerca de um metro e meio acabe derrotado",
     "五尺何寸", "texto duplicado pelo conversor anterior"),
    # --- 43_74: 御姿は七分くらいにて ------------------------------------------
    ("P1_Tijotengoku_43_74",
     "A figura tinha cerca de sete punhos [aproximadamente 21 cm] e atingia o teto",
     "A figura tinha cerca de 2,1 cm e atingia o teto",
     "七分", "ATENÇÃO: o original traz 七分 (=2,1 cm) mas diz «atingia o teto»; "
             "anomalia do original, não do tradutor"),
]


# ============================================================================
# 2.ª RONDA — unidades que apareceram nos chunks RETRADUZIDOS (13/10)
# (1 chō linear = 109 m · 1 chō areal = 9917 m² · 1 tan = 991,7 m² ·
#  1 kan = 3,75 kg · 1 ken = 1,82 m · 1 ri = 3,927 km)
# ============================================================================
RODADA2: list[tuple[str, str, str, str, str]] = [
    # --- 37_68: 反当たり三、四百貫 / 二、三十貫 / 開畳一町 -------------------
    ("P1_Tijotengoku_37_68",
     "de 300 a 400 kan de composto natural e cerca de 2.000 ienes de adubo químico por tan",
     "de 1,1 a 1,5 t de composto natural e cerca de 2.000 ienes de adubo químico por 990 m²",
     "貫/反", "300-400 kan = 1,1-1,5 t"),
    ("P1_Tijotengoku_37_68",
     "três sacas (hyō) por tan de colheita real",
     "três sacas (hyō) por 990 m² de colheita real",
     "反", "1 tan ≈ 990 m²"),
    ("P1_Tijotengoku_37_68",
     "espalho de 20 a 30 kan por tan de cal",
     "espalho de 75 a 112 kg por 990 m² de cal",
     "貫/反", "20-30 kan = 75-112 kg"),
    ("P1_Tijotengoku_37_68",
     "possuo cerca de um chō de campo aberto",
     "possuo cerca de 1 ha de campo aberto",
     "一町", "1 chō areal ≈ 9.917 m²"),
    # --- 44_75: 一間離れましても ---------------------------------------------
    ("P1_Tijotengoku_44_75",
     "mesmo a uma distância de um ken",
     "mesmo a uma distância de cerca de 1,8 m",
     "一間", "1 ken = 1,82 m"),
    # --- 163_222: 全耕地の一町五反歩の内一町歩 --------------------------------
    ("P2_Eiko_163_222",
     "dos um chō e cinco tan de toda a área cultivada, implementei um chō sem fertilizante",
     "dos cerca de 1,5 ha de toda a área cultivada, implementei cerca de 1 ha sem fertilizante",
     "一町五反", "1 chō 5 tan ≈ 1,5 ha"),
    # --- 50_301: 約二十丁はなれた --------------------------------------------
    ("P3_Kyusei_50_301",
     "a cerca de vinte chō [de distância]",
     "a cerca de 2,2 km de distância",
     "二十丁", "20 chō lineares = 2,18 km"),
    # --- 54_311: 五里四方の山中 ----------------------------------------------
    ("P3_Kyusei_54_311",
     "num raio de cinco ri de montanhas",
     "num raio de cerca de 20 km de montanhas",
     "五里", "5 ri = 19,6 km"),
    # --- 56_315: 全耕地一町三反 / 耕作面積一町三反 ---------------------------
    ("P3_Kyusei_56_315",
     "toda a área cultivada, um chō e três tan, e, desde aquele dia",
     "toda a área cultivada, cerca de 1,3 ha, e, desde aquele dia",
     "一町三反", "1 chō 3 tan ≈ 1,3 ha"),
    ("P3_Kyusei_56_315",
     "na área cultivada de um chō e três tan, em Showa 22",
     "na área cultivada de cerca de 1,3 ha, em Showa 22",
     "一町三反", "1 chō 3 tan ≈ 1,3 ha"),
]


# ============================================================================
# 3.ª RONDA — «tan»/«se» como ÁREA e produção «por tan» (1 tan ≈ 990 m²;
# 1 se = 畝 ≈ 99 m²; 6 tan 5 se ≈ 0,64 ha) + limpezas de métrica redundante.
# ============================================================================
RODADA3: list[tuple[str, str, str, str, str]] = [
    # --- 27_59: 三、四間（約五〜七メートル）— métrica já presente -------------
    ("P1_Tijotengoku_27_59",
     "A três ou quatro ken [aproximadamente cinco a sete metros]",
     "A cerca de cinco a sete metros",
     "三、四間", "colchete redundante"),
    # --- 3_9: 三町（3 ha）— métrica já presente ------------------------------
    ("P1_Tijotengoku_3_9",
     "cerca de 3 ha (três chō) de arrozais",
     "cerca de 3 ha de arrozais",
     "三町", "parêntese redundante"),
    # --- 102_103: 五反は五反でも -----------------------------------------------
    ("P2_Eiko_102_103",
     "mesmo em cinco tan sendo cinco tan",
     "mesmo em cerca de 0,5 ha sendo 0,5 ha",
     "五反", "5 tan ≈ 4.958 m²"),
    # --- 163_222: 六反五畝 / 反当たりの供米 / 一反当たり二俵半 ------------------
    ("P2_Eiko_163_222",
     "(seis tan, cinco se, aproximadamente)",
     "(cerca de 0,64 ha)",
     "六反五畝", "6 tan 5 se ≈ 6.443 m²"),
    ("P2_Eiko_163_222",
     "melhor classificação por tan, e o entregava",
     "melhor classificação por 990 m², e o entregava",
     "一反当", "1 tan ≈ 990 m²"),
    ("P2_Eiko_163_222",
     "A colheita foi de dois sacos e meio por tan",
     "A colheita foi de dois sacos e meio por 990 m²",
     "一反当", "1 tan ≈ 990 m²"),
    # --- produção «por tan» (≙ por 990 m²) ---------------------------------
    ("P2_Eiko_194_242", "treze sacas por tan", "treze sacas por 990 m²",
     "反当", "1 tan ≈ 990 m²"),
    ("P2_Eiko_245_275", "dez sacas por tan", "dez sacas por 990 m²",
     "反当", "1 tan ≈ 990 m²"),
    ("P2_Eiko_97_181", "quinze sacas por tan", "quinze sacas por 990 m²",
     "反当", "1 tan ≈ 990 m²"),
    ("P2_Eiko_97_181", "oito sacas por tan", "oito sacas por 990 m²",
     "反当", "1 tan ≈ 990 m²"),
    ("P2_Eiko_97_181", "a produção por tan e chegando",
     "a produção por 990 m² e chegando",
     "反当", "1 tan ≈ 990 m²"),
    ("P3_Kyusei_56_315", "(por tan)", "(por 990 m²)",
     "反当", "cabeçalho de tabela"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--rodada", type=int, default=1, choices=(1, 2, 3),
                    help="1: cm básicos · 2: chō/kan/ken/ri · 3: tan/se e por tan")
    args = ap.parse_args()

    tabela = {1: CONVERSOES, 2: RODADA2, 3: RODADA3}[args.rodada]
    por_item: dict[str, list[tuple[str, str, str, str]]] = {}
    for item, antes, depois, unidade, obs in tabela:
        por_item.setdefault(item, []).append((antes, depois, unidade, obs))

    registros, erros = [], []
    for item, subs in sorted(por_item.items()):
        arq = ITENS / f"{item}.json"
        dados = json.loads(arq.read_text(encoding="utf-8"))
        pt = dados.get("texto_pt") or ""
        novo = pt
        feitas = []
        for antes, depois, unidade, obs in subs:
            n = novo.count(antes)
            if n == 0 and depois in novo:
                continue        # já aplicado em execução anterior
            if n == 0:
                erros.append((item, antes, "não encontrado"))
                continue
            novo = novo.replace(antes, depois)
            feitas.append(
                {"unidade_jp": unidade, "antes": antes, "depois": depois,
                 "observacao": obs, "ocorrencias": n}
            )
        if not feitas:
            continue
        registro = {"item": item, "n": len(feitas), "substituicoes": feitas,
                    "pt_antes": len(pt), "pt_depois": len(novo)}
        if args.aplicar:
            BACKUPS.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            shutil.copy2(arq, BACKUPS / f"{item}_{stamp}.json")
            dados["texto_pt"] = novo
            dados.setdefault("reparos", []).append(
                {"tipo": "unidades_jp_residuais", "data": stamp,
                 "unidades": sorted({s["unidade_jp"] for s in feitas})}
            )
            arq.write_text(
                json.dumps(dados, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8",
            )
        registros.append(registro)
        print(f"  {item:28s} {len(feitas)} conversão(ões)")
        for s in feitas:
            print(f"      {s['unidade_jp']:8s} {s['antes'][:52]!r}")
            print(f"      {'':8s} -> {s['depois'][:52]!r}")

    RELATORIO.write_text(
        json.dumps({"aplicado": args.aplicar, "itens": registros,
                    "erros": erros}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    if erros:
        print("\nERROS (não aplicados):")
        for item, antes, motivo in erros:
            print(f"  {item}: {antes[:60]!r} — {motivo}")
    print(f"\n{'APLICADO' if args.aplicar else 'DRY-RUN'}: {len(registros)} item(ns), "
          f"{sum(r['n'] for r in registros)} conversões")
    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main())
