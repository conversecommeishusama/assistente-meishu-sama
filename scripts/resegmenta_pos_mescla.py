"""Reconstrói pt_anchor das obras que `mescla_e_aplica.py` corrigiu sem se
preocupar com âncora (decisão do usuário 2026-08-11: aplicar ignorando
âncora, resegmentar depois -- esse trabalho seria necessário de qualquer
forma antes de qualquer promoção).

Método: busca SEQUENCIAL por janela, nunca no arquivo inteiro -- é a mesma
lição de hoje (世界救世教奇蹟集: busca cega trocou "Tuberculose" por
"Varíola" porque os dois títulos começam igual). Pra cada artigo, na
ordem: se a âncora velha ainda bate a partir de onde a âncora anterior
parou, fica como está (maioria dos casos -- só o parágrafo específico da
correção mudou, o resto do artigo é idêntico). Se não bate mais, procura
dentro de uma JANELA logo à frente do cursor (nunca o arquivo inteiro),
encolhendo/crescendo o texto até achar algo único NESSA janela. Se nada
resolver dentro da janela, o artigo fica pendente -- nunca inventa
posição.

Uso:
    python3 scripts/resegmenta_pos_mescla.py <obra1> [obra2 ...]            # ensaio
    python3 scripts/resegmenta_pos_mescla.py <obra1> [obra2 ...] --aplicar
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from build_clean_large_indexes import clean_body  # noqa: E402
from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from aplica_no_artigo import PT_FONTE, PT_STAGING, SPEC_DIR  # noqa: E402
from repara_implanta_v2 import regenera_ancora  # noqa: E402
from implanta_semantico_v2 import paragrafo  # noqa: E402

JANELA_BUSCA = 6000     # nunca busca além disso à frente do cursor


def candidata_por_correcao(velha: str, itens_obra: list[dict], artigo: int) -> str | None:
    """Achado real (Eiko art85: 'A Forma de Pensar da Medicina' virou 'Teoria
    da Medicina Moderna') -- quando a própria correção reescreve o TÍTULO
    (início da âncora), o texto antigo simplesmente não existe mais em
    lugar nenhum, nem numa janela local. Reconstrói a âncora aplicando a
    correção DIRETO nela (mesmo método já usado em repara_implanta_v2.py),
    antes de cair pra busca.

    Critério de segurança: usa o `novo_paragrafo` de UM item isolado (não
    o de `mescla_grupo`, que já pode ter sido reescrito junto com outras
    correções do MESMO trecho e não bate mais com o disco) só quando esse
    item é o ÚNICO cujo "de" cai DENTRO da âncora -- não "o único item do
    artigo inteiro" (restrição excessiva descartada: Eiko art104 tinha 2
    itens no artigo, mas só 1 deles tocava a âncora/título, o outro era
    bem mais fundo no corpo -- o item do título continuava seguro de usar
    sozinho). O risco real (御讃歌集 art13: 2 itens, os DOIS caindo dentro
    da mesma âncora curta de 1 linha, mesclados numa chamada só) só existe
    quando mais de um "de" cai dentro da PRÓPRIA âncora -- aí sim o
    `novo_paragrafo` de cada item isolado não reflete o que
    `mescla_grupo()` realmente escreveu."""
    tocam_ancora = [it for it in itens_obra
                     if it.get("artigo") == artigo and it.get("de") and it["de"] in velha]
    if len(tocam_ancora) != 1:
        return None
    it = tocam_ancora[0]
    lim = paragrafo(velha, 0, len(velha), it["de"])
    if lim is None:
        return None
    np = it.get("novo_paragrafo", it["para"])
    return velha[:lim[0]] + np + velha[lim[1]:]


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    obras = [a for a in sys.argv[1:] if a != "--aplicar"]
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ck = json.loads((RAIZ / "reports/varredura_padronizacao/CHECKPOINT_IMPLANTA_V2.json")
                     .read_text(encoding="utf-8"))

    for obra in obras:
        f = PT_FONTE / obra
        if not f.exists():
            print(f"  {obra[:45]:<47} ARQUIVO AUSENTE")
            continue
        atual = f.read_text(encoding="utf-8")
        limpo_atual = clean_body(atual)

        sp = SPEC_DIR / f"{obra}.json"
        spec = json.loads(sp.read_text(encoding="utf-8"))
        arts = spec["articles"]
        itens_obra = [r for r in ck.values() if r.get("obra") == obra and "novo_paragrafo" in r]

        cursor = 0
        novas: list[tuple[int, str]] = []
        pendentes: list[tuple[int, str]] = []
        for i, a in enumerate(arts):
            velha = a.get("pt_anchor", "")
            if not velha:
                pendentes.append((i, "sem âncora antiga"))
                continue
            p = limpo_atual.find(velha, cursor)
            if p >= 0:
                novas.append((i, velha))
                cursor = p + 1
                continue
            # a própria correção pode ter reescrito o TÍTULO (início da
            # âncora) -- achado real (Eiko art85: "A Forma de Pensar da
            # Medicina" virou "Teoria da Medicina Moderna", o texto velho
            # nunca mais existe em lugar nenhum). Tenta reconstruir a
            # âncora aplicando a correção nela ANTES de procurar às cegas.
            # Janela BEM mais larga que a da busca cega -- é seguro porque
            # o candidato vem de uma correção JÁ APROVADA (não é achado por
            # coincidência de prefixo), então unicidade dentro de uma janela
            # larga ainda discrimina bem. Achado real (Eiko art332): o
            # artigo é longo (>20 mil caracteres) e a janela padrão nunca
            # alcançava a posição real.
            JANELA_CORRECAO = 40000
            fim_janela_corr = min(len(limpo_atual), cursor + JANELA_CORRECAO)
            trecho_corr = limpo_atual[cursor:fim_janela_corr]
            cand = candidata_por_correcao(velha, itens_obra, i)
            if cand is not None and trecho_corr.count(cand) == 1:
                novas.append((i, cand))
                cursor = cursor + trecho_corr.find(cand) + 1
                continue
            # busca cega (sem correção que explique a mudança): janela mais
            # estreita, de propósito -- maior risco de casar com o lugar
            # errado (achado real: 世界救世教奇蹟集, trocou "Tuberculose" por
            # "Varíola" de outro depoimento parecido).
            fim_janela = min(len(limpo_atual), cursor + max(3 * len(velha), JANELA_BUSCA))
            trecho_busca = limpo_atual[cursor:fim_janela]
            candb = regenera_ancora(velha, trecho_busca)
            if candb is None:
                pendentes.append((i, f"não achou na janela local, velha={velha[:60]!r}"))
                continue
            novas.append((i, candb))
            cursor = cursor + trecho_busca.find(candb) + 1

        if pendentes:
            print(f"  {obra[:45]:<47} {len(novas)}/{len(arts)} resolvidos, "
                  f"{len(pendentes)} PENDENTES:")
            for i, motivo in pendentes:
                print(f"      artigo {i}: {motivo}")
            continue

        for i, nova in novas:
            arts[i]["pt_anchor"] = nova
        anc = [a.get("pt_anchor", "") for a in arts]
        try:
            ok = len(anc) <= 1 or len(split_by_anchors(limpo_atual, anc, label=obra)) == len(anc)
        except ValueError as exc:
            ok = False
            print(f"  {obra[:45]:<47} split_by_anchors falhou: {exc}")
        if not ok:
            print(f"  {obra[:45]:<47} âncoras recompostas mas split_by_anchors não fecha -- não gravando")
            continue

        print(f"  {obra[:45]:<47} {len(arts)}/{len(arts)} âncoras OK, split_by_anchors fechou")
        if aplicar:
            shutil.copy(sp, sp.with_suffix(f".json.bak_resegmenta_{carimbo}"))
            sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
            (PT_STAGING / obra).write_text(atual, encoding="utf-8")

    if not aplicar:
        print("\n(ensaio -- nada gravado; rode com --aplicar)")


if __name__ == "__main__":
    main()
