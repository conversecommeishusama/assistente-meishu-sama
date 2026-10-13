#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ronda 4 — correções dos achados de gravidade baixa da auditoria R2.

Todos os itens foram verificados contra o japonês (e contra as convenções já
fixadas no acervo) antes de entrar nesta lista. Nada é aplicado em bloco:
cada substituição exige ocorrência única.

Uso:  .venv/bin/python scripts/aplicar_correcoes_auditoria_r4.py [--aplicar]
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
    # ============================================ PORTUGUÊS
    ("P3_Kyusei_56_315", "texto_pt",
     "Observando o percurso desta paciente, não há nada que não confirme",
     "Observando o percurso deste paciente, não há nada que não confirme", 1),
    ("P2_Eiko_134_151", "texto_pt",
     '"Uma Protesto contra', '"Um Protesto contra', 1),
    ("P1_Tijotengoku_3_9", "texto_pt",
     "Ainda que esgoteem a voz pregando", "Ainda que esgotem a voz pregando", 1),
    ("P1_Tijotengoku_36_67", "texto_pt",
     "da árvore que habitava o cinamomo, devido ao corte da árvore",
     "da árvore que habitava o enoki, devido ao corte da árvore", 1),
    ("P1_Tijotengoku_36_67", "texto_pt",
     "plante um cinamomo", "plante um enoki", 1),
    ("P2_Eiko_196_245", "texto_pt",
     '" — Assim ela sempre me encorajava.',
     '" — Assim ele sempre me encorajava.', 1),
    ("P2_Eiko_97_183", "texto_pt",
     "ainda vem argumentar com Lógica e se vangloriar",
     "ainda vem argumentar com lógica e se vangloriar", 1),
    ("P3_Kyusei_51_304", "texto_pt",
     "minha segunda filha, de constituição linfática, que febril ao menor motivo",
     "minha segunda filha, de constituição linfática, que tinha febre ao menor "
     "motivo", 1),
    ("P3_Kyusei_52_306", "texto_pt",
     "fui tomado pela ansiedade de que poderia acontecer o mesmo",
     "fui tomada pela ansiedade de que poderia acontecer o mesmo", 1),
    ("P4_Hikari_39_384", "texto_pt",
     "mesmo os parasitas que hoje são considerado grande problema, em especial "
     "o lombriga, têm como tese",
     "mesmo os parasitas que hoje são considerados grande problema, em especial "
     "a lombriga, têm como tese", 1),
    ("P4_Hikari_44_405", "texto_pt",
     "E isso aumenta dia após mês, mês após mês.",
     "E isso aumenta dia a dia, mês a mês.", 1),
    ("P4_Hikari_16_347", "texto_pt",
     "ficam atônitos com a notoriedade de seus efeitos",
     "ficam atônitos com a evidência de seus efeitos", 1),
    ("P4_Hikari_32_372", "texto_pt",
     "estima em cento e setenta ou oitenta mil",
     "estima em cento e setenta mil ou cento e oitenta mil", 1),
    ("P3_Kyusei_54_311", "titulo_pt",
     "Romance de Visita: Hakama para Dois",
     "Romance de Indagações: Duas Calças", 1),
    ("P3_Kyusei_54_311", "texto_pt",
     "Calças para Dois (1) — Iwasaki Sakae",
     "Duas Calças (1) — Iwasaki Sakae", 1),
    ("P1_Tijotengoku_12_20", "texto_pt",
     "A História dos Fantasmas (1)", "A História dos Fantasmas (1)", 0),
    ("P1_Tijotengoku_12_20", "texto_pt",
     "A História dos Fantasmas (2)", "A História dos Fantasmas (2)", 0),
    ("P1_Tijotengoku_12_20", "texto_pt",
     "Histórias de Fantasmas (3)", "A História dos Fantasmas (3)", 1),
    ("P1_Tijotengoku_12_20", "texto_pt", "Exemplo um", "Exemplo um", 0),

    # ============================================ INVERSÕES
    ("P1_Tijotengoku_37_68", "texto_pt",
     "é a irmã mais velha, a Flor-Princesa", "é o irmão mais velho, a Flor-Princesa", 1),
    ("P2_Eiko_161_219", "texto_pt",
     "Quando o presidente recebeu o Ohikari em meu nome, fiquei com o peito",
     "Quando recebi o Ohikari por intermédio do presidente, fiquei com o peito", 1),
    ("P1_Tijotengoku_39_70", "texto_pt",
     "o olho negro esquerdo se desvia do centro para a esquerda de forma fixa",
     "o olho negro esquerdo não se desvia do centro para a esquerda, ficando "
     "fixo", 1),
    ("P2_Eiko_204_253", "texto_pt",
     "se pensa também em um serviço de ônibus direto do Líder até o cume da montanha",
     "se pensa também num serviço de ônibus operado diretamente pelo fundador "
     "até o cume da montanha", 1),
    ("P2_Eiko_132_147", "texto_pt",
     "que toda vez que chorava ficava de bruços esperneando",
     "que toda vez que chorava virava-se de costas e esperneava", 1),
    ("P3_Kyusei_50_301", "texto_pt",
     "o pai da criança recomendou que tomássemos bastante cuidado",
     "meu marido recomendou que tomássemos bastante cuidado", 1),
    ("P2_Eiko_244_274", "texto_pt",
     'no artigo "O Homem Moderno que Carrega uma Bomba", publicado no Eikō nº '
     '184, juntamente com "O Johrei pelas Letras Impressas", Meishu-Sama ensina',
     'no artigo "O Johrei pelas Letras Impressas", publicado no Eikō nº 184 '
     'juntamente com "O Homem Moderno que Carrega uma Bomba", Meishu-Sama ensina', 1),

    # ============================================ MÉTRICAS
    ("P3_Kyusei_54_311", "texto_pt",
     "O piso de terra de um único cômodo atravessa da frente aos fundos.",
     "O piso de terra de cerca de 1,8 m de largura atravessa da frente aos fundos.", 1),
    ("P1_Tijotengoku_39_69", "texto_pt",
     "ficassem a apenas dois ou três quarteirões de distância",
     "ficassem a apenas cerca de 220 a 330 m de distância", 1),
    ("P2_Eiko_256_287", "texto_pt",
     "excreção de cerca de 2 L de urina", "excreção de cerca de 1,8 L de urina", 1),
    ("P1_Tijotengoku_16_33", "texto_pt",
     "isso chegará e será sentido a cerca de 3930 km de distância",
     "isso chegará e será sentido a muitos milhares de quilómetros de distância", 1),

    # ============================================ ACRÉSCIMOS
    ("P2_Eiko_163_222", "texto_pt",
     "de fato, houve alguma — algumas consultas e não poucas reações —, mas parece",
     "de fato, houve alguma — algumas consultas e alguma repercussão —, mas parece", 1),
    ("P2_Eiko_105_108", "texto_pt",
     'com o caractere "macaco" [申] por baixo',
     'com o caractere "macaco" [申] à direita', 1),
    ("P2_Eiko_96_179", "texto_pt", "a filha de quatro anos", "a criança de quatro anos", 1),
    ("P1_Tijotengoku_28_61", "texto_pt",
     "durante o Johrei do dia 8 de agosto, por volta das sete da noite",
     "durante o Johrei de agosto, por volta das sete da noite", 1),

    # ============================================ NÚMEROS
    ("P1_Tijotengoku_43_74", "texto_pt",
     "vomitava de uma a três vezes por dia (líquido amarelo)",
     "vomitava duas ou três vezes por dia (líquido amarelo)", 1),

    # ============================================ GLOSSÁRIO
    ("P1_Tijotengoku_40_72", "texto_pt",
     "As pernas — em especial a região do 席 — doem",
     "As pernas — em especial a região do joelho — doem", 1),
    ("P1_Tijotengoku_40_72", "texto_pt",
     "tabuletas dos espíritos ancestrais de todas as gerações",
     "tabuletas mortuárias (ihai) dos espíritos ancestrais de todas as gerações", 1),
    ("P1_Tijotengoku_51_81", "texto_pt",
     "gostaria de cultuar novas tabuletas memoriais dos antepassados",
     "gostaria de cultuar novas tabuletas mortuárias (ihai) dos antepassados", 1),
    ("P1_Tijotengoku_41_73", "texto_pt",
     "sufragamos sua tábua memorial", "sufragamos sua tabuleta", 1),
    ("P3_Kyusei_51_304", "texto_pt",
     "Junto à gratidão por esta graça divina, choro de emoção",
     "Junto à gratidão por este benefício material, choro de emoção", 1),
    ("P3_Kyusei_51_304", "texto_pt",
     "toda a família recebeu incontáveis graças",
     "toda a família recebeu incontáveis benefícios materiais", 1),
    ("P2_Eiko_193_239", "texto_pt",
     "para se receber a graça", "para se receber o benefício material", 1),
    ("P1_Tijotengoku_12_23", "texto_pt",
     "O caso acima seria maldição de Ryūjin?",  # 木龍 ≠ 龍神
     "O caso acima seria maldição do dragão da árvore (Mokuryū)?", 1),
    ("P1_Tijotengoku_20_41", "texto_pt",
     "papel de porta corrediça [kōshi]", "papel de porta corrediça [karakami]", 1),
    ("P2_Eiko_121_131", "texto_pt", "iguais às loachas", "iguais aos dojō (loach)", 1),
    ("P4_Hikari_31_369", "texto_pt",
     "Sr. Yusuri, pode se vangloriar", "Sr. Extorsionista, pode se vangloriar", 1),
    ("P4_Hikari_34_377", "texto_pt",
     "a coluna 寸鉄 também ficou", "a coluna Sun-Tetsu também ficou", 1),
    ("P4_Hikari_44_407", "texto_pt",
     "o primeiro recurso é o 寸鉄, não é?", "o primeiro recurso é o Sun-Tetsu, não é?", 1),
    ("P1_Tijotengoku_40_71", "texto_pt",
     "(Kamisadame)", "(Kansadame)", 1),
    ("P2_Eiko_119_127", "texto_pt",
     'o volume do Rokutō-sanryaku, que havia muito desejava',
     'o volume do Rikutō-sanryaku, que havia muito desejava', 1),

    # ============================================ NOMES PRÓPRIOS
    ("P1_Tijotengoku_11_4", "texto_pt",
     "o Sr. Ministro veio nos visitar", "o professor veio nos visitar", 1),
    ("P1_Tijotengoku_12_20", "texto_pt", "Westby", "Westby", 0),
    ("P1_Tijotengoku_12_20", "texto_pt", "Westbee", "Westby", 2),
    ("P1_Tijotengoku_12_20", "texto_pt",
     "Que o Deus Celestial o abençoe, leitor.",
     "Que o Deus Celestial o abençoe, Rector.", 1),
    ("P1_Tijotengoku_27_59", "texto_pt",
     "morava em Kakudahama, em Tóquio", "morava em Kakuda, em Tóquio", 1),
    ("P2_Eiko_191_237", "texto_pt",
     "a peregrinação do casal ao Santuário Central",
     "a peregrinação do casal à Sede Central", 1),
    ("P1_Tijotengoku_17_36", "texto_pt",
     "de Atae-cho, província de Mie", "de Atawa-chō, província de Mie", 1),
    ("P1_Tijotengoku_4_13", "texto_pt",
     "[Igreja Kannon do Grande Japão]", "[Igreja Kannon do Japão]", 1),
    ("P2_Eiko_168_227", "texto_pt",
     "dei entrada no Hospital Kyūsaikai", "dei entrada no Hospital Ekisaikai", 1),
    ("P2_Eiko_225_262", "texto_pt",
     "Grande Igreja de Tossu", "Grande Igreja de Tosu", 1),
    ("P2_Eiko_72_88", "texto_pt",
     "Kagoshimono (鹿児自物)", "Kagojimono (鹿児自物)", 1),
    ("P2_Eiko_73_89", "texto_pt",
     "A revista Shinjō, de novo", "A revista Shinsō, de novo", 1),
    ("P3_Kyusei_55_313", "texto_pt",
     "Hideshi Bajo (45)", "Hide Bajo (45)", 1),
    ("P2_Eiko_232_266", "texto_pt",
     "serviço de construção de Zuiunkyo", "serviço de construção de Zuiunzan", 1),
    ("P2_Eiko_98_185", "texto_pt",
     "no distrito de Kitatajima", "no distrito de Kitatoshima", 1),
    ("P2_Eiko_134_151", "texto_pt",
     "um menino chamado Eguchi Kōichi", "um menino chamado Eguchi Eichi", 1),
    ("P3_Kyusei_54_311", "texto_pt", "Kuzō", "Kyūzō", 2),

    # ============================================ DEGENERAÇÃO DE EDIÇÃO
    ("P1_Tijotengoku_32_66", "texto_pt",
     "de madeira a cerca de 2,4 m [cerca de 2,4 metros] abaixo",
     "de madeira a cerca de 2,4 m abaixo", 1),
    ("P2_Eiko_102_103", "texto_pt",
     "mesmo em cerca de 0,5 ha sendo 0,5 ha", "mesmo sendo cerca de 0,5 ha", 1),
    ("P4_Hikari_20_353", "texto_pt",
     "chega a cerca de 3 cm [≈3 cm]", "chega a cerca de 3 cm", 1),
    ("P2_Eiko_124_135", "texto_pt",
     "**Do comunismo à fé — convertido do comunismo à fé**",
     "**Do comunismo à fé**", 1),
    ("P3_Kyusei_57_316", "texto_pt",
     'o mesmo se dá com o "1 e 8" (一寸八分, cerca de 5,5 cm) de Kannon-Sama.',
     'o mesmo se dá com o "um e oito" — 一寸八分 (cerca de 5,5 cm) — de Kannon-Sama.', 1),
    ("P2_Eiko_119_128", "titulo_pt",
     "Sun-Tetsu Katsujin [Eikō nº 119]", "Sun-Tetsu Katsujin (Eikō nº 119)", 1),
    ("P2_Eiko_284_292", "texto_pt",
     "funcionários da sede O recebiam com reverência",
     "funcionários da sede o recebiam com reverência", 1),
    ("P4_Hikari_42_392", "texto_pt",
     "Devadatta, ou Devadatta (Daiba-datta), era primo de Shaka.",
     "Devadatta (Daiba-datta) — a forma abreviada 提婆 e a completa 提婆達多 — "
     "era primo de Shaka.", 1),

    # ============================================ OMISSÃO (jogo de palavras)
    ("P2_Eiko_83_97", "texto_pt",
     "à noite, mal consegue dormir direito — é o que se diz.",
     "à noite nem consegue fazer «Nehru» (ネール, trocadilho com 寝る, «dormir») "
     "— é o que se diz.", 1),

    # ============================================ JUNÇÃO
    ("P2_Eiko_132_147", "texto_pt",
     "Nossa Igreja, o milagre de, logo após a conversão e o uso do Ohikari, "
     "manifestar imediatamente o poder divino é algo que sempre se tem demonstrado;",
     "O milagre de, logo após a conversão e o uso do Ohikari, manifestar "
     "imediatamente o poder divino é algo que sempre se tem demonstrado em nossa "
     "Igreja;", 1),
]

# rótulos de fala a pôr em negrito no artigo 191_237 (o mesmo rótulo aparece
# noutras passagens já em negrito)
ROTULOS_191 = ["Suzuki", "Shibuta", "Egashira", "Kawabata", "Miyagi",
               "Hayata", "Kajiwara", "Nagatomo", "Furukawa", "Futami",
               "Sakami", "Moderador", "Presidente", "Senhor Presidente"]


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
            falhas.append(f"{item}.{campo}: {n} occ, esperado {esperado} — {old[:70]!r}")
            continue
        d[campo] = atual.replace(old, new)
        d.setdefault("reparos", []).append(
            {"tipo": "fix_auditoria_r4", "data": stamp, "campo": campo}
        )
        ok += 1

    # rótulos de fala → negrito (consistência de formatação)
    d = carregar("P2_Eiko_191_237")
    pt = d["texto_pt"]
    nrot = 0
    for r in ROTULOS_191:
        padrao = re.compile(rf"(?m)^({re.escape(r)}:)\s*$")
        pt, k = padrao.subn(r"**\1**", pt)
        nrot += k
    if nrot:
        d["texto_pt"] = pt
        d.setdefault("reparos", []).append(
            {"tipo": "fix_rotulos_fala", "data": stamp, "n": nrot}
        )
        ok += 1

    print(f"correções aplicadas: {ok} | falhas: {len(falhas)}")
    for f in falhas:
        print("  [FALHA]", f)

    if args.aplicar and not falhas:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        for item, d in cache.items():
            arq = ITENS / f"{item}.json"
            shutil.copy2(arq, BACKUPS / f"{item}_r4_{stamp}.json")
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
