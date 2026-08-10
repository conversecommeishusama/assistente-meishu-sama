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
    ("魑魅",   "\x00C\x00"),   # 魑魅魍魎 é palavra real -- e a varredura o RESTAURA
                             # (魐魅->魑魅), então roda-la de novo o converteria
                             # em 魔魅. O ensaio pegou isso na segunda passada.
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


# ---------------------------------------------------------------------------
# SEGUNDA ONDA: kanji legítimo trocado por OUTRO kanji legítimo.
#
# O inventário de glifos raros é cego a esta classe -- 吉 e 后 são japonês
# perfeitamente normal, e por isso nenhum deles apareceu na primeira varredura.
# O detector certo compara BIGRAMAS: os 128 livros vieram de outro pipeline e
# nunca passaram pelo OCR do Zenshū, então um bigrama frequente nos periódicos
# e AUSENTE nos livros é suspeito.
#
# Suspeito não é culpado. O detector devolveu 真山 (真山照政氏, o locutor),
# 置氏 (日置氏, sobrenome), 文省 (本文省略), 御対 (御対談) e 以で (所以で) --
# palavras legítimas que só não ocorrem nos livros. Tratar a lista do detector
# como lista de correção teria trocado o nome de duas pessoas reais.
#
# E DOIS ERAM DE MEISHU-SAMA, não do OCR:
#   曰われる  os livros trazem 曰く/曰うなり 50 vezes -- é a forma arcaica de
#             言う que ele escreve. Trocar seria revisar o original.
#   旺ん      os livros trazem 旺（さか）ん COM FURIGANA marcando a leitura.
#             É a grafia dele para 盛ん.
# Os dois ficam. O japonês não se revisa; corrige-se o que o OCR estragou.
#
# O teste que separa uma coisa da outra, e que vale para tudo aqui:
#   1. a forma suspeita não é palavra nenhuma em japonês;
#   2. ela tem ZERO ocorrências nos 128 livros;
#   3. a forma correta é abundante nos livros (同様 352, 向かっ 125, 財産 75);
#   4. todas as ocorrências foram lidas, não amostradas.
#
# Escopo: só os oito periódicos. Ao contrário da primeira onda, aqui o glifo de
# origem É legítimo nos livros -- 后 ocorre 16 vezes lá e as 16 são imperatriz
# (光明皇后, 神功皇后, 皇太后陛下). Nos periódicos, nenhuma das 308 é.
# ---------------------------------------------------------------------------

PERIODICOS = {"Eiko.txt", "Hikari.txt", "Kyusei.txt", "Tijotengoku.txt",
              "Medicina_do_Amanha.txt", "Jornais.txt", "Ensinamentos_diversos.txt",
              "Revista_Asahi.txt", "Esboco_da_Medicina.txt"}

# Compostos da segunda onda, aplicados antes das regras de caractere.
COMPOSTOS2 = [
    ("住吉様", "\x00A\x00"),   # protege a divindade da regra 吉 -> 同
    ("の后は",  "\x00B\x00"),   # 天皇の后は — consorte, não 向
    ("吉胝",   "同胞"),   # 「四方の海みな同胞と思ふ世に」, o waka do Imperador Meiji
    ("一吉",   "一同"),
    ("混吉",   "混同"),
    ("協吉",   "協同"),
    ("后後",   "今後"),   # as duas únicas ocorrências de 后 que não são 向
    ("始未",   "始末"),
    ("財献",   "貢献"),
    ("負産",   "財産"),
    ("実観",   "客観"),   # o próprio texto contrasta: 主観 é o osso, 客観 a pele
    # TERCEIRA ONDA, achada rodando o detector de bigramas outra vez depois de
    # aplicar a segunda. 吐 tinha ZERO ocorrências nos periódicos e 392 nos
    # livros: sumiu inteiro, virou 名. Li as 31 e são todas 嘘を吐く, 溜息を
    # 吐く, 弱音を吐く, 嘔吐, 吐血 -- enquanto 二名/一名/大名/御名 são 名 de
    # verdade e ficam. 負閥/負政/文化負 são 財閥/財政/文化財, e 抱負/負ける
    # ficam. 断片雄/蒐雄/編雄 são 集: sobra da varredura condicional de 05/08,
    # que tratou 雄->集 e parou nos casos que via.
    ("嘔名",   "嘔吐"),
    ("名 血", "吐血"),
    ("文化負", "文化財"),
    ("負閥",   "財閥"),
    ("負政",   "財政"),
    ("断片雄", "断片集"),
    ("蒐雄",   "蒐集"),
    ("編雄",   "編集"),
]

# 吉 é 同 só nestes compostos; fora deles é nome próprio (吉田, 秀吉, 岡田茂吉).
SEG_DOU = "様じ一時情志氏感権音国"
# Caracteres que formam nome próprio com 吉 e o protegem da regra acima.
NOME_KICHI = "秀茂住不定達藤清千三五良村万寅"


def emenda2(t: str) -> str:
    """Segunda onda. Só faz sentido nos periódicos -- ver bloco acima."""
    import re as _re
    for a, b in COMPOSTOS2:
        t = t.replace(a, b)
    # As duas guardas não são teóricas: o teste de fumaça converteu
    # 皇太后陛下 em 皇太向陛下 e 岡田茂吉氏 em 岡田茂同氏. Nenhum dos dois
    # ocorre nos periódicos, mas uma regra não pode depender só do escopo.
    t = _re.sub(f"(?<![{NOME_KICHI}])吉(?=[{SEG_DOU}])", "同", t)
    t = _re.sub("(?<![皇太])后", "向", t)
    t = _re.sub("名(?=[くきいか])", "吐", t)
    return t.replace("\x00A\x00", "住吉様").replace("\x00B\x00", "の后は")


def emenda(t: str) -> str:
    for a, b in COMPOSTOS:
        t = t.replace(a, b)
    t = re.sub(f"吊(?![ 　]?[{PENDURAR}])", "名", t)
    for a, b in SIMPLES.items():
        t = t.replace(a, b)
    return t.replace("\x00C\x00", "魑魅")


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
        if f.name in PERIODICOS:
            depois = emenda2(depois)
        c = conta(antes)
        if antes == depois:
            continue

        sp = SPEC / f"{f.name}.json"
        d = anc_novas = None
        if sp.exists():
            d = json.loads(sp.read_text(encoding="utf-8"))
            arts = d.get("articles", [])
            # A âncora NÃO recebe as regras de novo: ela é um recorte do texto,
            # e um recorte pode cortar no meio de um composto. A âncora 28 do
            # Tijotengoku termina exatamente num 吉 cujo alvo depende do
            # caractere SEGUINTE, que ficou de fora do recorte -- a regra a
            # deixava intacta enquanto o texto virava 同, e a busca falhava.
            # Como toda substituição preserva o comprimento, basta recortar a
            # mesma faixa do texto já emendado.
            anc_novas = []
            for a in arts:
                v = a.get("jp_anchor", "")
                i = antes.find(v)
                anc_novas.append(depois[i:i + len(v)] if v and i >= 0 else v)
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
