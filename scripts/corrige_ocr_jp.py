"""Emenda a corrupção de leitura óptica no japonês de trabalho.

O japonês dos periódicos veio por OCR do PDF do Zenshū, com substituições
sistemáticas por caracteres de forma parecida -- quase sempre a forma
simplificada chinesa ou um kanji raríssimo. Uma varredura de 05/08 corrigiu
seis classes (3.034 caracteres) e parou aí. Restaram cinquenta e tantas.

Isso não é decisão de tradução: é restaurar a fonte. O efeito de deixar como
está é duplo -- quem revisa a tradução compara contra um original adulterado, e
o desafiador da triagem vinha derrubando achados corretos por tomar o glifo
corrompido como autoridade ("os dois leram 喜ぶべし, mas o dossiê traz 喛ぶべし").

MÉTODO. Nenhuma substituição entrou aqui por semelhança de forma. Para cada
glifo eu li TODAS as ocorrências do acervo -- não amostra -- e só o incluí
quando todos os contextos convergiam para o mesmo alvo. Os que não convergiram
estão em INCERTOS, no fim do arquivo, e não são tocados.

Três casos exigiram regra condicional, porque o glifo corrompido também existe
em japonês legítimo:

  吊  648 ocorrências, das quais 77 são o 吊 verdadeiro. A primeira versão da
      regra excluía só as formas verbais (吊る "o músculo repuxa", 吊って
      "pendurar", 吊り) e teria convertido 吊橋 em 名橋, 吊革 em 名革, 吊柿 em
      名柿 -- oito livros fora dos periódicos, exatamente a classe de estrago
      de 07/08. O ensaio mostrou isso antes de qualquer gravação. A lista de
      rejeito passou a incluir os substantivos: 革 (alça de trem), 橋 (ponte
      suspensa), 柿 (caqui pendurado), 皮, 上 (吊上げる, revirar os olhos).
      As outras 571 são 名 -- 有名, 名画, 名人, 名づける, 汝の名. Uma exceção
      dentro da exceção: 改吊した é 改名した, e vem antes da regra geral.
  抝  o mesmo glifo cobre dois alvos: 選抝 é 選択, 抝ばず/抝ぶ é 選ばず/選ぶ.
  撯  杜撯 é 杜撰; 撯ぶところ é 選ぶところ.

E um que PARECE corrupção e não é: 盡 (12 ocorrências, todas 尽くす/尽きる/
盡十方世界). É kyūjitai legítimo, e o acervo guarda ortografia antiga em outros
pontos. Fica. O mesmo vale para 挾, 爐, 繩, 罐, 爼, 濶, 潑 -- formas velhas, não
defeito de leitura.

A âncora de segmentação é busca de texto literal: se o texto muda e a âncora
não, a obra inteira perde a divisão por artigo. Por isso cada âncora recebe a
mesma emenda, e a conferência roda `split_by_anchors` -- a função que a produção
usa de verdade -- antes de gravar. Se a contagem de artigos não bater, a obra
volta inteira ao backup.

    python3 scripts/corrige_ocr_jp.py --ensaio    # não grava, só relata
    python3 scripts/corrige_ocr_jp.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

JP = RAIZ / "reports/livros_trabalho/jp"
SPEC = RAIZ / "reports/livros_trabalho/segmentacao_manual"

# Compostos primeiro: são exceções às regras simples que vêm depois.
COMPOSTOS = [
    ("断未魑", "断末魔"),   # 未 é legítimo em toda parte, menos aqui
    ("改吊",   "改名"),     # único 吊し que não é "pendurar"
    ("選抝",   "選択"),
    ("杜撯",   "杜撰"),
]

# Glifo -> alvo, quando TODAS as ocorrências do acervo convergem.
SIMPLES = {
    "实": "実", "扊": "手", "飝": "食", "痚": "痛", "页": "風", "卖": "単",
    "朩": "未", "忚": "応", "魑": "魔", "頺": "頼", "貟": "負", "亣": "交",
    "宠": "宣", "雂": "雄", "筓": "答", "吆": "吉", "恮": "息", "紌": "納",
    "审": "室", "雤": "雨", "筊": "筋", "单": "南", "遾": "避", "刉": "刊",
    "泤": "泥", "层": "居", "敶": "敷", "慦": "慨", "頹": "頻", "癫": "癬",
    "慥": "慧", "喛": "喜", "抭": "抱", "务": "劣",
    # cauda, cada uma com todos os contextos conferidos
    "枞": "枠", "溂": "溌", "諹": "諺", "雃": "雅", "穁": "穂", "峢": "峨",
    "泋": "泌", "殶": "殷", "駇": "駆", "貾": "貿", "粙": "粛", "冈": "冊",
    "慤": "僅", "屌": "屍", "隇": "隈", "敤": "敦", "旪": "旬", "杒": "杓",
    "綼": "綽", "溁": "剌", "魐": "魑", "蘈": "蘊", "欢": "歓", "腼": "膀",
    "抝": "選", "撯": "選",
}

# 吊 é 名, exceto quando é mesmo "pendurar/repuxar" -- e aí vem seguido destes.
# Levantados varrendo TODOS os 648 casos do acervo, não por hipótese: as cinco
# formas verbais mais os quatro substantivos 吊革/吊橋/吊柿/吊皮 e o 吊上げる.
PENDURAR = "るりっれし革橋柿皮上"
# Um único caso do acervo traz espaço no meio (「足の吊 りが取れず」), daí o [ 　]? na regra.

# Conferidos e deixados de fora: contextos divergentes ou alvo não determinado.
INCERTOS = {
    "瀰": "知れ瀰る (渡?) e 瀰漫 (legítimo)",
    "莒": "経莒 / 硯莒 — 筥? 匣?",
    "击": "投击 / 击嶺上 — alvo não determinado",
    "顶": "神山顶 — 颪? ocorrência única",
    "吋": "皇吋 / 天照皇吋 — 神? 大神?",
    "慂": "慧慂 é 慫慂: o corrompido é o 慧 anterior, não o 慂",
    "諨": "諨言 — 讒? ocorrência única",
    "僣": "僭上 / 僭称 — 僣 é variante aceita de 僭",
}


def emenda(t: str) -> str:
    for a, b in COMPOSTOS:
        t = t.replace(a, b)
    t = re.sub(f"吊(?![ 　]?[{PENDURAR}])", "名", t)
    for a, b in SIMPLES.items():
        t = t.replace(a, b)
    return t


def conta(t: str) -> Counter:
    c = Counter()
    for a, _ in COMPOSTOS:
        c[a] += t.count(a)
    c["吊"] += len(re.findall(f"吊(?![ 　]?[{PENDURAR}])", t))
    for a in SIMPLES:
        c[a] += t.count(a)
    return +c


def main() -> None:
    ensaio = "--ensaio" in sys.argv
    carimbo = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    total = Counter()
    tocadas = revertidas = 0

    for f in sorted(JP.glob("*.txt")):
        antes = f.read_text(encoding="utf-8")
        depois = emenda(antes)
        c = conta(antes)
        if antes == depois:
            continue

        sp = SPEC / f"{f.name}.json"
        d = anc_novas = None
        if sp.exists():
            d = json.loads(sp.read_text(encoding="utf-8"))
            arts = d.get("articles", [])
            anc_novas = [emenda(a.get("jp_anchor", "")) for a in arts]
            # a âncora só vale se ainda dividir a obra em tantos artigos quanto a spec
            if len(anc_novas) > 1 and all(anc_novas):
                try:
                    n = len(split_by_anchors(clean_body(depois), anc_novas, label=f.name))
                except ValueError as exc:
                    print(f"  !! {f.name[:44]:<46} âncora falhou: {str(exc)[:50]}")
                    revertidas += 1
                    continue
                if n != len(anc_novas):
                    print(f"  !! {f.name[:44]:<46} {n} blocos para {len(anc_novas)} âncoras")
                    revertidas += 1
                    continue

        tocadas += 1
        total += c
        print(f"  {f.name[:44]:<46} {sum(c.values()):>5}  "
              + " ".join(f"{k}{v}" for k, v in c.most_common(4)))

        if ensaio:
            continue
        shutil.copy(f, f.with_suffix(f".txt.bak_ocr_{carimbo}"))
        f.write_text(depois, encoding="utf-8")
        if d is not None and anc_novas is not None:
            for a, nova in zip(d["articles"], anc_novas):
                if a.get("jp_anchor") and a["jp_anchor"] != nova:
                    a["jp_anchor"] = nova
            shutil.copy(sp, sp.with_suffix(f".json.bak_ocr_{carimbo}"))
            sp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{tocadas} obras, {sum(total.values())} caracteres emendados"
          + (f", {revertidas} preservadas por âncora" if revertidas else ""))
    print(f"{len(total)} classes com ocorrência real\n")
    print("as maiores:")
    for k, v in total.most_common(10):
        alvo = dict(COMPOSTOS).get(k) or ("名" if k == "吊" else SIMPLES.get(k))
        print(f"  {k} -> {alvo}  {v:>5}")
    if ensaio:
        print("\n(ensaio — nada foi gravado)")


if __name__ == "__main__":
    main()
