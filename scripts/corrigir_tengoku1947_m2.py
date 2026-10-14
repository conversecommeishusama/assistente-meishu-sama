#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ronda de correções M2 do livro 『天国の福音』 (1947).

Correções derivadas da 2.ª onda de revisão (auditoria R2, 88 artigos, 29
achados). Seis desses achados (unidades de 015, 071, 075, 076, 100) já tinham
sido resolvidos pela ronda M1.

FALSOS POSITIVOS DOCUMENTADOS (NÃO corrigir de novo):
  * `然毒 = "toxina hereditária"` (004, 006) — é a entrada do glossário oficial
    (`然毒 -> toxina hereditária`), confirmada por 62 usos no acervo publicado.
    O auditor supôs que 然 devia significar «varíola», mas a abreviatura é
    definida pelo próprio autor («天然痘毒素（以下略して然毒と称す）»).
  * `運命 = "destino mutável"` (092) — igualmente do glossário
    (`運命 -> destino mutável (destino) — distinto de 宿命`), com 170 usos no
    acervo. Não é acréscimo do tradutor.
  * `凝り = "Nódulo"` (005, 021, 042) — entrada do glossário
    (`凝り -> Nódulo`; cf. `固結 -> solidificação (endurecimento/nódulo)`).
    O texto japonês apresenta-o como o nome vulgar do toxina solidificada
    («俗に凝りと名づくるのもそれである», «即ち肩の凝りである»). O único reparo
    real era o **maiúscula no meio da frase** («Nódulo nos ombros»), corrigido
    abaixo. Exceção: em 036, 肩の凝り aparece numa lista de achaques
    («頭痛、肩の凝り等に悩み»), onde a forma consagrada do acervo é
    «rigidez nos ombros» (49 usos) — aí passa a essa forma.
  * 天国 = "Reino dos Céus" (104) — é citação bíblica («O Reino dos Céus está
    próximo; arrependei-vos»), não o termo de Meishu-Sama; mantém-se. Já em 001
    e 064 trata-se do próprio título da obra, e passa a «Paraíso» conforme o
    glossário (`天国 -> Paraíso`; cf. `地上天国 -> Paraíso Terrestre`).

Uso:  .venv/bin/python scripts/corrigir_tengoku1947_m2.py [--aplicar]
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_tengoku1947" / "itens"

SUBS: list[tuple[int, str, str, str]] = [
    # ---------- 001 / 064: 天国 = Paraíso (título da própria obra)
    (1, "titulo_pt", "Prefácio do Evangelho do Reino dos Céus",
     "Prefácio do Evangelho do Paraíso"),
    (1, "texto_pt", "Prefácio do Evangelho do Reino dos Céus",
     "Prefácio do Evangelho do Paraíso"),
    (64, "texto_pt", 'dei a este livro o título de "Evangelho do Reino dos Céus"',
     'dei a este livro o título de "Evangelho do Paraíso"'),
    # ---------- 光明 como substantivo comum (o glossário só lista o amuleto)
    (1, "texto_pt", "resplandece de júbilo e Kōmyō",
     "resplandece de júbilo e luz"),
    (61, "texto_pt", "o Mundo do Dia é a era Kōmyō",
     "o Mundo do Dia é a era da Luz"),
    (64, "texto_pt", "onde brilha a Kōmyō não é de modo algum um sonho",
     "onde brilha a Luz não é de modo algum um sonho"),
    (92, "texto_pt", "Vislumbram Kōmyō no futuro e a ansiedade se dissolve",
     "Vislumbram luz no futuro e a ansiedade se dissolve"),
    # ---------- 004: coerência com a entrada `陰性然毒` do glossário
    (4, "texto_pt", "essa toxina varíolica latente que permanece",
     "essa toxina hereditária latente que permanece"),
    # ---------- 006: 天正 lê-se Tenshō (Tencho é 天長, outra era)
    (6, "texto_pt", "em Tencho 5 (982 d.C.)", "no ano 5 de Tenshō (982 d.C.)"),
    # ---------- 011: 鈍痛 é qualidade da dor, oposta a 鋭痛 (dor aguda)
    (11, "texto_pt", "é quase sempre dores persistentes",
     "é quase sempre dor surda (contusa)"),
    # ---------- 014: 誘発 = indução/desencadeamento (não «transmissão»);
    #            逆理的浄化停止 = interrupção antinatural da purificação
    (14, "texto_pt",
     "Eu advogo que o contágio deveria ser chamado de transmissão",
     "Eu advogo que o contágio seja chamado de indução (desencadeamento)"),
    (14, "texto_pt",
     "executa uma poderosa interrupção do Princípio Inverso da purificação",
     "executa uma poderosa e antinatural interrupção da purificação"),
    # ---------- 015: acréscimo temporal (彼の = «aqueles», não «de outrora»)
    (15, "texto_pt", "Os camponeses de outrora, porque comem alimentação simples",
     "Aqueles camponeses, porque comem alimentação simples"),
    # ---------- capitais injustificadas no meio da frase
    (21, "texto_pt", "Isto é, Nódulo nos ombros.", "Isto é, o nódulo nos ombros."),
    (21, "texto_pt", "Nódulo extremamente acentuado nos ombros",
     "nódulo extremamente acentuado nos ombros"),
    (42, "texto_pt",
     "Sua causa é o Nódulo extremo na nuca e nos ombros. Isto é, quando o "
     "Nódulo,", "Sua causa é o nódulo extremo na nuca e nos ombros. Isto é, "
     "quando o nódulo,"),
    (42, "texto_pt", "melancolia, Nódulos no pescoço e nos ombros",
     "melancolia, nódulos no pescoço e nos ombros"),
    # ---------- 036: lista de achaques — forma consagrada do acervo
    (36, "texto_pt", "nódulo nos ombros, etc.", "rigidez nos ombros, etc."),
    # ---------- 037: 一貫目 = 3,75 kg por mês
    (37, "texto_pt",
     "perde cerca de um kanme (unidade japonesa de peso) de peso por mês",
     "perde cerca de 3,75 kg (um kanme) de peso por mês"),
    # ---------- 069: 大光明世界 = «Mundo da Grandiosa Luz» (glossário)
    (69, "texto_pt", "isto é, o Mundo de Daikōmyō",
     "isto é, o Mundo da Grandiosa Luz (Daikōmyō)"),
    # ---------- 075: 寅吉 = Torakichi
    (75, "texto_pt",
     'O voo aéreo de Torigichi, descrito no famoso "Torigichi Monogatari"',
     'O voo aéreo de Torakichi, descrito no famoso "Torakichi Monogatari"'),
    # 075: 〇〇〇〇 / 〇〇〇〇〇 são supressões editoriais do original
    (75, "texto_pt", "Casos como os de Fulano e Beltrano",
     "Casos como os de 〇〇〇〇 e 〇〇〇〇〇"),
    # ---------- 094: 娑婆はモウ凝りごりです (jogo 凝り/懲り懲り = «já estou farto»)
    (94, "texto_pt", "O mundo profano já é, para mim, um Nódulo.",
     "O mundo profano já me é insuportável."),
    # ---------- 098: 酒屋 = loja de bebidas (forma do acervo); 書生 = estudante
    (98, "texto_pt", "perambulava bebendo pelas tabernas da vizinhança",
     "perambulava bebendo pelas lojas de bebidas da vizinhança"),
    (98, "texto_pt", "o espírito do velho dono da taberna da vizinhança",
     "o espírito do velho dono da loja de bebidas da vizinhança"),
    (98, "texto_pt", "um estudante [serviçal] da minha casa",
     "um estudante que servia em minha casa"),
    # ---------- 099: discurso directo do espírito (original em 1.ª pessoa)
    (99, "texto_pt",
     "que não se esforçou além dos seus limites com a intenção de receber "
     "agradecimento; que fazer uma coisa dessas era uma grande falta de "
     "delicadeza; que havia limites para menosprezar uma pessoa.",
     "«Não me esforcei com a intenção de receber agradecimento; fazer uma "
     "coisa dessas é uma grande falta de delicadeza; há limites para "
     "menosprezar uma pessoa.»"),
    # ---------- 100: 酸漿提灯 (lanterna em forma de cálice de physalis)
    (100, "texto_pt", "do tamanho de uma lanterna de hōzuki",
     "do tamanho de uma lanterna de hōzuki (lanterna de papel em forma de "
     "cálice de physalis)"),
    # ---------- 104: 科学にして科学に非ず、宗教にして宗教に非ず
    (104, "texto_pt",
     "não são ciência e não são ciência; são religião e não são religião",
     "nem são ciência nem deixam de ser ciência; nem são religião nem deixam "
     "de ser religião"),
]

# substituições globais dentro de um item: (ordem, campo, antigo, novo)
GLOBAIS: list[tuple[int, str, str, str]] = [
    # 098 fala de «sake»; as secções 075 e 076 usam «saquê» (87 usos no acervo)
    (98, "texto_pt", "sake", "saquê"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    itens: dict[int, tuple[Path, dict]] = {}
    for p in sorted(glob.glob(str(ITENS / "*.json"))):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        itens[d["ordem"]] = (Path(p), d)

    ok = 0
    falhas: list[str] = []
    for ordem, campo, antigo, novo in SUBS:
        if ordem not in itens:
            falhas.append(f"[{ordem}] item inexistente")
            continue
        d = itens[ordem][1]
        texto = d.get(campo, "")
        if novo in texto and antigo not in texto:
            ok += 1
            continue                        # já aplicado
        n = texto.count(antigo)
        if n != 1:
            falhas.append(f"[{ordem}] {campo}: {n} ocorrência(s) de "
                          f"{antigo[:70]!r}")
            continue
        d[campo] = texto.replace(antigo, novo)
        ok += 1

    for ordem, campo, antigo, novo in GLOBAIS:
        d = itens[ordem][1]
        rx = re.compile(rf"(?<!saq){re.escape(antigo)}")
        d[campo], n = rx.subn(novo, d[campo])
        print(f"  [global] {ordem} {campo}: {antigo} -> {novo} ({n}×)")
        ok += 1

    if args.aplicar:
        for ordem, (caminho, d) in itens.items():
            if str(ordem) not in {str(x[0]) for x in SUBS + GLOBAIS}:
                continue
            caminho.write_text(json.dumps(d, ensure_ascii=False, indent=1)
                               + "\n", encoding="utf-8")

    print(f"\nsubstituições válidas: {ok}/{len(SUBS) + len(GLOBAIS)}")
    if falhas:
        print("PROBLEMAS:")
        for f in falhas:
            print("  ", f)

    print("\n--- validação ---")
    for ordem in sorted({x[0] for x in SUBS + GLOBAIS}):
        pt = itens[ordem][1]["texto_pt"]
        tit = itens[ordem][1]["titulo_pt"]
        q = pt.count('"')
        marcas = []
        if "Kōmyō" in pt and "Komyo-Nyorai" not in pt:
            marcas.append("Kōmyō isolado")
        if "Reino dos Céus" in pt:
            marcas.append("Reino dos Céus")
        if re.search(r"(?<![.!?:]\s)\bNódulo", pt):
            marcas.append("Nódulo maiúsculo")
        print(f"  [{ordem:>3}] aspas {q} {'OK' if q % 2 == 0 else '>>> ÍMPAR'}"
              f" | {len(pt):>6}c | {tit[:38]}"
              + (f"  <<< {', '.join(marcas)}" if marcas else ""))
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
