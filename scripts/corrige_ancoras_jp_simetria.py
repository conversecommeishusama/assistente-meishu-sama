"""Realinha as âncoras JAPONESAS com as portuguesas.

A correção de âncoras de 2026-08-07 (`corrige_ancoras_byline.py`) moveu 183
`pt_anchor` da byline/rótulo de diálogo para o título do artigo -- e mexeu SÓ
no lado português. O japonês ficou para trás, e os dois lados passaram a
delimitar artigos diferentes:

    art86 JP  ...termina com 「夢に明主様の御浄霊を戴き奇蹟の前に平伏す」
                             (o título do art87) + endereço
    art87 JP  começa em 大浄大教会　赤松みのゑ（49）   <- byline
    art87 PT  começa em "**Recebendo o Johrei de Meishu-Sama em Sonho...**"

Defeito introduzido por mim, achado ao verificar por que o julgamento de
glossário acusava 明主様 como omitido: não estava omitido, estava no artigo
vizinho de um dos lados.

Este script aplica ao `jp_anchor` a mesma lógica já usada no português: se a
âncora aponta para uma byline e o cabeçalho do artigo (título japonês) ficou
preso no fim do artigo anterior, move a âncora para o título.

Só toca obras em que o português JÁ foi corrigido -- o alvo é restaurar a
simetria, não abrir uma frente nova.

Uso:
    python3 scripts/corrige_ancoras_jp_simetria.py            # diagnóstico
    python3 scripts/corrige_ancoras_jp_simetria.py --aplicar
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

JP_STAGING = RAIZ / "reports/livros_trabalho/jp"
JP_PROD = RAIZ / "textos_japones"
PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"

# Obras cujo pt_anchor foi movido hoje. Fora delas não há assimetria a
# corrigir, e mexer seria abrir escopo sem necessidade.
ALVOS = [
    "19530910-世界救世教奇蹟集.txt",
    "19510815-結核の革命的療法.txt",
    "19550425-浄霊法講座（七）婦人科『浄霊法講座』7号.txt",
]

# Byline japonesa: igreja + nome + (idade), ou nome + (idade)
RE_BYLINE_JP = re.compile(
    r"^[^\s　]{0,12}(教会|分院|支部)[\s　]*[^\s　（(]{1,12}[\s　]*[（(]\s*\d{1,3}\s*[)）]"
    r"|^[^\s　（(]{2,12}[\s　]*[（(]\s*\d{1,3}\s*[)）]")
# Rótulo de diálogo japonês
RE_DIALOGO_JP = re.compile(r"^[（(]?(御伺|お伺|御垂示|御教え|質問|問)[）)]?")
# Endereço japonês. NÃO usar `[都道府県]` como classe solta: 道 é palavra
# comum ("caminho") e faria 「二道かけていた愚かな私の告白」 ser lido como
# endereço. Este projeto já cometeu e corrigiu exatamente esse erro em
# `jp_line_split.py` (RE_EDITORIAL_META tratava 道 de 夫婦の道 como endereço,
# suprimindo títulos legítimos em todo o corpus). Exige província real no
# início, ou terminação de divisão administrativa.
RE_ENDERECO_JP = re.compile(
    r"^(北海道|東京都|大阪府|京都府|.{2,4}県)"
    r"|[市区郡町村丁目]\s*$")
RE_DIVISOR = re.compile(r"^[\s\-—–─*=_·・]{2,}$")


def le(caminho: Path) -> str:
    return clean_body(caminho.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n"))


def cabecalho_vazado_jp(corpo_anterior: str) -> list[str]:
    """Linhas do fim do artigo japonês anterior que abrem o próximo.

    No japonês não há pontuação final confiável em título, então a
    classificação é por forma: linha curta que não termina em 。 e que seja
    título, endereço ou byline pertence ao cabeçalho seguinte.
    """
    linhas = [ln.rstrip() for ln in corpo_anterior.splitlines()]
    vazadas: list[str] = []
    for ln in reversed(linhas):
        s = ln.strip()
        if not s:
            if vazadas:
                continue
            break
        if RE_DIVISOR.fullmatch(s):
            break
        # Só 。 e comprimento marcam corpo. Título japonês pode terminar em
        # ！ ou ？ -- 「ああ奇蹟なり！！奇蹟なり！！！」 é título de depoimento,
        # e parar nele escondia o cabeçalho seguinte. É o mesmo defeito de
        # parada que já tinha aparecido no lado português.
        if len(s) > 60 or s.endswith("。"):
            break
        vazadas.insert(0, s)
        if len(vazadas) > 5:
            return []
    return vazadas


def eh_titulo_jp(linha: str) -> bool:
    s = linha.strip()
    if len(s) < 4 or RE_DIVISOR.fullmatch(s):
        return False
    if RE_BYLINE_JP.match(s) or RE_ENDERECO_JP.search(s):
        return False
    return True


def analisa(nome: str) -> dict:
    spec_path = SPEC_DIR / f"{nome}.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    arts = spec.get("articles", [])
    anc = [a.get("jp_anchor", "") for a in arts]
    if len(arts) <= 1 or not all(anc):
        return {"arquivo": nome, "erro": "spec sem âncoras japonesas"}
    texto = le(JP_STAGING / nome)
    try:
        corpos = split_by_anchors(texto, anc, label=nome)
    except ValueError as exc:
        return {"arquivo": nome, "erro": f"split falhou antes de mexer: {exc}"}

    pos_anc, cursor = [], 0
    for a in anc:
        p = texto.find(a.strip().splitlines()[0], cursor)
        pos_anc.append(p)
        cursor = max(cursor, p + 1)

    propostas = []
    for i in range(1, len(arts)):
        primeira = anc[i].strip().splitlines()[0].strip()
        if not (RE_BYLINE_JP.match(primeira) or RE_DIALOGO_JP.match(primeira)):
            continue
        vazadas = cabecalho_vazado_jp(corpos[i - 1])
        if not vazadas:
            continue
        nova = ""
        for cand in vazadas:
            if not eh_titulo_jp(cand) or pos_anc[i - 1] < 0:
                continue
            # Unicidade GLOBAL é exigente demais: `split_by_anchors` procura a
            # partir de um cursor, e um título como 結核恐怖症 ("fobia de
            # tuberculose") aparece 11 vezes como expressão comum no corpo dos
            # depoimentos. O que precisa ser verdade é que a PRIMEIRA
            # ocorrência depois da âncora anterior seja o cabeçalho deste
            # artigo -- isto é, caia antes de onde a âncora atual aponta.
            p = texto.find(cand, pos_anc[i - 1] + 1)
            if p < 0 or p >= pos_anc[i]:
                continue
            nova = cand
            break
        if not nova:
            continue
        propostas.append({
            "artigo": i, "atual": anc[i], "nova": nova,
            "title_jp_atual": arts[i].get("title_jp", ""),
        })
    return {"arquivo": nome, "n": len(arts), "propostas": propostas}


def aplica(nome: str, propostas: list[dict]) -> dict:
    spec_path = SPEC_DIR / f"{nome}.json"
    original = spec_path.read_text(encoding="utf-8")
    spec = json.loads(original)
    arts = spec["articles"]
    for p in propostas:
        a = arts[p["artigo"]]
        a["jp_anchor"] = p["nova"]
        if not (a.get("title_jp") or "").strip():
            a["title_jp"] = p["nova"]
    anc = [a["jp_anchor"] for a in arts]
    res = {"arquivo": nome, "aplicadas": len(propostas)}
    for rotulo, base in (("staging", JP_STAGING), ("produção", JP_PROD)):
        f = base / nome
        if not f.exists():
            res[rotulo] = "ausente"
            continue
        try:
            c = split_by_anchors(le(f), anc, label=nome)
        except ValueError as exc:
            spec_path.write_text(original, encoding="utf-8")
            return {"arquivo": nome, "REVERTIDO": f"{rotulo}: {exc}"}
        if len(c) != len(arts):
            spec_path.write_text(original, encoding="utf-8")
            return {"arquivo": nome, "REVERTIDO": f"{rotulo}: {len(c)} != {len(arts)}"}
        res[rotulo] = f"{len(c)}/{len(arts)} ok"
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (spec_path.parent / f"{spec_path.name}.bak_pre_simetria_{carimbo}").write_text(
        original, encoding="utf-8")
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    total = 0
    for nome in ALVOS:
        for rodada in range(1, 6):
            r = analisa(nome)
            props = r.get("propostas") or []
            if r.get("erro") or not props:
                break
            total += len(props)
            print(f"\n{nome[:44]} — rodada {rodada}: {len(props)} âncoras JP a mover")
            for p in props[:3]:
                print(f"   art {p['artigo']:>4}: {p['atual'][:40]!r}")
                print(f"          -> {p['nova'][:56]!r}")
            if len(props) > 3:
                print(f"   ... mais {len(props) - 3}")
            if not aplicar:
                break
            res = aplica(nome, props)
            print("  ", res)
            if "REVERTIDO" in res:
                break
    print(f"\nTOTAL: {total} âncoras japonesas")
    if not aplicar:
        print("(diagnóstico apenas — rode com --aplicar)")


if __name__ == "__main__":
    main()
