"""Corrige corrupção de OCR no corpus japonês.

Os arquivos de periódico foram extraídos por OCR do PDF do Zenshū e trouxeram
substituições sistemáticas de caractere. A mais grave: **641 das 1.870
ocorrências de 明主様 estão escritas 明为様** -- um terço. Quem revisa tradução
comparando com o japonês está lendo um original corrompido, e a busca em
japonês do aplicativo não encontra essas 641.

Quatro caracteres não existem em japonês e são sempre erro:

    亓 -> 五     四人も亓人も, 亓十くらい
    为 -> 主     民为的国家, 明为様
    尐 -> 少     尐しずつ, 尐なくとも
    吅 -> 合     場吅でも

Dois também existem legitimamente e exigem contexto -- verificado lendo TODOS
os bigramas de cada um, não por amostra:

    朋 -> 服     服む/服装/服用/征服/克服/屈服/服従
                 MAS 朋友 (amigos, 1x) e 朋子 (nome próprio, 2x) são reais
    雄 -> 集     集まる/集める/集団/集中/集溜/特集号/集積/集録/集落/集散/
                 集局(編集局)/蒐集品/苦集滅道
                 MAS 英雄, 雄大, 雌雄, 雄弁, 雄々しい, 雄鶏 e dezenas de nomes
                 próprios terminados em 雄 (義雄, 益雄, 数雄, 久雄) são reais

Uso:
    python3 scripts/corrige_ocr_japones.py            # mostra, não grava
    python3 scripts/corrige_ocr_japones.py --aplicar
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

BASES_JP = [RAIZ / "reports/livros_trabalho/jp", RAIZ / "textos_japones"]
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"

INCONDICIONAIS = {"亓": "五", "为": "主", "尐": "少", "吅": "合"}

# 朋 -> 服, exceto diante de 友 (朋友) e 子 (朋子, nome)
RE_HO = re.compile(r"朋(?![友子])")

# 雄 -> 集, só nos compostos confirmados por leitura, e nunca depois de 英
SEGUINTES_SHU = "まめむ団中溜号積録落散滅局品合"
RE_YU = re.compile(r"(?<!英)雄(?=[" + SEGUINTES_SHU + r"])")


def corrige(texto: str) -> tuple[str, Counter]:
    contagem: Counter = Counter()
    for errado, certo in INCONDICIONAIS.items():
        n = texto.count(errado)
        if n:
            contagem[f"{errado}->{certo}"] += n
            texto = texto.replace(errado, certo)
    novo, n = RE_HO.subn("服", texto)
    if n:
        contagem["朋->服"] += n
    texto = novo
    novo, n = RE_YU.subn("集", texto)
    if n:
        contagem["雄->集"] += n
    return novo, contagem


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    total: Counter = Counter()
    por_obra: dict[str, int] = {}

    for base in BASES_JP:
        for p in sorted(base.glob("*.txt")):
            texto = p.read_text(encoding="utf-8")
            novo, cont = corrige(texto)
            if not cont:
                continue
            total.update(cont)
            if base is BASES_JP[0]:
                por_obra[p.name] = sum(cont.values())
            if aplicar:
                if base is BASES_JP[0]:
                    p.with_suffix(f".txt.bak_pre_ocr_{carimbo}").write_text(
                        texto, encoding="utf-8")
                p.write_text(novo, encoding="utf-8")

    print(f"{sum(total.values())} correções")
    for k, v in total.most_common():
        print(f"  {k}  {v:>6}")
    print()
    for obra, n in sorted(por_obra.items(), key=lambda x: -x[1])[:12]:
        print(f"  {n:>6}  {obra[:56]}")

    if not aplicar:
        print("\n(diagnóstico apenas — rode com --aplicar)")
        return

    # Âncoras japonesas que continham caractere corrompido mudaram junto com o
    # texto: aplica a MESMA correção na âncora e revalida.
    print("\nrevalidando âncoras japonesas...")
    ajustadas = ruins = 0
    for obra in por_obra:
        spec_path = SPEC_DIR / f"{obra}.json"
        if not spec_path.exists():
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        arts = spec.get("articles", [])
        anc = [a.get("jp_anchor", "") for a in arts]
        if len(anc) <= 1 or not all(anc):
            continue
        original = spec_path.read_text(encoding="utf-8")
        mudou = False
        for a in arts:
            novo_anc, cont = corrige(a.get("jp_anchor", ""))
            if cont:
                a["jp_anchor"] = novo_anc
                if a.get("title_jp"):
                    a["title_jp"] = corrige(a["title_jp"])[0]
                mudou = True
                ajustadas += 1
        if mudou:
            spec_path.with_suffix(f".json.bak_pre_ocr_{carimbo}").write_text(
                original, encoding="utf-8")
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
            anc = [a["jp_anchor"] for a in arts]
        for base in BASES_JP:
            f = base / obra
            if not f.exists():
                continue
            try:
                c = split_by_anchors(clean_body(f.read_text(encoding="utf-8")), anc, label=obra)
                if len(c) != len(anc):
                    raise ValueError(f"{len(c)} != {len(anc)}")
            except ValueError as exc:
                print(f"  QUEBROU {base.name}/{obra}: {exc}")
                ruins += 1
    print(f"  {ajustadas} âncoras corrigidas junto com o texto, {ruins} quebradas")


if __name__ == "__main__":
    main()
