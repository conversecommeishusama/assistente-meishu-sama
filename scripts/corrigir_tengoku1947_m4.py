#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ronda M4: correções da 3.ª onda de revisão (auditoria R3, 104 artigos, 31 achados).

FALSOS POSITIVOS — entradas do glossário oficial que o auditor tomou por
invenção do tradutor (NÃO corrigir de novo; já justificados na M2 e agora
reconfirmados):

    道理   -> Caminho Perfeito          叡智  -> Sabedoria Sagrada
    下熱   -> redução da febre ou a febre baixa
    経綸   -> Plano Divino (sujeito Deus/主神)
    御利益 -> benefício material (graça)
    同化霊 -> espírito híbrido          正守護神 -> espírito protetor guardião
    霊衣   -> Aura                      中有界  -> Mundo Intermediário
    種痘   -> vacinação

  EXCEÇÃO REAL dentro desse grupo: **道理** em 007, 021 e 078 não é o termo
  doutrinário («Caminho Perfeito»), mas o sentido comum «razão/lógica/
  conclusão»; a substituição literal produzia frases sem sentido
  («chegar-se-ia ao seguinte Caminho Perfeito», «é o Caminho Perfeito que esse
  país…», «atribuindo o Caminho Perfeito, interpretam-no como bem»). Nesses três
  lugares passa a «razão/conclusão lógica». Recomenda-se anotar no glossário que
  «Caminho Perfeito» só vale no sentido doutrinário — a entrada é
  sensível ao contexto, como acontece com 凝り (Nódulo/nódulo) e 光明 (Kōmyō/luz).

  Também aceites como estão (decisão registada):
  * 007 「火を睹るよりも瞭か» = «mais claro que a luz do Sol» — equivalência
    idiomática portuguesa, o sentido de obviedade está preservado;
  * 055 「血膜炎» traduzido «pleurisia» — a transcrição da edição traz 血膜炎
    (forma anómala; 肋膜炎 é o termo corrente, e pleurisia é a complicação
    clássica do sarampo referida na mesma lista). Mantido por ser a leitura
    médica correcta do passo;
  * 004 種痘 = «vacinação» (glossário).

Uso:  .venv/bin/python scripts/corrigir_tengoku1947_m4.py [--aplicar]
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_tengoku1947" / "itens"

SUBS: list[tuple[int, str, str, str]] = [
    # ---------- 004: a abreviatura criada pelo autor é 然毒 = «toxina
    #          hereditária» (glossário). «toxina varíolica» não abrevia nada e
    #          ainda tinha a acentuação errada (variólico/a, não varíolico/a).
    (4, "texto_pt",
     'a toxina da varíola (doravante abreviada como "toxina varíolica")',
     'a toxina da varíola (doravante designada "toxina hereditária")'),
    (4, "texto_pt",
     "por causa desse processo de purificação, a toxina varíolica, buscando "
     "ser eliminada",
     "por causa desse processo de purificação, a toxina hereditária, buscando "
     "ser eliminada"),
    (4, "texto_pt",
     "esse processo natural de eliminação da toxina varíolica, ou seja, "
     "enfraquece",
     "esse processo natural de eliminação da toxina hereditária, ou seja, "
     "enfraquece"),
    (4, "texto_pt",
     "Dessa forma, a toxina varíolica que perdeu o poder de eliminação",
     "Dessa forma, a toxina hereditária que perdeu o poder de eliminação"),
    # 陰化然毒 (latente) vs 陰性然毒 (negativa): a distinção do original
    (4, "texto_pt",
     "o que acontece com essa toxina hereditária latente que permaneceu?",
     "o que acontece com essa toxina hereditária negativa que permaneceu?"),
    # ---------- 007 / 021 / 078: 道理 no sentido comum (razão/lógica)
    (7, "texto_pt", "chegar-se-ia ao seguinte Caminho Perfeito:",
     "chegar-se-ia à seguinte conclusão lógica:"),
    (21, "texto_pt",
     "é o Caminho Perfeito que esse país não pode deixar de se tornar uma "
     "nação amante da paz.",
     "é a razão pela qual esse país não pode deixar de se tornar uma nação "
     "amante da paz."),
    (78, "texto_pt",
     "A isso, atribuindo o Caminho Perfeito, interpretam-no como bem",
     "A isso, dando uma razão, interpretam como bem"),
    # ---------- 058: 右 = «o supramencionado», não «do lado direito»
    (58, "texto_pt",
     "Mas, então, o que vem a ser essa solidificação do lado direito?",
     "Mas, então, o que vem a ser essa solidificação mencionada acima?"),
    # ---------- 064: sintaxe fundida + redundância «Além disso, além»
    (64, "texto_pt",
     "quem possui toxinas medicamentosas tem sempre, em alguma parte do "
     "corpo, ocorre a purificação — e é por isso.",
     "quem possui toxinas medicamentosas tem sempre, em alguma parte do "
     "corpo, a ocorrência de purificação — e é por isso."),
    (64, "texto_pt",
     "Além disso, além do que foi dito, há o problema da pobreza.",
     "Além do que foi dito, há o problema da pobreza."),
    # ---------- 066: 霊衣 e アウル são a mesma coisa (glossário: 霊衣 = Aura);
    #          a frase japonesa limita-se a dar o nome ocidental
    (66, "texto_pt",
     'de Aura. Em língua ocidental, chama-se "Aura".',
     "de Aura. Em língua ocidental, é essa a sua designação."),
    # ---------- 073: 数尺 («alguns palmos») com equivalência métrica
    (73, "texto_pt", "viu, a alguns palmos acima de seus olhos,",
     "viu, a cerca de um metro (alguns shaku) acima de seus olhos,"),
    (73, "texto_pt", "Isso deve ter sido meu yutai daquela ocasião",
     "Isso deve ter sido meu corpo astral (yutai) daquela ocasião"),
    (73, "texto_pt", "um certo monge de elevada estirpe e um certo estudioso",
     "um certo monge eminente e um certo estudioso"),
    (73, "texto_pt", "batem com aquelas barras de ferro atadas, e, segundo",
     "batem com aquelas barras de ferro com cabo, e, segundo"),
    # ---------- 078: 八百万 = oito milhões (miríades); 正邪一如; romanização
    (78, "texto_pt", "ainda que se fale das oito miríades de divindades",
     "ainda que se fale das oito milhões de divindades"),
    (78, "texto_pt", '"Embora existam oito miríades de divindades, atentai',
     '"Embora existam oito milhões de divindades, atentai'),
    (78, "texto_pt", 'e "bem e mal são unidade"', 'e "correto e perverso são um só"'),
    (78, "texto_pt", "conforme o tempo, o local e a posição (Jishoi);",
     "conforme o tempo, o local e a posição;"),
    # ---------- 016: mesmo 道理 no sentido comum (a varredura do resíduo)
    (16, "texto_pt",
     "esse é o Caminho Perfeito: todo o corpo não pode deixar de rejuvenescer.",
     "essa é a razão pela qual todo o corpo não pode deixar de rejuvenescer."),
    # ---------- 061: 森羅万象 não traz número; «miríades» sugeria quantidade
    (61, "texto_pt", "todas as miríades de fenômenos entre o céu e a terra",
     "todos os incontáveis fenômenos entre o céu e a terra"),
    # ---------- 081: 迷蒙的 = confuso/obscuro; 正邪 = correto e maligno;
    #          大学 = universidade
    (81, "texto_pt", "não é de modo algum algo enganoso;",
     "não é de modo algum algo confuso;"),
    (81, "texto_pt", "há, sim, distinção entre o correto e o falso,",
     "há, sim, distinção entre o correto e o maligno,"),
    (81, "texto_pt", "há faculdades de ciência espiritual em diversas regiões",
     "há universidades de ciência espiritual em diversas regiões"),
    # ---------- 095: indumentária transliterada sem forma completa na 1.ª vez
    (95, "texto_pt", "vestida com um junihitoe,",
     "vestida com um junihitoe (veste cerimonial de doze camadas),"),
    (95, "texto_pt", "vestiu um uchikake e sentou-se ao lado.",
     "vestiu um uchikake (manto cerimonial) e sentou-se ao lado."),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    itens: dict[int, Path] = {}
    dados: dict[int, dict] = {}
    for p in sorted(glob.glob(str(ITENS / "*.json"))):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        itens[d["ordem"]] = Path(p)
        dados[d["ordem"]] = d

    ok = 0
    falhas: list[str] = []
    for ordem, campo, antigo, novo in SUBS:
        d = dados.get(ordem)
        if d is None:
            falhas.append(f"[{ordem}] item inexistente")
            continue
        texto = d.get(campo, "")
        if novo in texto and antigo not in texto:
            ok += 1
            continue
        n = texto.count(antigo)
        if n != 1:
            falhas.append(f"[{ordem}] {campo}: {n}× {antigo[:60]!r}")
            continue
        d[campo] = texto.replace(antigo, novo)
        ok += 1

    if args.aplicar:
        for ordem in {x[0] for x in SUBS}:
            itens[ordem].write_text(
                json.dumps(dados[ordem], ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8")

    print(f"substituições válidas: {ok}/{len(SUBS)}")
    for f in falhas:
        print("  PROBLEMA:", f)

    print("\n--- resíduos a confirmar ---")
    import re
    for termo in ("toxina varíolica", "Caminho Perfeito", "Jishoi",
                  "miríades", "enganoso"):
        achados = [(n, dados[n]["titulo_pt"])
                   for n in sorted(dados) if termo in dados[n]["texto_pt"]]
        print(f"  {termo:<18} {len(achados)} secção(ões): {achados}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
