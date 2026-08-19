#!/usr/bin/env python3
"""Checador DETERMINÍSTICO de cobertura estrutural (não-LLM).

Garante que NADA do JP ficou sem tradução, independente do formato (frase,
tabela, diagrama, sequência de kana/kanji).

Por que existe: executor e auditor (ambos LLM) trabalham por "sentido", não por
"cobertura" — deixaram passar conteúdo não traduzido (ex.: a tabela gojūon do
Curso Kannon, T1 do teste de retradução dos escritos).

Método:
1. Detecta BLOCOS NÃO-PROSAICOS no JP: linhas com kana/kanji sem pontuação de
   frase (`。！？.!?…`) — tabelas, diagramas, sequências de caracteres espaçados.
2. Converte kana → romaji (mapeamento fonético).
3. Verifica se cada bloco tem correspondência no PT (por âncora fonética).
4. Bloco do JP sem correspondência no PT = conteúdo ficou para trás → reporta.

Refinamento anti-falso-positivo: para blocos com 2+ linhas (tabelas), verifica a
TABELA COMPLETA (as N linhas) — não apenas 3 fonemas que podem aparecer citados
no texto corrido.

Uso (módulo):
    from checador_cobertura import checar_cobertura
    achados = checar_cobertura(jp, pt)
    # achados = [{"bloco": "ア イ ウ エ オ ...", "romaji": "a i u e o ...", "motivo": "sem correspondência no PT"}, ...]
"""
from __future__ import annotations

import re

# Mapeamento katakana → romaji. Dígrafos (combinações 2-3 kana) primeiro,
# para capturar ダイ=dai, ガワ=gawa, シン=shin etc.
_DIGRAFOS = {
    "キャ": "kya", "キュ": "kyu", "キョ": "kyo",
    "シャ": "sha", "シュ": "shu", "ショ": "sho",
    "チャ": "cha", "チュ": "chu", "チョ": "cho",
    "ニャ": "nya", "ニュ": "nyu", "ニョ": "nyo",
    "ヒャ": "hya", "ヒュ": "hyu", "ヒョ": "hyo",
    "ミャ": "mya", "ミュ": "myu", "ミョ": "myo",
    "リャ": "rya", "リュ": "ryu", "リョ": "ryo",
    "ギャ": "gya", "ギュ": "gyu", "ギョ": "gyo",
    "ジャ": "ja", "ジュ": "ju", "ジョ": "jo",
    "ビャ": "bya", "ビュ": "byu", "ビョ": "byo",
    "ピャ": "pya", "ピュ": "pyu", "ピョ": "pyo",
}

KANA_ROMAJI = {
    "ア": "a", "イ": "i", "ウ": "u", "エ": "e", "オ": "o",
    "カ": "ka", "キ": "ki", "ク": "ku", "ケ": "ke", "コ": "ko",
    "サ": "sa", "シ": "shi", "ス": "su", "セ": "se", "ソ": "so",
    "タ": "ta", "チ": "chi", "ツ": "tsu", "テ": "te", "ト": "to",
    "ナ": "na", "ニ": "ni", "ヌ": "nu", "ネ": "ne", "ノ": "no",
    "ハ": "ha", "ヒ": "hi", "フ": "fu", "ヘ": "he", "ホ": "ho",
    "マ": "ma", "ミ": "mi", "ム": "mu", "メ": "me", "モ": "mo",
    "ヤ": "ya", "ユ": "yu", "ヨ": "yo",
    "ラ": "ra", "リ": "ri", "ル": "ru", "レ": "re", "ロ": "ro",
    "ワ": "wa", "ヰ": "wi", "ヱ": "we", "ヲ": "wo", "ン": "n",
    "ガ": "ga", "ギ": "gi", "グ": "gu", "ゲ": "ge", "ゴ": "go",
    "ザ": "za", "ジ": "ji", "ズ": "zu", "ゼ": "ze", "ゾ": "zo",
    "ダ": "da", "ヂ": "ji", "ヅ": "zu", "デ": "de", "ド": "do",
    "バ": "ba", "ビ": "bi", "ブ": "bu", "ベ": "be", "ボ": "bo",
    "パ": "pa", "ピ": "pi", "プ": "pu", "ペ": "pe", "ポ": "po",
    "ャ": "ya", "ュ": "yu", "ョ": "yo", "ッ": "", "ー": "",
}


def _kana_para_romaji(texto: str) -> str:
    """Converte uma string de kana para romaji, resolvendo dígrafos primeiro."""
    out = []
    i = 0
    while i < len(texto):
        c = texto[i]
        # tentar dígrafo de 2-3 kana
        if c in "キャシャチャニャヒャミャリャギャジャビャピャキュシュチュニュヒュミュリュギュジュビュピュキョショチョニョヒョミョリョギョジョビョピョ":
            for n in (3, 2):
                if texto[i:i+n] in _DIGRAFOS:
                    out.append(_DIGRAFOS[texto[i:i+n]])
                    i += n
                    break
            else:
                out.append(KANA_ROMAJI.get(c, c))
                i += 1
        else:
            out.append(KANA_ROMAJI.get(c, c))
            i += 1
    return "".join(out)


def _linha_para_romaji(linha: str) -> str:
    """Converte uma linha de kana espaçados para romaji (kanji ficam como estão)."""
    return " ".join(_kana_para_romaji(c) if c in KANA_ROMAJI or c in _DIGRAFOS else c
                     for c in linha if c.strip())


RE_PONTUACAO_FRASE = re.compile(r"[。！？!?…]")
# KANA (hiragana+katakana) e KANJI separados — para distinguir linhas só-kana
# (que geram âncora fonética de linha inteira) de linhas com kanji.
RE_KANA = re.compile(r"[\u3040-\u30ff]")
RE_KANJI = re.compile(r"[\u4e00-\u9fff]")
RE_JAP = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
# Partículas/função gramatical em hiragana — indicam PROSA explicativa, não diagrama.
RE_PARTICULAS = re.compile(r"[はがをとへにのなりですあるいますとなる]")
RE_ASPAS = re.compile(r"[「」『』\"']")


def _eh_bloco_nao_prosaico(linha: str) -> bool:
    """Linha que é só kana/kanji espaçados, sem pontuação de frase nem partículas.

    Diagramas/tabelas = linhas de kana/kanji puros (silabário, decomposição
    visual). Prosa explicativa = linhas com partículas gramaticais ou aspas.
    """
    s = linha.strip()
    if not s:
        return False
    if RE_PONTUACAO_FRASE.search(s):
        return False
    if RE_PARTICULAS.search(s):
        return False  # tem partícula → é prosa, não diagrama
    if RE_ASPAS.search(s):
        return False  # tem aspas → é citação/prosa, não diagrama
    jap = len(RE_JAP.findall(s))
    if jap == 0:
        return False
    # maioria dos caracteres é japonês (kana/kanji)
    total = len(re.sub(r"[\s\u3000]", "", s))
    return jap / max(total, 1) > 0.5


def _extrair_blocos_jp(jp: str) -> list[list[str]]:
    """Agrupa linhas não-prosaicas consecutivas em blocos (ex.: tabela = 5 linhas)."""
    linhas = jp.splitlines()
    blocos = []
    atual = []
    for l in linhas:
        if _eh_bloco_nao_prosaico(l):
            atual.append(l.strip())
        else:
            if atual:
                blocos.append(atual)
                atual = []
    if atual:
        blocos.append(atual)
    return blocos


def _romaji_da_tabela(bloco: list[str]) -> str:
    """Converte todas as linhas do bloco para romaji, juntas."""
    return " ".join(_linha_para_romaji(l) for l in bloco)


def checar_cobertura(jp: str, pt: str, min_linhas: int = 1) -> list[dict]:
    """Verifica se todos os blocos não-prosaicos do JP têm correspondência no PT.

    Retorna lista de achados (blocos do JP sem correspondência no PT).
    Cada achado: {"bloco": [...], "romaji": "...", "motivo": "..."}
    """
    blocos = _extrair_blocos_jp(jp)
    pt_norm = re.sub(r"\s+", " ", pt).lower()
    # versão contígua (sem espaços) para comparar âncoras de linha inteira
    pt_cont = re.sub(r"[\s\u3000]", "", pt).lower()

    achados = []
    for bloco in blocos:
        if len(bloco) < min_linhas:
            continue

        # Para CADA linha do bloco, extrair a âncora. Para linhas de KANA (só
        # kana espaçado, sem kanji), a âncora é a linha INTEIRA convertida para
        # romaji contíguo (ex.: "aiueohahifuheho"), comparada contra o PT
        # contíguo — específica o bastante para não colidir com citação no texto.
        # Para linhas com KANJI, usa os fonemas sem espaços (ex.: "okada").
        anchors_por_linha = []
        for linha in bloco:
            romaji = _linha_para_romaji(linha).strip()
            fonemas = [x for x in romaji.split() if x and not RE_JAP.search(x)]
            tem_kanji = bool(RE_KANJI.search(linha))
            if tem_kanji:
                anchors_por_linha.append("".join(fonemas[:5]).lower())
            else:
                anchors_por_linha.append("".join(fonemas).lower())

        # Tabela (2+ linhas): verificar quantas linhas têm âncora no PT.
        linhas_kana = [a for a in anchors_por_linha if len(a) >= 3]
        presentes = [a for a in linhas_kana if (a in pt_norm or a in pt_cont)]
        # Verificar também se o bloco aparece VERBATIM (kanji/kana cru) no PT —
        # nesse caso NÃO é omissão (o conteúdo está lá), apenas pode faltar
        # romanização (julgado por executor/auditor). Verbatim TEM PRIORIDADE:
        # presente em japonês cru = observação, não bloqueio.
        verbatim = any(l in pt for l in bloco if len(l.strip()) >= 2)
        if verbatim:
            achados.append({
                "bloco": bloco,
                "romaji": "",
                "motivo": f"bloco presente em japonês cru (não romanizado) no PT — conferir romanização ({len(presentes)}/{len(linhas_kana)} âncoras fonéticas)",
            })
        elif linhas_kana:
            if len(presentes) == 0:
                achados.append({
                    "bloco": bloco,
                    "romaji": _romaji_da_tabela(bloco),
                    "motivo": f"bloco ({len(bloco)} linhas): nenhuma âncora encontrada no PT — conteúdo omitido",
                })
            elif len(presentes) < len(linhas_kana):
                achados.append({
                    "bloco": bloco,
                    "romaji": _romaji_da_tabela(bloco),
                    "motivo": f"tabela ({len(bloco)} linhas): apenas {len(presentes)}/{len(linhas_kana)} linha(s) com âncora no PT — tabela INCOMPLETA",
                })
            # se todas presentes → OK (tabela completa representada)
        else:
            achados.append({
                "bloco": bloco,
                "romaji": "",
                "motivo": "bloco só kanji (sem âncora fonética) — conferir se foi traduzido/romanizado no PT",
            })

    return achados


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) < 3:
        print("uso: python3 checador_cobertura.py <jp.txt> <pt.txt>")
        sys.exit(1)
    jp_txt = Path(sys.argv[1]).read_text(encoding="utf-8")
    pt_txt = Path(sys.argv[2]).read_text(encoding="utf-8")
    achados = checar_cobertura(jp_txt, pt_txt)
    if achados:
        print(f"⚠️ {len(achados)} bloco(s) sem correspondência no PT:")
        for a in achados:
            print(f"  - {a['bloco'][:2]} ... {a['motivo']}")
        sys.exit(1)
    else:
        print("✅ Todos os blocos não-prosaicos do JP têm correspondência no PT.")
        sys.exit(0)
