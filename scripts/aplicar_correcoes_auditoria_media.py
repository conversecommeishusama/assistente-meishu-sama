#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aplica as correções validadas da auditoria (achados de gravidade média).

Cada correção é verificada contra o japonês antes de ser aplicada. Todas as
substituições exigem ocorrência única (a não ser que `n` seja indicado).
Backup em reports/traducao_periodicos/backups_auditoria/.

Uso:  .venv/bin/python scripts/aplicar_correcoes_auditoria_media.py [--aplicar]
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

# ---------------------------------------------------------------- correções
# (item, campo, texto_antigo, texto_novo, nº esperado de ocorrências)
SUBS: list[tuple[str, str, str, str, int]] = [
    # 1-2. 28_61: 小乗的に = "à maneira do Pequeno Veículo (shōjō)", não "no início"
    ("P1_Tijotengoku_28_61", "texto_pt",
     "como método de Johrei, no início (Shojo) esforçar-se ao máximo",
     "como método de Johrei, à maneira do Pequeno Veículo (shōjō), "
     "esforçar-se ao máximo", 1),
    ("P1_Tijotengoku_28_61", "texto_pt",
     '"no início (Shojo)..."', '"à maneira do Pequeno Veículo (shōjō)"...', 1),
    ("P1_Tijotengoku_28_61", "texto_pt",
     "e, para facilitar", "e, para facilitar", 0),  # controlo (0 = ignorar)
    # 2. 28_61: 恒雄 = Tsuneo (não Nagao)
    ("P1_Tijotengoku_28_61", "texto_pt", "Nagao", "Tsuneo", 3),
    # 3. 54_82: 私の水子二名 = os MEUS mizuko, não "da esposa"
    ("P1_Tijotengoku_54_82", "texto_pt",
     "três irmãs, dois fetos de minha esposa, um sobrinho e a mãe da esposa",
     "três irmãs, meus dois mizuko (filhos natimortos), um sobrinho e a mãe "
     "da esposa", 1),
    # 4. 171_232: 浄化しなければよいが = "tomara que não precise purificar-se"
    ("P2_Eiko_171_232", "texto_pt",
     "estava engordando muito, dizia que seria bom purificar-se;",
     "estava engordando muito, dizia: “tomara que não precise passar por "
     "purificação”;", 1),
    # 5. 57_317: 一里 → métrico (1 ri ≈ 3,9 km)
    ("P3_Kyusei_57_317", "texto_pt",
     "percorrer a pé, numa légua de caminho, a cidade de Nagara",
     "percorrer a pé, num percurso de cerca de 4 km, a cidade de Nagara", 1),
    # 7. 18_37: その人の手柄によって = pelos PRÓPRIOS méritos
    ("P1_Tijotengoku_18_37", "texto_pt",
     "Há ainda quem receba graças de Deus pelos méritos de outrem, e pessoas",
     "Há ainda quem receba graças de Deus pelos próprios méritos, e pessoas", 1),
    # 8. 25_53: 道理 = "razão/princípio", não "Caminho Perfeito"
    ("P1_Tijotengoku_25_53", "texto_pt",
     "tendo em mente o Caminho Perfeito acima, observem a questão com serenidade",
     "tendo em mente as razões acima expostas, observem a questão com "
     "serenidade", 1),
    # 9-10. 31_65: marcador em inglês + forma canónica de 位牌
    ("P1_Tijotengoku_31_65", "texto_pt", "Question:", "Pergunta:", 1),
    ("P1_Tijotengoku_31_65", "texto_pt",
     "A ordem das tábuas memoriais está errada.",
     "A ordem das tabuletas mortuárias (ihai) está errada.", 1),
    ("P1_Tijotengoku_31_65", "texto_pt", "tábuas memoriais", "tabuletas", 2),
    ("P1_Tijotengoku_31_65", "texto_pt",
     "e a tábua memorial exposta à esquerda", "e a tabuleta exposta à esquerda", 1),
    # 12. 133_149: 十人中十人 = dez entre dez
    ("P2_Eiko_133_149", "texto_pt",
     "nove entre dez, todas faziam cara de espanto",
     "dez entre dez, todas faziam cara de espanto", 1),
    # 13-14. 水素 = hidrogénio (não "Elemento Água")
    ("P2_Eiko_150_202", "texto_pt",
     "agregado íntimo de Elemento Água", "agregado denso de hidrogênio", 1),
    ("P2_Eiko_159_214", "texto_pt",
     "cria o Elemento Água e desempenha o papel da atividade terrestre",
     "cria o hidrogênio e desempenha o papel da atividade terrestre", 1),
    # 15. 168_227: それは事実が承知しない = "os fatos não o consentem"
    ("P2_Eiko_168_227", "texto_pt",
     "certamente riria de nós — e não há fato que o desminta.",
     "certamente riria de nós — mas os fatos não o consentem.", 1),
    # 16. 178_233: 位牌 → forma canónica
    ("P2_Eiko_178_233", "texto_pt",
     "dedicando-lhe uma placa memorial", "dedicando-lhe uma tabuleta mortuária (ihai)", 1),
    ("P2_Eiko_178_233", "texto_pt", "placa memorial", "tabuleta", 2),
    # 17. 195_244: 一尺余り → métrico
    ("P2_Eiko_195_244", "texto_pt",
     "esta pequena massa de pouco mais de um palmo [de comprimento]",
     "esta pequena massa de pouco mais de 30 cm [de comprimento]", 1),
    # 19. 199_247: 結く = atar
    ("P2_Eiko_199_247", "texto_pt",
     "ele disse que ajudaria a amarrotá-las", "ele disse que ajudaria a atá-las", 1),
    # 20. 214_254: 三宅支部 = Miyake
    ("P2_Eiko_214_254", "texto_pt", "do Posto Mishima", "do Posto Miyake", 1),
    # 21. 219_258: 三家本 = Mikamoto
    ("P2_Eiko_219_258", "texto_pt", "Miyamoto Takao", "Mikamoto Takao", 1),
    # 22. 224_261: 二千万石 → métrico (1 koku ≈ 180 L)
    ("P2_Eiko_224_261", "texto_pt",
     "já faltam vinte milhões de koku;",
     "já faltam vinte milhões de koku (cerca de 3,6 bilhões de litros);", 1),
    # 23. 239_272: 九百万 = 9 milhões
    ("P2_Eiko_239_272", "texto_pt",
     "é preciso aplicar no mínimo de 900 mil a 3 milhões de unidades",
     "é preciso aplicar no mínimo de 9 milhões a 3 milhões de unidades", 1),
    # 24-25. 254_285: 一里 → métrico; 飛躍的に = aos saltos
    ("P2_Eiko_254_285", "texto_pt",
     "caminhar de ida e volta uma légua até o templo de Kokubunji",
     "caminhar de ida e volta cerca de 4 km até o templo de Kokubunji", 1),
    ("P2_Eiko_254_285", "texto_pt",
     "me tornei mais saudável de forma salpicada",
     "me tornei mais saudável de forma extraordinária", 1),
    # 26. 284_292: 栄光 = glória (não o jornal Eikō)
    ("P2_Eiko_284_292", "texto_pt",
     "Pela Eikō deste dia em que me foi concedido estar neste humilde posto, "
     "expresso minha profunda gratidão.",
     "Por esta glória do dia em que me foi concedido estar neste humilde "
     "posto, expresso minha profunda gratidão.", 1),
    # 27. 86_158: アプレゲール = do pós-guerra
    ("P2_Eiko_86_158", "texto_pt",
     "Agora, uma nova religião apregoada, cujo nome já é religião PL",
     "Agora, uma nova religião do pós-guerra (après-guerre), cujo nome já é "
     "religião PL", 1),
    # 28. 98_184: いずれ = mais cedo ou mais tarde
    ("P2_Eiko_98_184", "texto_pt",
     "hora alguma se lançará talvez a bomba atômica sobre a Manchúria",
     "mais cedo ou mais tarde, talvez se lance a bomba atômica sobre a "
     "Manchúria", 1),
    # 30. 54_310: 徳球 = Tokukyū (coerência com 58_318)
    ("P3_Kyusei_54_310", "texto_pt", "O Tokudama, suando", "O Tokukyū, suando", 1),
    # 31. 62_323: コーサン党 = trocadilho com 降参 (rendição)
    ("P3_Kyusei_62_323", "texto_pt",
     "logo ele vai se tornar líder do Partido Comunista.",
     "logo ele vai se tornar líder do Partido da Rendição (kōsan).", 1),
    # 33. 32_374: 苦戦最中でも何でもない = NÃO é batalha difícil
    ("P4_Hikari_32_374", "texto_pt",
     "e não é exagero dizer que estamos em plena batalha difícil; há nisso um "
     "interesse fascinante",
     "e não é de modo algum uma batalha difícil — há nisso um interesse "
     "fascinante", 1),
    # 6. 14_29: título atribui o artigo à revista errada
    ("P1_Tijotengoku_14_29", "titulo_pt",
     "Prefácio (Eikō [revista Eikō], nº 14)",
     "Prefácio (Tijotengoku nº 14)", 1),
]

# notas finais omitidas: item -> texto JP a traduzir e anexar
NOTAS_OMITIDAS = {
    "P2_Eiko_195_244": (
        "(注) アイク・ア元帥（Dwight David Eisenhower、1890-1969）第三四代"
        "アメリカ合衆国大統領（在任 1953-1961）アイゼンハウアーの愛称。"
        "第２次世界大戦時の連合軍最高司令官として、日独伊の枢軸国を破った。"
        "戦後は朝鮮戦争・インドシナ戦争を解決。ＮＡＴＯ軍最高司令官として"
        "西ヨーロッパの反共軍事体制を整えた。共和党。"
    ),
    "P3_Kyusei_50_300": (
        "(注) 提婆、提婆達多（だいばだった） 釈迦の従弟。大変有能な人物で"
        "あったが、逆恨みから釈迦とその教団に執拗な嫌がらせをした。"
    ),
}

# duplicação: item -> início exato do parágrafo a remover
PARAGRAFOS_DUPLICADOS = {
    "P4_Hikari_12_340": "As almas internas das pessoas despertam a partir do exterior.",
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
    ap.add_argument("--so-notas", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cache: dict[str, dict] = {}
    falhas: list[str] = []
    aplicadas = 0

    def carregar(item: str) -> dict:
        if item not in cache:
            cache[item] = json.loads((ITENS / f"{item}.json").read_text(encoding="utf-8"))
        return cache[item]

    if not args.so_notas:
        for item, campo, old, new, esperado in SUBS:
            if esperado == 0:
                continue
            d = carregar(item)
            atual = d.get(campo) or ""
            n = atual.count(old)
            if n != esperado:
                msg = f"{item}.{campo}: {n} ocorrência(s), esperado {esperado} — {old[:60]!r}"
                print("  [FALHA]", msg)
                falhas.append(msg)
                continue
            d[campo] = atual.replace(old, new)
            d.setdefault("reparos", []).append(
                {"tipo": "fix_auditoria_media", "data": stamp, "campo": campo}
            )
            aplicadas += 1
            print(f"  [ok] {item}.{campo}: {old[:50]!r}")

    for item, jp_nota in NOTAS_OMITIDAS.items():
        d = carregar(item)
        if "nota_auditoria" in json.dumps(d.get("reparos", []), ensure_ascii=False):
            print(f"  [skip] {item}: nota já acrescentada")
            continue
        try:
            nota = traduzir_nota(jp_nota)
        except Exception as exc:  # noqa: BLE001
            msg = f"{item}: falha a traduzir a nota ({exc})"
            print("  [FALHA]", msg)
            falhas.append(msg)
            continue
        d["texto_pt"] = (d.get("texto_pt") or "").rstrip() + "\n\n" + nota
        d.setdefault("reparos", []).append(
            {"tipo": "nota_auditoria", "data": stamp, "campo": "texto_pt"}
        )
        aplicadas += 1
        print(f"  [ok] {item}: nota final acrescentada ({len(nota)}c)")

    for item, inicio in PARAGRAFOS_DUPLICADOS.items():
        d = carregar(item)
        paras = re.split(r"\n\s*\n", d["texto_pt"])
        alvo = [i for i, p in enumerate(paras) if p.startswith(inicio)]
        if len(alvo) != 1:
            msg = f"{item}: parágrafo duplicado não localizado (candidatos={alvo})"
            print("  [FALHA]", msg)
            falhas.append(msg)
            continue
        removido = paras.pop(alvo[0])
        d["texto_pt"] = "\n\n".join(paras)
        d.setdefault("reparos", []).append(
            {"tipo": "dedup_auditoria", "data": stamp, "chars": len(removido)}
        )
        aplicadas += 1
        print(f"  [ok] {item}: parágrafo duplicado removido ({len(removido)}c)")

    print(f"\ncorreções aplicadas em memória: {aplicadas} | falhas: {len(falhas)}")

    if args.aplicar and not falhas:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        for item, d in cache.items():
            arq = ITENS / f"{item}.json"
            shutil.copy2(arq, BACKUPS / f"{item}_media_{stamp}.json")
            arq.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
        print(f"gravados {len(cache)} ficheiros (backup em {BACKUPS.name}/)")
    elif args.aplicar:
        print("NADA GRAVADO: há falhas a resolver primeiro.")
        return 1
    else:
        print("(dry-run; use --aplicar para gravar)")
    return 0 if not falhas else 1


if __name__ == "__main__":
    raise SystemExit(main())
