"""Auditoria completa pedida pelo usuário (2026-08-11): confirma que os
ajustes decididos foram REALMENTE aplicados (não só que o checkpoint diz
"novo_paragrafo"), que PT e JP têm o mesmo número de artigos por obra
(mesma spec, then correspondência estrutural), e que toda âncora (PT e
JP) resolve contra a função real de produção.

Três checagens, cada uma reportada em separado -- nunca resume "tudo OK"
sem mostrar os números:

1. ESTRUTURA -- split_by_anchors (a função real de produção) contra
   PT (2 cópias) e JP, para as 137 obras.
2. APLICAÇÃO -- para cada item aceito no checkpoint (tem 'novo_paragrafo'),
   confere se o texto 'de' (o que devia ter sido substituído) ainda
   aparece LITERALMENTE no artigo -- se aparecer, a correção não foi
   aplicada de verdade, não importa o que o checkpoint diz.
3. PARIDADE PT/JP -- mesmo número de artigos nos dois specs (sempre
   devia ser True, já que os dois vêm da mesma lista de `articles`, mas
   confere mesmo assim -- e confere que nenhum jp_anchor ou pt_anchor
   ficou vazio).

Uso: python3 scripts/auditoria_final_completa.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from build_clean_large_indexes import clean_body  # noqa: E402
from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from aplica_no_artigo import janelas  # noqa: E402
from implanta_semantico_v2 import paragrafo  # noqa: E402

SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
JP_DIR = RAIZ / "reports/livros_trabalho/jp"
CHECKPOINT = RAIZ / "reports/varredura_padronizacao/CHECKPOINT_IMPLANTA_V2.json"


def checa_estrutura():
    print("=" * 70)
    print("1. ESTRUTURA -- split_by_anchors (PT x2 cópias + JP)")
    print("=" * 70)
    total = 0
    quebradas_pt, quebradas_jp, dessinc, ancoras_vazias, sem_jp = [], [], [], [], []
    for sp_path in sorted(SPEC_DIR.glob("*.txt.json")):
        obra = sp_path.name[:-len(".json")]
        fa, fb = PT_FONTE / obra, PT_STAGING / obra
        if not fa.exists() or not fb.exists():
            continue
        total += 1
        ta, tb = fa.read_text(encoding="utf-8"), fb.read_text(encoding="utf-8")
        if ta != tb:
            dessinc.append(obra)
        spec = json.loads(sp_path.read_text(encoding="utf-8"))
        arts = spec.get("articles", [])
        for i, a in enumerate(arts):
            if not a.get("pt_anchor", "").strip() or not a.get("jp_anchor", "").strip():
                ancoras_vazias.append(f"{obra}[{i}]")
        anc_pt = [a.get("pt_anchor", "") for a in arts]
        if len(anc_pt) > 1:
            try:
                ok = len(split_by_anchors(clean_body(ta), anc_pt, label=obra)) == len(anc_pt)
            except ValueError as exc:
                ok = False
            if not ok:
                quebradas_pt.append(obra)
        fjp = JP_DIR / obra
        if not fjp.exists():
            sem_jp.append(obra)
            continue
        anc_jp = [a.get("jp_anchor", "") for a in arts]
        if len(anc_jp) > 1:
            tjp = fjp.read_text(encoding="utf-8")
            try:
                ok = len(split_by_anchors(clean_body(tjp), anc_jp, label=obra + "[JP]")) == len(anc_jp)
            except ValueError:
                ok = False
            if not ok:
                quebradas_jp.append(obra)

    print(f"total obras: {total}")
    print(f"PT quebradas: {len(quebradas_pt)}  {quebradas_pt}")
    print(f"JP quebradas: {len(quebradas_jp)}  {quebradas_jp}")
    print(f"sem arquivo JP: {len(sem_jp)}  {sem_jp}")
    print(f"PT staging dessincronizado: {len(dessinc)}  {dessinc}")
    print(f"âncoras vazias (pt ou jp): {len(ancoras_vazias)}  {ancoras_vazias[:20]}")
    return not (quebradas_pt or quebradas_jp or dessinc or ancoras_vazias or sem_jp) and total == 137


def checa_paridade_pt_jp():
    print()
    print("=" * 70)
    print("3. PARIDADE PT/JP -- mesmo número de artigos por obra")
    print("=" * 70)
    problemas = []
    for sp_path in sorted(SPEC_DIR.glob("*.txt.json")):
        obra = sp_path.name[:-len(".json")]
        spec = json.loads(sp_path.read_text(encoding="utf-8"))
        arts = spec.get("articles", [])
        n_pt = sum(1 for a in arts if a.get("pt_anchor", "").strip())
        n_jp = sum(1 for a in arts if a.get("jp_anchor", "").strip())
        if n_pt != len(arts) or n_jp != len(arts) or n_pt != n_jp:
            problemas.append((obra, len(arts), n_pt, n_jp))
    if problemas:
        for obra, n, npt, njp in problemas:
            print(f"  *** {obra}: {n} artigos, {npt} com pt_anchor, {njp} com jp_anchor")
    else:
        print("todas as 137 obras: mesmo número de artigos com pt_anchor e jp_anchor preenchidos")
    return not problemas


def checa_aplicacao():
    print()
    print("=" * 70)
    print("2. APLICAÇÃO -- 'de' ainda aparece no artigo? (não devia)")
    print("=" * 70)
    ck = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    aceitos = [r for r in ck.values() if "novo_paragrafo" in r]
    print(f"{len(aceitos)} itens aceitos no checkpoint original a conferir\n")

    por_obra: dict[str, list[dict]] = {}
    for r in aceitos:
        por_obra.setdefault(r["obra"], []).append(r)

    nao_aplicados = []
    obras_sem_arquivo = []
    total_checados = 0
    for obra, itens in por_obra.items():
        f = PT_FONTE / obra
        if not f.exists():
            obras_sem_arquivo.append(obra)
            continue
        texto = f.read_text(encoding="utf-8")
        limpo = clean_body(texto)
        jan = janelas(obra, limpo)
        for it in itens:
            total_checados += 1
            de = it["de"]
            if not de:
                continue
            # escopo de ARTIGO, não do arquivo inteiro -- "de" pode
            # legitimamente aparecer em OUTRO artigo do mesmo livro (frase
            # comum, citação repetida) sem que isso signifique que a
            # correção deste artigo específico não foi aplicada.
            artigo = it["artigo"]
            if jan is not None and artigo < len(jan):
                ini, fim = jan[artigo]
                escopo = limpo[ini:fim]
            else:
                escopo = limpo  # sem janela -- cai pro arquivo inteiro mesmo
            if escopo.count(de) > 0:
                nao_aplicados.append((obra, artigo, de, it.get("para", "")))

    print(f"{total_checados} itens conferidos, {len(obras_sem_arquivo)} obras sem arquivo")
    print(f"\n{len(nao_aplicados)} itens onde 'de' AINDA aparece no texto (possível não-aplicação):")
    for obra, art, de, para in nao_aplicados[:60]:
        print(f"  {obra[:35]:<37} art{art:<4} de={de[:55]!r}")
    if len(nao_aplicados) > 60:
        print(f"  ... e mais {len(nao_aplicados) - 60}")
    return nao_aplicados


if __name__ == "__main__":
    estrutura_ok = checa_estrutura()
    paridade_ok = checa_paridade_pt_jp()
    nao_aplicados = checa_aplicacao()

    print()
    print("=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"estrutura (split_by_anchors PT+JP, 137 obras): {'OK' if estrutura_ok else 'PROBLEMA'}")
    print(f"paridade PT/JP (contagem de artigos): {'OK' if paridade_ok else 'PROBLEMA'}")
    print(f"aplicação ('de' sumiu do texto): {len(nao_aplicados)} suspeitos de 'de' ainda presente")
