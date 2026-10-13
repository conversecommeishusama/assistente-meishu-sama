#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ronda 3 — correções dos achados da auditoria R2 (verificação).

Todos os itens abaixo foram verificados contra o japonês antes de entrar nesta
lista. Inclui: erros de português introduzidos por edições anteriores, erros de
fator numérico, unidades japonesas ainda não convertidas, formas canónicas do
glossário, nomes próprios e inversões de sentido.

Uso:  .venv/bin/python scripts/aplicar_correcoes_auditoria_r3.py [--aplicar]
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

# (item, campo, antigo, novo, nº esperado de ocorrências)
SUBS: list[tuple[str, str, str, str, int]] = [
    # ============================================ PORTUGUÊS (edição anterior)
    ("P1_Tijotengoku_37_68", "texto_pt",
     "No início era comparatively gordo", "No início era comparativamente gordo", 1),
    ("P1_Tijotengoku_25_52", "texto_pt",
     "sem consegu ir fechá-las", "sem conseguir fechá-las", 1),
    ("P2_Eiko_182_234", "titulo_pt",
     "A Exemplo de Vítimas da Medicina", "Um Exemplo de Vítimas da Medicina", 1),
    ("P2_Eiko_204_253", "texto_pt",
     "mais de cem servidores suspensam com guindastes",
     "mais de cem servidores suspendem com guindastes", 1),
    ("P1_Tijotengoku_50_80", "texto_pt",
     "Respeitosamente, [eu] inquiriro.", "Respeitosamente, [eu] inquiro.", 1),
    ("P1_Tijotengoku_3_9", "texto_pt",
     "Ocasionamente há pregadores", "Ocasionalmente há pregadores", 1),
    ("P4_Hikari_38_382", "texto_pt",
     "isso se deve-se à reencarnação", "isso se deve à reencarnação", 1),
    ("P2_Eiko_248_278", "texto_pt",
     "em cerca de meia lua o rosto", "em cerca de meio mês o rosto", 1),
    ("P2_Eiko_254_285", "texto_pt",
     "Cerca de meia lua depois", "Cerca de meio mês depois", 1),
    ("P2_Eiko_102_103", "texto_pt",
     "cerca de 12 cm (cerca de 12 cm)", "cerca de 12 cm", 1),
    ("P2_Eiko_169_228", "texto_pt", "se tornou muito mais gentil",  # género
     "ele se tornou muito mais gentil", 0),  # 0 = controlo (revisão manual)

    # ============================================ NÚMEROS (erro de fator)
    ("P2_Eiko_129_141", "texto_pt",
     "na maioria dos casos em dois ou três minutos se recebe a proteção divina",
     "na maioria dos casos em vinte ou trinta minutos se recebe a proteção divina", 1),
    ("P1_Tijotengoku_23_47", "texto_pt",
     "cerca de 18,0 milhões de L", "cerca de 1,8 milhão de L", 2),
    ("P1_Tijotengoku_23_47", "texto_pt",
     "Diante dos oito milhões de koku dos Tokugawa",
     "Diante dos 1,44 bilhão de L (oito milhões de koku) dos Tokugawa", 1),
    ("P4_Hikari_44_405", "texto_pt",
     "o Bungeishunju publicou cinquenta e cinco bilhões",
     "o Bungeishunju publicou cinco bilhões e meio", 1),
    ("P1_Tijotengoku_17_36", "texto_pt",  # Showa 10, não duração
     "morreu de lepra em dez anos", "morreu de lepra em Showa 10 [1935]", 1),
    ("P1_Tijotengoku_12_23", "texto_pt",
     '"cinquenta e seis bilhões e setecentos milhões de anos"',
     '"cerca de 5,67 bilhões de anos"', 1),
    ("P1_Tijotengoku_39_69", "texto_pt",
     "Quatro, cinco minutos se passaram", "Quarenta, cinquenta minutos se passaram", 1),
    ("P2_Eiko_256_286", "texto_pt",
     "atinge a casa dos milhares", "atinge a casa das dezenas de milhares", 1),
    ("P2_Eiko_102_103", "texto_pt",
     "um to (cerca de 72 litros)", "um tō (cerca de 18 litros)", 0),

    # ============================================ UNIDADES → MÉTRICO
    ("P3_Kyusei_56_315", "texto_pt",
     "numa igreja a cerca de uma légua [4 km] de distância",
     "numa igreja a cerca de 4 km de distância", 1),
    ("P3_Kyusei_56_315", "texto_pt",
     "a uma clínica a mais de três léguas [cerca de 12 km]",
     "a uma clínica a mais de 12 km", 1),
    ("P3_Kyusei_56_315", "texto_pt",
     "por um caminho de montanha de cerca de uma légua [4 km]",
     "por um caminho de montanha de cerca de 4 km", 1),
    ("P3_Kyusei_52_306", "texto_pt",
     "o médico fica a uma légua e meia", "o médico fica a cerca de 6 km", 1),
    ("P2_Eiko_134_151", "texto_pt",
     "Caminhando cerca de uma légua e meia", "Caminhando cerca de 6 km", 1),
    ("P4_Hikari_5_395", "texto_pt",
     "a uma légua de Atami", "a cerca de 4 km de Atami", 1),
    ("P4_Hikari_42_390", "texto_pt",
     "a área em Ginyama é de cerca de 120 mil tsubo (cerca de 397 mil m²)",
     "a área em Ginyama é de cerca de 397 mil m²", 1),
    ("P4_Hikari_42_390", "texto_pt",
     "mas o fato é de trinta e tantos mil tsubo",
     "mas o fato é de cerca de 99 a 132 mil m²", 1),
    ("P4_Hikari_42_390", "texto_pt",
     "na verdade são dez e tantos mil tsubo",
     "na verdade são cerca de 33 a 46 mil m²", 1),
    ("P2_Eiko_97_181", "texto_pt",
     "em alguns poucos tsubo de terra", "em apenas poucos metros quadrados de terra", 1),
    ("P2_Eiko_102_103", "texto_pt",
     "pela estimativa de colheita por medição em tsubo",
     "pela estimativa de colheita por 坪刈り (tsubo-gari, colheita de amostra)", 1),
    ("P2_Eiko_102_103", "texto_pt",
     "fiz medição por tsubo", "fiz a amostragem por tsubo (坪刈り)", 1),
    ("P3_Kyusei_55_313", "texto_pt",
     "que ficava a quatro ou cinco quadras de distância",
     "que ficava a cerca de 400 a 550 m de distância", 1),
    ("P3_Kyusei_55_313", "texto_pt",
     "percorri sem nenhum esforço os mais de dez quarteirões até a casa",
     "percorri sem nenhum esforço mais de 1 km até a casa", 1),
    ("P4_Hikari_11_338", "texto_pt",
     "a alguns quarteirões além do bosque de ameixeiras",
     "algumas centenas de metros além do bosque de ameixeiras", 1),
    ("P4_Hikari_11_338", "texto_pt",
     "quem poderia imaginar que a poucos quarteirões adiante",
     "quem poderia imaginar que a algumas centenas de metros adiante", 1),
    ("P1_Tijotengoku_22_44", "texto_pt",
     "uma grande pedra angular de cerca de 5,5 m quadrados",
     "uma grande pedra angular de cerca de 5,5 m de lado", 1),
    ("P1_Tijotengoku_23_48", "texto_pt",
     "separe cerca de 91 cm quadrados de terra",
     "separe um quadrado de cerca de 91 cm de lado", 1),
    ("P1_Tijotengoku_11_4", "texto_pt",
     "uma nuvem branca do tamanho de cerca de um pé [shaku] quadrado",
     "uma nuvem branca com cerca de 30 cm de lado", 1),
    ("P2_Eiko_87_162", "texto_pt",
     "era cerca de 30 cm e cerca de 21,2 a 24,2 cm",
     "era de cerca de 51,5 a 54,5 cm", 1),
    ("P2_Eiko_87_162", "texto_pt",
     "flutuava cerca de cerca de 12,1 a 15,1 cm",
     "flutuava a cerca de 12 a 15 cm", 1),
    ("P2_Eiko_112_116", "texto_pt",
     "desde cerca de 30 cm até cerca de 3 cm, e mesmo até cerca de 3 cm",
     "desde cerca de 30 cm até cerca de 9 cm, e mesmo até cerca de 3 cm", 1),
    ("P1_Tijotengoku_43_74", "texto_pt",
     "A figura tinha cerca de 2,1 cm e atingia o teto de tão grande",
     "A figura ocupava cerca de sete décimos da altura até o teto, de tão grande", 1),
    ("P2_Eiko_71_87", "texto_pt",
     "ultrapassar cem milhões de koku — tudo isso é canja",
     "ultrapassar cem milhões de koku (cerca de 18 bilhões de litros) — tudo "
     "isso é canja", 1),
    ("P1_Tijotengoku_23_47", "texto_pt",
     "o pagamento do estipêndio em koku aos daimiôs hereditários",
     "o pagamento do estipêndio em koku (石高, a base fiscal do feudo) aos "
     "daimiôs hereditários", 1),

    # ============================================ GLOSSÁRIO
    ("P1_Tijotengoku_28_61", "texto_pt",
     "Como o Komyo-Nyorai é uma Imagem da Luz Divina",
     "Como o Komyo-Nyorai é um objeto sagrado de culto (goshintai)", 1),
    ("P1_Tijotengoku_30_64", "texto_pt",
     "a Imagem da Luz Divina deve ser feita de hinoki",
     "o objeto sagrado de culto (goshintai) deve ser feito de hinoki", 1),
    ("P3_Kyusei_50_301", "texto_pt",
     'o poema de louvor "Ainda que seja qual for a provação',
     'o Salmo "Ainda que seja qual for a provação', 1),
    ("P1_Tijotengoku_12_23", "texto_pt",
     "entre o espírito de vermes intestinais e o espírito de gato",
     "entre o espírito de serpente (長虫) e o espírito de gato", 1),
    ("P1_Tijotengoku_12_23", "texto_pt",
     "Há muitos casos em que vermes intestinais ou gatos estão possuídos",
     "Há muitos casos em que serpentes ou gatos estão possuídos", 1),
    ("P1_Tijotengoku_17_36", "texto_pt",
     "recite o Norito da Grande Purificação", "recite o Amatsu Norito", 1),
    ("P3_Kyusei_59_320", "texto_pt",
     "recitei com todo o fervor o Norito de Amatsu",
     "recitei com todo o fervor o Amatsu Norito (Norito Celestial)", 1),
    # 五六七 (número/igreja) → Miroku
    ("P3_Kyusei_51_304", "texto_pt", "Igreja 567", "Igreja Miroku", 1),
    ("P3_Kyusei_49_298", "texto_pt",
     "Igreja Média Hikari [do] 567", "Igreja Média Hikari de Miroku", 1),
    ("P3_Kyusei_59_320", "texto_pt",
     "Igreja Miroku 567", "Igreja Grande Miroku", 2),
    ("P3_Kyusei_64_326", "texto_pt",
     "Igreja Grande 567", "Igreja Grande Miroku", 1),
    ("P1_Tijotengoku_21_42", "texto_pt",
     "a do Culto Especial de 567 do ano passado",
     "a do Grande Culto de Miroku do ano passado", 1),

    # ============================================ NOMES PRÓPRIOS
    ("P1_Tijotengoku_24_50", "texto_pt", "Tsuranuki", "Tsurayuki", 1),
    ("P2_Eiko_134_151", "texto_pt", "Yamahiko", "Yamabiko", 10),
    ("P2_Eiko_168_227", "texto_pt", '"BAS" e "injeções"', '"PAS" e "injeções"', 1),
    ("P3_Kyusei_52_306", "texto_pt",
     "mordido por uma cobra aodaishō", "mordido por uma víbora mamushi", 1),
    ("P1_Tijotengoku_20_41", "texto_pt",
     '"Tochiboki-san"', '"Tochinoki-san"', 1),
    ("P2_Eiko_254_285", "texto_pt",
     "Igreja Média Hakui", "Igreja Média Hakuai", 1),
    ("P3_Kyusei_54_311", "texto_pt", "Kuzō", "Kyūzō", 0),
    ("P1_Tijotengoku_29_63", "texto_pt",
     "o Santuário Kaji", "o Santuário Karo", 1),

    # ============================================ INVERSÕES
    ("P1_Tijotengoku_12_20", "texto_pt",
     "de acontecimentos de quando ela tinha apenas cinco anos",
     "de acontecimentos de quando ele tinha apenas cinco anos", 1),
    ("P1_Tijotengoku_17_36", "texto_pt",
     "um irmão mais novo do falecido marido, morto em Iwo Jima na guerra, "
     "estava levando a criança consigo",
     "um irmão mais novo do marido (morto em Iwo Jima na guerra) estava "
     "levando a criança consigo", 1),
    ("P1_Tijotengoku_50_80", "texto_pt",
     "quanto à proteção divina que esteve suspensa durante os primeiros dez meses",
     "quanto à proteção divina que fez cessar a bebida durante os primeiros dez meses", 1),
    ("P3_Kyusei_59_320", "texto_pt",
     "Será que recebi do meu filho primogênito a vida da criança que estava "
     "para nascer?",
     "Será que a vida da criança que estava para nascer foi concedida ao meu "
     "filho primogênito?", 1),
    ("P2_Eiko_254_285", "texto_pt",
     "dei alta em trinta de setembro", "recebi alta em trinta de setembro", 1),
    ("P2_Eiko_136_154", "texto_pt",
     "o quão terrível é o efeito do espírito das toxinas medicamentosas sobre o corpo",
     "o quão terríveis são as coisas que as toxinas medicamentosas causam ao "
     "espírito e ao corpo", 1),
    ("P2_Eiko_86_158", "texto_pt",
     "não deram à sua o nome nada moderno de Igreja Messiânica?",
     "não deram à sua o nome terrivelmente moderno de Igreja Messiânica?", 1),
    ("P2_Eiko_193_239", "texto_pt",
     "também em minha casa paterna em Aomori, ela foi admitida como membro dos fiéis",
     "também os de minha casa paterna em Aomori foram admitidos como fiéis", 1),
    ("P2_Eiko_163_222", "texto_pt",
     "Primeiro, semeei as sementes em 10 de abril",
     "Primeiro, separei as sementes em 10 de abril", 1),
    ("P3_Kyusei_54_311", "texto_pt",
     "faça a purificação pra mim, vai, papai!",
     "enxote-o pra mim, vai, papai!", 1),
]

NOTAS = {
    "P1_Tijotengoku_3_9": None,   # preenchido abaixo (JP)
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cache: dict[str, dict] = {}
    falhas: list[str] = []
    ok = 0

    def carregar(item: str) -> dict:
        if item not in cache:
            cache[item] = json.loads((ITENS / f"{item}.json").read_text(encoding="utf-8"))
        return cache[item]

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
            {"tipo": "fix_auditoria_r3", "data": stamp, "campo": campo}
        )
        ok += 1

    print(f"substituições aplicadas: {ok} | falhas: {len(falhas)}")
    for f in falhas:
        print("  [FALHA]", f)

    if args.aplicar and not falhas:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        for item, d in cache.items():
            arq = ITENS / f"{item}.json"
            shutil.copy2(arq, BACKUPS / f"{item}_r3_{stamp}.json")
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
