"""Aplica as trocas que a guarda de unicidade por ARQUIVO deixou de fora.

O aplicador padrão só grava quando o trecho ocorre uma única vez no arquivo
inteiro -- a salvaguarda que existe desde o desastre do replace global. Mas a
troca foi decidida lendo UM artigo, e é nele que ela deve valer: numa obra de
200 depoimentos, "Ministro Responsável" ou "espírito da palavra" repetem em
dezenas de lugares e a troca legítima do artigo 12 é descartada por causa do
artigo 130. Na 4ª passada isso descartou 54 de 159.

Aqui o escopo é o artigo: a âncora do artigo e a do seguinte delimitam a
janela no texto BRUTO, e a troca só é gravada se o trecho for único DENTRO
dessa janela. Continua não havendo replace global -- o escopo apertou, não
afrouxou.

Se a janela não puder ser determinada com segurança (âncora ausente do texto
bruto, ordem não confirmada), o artigo é pulado e reportado.

Uso:
    python3 scripts/aplica_no_artigo.py <ARQUIVO.json>            # diagnóstico
    python3 scripts/aplica_no_artigo.py <ARQUIVO.json> --aplicar
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
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"


def janelas(obra: str, texto: str) -> list[tuple[int, int]] | None:
    """Início e fim de cada artigo no texto BRUTO, pelas âncoras em ordem."""
    sp = SPEC_DIR / f"{obra}.json"
    if not sp.exists():
        return None
    arts = json.loads(sp.read_text(encoding="utf-8")).get("articles", [])
    if not arts:
        return None
    if len(arts) == 1:
        # obra de artigo único: a janela é o arquivo, e escopo de artigo e de
        # arquivo coincidem -- a guarda de unicidade continua valendo igual
        return [(0, len(texto))]
    inicios, cursor = [], 0
    for a in arts:
        anc = a.get("pt_anchor", "")
        if not anc:
            return None
        p = texto.find(anc, cursor)
        if p < 0:
            # A âncora foi gravada contra o texto de clean_body(), que colapsa
            # 4+ quebras de linha em 3 -- no bruto elas continuam 4 e a busca
            # literal falha. Caso real: 御教え集3号, 4 de 10 âncoras.
            # Aqui a busca aceita QUALQUER número de quebras onde a âncora tem
            # uma sequência delas; o resto continua literal.
            flex = re.sub(r"\n+", lambda m: r"\n{%d,}" % len(m.group()),
                          re.escape(anc).replace("\\\n", "\n"))
            m = re.compile(flex).search(texto, cursor)
            if not m:
                return None        # aí sim não é localizável: desiste
            p = m.start()
        inicios.append(p)
        cursor = p + 1
    fins = inicios[1:] + [len(texto)]
    return list(zip(inicios, fins))


def main() -> None:
    alvo = RAIZ / "reports/varredura_padronizacao" / sys.argv[1]
    aplicar = "--aplicar" in sys.argv
    dados = json.loads(alvo.read_text(encoding="utf-8"))
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    por_obra: dict[str, list[tuple[int, dict]]] = {}
    for r in dados:
        for t in r.get("trocas", []):
            por_obra.setdefault(r["obra"], []).append((r["artigo"], t))

    aplicadas = ja = sem_janela = ambiguas = 0
    for obra, itens in sorted(por_obra.items()):
        f = PT_FONTE / obra
        if not f.exists():
            continue
        texto = f.read_text(encoding="utf-8")
        js = janelas(obra, texto)
        if js is None:
            sem_janela += len(itens)
            print(f"  SEM JANELA {obra[:40]} ({len(itens)} trocas)")
            continue
        original = texto
        for art, t in sorted(itens, key=lambda x: -x[0]):   # de trás p/ frente
            if art >= len(js):
                continue
            ini, fim = js[art]
            trecho = texto[ini:fim]
            n = trecho.count(t["de"])
            if n == 0:
                ja += 1                                   # já aplicada antes
                continue
            if n > 1:
                ambiguas += 1
                print(f"  AMBÍGUA {obra[:30]} art{art}: {t['de'][:44]!r} ({n}x no artigo)")
                continue
            texto = texto[:ini] + trecho.replace(t["de"], t["para"]) + texto[fim:]
            aplicadas += 1
        if aplicar and texto != original:
            f.with_suffix(f".txt.bak_pre_artigo_{carimbo}").write_text(
                original, encoding="utf-8")
            f.write_text(texto, encoding="utf-8")
            st = PT_STAGING / obra
            if st.exists():
                st.write_text(texto, encoding="utf-8")

    print(f"\n{aplicadas} aplicadas no escopo do artigo | {ja} já estavam | "
          f"{ambiguas} ambíguas no próprio artigo | {sem_janela} sem janela")
    if not aplicar:
        print("(diagnóstico apenas -- rode com --aplicar)")
        return

    ruins = 0
    for obra in por_obra:
        sp = SPEC_DIR / f"{obra}.json"
        if not sp.exists():
            continue
        anc = [a.get("pt_anchor", "") for a in
               json.loads(sp.read_text(encoding="utf-8")).get("articles", [])]
        if len(anc) <= 1 or not all(anc):
            continue
        for base in (PT_FONTE, PT_STAGING):
            g = base / obra
            if not g.exists():
                continue
            try:
                if len(split_by_anchors(clean_body(g.read_text(encoding="utf-8")),
                                        anc, label=obra)) != len(anc):
                    raise ValueError("contagem")
            except ValueError as exc:
                print(f"  QUEBRADA {base.name}/{obra}: {str(exc)[:90]}")
                ruins += 1
    print(f"verificação: {ruins} âncoras quebradas")


if __name__ == "__main__":
    main()
