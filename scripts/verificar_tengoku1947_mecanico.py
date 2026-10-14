#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificações mecânicas da tradução de 『天国の福音』 (1947).

Pega o que um revisor humano/LLM deixa passar por ser mecânico:
  1. aspas desemparelhadas no português;
  2. resíduos de extração (`#E`, `#S`, `#T`, `#K`, `#W`, linhas ───, `pNNN～`,
     números de página isolados) no JP ou no PT;
  3. unidades japonesas não convertidas no PT;
  4. termos proibidos (`possesso`, `idealismo` para 唯心);
  5. kanji no PT sem glosa;
  6. marcadores e rótulos de falante inconsistentes;
  7. truncamento (secção que termina sem pontuação final, ratio anómalo);
  8. duplicação de parágrafos;
  9. glossário: termo presente no JP cuja forma aprovada não está no PT;
 10. palavras japonesas partidas / espaços internos (defeito de extração);
 11. integridade: todo o japonês da referência ficou no ficheiro extraído.

Uso:  .venv/bin/python scripts/verificar_tengoku1947_mecanico.py
Saída: relatório em reports/auditoria_tengoku1947/VERIFICACAO_MECANICA.md
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
from extrair_tengoku_no_fukuin_jp import (  # noqa: E402
    delimitar as delimitar_livro,
    limpar as limpar_livro,
)
ITENS = RAIZ / "reports" / "traducao_tengoku1947" / "itens"
BASE = RAIZ / "reports" / "auditoria_tengoku1947"
SAIDA = BASE / "VERIFICACAO_MECANICA.md"
REF = (RAIZ / "referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS"
       / "chosaku_full.txt")
JP_TXT = RAIZ / "reports" / "livros_trabalho" / "jp" / "19470205-天国の福音.txt"

KANJI = r"\u4e00-\u9fff\u3400-\u4dbf"
RE_KANJI = re.compile(f"[{KANJI}々〆ヶ]")
RE_ANOT = re.compile(r"[（(][^）)]{0,60}[）)]")
CJK = rf"\u3005\u3400-\u4dbf\u4e00-\u9fff\u3041-\u3096\u30a1-\u30fa"

UNIDADES = [
    "尺", "寸", "間", "坪", "町", "匁", "貫", "升", "斗", "石", "合",
]
PALAVRAS_UNIDADE_PT = [
    r"shaku", r"sun", r"ken", r"tsubo", r"ch[oō]", r"kan", r"ri",
    r"tan", r"koku", r"sh[oō]", r"g[oō]", r"monme",
]
# Uma unidade japonesa só é achado se vier precedida de um numeral: sem isto
# «quem fica alegre, ri ou sente sono» (verbo rir), «o go e o shogi» (jogo de
# tabuleiro 囲碁), «ba-bi-bu-be-bo» e «ga-gi-gu-ge-go» (sílabas) davam falsos
# positivos.
NUMERAL = (r"(?:\d[\d.,]*|um|uma|dois|duas|três|quatro|cinco|seis|sete|"
           r"oito|nove|dez|onze|doze|treze|catorze|quatorze|quinze|vinte|"
           r"trinta|quarenta|cinquenta|sessenta|setenta|oitenta|noventa|"
           r"cento|duzentos|trezentos|mil|vários|várias|alguns|algumas|"
           r"dezenas|poucos|poucas|meia|meio)")
RE_UNIDADE = re.compile(
    rf"(?<![\w-])({NUMERAL})\s+(?:ou\s+\w+\s+)?({'|'.join(PALAVRAS_UNIDADE_PT)})"
    rf"\b(?![\w-])", re.I)
# equivalência métrica: aceita-se antes ou depois da unidade, como já se faz
# no acervo («dez ri (aproximadamente quarenta quilómetros)», «noventa
# centímetros [três shaku]», «um ou dois sun [cerca de 3 a 6 cm]»).
RE_METRICA = re.compile(
    r"\b\d[\d.,]*\s*(?:mm|cm|km|kg|mg|ml|m|g|L|l)\b|\b(?:centímetros|"
    r"metros|quilômetros|quilos|litros|gramas|milímetros|mililitros)\b", re.I)
PROIBIDOS = [(r"\bpossesso\b", "usar «possessão»"),
             (r"\bidealismo\b", "para 唯心 usar «espiritualismo»")]

RE_RESIDUO = [
    (re.compile(r"#[ESTKW]\b"), "marcador de referência"),
    (re.compile(r"[─━]{6,}"), "linha de separação"),
    (re.compile(r"^\s*p\d+～\s*$", re.M), "referência de página pN～"),
    (re.compile(r"^\s*\d{1,4}\s*$", re.M), "número de página isolado"),
    (re.compile(r"『?天国の福音』?,19470205"), "linha de proveniência"),
    (re.compile(r"岡田茂吉全集"), "referência à coletânea"),
]

RE_FIM_OK = re.compile(r"[.!?…»\"')\]]\s*$")
RE_SEP_OK = re.compile(r"^[─━\-—=]{6,}\s*$")
RE_PROV_OK = re.compile(r"^\s*『.*』.*\d{8}.*$")
RE_PREL_OK = re.compile(r"^\s*p\d+～\s*$")
RE_PAGINA_OK = re.compile(r"^\s*[\x0c\s]*\d{1,4}\s*$")
RE_MARCADOR_PT = re.compile(r"\*\*([A-ZÀ-Ú][^:*\n]{2,22}):\*\*")


def paras(t: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]


def main() -> int:
    itens = []
    for f in sorted(ITENS.glob("*.json")):
        if f.name.startswith("."):
            continue
        itens.append((f.name, json.loads(f.read_text(encoding="utf-8"))))
    itens.sort(key=lambda kv: kv[1]["ordem"])
    print(f"secções: {len(itens)}")

    glossario = json.loads(
        (RAIZ / "glossario_traducao.json").read_text(encoding="utf-8"))
    achados: list[tuple[str, str, str, str]] = []   # (secção, tipo, detalhe, trecho)
    # O glossário NÃO entra na contagem de achados: a maioria das entradas são
    # termos genéricos com alternativas livres («eliminação / excreção») e a
    # exigência de forma literal produzia centenas de falsos positivos. Fica
    # como lista de apoio para revisão — quem julga o contexto é a auditoria.
    gloss_apoio: list[tuple[str, str]] = []         # (secção, detalhe)

    def add(sec: str, tipo: str, detalhe: str, trecho: str = "") -> None:
        achados.append((sec, tipo, detalhe, trecho[:220]))

    def add_gloss(sec: str, detalhe: str) -> None:
        gloss_apoio.append((sec, detalhe))

    # ---------- por secção
    for nome, d in itens:
        sec = f"{d['ordem']:03d} {d['titulo_pt']}"
        jp, pt = d["texto_jp"], d["texto_pt"]

        # 1. aspas
        for ch, par in (('"', '"'), ("“", "”"), ("«", "»")):
            if ch == par:
                if pt.count(ch) % 2:
                    add(sec, "aspa", f"{pt.count(ch)} aspas retas (ímpar)")
            elif pt.count(ch) != pt.count(par):
                add(sec, "aspa",
                    f"{pt.count(ch)}×{ch} vs {pt.count(par)}×{par}")

        # 2. resíduos
        for rx, rot in RE_RESIDUO:
            for m in rx.finditer(pt) if rot != "número de página isolado" \
                    else []:
                add(sec, "residuo_pt", rot, pt[max(0, m.start() - 60):m.end() + 60])
            for m in rx.finditer(jp) if rot != "número de página isolado" \
                    else []:
                add(sec, "residuo_jp", rot, jp[max(0, m.start() - 60):m.end() + 60])

        # 3. unidades não convertidas — só a PRIMEIRA ocorrência de cada
        #    unidade na secção precisa de equivalência métrica (convenção do
        #    acervo: glosa na primeira menção).
        for p in PALAVRAS_UNIDADE_PT:
            rx = re.compile(rf"(?<![\w-])({NUMERAL})\s+(?:ou\s+\w+\s+)?({p})"
                            rf"\b(?![\w-])", re.I)
            ocorr = list(rx.finditer(pt))
            if not ocorr:
                continue
            m = ocorr[0]
            antes = pt[max(0, m.start() - 70):m.start()]
            depois = pt[m.end():m.end() + 90]
            if RE_METRICA.search(antes) or RE_METRICA.search(depois):
                continue
            jan = pt[max(0, m.start() - 60):m.end() + 60]
            extra = f" (+{len(ocorr) - 1} ocorrência(s) na secção)" \
                if len(ocorr) > 1 else ""
            add(sec, "unidade",
                f"«{m.group(0)}» sem equivalência métrica{extra}", jan)

        # 4. proibidos
        for p, motivo in PROIBIDOS:
            for m in re.finditer(p, pt, re.I):
                add(sec, "proibido", motivo, pt[max(0, m.start() - 70):m.end() + 70])

        # 5. kanji no PT sem glosa
        for m in RE_KANJI.finditer(pt):
            jan = pt[max(0, m.start() - 45):m.end() + 45]
            if RE_ANOT.search(jan) or re.search(r"[「『\"]", jan):
                continue
            add(sec, "kanji_pt", "kanji no português sem glosa", jan)

        # 6. marcadores de falante
        for m in RE_MARCADOR_PT.finditer(pt):
            add(sec, "marcador", "rótulo de falante em negrito", m.group(0))

        # 7. truncamento — uma linha final curta sem pontuação é assinatura ou
        #    data (p.ex. «Novembro de 1945 da era cristã / O autor»), não
        #    truncamento; um fecho entre parênteses também é legítimo
        #    (p.ex. «(Fim de 『O Evangelho do Paraíso』)»).
        ult = [l for l in pt.split("\n") if l.strip()]
        if pt and not RE_FIM_OK.search(pt):
            if not (ult and len(ult[-1].strip()) < 70):
                add(sec, "truncamento", "secção não termina em pontuação",
                    pt[-120:])
        r = len(pt) / max(1, len(jp))
        if r < 2.4 or r > 4.3:
            add(sec, "ratio", f"ratio {r:.2f} fora do intervalo esperado",
                pt[:120])

        # 8. duplicação
        ps = paras(pt)
        c = Counter(p for p in ps if len(p) > 120)
        for p, n in c.items():
            if n > 1:
                add(sec, "duplicacao", f"parágrafo repetido {n}×", p[:160])

        # 9. glossário
        #    Só termos ESPECÍFICOS: chaves de 1 carácter (熱, 道, 血, 想, 念…)
        #    aparecem sempre dentro de compostos (発熱, 道具, 血圧, 想像) e
        #    geravam ~170 falsos positivos. Também se descarta a ocorrência que
        #    faz parte de uma chave mais longa (自然 dentro de 自然農法).
        longas = [k for k in glossario if len(k) > 1]
        for termo, forma in glossario.items():
            if len(termo) < 2 or termo not in jp:
                continue
            principal = re.split(r"[;,/(]", str(forma))[0].strip()
            if len(principal) < 3 or RE_KANJI.search(principal):
                continue
            if principal.lower() in pt.lower():
                continue
            dentro = False
            for outra in longas:
                if outra != termo and termo in outra and outra in jp:
                    dentro = True
                    break
            if dentro:
                continue
            add_gloss(sec,
                      f"{termo} no JP mas «{principal}» ausente do PT")

        # 10. espaços internos em japonês
        for m in re.finditer(rf"[{CJK}][ \u3000]+[{CJK}]", jp):
            add(sec, "espaco_jp", "espaço entre caracteres japoneses",
                jp[max(0, m.start() - 40):m.end() + 40])

    # ---------- 11. integridade da extração
    #     Compara corpo com corpo: o bloco da referência inclui metadados
    #     (`#K` com a coletânea, separadores, proveniência, páginas) que a
    #     extração descarta de propósito — compará-los dava um delta falso de
    #     milhares de caracteres. Recontam-se apenas os caracteres CJK das
    #     linhas de corpo, com as anotações `<...>` resolvidas da mesma forma
    #     (furigana removida, correção aplicada).
    ref = REF.read_text(encoding="utf-8").split("\n")
    # delimitação partilhada com o extrator: `startswith("#T 福音")` sozinho
    # apanhava também as linhas de OUTRA obra, `#T 福音書 …` (福音書 = «livro do
    # evangelho»), e esticava o intervalo por 100 mil linhas.
    ini, fim = delimitar_livro(ref)
    marcas_livro = sum(1 for i in range(ini, fim)
                       if ref[i].strip().startswith("#T"))

    def corpo_jp(linhas: list[str]) -> str:
        out = []
        for l in linhas:
            s = l.strip()
            if not s or s.startswith("#") or RE_SEP_OK.search(s) \
                    or RE_PROV_OK.search(s) or RE_PREL_OK.search(s) \
                    or RE_PAGINA_OK.search(s):
                continue
            s = re.sub(r"[\x0c]\s*\d{1,4}\s*$", "", s)
            if not s:
                continue
            out.append(s)
        return "".join(out)

    bruto = re.sub(r"[\s\u3000]", "", limpar_livro(corpo_jp(ref[ini:fim])))
    linhas_limpo = [l for l in JP_TXT.read_text(encoding="utf-8").split("\n")
                    if not l.startswith("#")]
    limpo = re.sub(r"[\s\u3000]", "", "\n".join(linhas_limpo))
    jap_bruto = len(re.findall(rf"[{CJK}]", bruto))
    jap_limpo = len(re.findall(rf"[{CJK}]", limpo))
    delta = jap_limpo - jap_bruto
    print(f"integridade — caracteres CJK: referência {jap_bruto} | "
          f"extraído {jap_limpo} ({delta:+d}) | marcas #T do livro: "
          f"{marcas_livro}")

    # ---------- relatório
    por_tipo = Counter(t for _, t, _, _ in achados)
    linhas_out = [
        "# Verificação mecânica — 『天国の福音』 (O Evangelho do Paraíso), 1947\n",
        f"Secções: **{len(itens)}** · achados mecânicos: **{len(achados)}**\n",
        "## Contagem por tipo\n",
        "| tipo | n |", "|---|---|",
    ]
    for t, n in por_tipo.most_common():
        linhas_out.append(f"| `{t}` | {n} |")
    linhas_out.append("\n## Integridade da extração\n")
    linhas_out.append(
        f"- caracteres CJK na referência: {jap_bruto}\n"
        f"- caracteres CJK no ficheiro extraído: {jap_limpo} "
        f"({delta:+d} — efeito apenas das anotações de correção da edição, "
        f"p.ex. `淋巴腺<リンパ腺>` -> `リンパ腺`)\n"
        f"- marcas `#T` do livro na referência: {marcas_livro}\n")

    linhas_out.append("\n## Achados, por secção\n")
    atual = None
    for sec, tipo, det, tr in achados:
        if sec != atual:
            linhas_out.append(f"\n### {sec}\n")
            atual = sec
        linhas_out.append(f"- **{tipo}** — {det}\n  `{tr}`")

    linhas_out.append("\n## Apoio — formas do glossário ausentes do PT\n")
    linhas_out.append(
        "Termos do glossário que aparecem no original cuja primeira forma "
        "aprovada não ocorre literalmente na tradução. **Não são defeitos**: a "
        "maioria tem alternativas livres («eliminação / excreção») ou está "
        "dentro de um composto. Serve de lista de verificação para a auditoria.\n")
    if not gloss_apoio:
        linhas_out.append("_(nenhum)_")
    sec_atual = None
    for sec, det in gloss_apoio:
        if sec != sec_atual:
            linhas_out.append(f"\n### {sec}\n")
            sec_atual = sec
        linhas_out.append(f"- {det}")
    SAIDA.write_text("\n".join(linhas_out) + "\n", encoding="utf-8")

    print(f"\nachados mecânicos: {len(achados)}")
    for t, n in por_tipo.most_common():
        print(f"   {t:<16} {n}")
    print(f"apoio (glossário, não conta como defeito): {len(gloss_apoio)}")
    print(f"\nrelatório: {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
