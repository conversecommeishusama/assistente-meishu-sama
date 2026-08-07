"""Repara o dano da troca global de `aplica_decisoes_glossario.py`.

BUG: o script contava as ocorrências POR ARTIGO -- justamente para só trocar
quando o japonês e o português batessem -- mas aplicava com `texto.replace()`
no ARQUIVO INTEIRO. Aprovar um artigo trocava o livro todo. Aprovei 28 trocas
para 祝詞; ele fez ~400.

    oração  2019 -> 1673     norito  152 -> 552
    orações  129 ->  100
    prece    302 ->  277

Restaurar o arquivo não serve: os mesmos 15 livros receberam hoje muita
correção legítima (purificação, Paraíso Terrestre, hortaliças, Byōbu Kannon).

MÉTODO: para cada ocorrência da forma canônica no arquivo atual, pega o
contexto imediatamente anterior e procura esse mesmo contexto na cópia
íntegra de `textos_portugues/` (não tocada hoje). O que estiver naquela
posição no arquivo limpo é a palavra original. Se for uma das formas
trocadas, e o japonês do artigo correspondente NÃO tiver a chave que
justificaria, reverte.

Contexto local em vez de diff: as mesmas linhas mudaram por outros motivos
hoje, então nem o diff por palavra nem o por linha isolam as substituições.

Uso:
    python3 scripts/repara_troca_global.py            # diagnóstico
    python3 scripts/repara_troca_global.py --aplicar
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

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
PT_LIMPO = RAIZ / "textos_japones"  # placeholder, corrigido abaixo
PT_LIMPO = RAIZ / "textos_portugues"
JP_DIR = RAIZ / "reports/livros_trabalho/jp"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"

# canônica -> (formas que podem ter sido trocadas, chave japonesa)
ALVOS = {
    "norito": (["orações", "oração", "preces", "prece"], "祝詞"),
    "filial": (["Centros Regionais", "centros regionais", "núcleos", "núcleo"], "支部"),
    # Rodada 1 do mesmo script, com o mesmo defeito de replace global.
    "Daikōmyō Nyorai": (["grande Komyo-Nyorai", "Komyo-Nyorai"], "大光明如来"),
    "espíritos malignos": (["Espíritos do Mal", "espíritos do mal"], "悪霊"),
    "espírito maligno": (["Espírito do Mal", "espírito do mal"], "悪霊"),
    "o Grão-Mestre": (["o Mestre"], "大先生"),
    "Mundo de Miroku": (["era de Miroku"], "五六七の世"),
    "Igreja Média": (["Igreja Central"], "中教会"),
    "tuberculose pulmonar": (["doença pulmonar"], "肺結核"),
    "sangue turvo": (["sangue impuro", "sangue sujo"], "濁血"),
    "Templo Messiânico": (["Salão Messiânico"], "メシヤ会館"),
}
CONTEXTO = 55


def artigos_jp(obra: str) -> list[str]:
    spec_path = SPEC_DIR / f"{obra}.json"
    jp = JP_DIR / obra
    if not spec_path.exists() or not jp.exists():
        return []
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    texto = clean_body(jp.read_text(encoding="utf-8", errors="replace"))
    arts = spec.get("articles", [])
    anc = [a.get("jp_anchor", "") for a in arts]
    if len(arts) <= 1 or not all(anc):
        return [texto]
    try:
        pedacos = split_by_anchors(texto, anc, label=obra)
    except ValueError:
        return [texto]
    return pedacos if len(pedacos) == len(arts) else [texto]


def fronteiras_pt(obra: str, texto: str) -> list[int]:
    spec_path = SPEC_DIR / f"{obra}.json"
    if not spec_path.exists():
        return []
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    pos, cursor = [], 0
    for a in spec.get("articles", []):
        anc = (a.get("pt_anchor") or "").strip()
        if not anc:
            continue
        p = texto.find(anc.splitlines()[0], cursor)
        if p >= 0:
            pos.append(p)
            cursor = p + 1
    return pos


def artigo_de(pos_char: int, fronteiras: list[int]) -> int:
    idx = -1
    for i, f in enumerate(fronteiras):
        if f <= pos_char:
            idx = i
        else:
            break
    return idx


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tot_rev = tot_ok = tot_sem = 0
    tocados = []

    for p in sorted(PT_FONTE.glob("*.txt")):
        obra = p.name
        limpo_path = PT_LIMPO / obra
        if not limpo_path.exists():
            continue
        atual = p.read_text(encoding="utf-8")
        if not any(c in atual for c in ALVOS):
            continue
        limpo = limpo_path.read_text(encoding="utf-8", errors="replace")
        limpo_n = norm(limpo)

        ajp = artigos_jp(obra)
        fr = fronteiras_pt(obra, clean_body(atual))
        rev = ok = sem = 0
        saida, cursor = [], 0

        padrao = re.compile("|".join(re.escape(c) for c in ALVOS), re.IGNORECASE)
        for m in padrao.finditer(atual):
            canonica = m.group().lower()
            if canonica not in ALVOS:
                continue
            formas, chave = ALVOS[canonica]

            # Justificado pelo japonês do artigo? Então nem mexe.
            idx = artigo_de(m.start(), fr) if fr else -1
            if ajp and 0 <= idx < len(ajp) and chave in ajp[idx]:
                ok += 1
                continue

            antes = norm(atual[max(0, m.start() - CONTEXTO): m.start()]).strip()
            if len(antes) < 20:
                sem += 1
                continue
            pos = limpo_n.find(antes)
            if pos < 0 or limpo_n.count(antes) != 1:
                sem += 1
                continue
            seguinte = limpo_n[pos + len(antes): pos + len(antes) + 40].lstrip()
            original = next((f for f in formas
                             if seguinte.lower().startswith(f.lower())), None)
            if not original:
                sem += 1
                continue
            saida.append(atual[cursor: m.start()])
            # preserva a caixa do que estava lá
            saida.append(original if not m.group()[0].isupper()
                         else original[0].upper() + original[1:])
            cursor = m.end()
            rev += 1

        if not rev:
            continue
        saida.append(atual[cursor:])
        tot_rev += rev
        tot_ok += ok
        tot_sem += sem
        tocados.append((obra, rev, ok, sem))
        if aplicar:
            novo = "".join(saida)
            p.with_suffix(f".txt.bak_pre_reparo_{carimbo}").write_text(atual, encoding="utf-8")
            p.write_text(novo, encoding="utf-8")
            st = PT_STAGING / obra
            if st.exists():
                st.write_text(novo, encoding="utf-8")

    print(f"{tot_rev} revertidas | {tot_ok} legítimas mantidas | "
          f"{tot_sem} sem contexto recuperável")
    for obra, r, o, s in sorted(tocados, key=lambda x: -x[1])[:12]:
        print(f"  {obra[:42]:<44} rev {r:>4}  ok {o:>3}  indeterm {s}")
    if not aplicar:
        print("\n(diagnóstico apenas — rode com --aplicar)")


if __name__ == "__main__":
    main()
