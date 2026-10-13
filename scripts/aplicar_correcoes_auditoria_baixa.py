#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Correções dos achados de gravidade baixa da auditoria dos periódicos.

Agrupa: formas canónicas do glossário (御利益, 御神徳, 運命, 御浄化, 観音様…),
português, nomes próprios, primeira ocorrência, métricas, inversões,
acréscimos, junção e notas finais omitidas.

Uso:  .venv/bin/python scripts/aplicar_correcoes_auditoria_baixa.py [--aplicar]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from traduzir_periodicos_meishu_sama import divide_chunks, traduzir_com_alertas  # noqa: E402

ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_auditoria"

SUBS: list[tuple[str, str, str, str, int]] = [
    # ---------------------------------------------------- glossário
    ("P2_Eiko_131_145", "texto_pt",
     "recebendo as mais diversas graças, passamos os dias com alegria",
     "recebendo os mais diversos benefícios materiais, passamos os dias com "
     "alegria", 1),
    ("P3_Kyusei_64_326", "texto_pt",
     "Ah! Diante deste milagre, desta graça,",
     "Ah! Diante deste milagre, deste benefício material,", 1),
    ("P1_Tijotengoku_13_24", "texto_pt",
     "concedeu a graça da cura das doenças por meio de remédios espirituais",
     "concedeu o benefício material da cura das doenças por meio de remédios "
     "espirituais", 1),
    ("P1_Tijotengoku_32_66", "texto_pt",
     "em duas semanas recebeu o benefício [a graça]",
     "em duas semanas recebeu o benefício material", 1),
    ("P4_Hikari_33_375", "titulo_pt",
     "O Ohikari sem Benefícios", "O Ohikari sem Benefício Material", 1),
    ("P3_Kyusei_49_298", "texto_pt",
     "agradecemos às vastas e ilimitadas graças divinas",
     "agradecemos à vasta e ilimitada Virtude Divina", 1),
    ("P2_Eiko_129_141", "texto_pt",
     "tenho recebido inúmeras proteções divinas e graças divinas e, por essa bênção",
     "tenho recebido inúmeras proteções divinas e Virtudes Divinas e, por essa "
     "bênção", 1),
    ("P2_Eiko_129_141", "texto_pt",
     "diante dessa grandiosa Graça Divina as lágrimas caíram sem cessar",
     "diante dessa grandiosa Virtude Divina as lágrimas caíram sem cessar", 1),
    ("P2_Eiko_129_141", "texto_pt",
     "diante da grandeza da Graça Divina", "diante da grandeza da Virtude Divina", 1),
    ("P2_Eiko_238_271", "texto_pt",
     "temos recebido diariamente grandiosas graças divinas",
     "temos recebido diariamente a grandiosa Virtude Divina", 1),
    ("P2_Eiko_238_271", "texto_pt",
     "Dentre as muitas graças divinas que temos recebido",
     "Dentre as muitas Virtudes Divinas que temos recebido", 1),
    ("P2_Eiko_238_271", "texto_pt",
     "sobre a graça divina concedida a meu neto Hajime",
     "sobre a Virtude Divina concedida a meu neto Hajime", 1),
    ("P3_Kyusei_61_321", "texto_pt",
     "Dentre as numerosas graças divinas que recebi",
     "Dentre as numerosas Virtudes Divinas que recebi", 1),
    ("P1_Tijotengoku_19_39", "texto_pt",
     "entre o temperamento das pessoas e o destino.",
     "entre o temperamento das pessoas e o destino mutável.", 1),
    ("P2_Eiko_158_212", "texto_pt",
     "sua sorte sofre de imediato uma grande reviravolta",
     "seu destino mutável sofre de imediato uma grande reviravolta", 1),
    ("P2_Eiko_116_123", "texto_pt",
     "fizemos consagrar a Byōbu Kannon,",
     "fizemos consagrar a Byōbu Kannon-Sama,", 1),
    ("P1_Tijotengoku_24_51", "texto_pt",
     "a atuação do Miroku do corpo de resposta (ōjin)",
     "a atuação do Miroku do corpo de recompensa (hōjin)", 1),
    ("P1_Tijotengoku_22_44", "texto_pt",
     "Foi esse o início do período dos Reinos Combatentes",
     "Foi esse o início do período Sengoku", 1),
    ("P2_Eiko_87_160", "texto_pt",
     "eu gostaria de dizer que é cada um por si, mas seria cruel demais",
     "eu gostaria de dizer que cada um colhe o que plantou, mas seria cruel "
     "demais", 1),
    # ---------------------------------------------------- português
    ("P1_Tijotengoku_24_51", "texto_pt",
     "Tenho sinais (negra) no centro da testa",
     "Tenho sinais (pintas negras) no centro da testa", 1),
    ("P1_Tijotengoku_48_78", "texto_pt",
     "após cerca de três anos, fui obrigado a aceitar, sem desejar",
     "após cerca de três anos, fui obrigada a aceitar, sem desejar", 1),
    ("P1_Tijotengoku_48_78", "texto_pt",
     "concedei vossa proteção divina dia após dia; e, após a conversão, "
     "especialmente, permitistes-nos a sagrada dedicação.",
     "concedeis vossa proteção divina dia após dia; e, após a conversão, "
     "especialmente, permitistes-nos a sagrada dedicação.", 1),
    ("P2_Eiko_116_123", "texto_pt",
     "eu, seguindo o exemplo que eu mesmo já havia dado antes, meu pai e eu "
     "nos convertemos",
     "eu me converti primeiro e, em seguida, meu pai também se converteu", 1),
    ("P2_Eiko_120_129", "texto_pt",
     "Dois filhos pequenos salvas da torrente de lama",
     "Dois filhos amados salvos da torrente de lama", 1),
    ("P2_Eiko_124_136", "texto_pt",
     "provavelmente o verão passar como nuvem e fumaça diante dos olhos, como sempre.",
     "provavelmente, como sempre, isso passará como nuvem e fumaça diante dos "
     "olhos.", 1),
    ("P2_Eiko_194_240", "titulo_pt",
     "Aspectos de uma Doença Espiritual", "Um Exemplo de Doença Espiritual", 1),
    ("P2_Eiko_226_263", "titulo_pt",
     'Meishu-Sama fala sobre "A Importância do Havaí',
     'Meishu-Sama fala sobre "A Importância do Havaí"', 1),
    ("P2_Eiko_244_274", "texto_pt",
     "Em nenhum lugar havia algo que eu pudesse obter, e era tão feia",
     "Era de uma feiura sem nenhum atrativo, e tão feia", 1),
    ("P2_Eiko_247_277", "texto_pt",
     "Foi no ano passado, não é? O que fizeram a celebração comemorativa",
     "Foi no ano passado, não é? A celebração comemorativa", 1),
    ("P2_Eiko_257_288", "texto_pt", "rejuvenescEU", "rejuvenesceu", 1),
    ("P2_Eiko_74_90", "texto_pt",
     'a expressão "falta de merda e peido"',
     'a expressão "o pecado de merda e peido"', 1),
    ("P2_Eiko_81_95", "texto_pt",
     "quero trocá-la por um novo", "quero trocá-la por uma nova", 1),
    ("P3_Kyusei_48_294", "titulo_pt",
     'A Veracidade do Johrei e a Crítica à "Graça',
     'A Veracidade do Johrei e a Crítica à "Graça"', 1),
    ("P4_Hikari_22_354", "titulo_pt",
     'Requerendo Reflexão do "Yomiuri',
     'Requerendo Reflexão do "Yomiuri"', 1),
    ("P4_Hikari_38_382", "texto_pt",
     "deve à reencarnação de uma 蜷 (toguro ou nina?)",
     "deve-se à reencarnação de um toguro (ou nina?)", 1),
    # ---------------------------------------------------- nomes próprios
    ("P3_Kyusei_64_326", "texto_pt",
     "Igreja Média Hikari no Michi, Igreja Grande Taisei",
     "Igreja Média Kōmyō no Michi, Igreja Grande Taisei", 1),
    ("P3_Kyusei_64_326", "texto_pt",
     "Igreja 567, Igreja Média Shinmoto",
     "Igreja Grande 567, Igreja Média Shinmoto", 1),
    ("P2_Eiko_106_109", "texto_pt", "Yumei-kun", "Musei-kun", 2),
    ("P2_Eiko_136_154", "texto_pt", "Igreja Média Seimei", "Igreja Média Seisei", 1),
    ("P2_Eiko_247_277", "texto_pt",
     "tomar resolutamente Diagin", "tomar resolutamente Diajin", 1),
    ("P4_Hikari_42_393", "texto_pt", "Sr. Mune Akizuki", "Sr. Sō Akizuki", 1),
    # ---------------------------------------------------- primeira ocorrência
    ("P1_Tijotengoku_14_30", "texto_pt",
     "mandei fazer as tabuletas memoriais dos antepassados",
     "mandei fazer as tabuletas mortuárias (ihai) dos antepassados", 1),
    ("P1_Tijotengoku_26_56", "texto_pt",
     "venho venerando as tábuas memoriais dos antepassados de todas as gerações "
     "da família Oishi",
     "venho venerando as tabuletas mortuárias (ihai) dos antepassados de todas "
     "as gerações da família Oishi", 1),
    ("P1_Tijotengoku_26_56", "texto_pt", "tábuas memoriais", "tabuletas", 6),
    ("P1_Tijotengoku_32_66", "texto_pt",
     "Ao recitar o Norito Amatsu", "Ao recitar o Amatsu Norito (Norito Celestial)", 1),
    ("P1_Tijotengoku_32_66", "texto_pt",
     "memorizava o Norito Amatsu", "memorizava o Amatsu Norito", 1),
    # ---------------------------------------------------- métricas
    ("P1_Tijotengoku_22_44", "texto_pt",
     "situada a vários jō acima do riacho",
     "situada cerca de 9 a 12 m acima do riacho", 1),
    ("P1_Tijotengoku_49_79", "texto_pt",
     "caminha com passos cautelosos por dois ou três quarteirões",
     "caminha com passos cautelosos por cerca de 200 a 330 m", 1),
    # ---------------------------------------------------- inversões
    ("P2_Eiko_122_132", "texto_pt",
     "Como a Sra. Konishi disse", "Como disse o reverendo instrutor", 1),
    ("P2_Eiko_222_260", "texto_pt",
     "Se não me engano, há alguns anos", "Não me esqueço: há alguns anos", 1),
    # ---------------------------------------------------- acréscimos
    ("P2_Eiko_125_138", "texto_pt",
     "erro de discernimento, erro de julgamento, desencontro à mesa",
     "erro de discernimento, desencontro à mesa", 1),
    ("P2_Eiko_89_165", "texto_pt",
     "como se lavassem o traseiro com pedra-pomes",
     "como se lavassem o traseiro com sabão", 1),
    # ---------------------------------------------------- junção
    ("P4_Hikari_15_345", "texto_pt",
     "Quem desperta para isso, viver no mundo se torna fácil.",
     "Para quem desperta isto, viver no mundo torna-se fácil.", 1),
    # ---------------------------------------------------- omissões (conteúdo)
    ("P2_Eiko_131_146", "texto_pt",
     "quero esmagar a teoria dos insetos — que não são insetos.",
     "quero esmagar o ateísmo (ムシン論, «teoria dos insetos» — jogo de "
     "palavras com 無神論, «ateísmo»).", 1),
    ("P2_Eiko_196_245", "texto_pt",
     "Kayoko (então com três anos), para que lhe curassem a supuração",
     "Kayoko (então com três anos), para que lhe curassem a supuração, que já "
     "se arrastava havia cerca de meio ano", 1),
    ("P2_Eiko_199_248", "texto_pt",
     "e, ofegante, começou a falar:",
     "e, dizendo que lhe fora concedido um prazo de dez minutos, ofegante, "
     "começou a falar:", 1),
]

# notas finais omitidas: item -> JP
NOTAS = {
    "P1_Tijotengoku_24_49":
        "(注) アプレゲール 戦後派。第一次大戦後、フランスなどに興った芸術上の"
        "新傾向。特に第二次大戦後、従来の思想・道徳に拘束されず奔放に行動する"
        "若い人々。",
    "P2_Eiko_69_85":
        "(注) アプレゲール、戦後派。第一次大戦後、フランスなどに興った芸術上の"
        "新傾向。特に第二次大戦後、従来の思想・道徳に拘束されずに行動する"
        "若い人々。",
    "P2_Eiko_72_88":
        "(注) 紫微（しび）、《「紫微垣（しびえん）」の略》中国古代の天文学で、"
        "天を三垣（えん）二八宿に分けた、その一。北極星を中心とした、小熊座・"
        "大熊座・竜座・カシオペヤ座などの星座群にあたり、天帝の住む場所と"
        "された。転じて、天子・天位・宮廷を示す。紫微宮。\n\n"
        "鹿児自物（かごじもの）、《「じもの」は接尾語》鹿の子のように。鹿の子"
        "は一年に一回、一頭だけ生まれるところから、あとに「ひとり」「ひとり子」"
        "などを伴う修飾句として用いられる。",
    "P2_Eiko_97_182":
        "(注) 玄翁（げんのう）頭の両端にとがった部分のない金槌。石を割ったり、"
        "のみをたたいたりするのに用いる。「玄能」",
    "P4_Hikari_29_362":
        "(注) 奇貨（きか）居（お）くべし、史記、呂不韋が秦の始皇帝の父親"
        "（子楚）を援助するときの言葉「掘り出し物だ。今が買いどきだ」という"
        "意味。この故事から、得がたい機会だからこれをうまく利用しなければ"
        "ならない。という意味で使う。",
    "P4_Hikari_32_371":
        "(注) 蟷螂の斧（とうろうのおの）、カマキリがどんなに強い相手に向かっても"
        "斧のような前足を振り上げて威嚇するさま。はかない抵抗のたとえ。",
    "P4_Hikari_43_403":
        "(注) この御文章は、寸鉄と差し替えになった版がある。その寸鉄は"
        "「光」46号に再掲載されている。",
}

# entrada adicional a acrescentar a uma nota já existente
NOTAS_EXTRA = {
    "P2_Eiko_102_104": (
        "Neste caso: “O que é a eleição...”.",
        "Neste caso: “O que é a eleição...”.\n\n"
        "Osan-don (お爨どん): designação comum da criada que trabalha na cozinha.",
    ),
}


def traduzir_nota(jp: str) -> str:
    partes = []
    for sub in divide_chunks(jp, 1400):
        nova, _ = traduzir_com_alertas(sub, "Meishu-Sama (autor do artigo)")
        if not nova:
            raise RuntimeError("sub-bloco da nota voltou vazio")
        partes.append(nova)
    nota = "\n\n".join(partes).strip()
    return nota if nota.startswith("(") else f"(Nota) {nota}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cache: dict[str, dict] = {}
    falhas: list[str] = []
    n_ok = 0

    def carregar(item: str) -> dict:
        if item not in cache:
            cache[item] = json.loads((ITENS / f"{item}.json").read_text(encoding="utf-8"))
        return cache[item]

    for item, campo, old, new, esperado in SUBS:
        d = carregar(item)
        atual = d.get(campo) or ""
        n = atual.count(old)
        if n != esperado:
            msg = (f"{item}.{campo}: {n} ocorrência(s), esperado {esperado} — "
                   f"{old[:70]!r}")
            print("  [FALHA]", msg)
            falhas.append(msg)
            continue
        d[campo] = atual.replace(old, new)
        d.setdefault("reparos", []).append(
            {"tipo": "fix_auditoria_baixa", "data": stamp, "campo": campo}
        )
        n_ok += 1

    for item, jp_nota in NOTAS.items():
        d = carregar(item)
        if any(r.get("tipo") == "nota_auditoria_baixa" for r in d.get("reparos", [])):
            print(f"  [skip] {item}: nota já presente")
            continue
        try:
            nota = traduzir_nota(jp_nota)
        except Exception as exc:  # noqa: BLE001
            msg = f"{item}: falha na nota ({exc})"
            print("  [FALHA]", msg)
            falhas.append(msg)
            continue
        d["texto_pt"] = (d.get("texto_pt") or "").rstrip() + "\n\n" + nota
        d.setdefault("reparos", []).append(
            {"tipo": "nota_auditoria_baixa", "data": stamp}
        )
        n_ok += 1
        print(f"  [ok] {item}: nota final ({len(nota)}c)")

    for item, (old, new) in NOTAS_EXTRA.items():
        d = carregar(item)
        n = (d.get("texto_pt") or "").count(old)
        if n != 1:
            msg = f"{item}: entrada extra da nota não localizada ({n}×)"
            print("  [FALHA]", msg)
            falhas.append(msg)
            continue
        d["texto_pt"] = d["texto_pt"].replace(old, new)
        d.setdefault("reparos", []).append(
            {"tipo": "nota_extra_auditoria", "data": stamp}
        )
        n_ok += 1
        print(f"  [ok] {item}: entrada extra na nota")

    print(f"\ncorreções: {n_ok} | falhas: {len(falhas)}")
    for f in falhas:
        print("   -", f)

    if args.aplicar and not falhas:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        for item, d in cache.items():
            arq = ITENS / f"{item}.json"
            shutil.copy2(arq, BACKUPS / f"{item}_baixa_{stamp}.json")
            arq.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
        print(f"gravados {len(cache)} ficheiros")
    elif args.aplicar:
        print("NADA GRAVADO")
        return 1
    else:
        print("(dry-run; use --aplicar para gravar)")
    return 0 if not falhas else 1


if __name__ == "__main__":
    raise SystemExit(main())
