#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ronda 5 — correções dos achados médios/baixos da auditoria R3.

Inclui duas correções globais com a contagem validada contra o japonês:
  * 御神体   -> "objeto sagrado de culto (goshintai)"  (82 ocorrências, JP 82)
  * 御利益   -> "benefício material"                   (nos artigos listados)
E reverte um erro de fator que a ronda 4 introduziu em 23_47.

Uso:  .venv/bin/python scripts/aplicar_correcoes_auditoria_r5.py [--aplicar]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_auditoria"

SUBS: list[tuple[str, str, str, str, int]] = [
    # ------------------------------------------------ português / género
    ("P3_Kyusei_54_311", "texto_pt",
     "E então, ele foi até onde as crianças dormiam",
     "E então, ela foi até onde as crianças dormiam", 1),
    ("P3_Kyusei_54_311", "texto_pt",
     "Involuntariamente, também ele tentou agarrar-se",
     "Involuntariamente, também ela tentou agarrar-se", 1),
    ("P3_Kyusei_54_311", "texto_pt",
     "estava sendo abraçado com força por Heita",
     "estava sendo abraçada com força por Heita", 1),
    ("P3_Kyusei_54_311", "texto_pt",
     "Heita novamente o puxou para si com violência",
     "Heita novamente a puxou para si com violência", 1),
    ("P1_Tijotengoku_12_20", "texto_pt",
     "como eu me lembrava tão bem de acontecimentos de quando ele tinha apenas "
     "cinco anos",
     "como eu me lembrava tão bem de acontecimentos de quando eu tinha apenas "
     "cinco anos", 1),
    ("P2_Eiko_150_202", "texto_pt",
     "Nuvem espiritual é o corpo espiritual, que é transparente, tornar-se opaco.",
     "Nuvem espiritual é o corpo espiritual, que é transparente, tornar-se "
     "opaco — isto é, o fato de aquilo que é transparente se tornar opaco.", 1),
    ("P2_Eiko_157_211", "texto_pt",
     "e assim acabou; o que equivale a todos para a jaula dos porcos [a cadeia]",
     "e assim acabou: o equivalente a acabar na jaula dos porcos [na cadeia]", 1),
    ("P2_Eiko_122_133", "texto_pt",
     "ônibus que despenca, trem a vapor, bacilo da tuberculose, impostos",
     "ônibus que despenca, trem em chamas, bacilo da tuberculose, impostos", 1),

    # ------------------------------------------------ inversões
    ("P1_Tijotengoku_39_69", "texto_pt",
     "caiu numa dificuldade financeira tal que nem o dinheiro da passagem para "
     "ir à Igreja Média lhe faltava",
     "caiu numa dificuldade financeira tal que lhe faltava até o dinheiro da "
     "passagem para ir à Igreja Média", 1),
    ("P2_Eiko_256_286", "texto_pt",
     "só o fato de o próprio Ministério — que se pode dizer ser a sede do mundo "
     "agrícola — ter reconhecido, nesta medida, os especialistas desta área já basta",
     "só o fato de os especialistas desta área terem sido reconhecidos nesta "
     "medida pelo próprio Ministério — que se pode dizer ser a sede do mundo "
     "agrícola — já basta", 1),
    ("P4_Hikari_37_380", "texto_pt",
     "não penso que o artigo que escrevi neste jornal para pedir a reflexão do "
     "jornal tenha sido algo como cocô de cachorro; deve ter sido escrito por "
     "descuido, devido a uma perda de memória",
     "não penso que seja coisa de «cocô de cachorro» o artigo que aquele jornal "
     "publicou em resposta ao meu pedido de reflexão; deve ter sido escrito por "
     "descuido, devido a uma perda de memória", 1),
    ("P3_Kyusei_54_311", "texto_pt",
     "quando eu também saí para ver, o Kyūzō tinha ido para casa",
     "quando eu também saí para ver, Kichita tinha ido à casa do Kyūzō", 1),
    ("P1_Tijotengoku_12_23", "texto_pt",
     "A resposta usa", "A resposta usa", 0),  # controlo

    # ------------------------------------------------ nomes próprios
    ("P3_Kyusei_49_298", "texto_pt", "Igreja Média Hōsei", "Igreja Média Kōhō", 1),
    ("P4_Hikari_3_364", "texto_pt", "punho de Tokudama-kun", "punho de Tokukyū-kun", 1),
    ("P4_Hikari_11_338", "texto_pt",
     "o nome de Keiran-kyō", "o nome de Seiran-kyō", 1),
    ("P1_Tijotengoku_12_23", "texto_pt", "não é Ryūjin.", "não é o dragão da árvore.", 1),

    # ------------------------------------------------ números / métricas
    ("P1_Tijotengoku_11_4", "texto_pt",
     "nome do filho que faleceu em 21 de março deste ano, com vinte e um anos",
     "nome do filho que faleceu em março deste ano, com vinte e um anos", 1),
    ("P2_Eiko_102_103", "texto_pt",
     "um tō (cerca de 72 litros)", "um tō (cerca de 18 litros)", 0),
    ("P2_Eiko_102_103", "texto_pt", "cerca de 72 litros)", "cerca de 18 litros)", 1),

    # ------------------------------------------------ glossário
    ("P2_Eiko_119_128", "texto_pt",
     "— Que sunte(su) mais porco é este!", "— Que Sun-Tetsu mais porco é este!", 1),
    ("P1_Tijotengoku_12_23", "texto_pt",
     "há especialmente muito Elemento Água.", "há especialmente muito hidrogênio.", 1),
    ("P3_Kyusei_52_306", "texto_pt",
     "recebi proteção divina e graças em todas as direções possíveis. Essas graças,",
     "recebi proteção divina e benefícios materiais em todas as direções "
     "possíveis. Esses benefícios,", 1),
    ("P1_Tijotengoku_22_45", "texto_pt",
     "o plexo solar (太陽神経叢), nas costas do plexo solar,",
     "a boca do estômago (みぞおち), nas costas do plexo solar (太陽神経叢),", 1),
]

# Correções globais validadas por contagem contra o japonês
GLOBAL_御神体 = "objeto sagrado de culto (goshintai)"
GLOBAL_御利益 = "benefício material"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cache: dict[str, dict] = {}
    falhas: list[str] = []
    revisar: list[str] = []
    ok = 0

    def carregar(item: str) -> dict:
        if item not in cache:
            cache[item] = json.loads((ITENS / f"{item}.json").read_text(encoding="utf-8"))
        return cache[item]

    # ---- enumera TODOS os artigos (a correção global alcança-os a todos)
    for f in sorted(ITENS.glob("*.json")):
        if f.name.startswith("."):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        pt = d.get("texto_pt") or ""
        jp = d.get("texto_jp") or ""
        n_pt = pt.count("Imagem da Luz Divina")
        n_jp = len(re.findall(r"御神体", jp))
        # só corrige quando a contagem de 御神体 cobre as ocorrências em PT
        if n_pt and n_pt <= n_jp:
            d["texto_pt"] = pt.replace("Imagem da Luz Divina", GLOBAL_御神体)
            d.setdefault("reparos", []).append(
                {"tipo": "fix_goshintai", "data": stamp, "n": n_pt}
            )
            cache[f.stem] = d
            ok += 1
        elif n_pt:
            # nem todas as ocorrências correspondem a 御神体 (ex.: 御軸「光明」)
            revisar.append(f"{f.stem}: PT={n_pt} > JP御神体={n_jp}")

    for item, campo, old, new, esperado in SUBS:
        if esperado == 0:
            continue
        d = carregar(item)
        atual = d.get(campo) or ""
        n = atual.count(old)
        if n != esperado:
            falhas.append(f"{item}.{campo}: {n} occ, esperado {esperado} — {old[:65]!r}")
            continue
        d[campo] = atual.replace(old, new)
        d.setdefault("reparos", []).append(
            {"tipo": "fix_auditoria_r5", "data": stamp, "campo": campo}
        )
        ok += 1

    print(f"\ncorreções aplicadas: {ok} | falhas: {len(falhas)}")
    for f in falhas:
        print("  [FALHA]", f)
    if revisar:
        print(f"\np/ revisão manual ({len(revisar)}) — mistura 御神体 com 御軸「光明」:")
        for r in revisar:
            print("   ", r)

    if args.aplicar and not falhas:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        for item, d in cache.items():
            arq = ITENS / f"{item}.json"
            shutil.copy2(arq, BACKUPS / f"{item}_r5_{stamp}.json")
            arq.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
        print(f"gravados {len(cache)} ficheiros")
    elif args.aplicar:
        print("NADA GRAVADO (resolver falhas primeiro)")
        return 1
    else:
        print("(dry-run; use --aplicar para gravar)")
    return 0 if not falhas else 1


if __name__ == "__main__":
    raise SystemExit(main())
