"""Reinvestiga os itens que ficaram com 'resposta vazia' no cálculo original
(45 de 66 recusados, achado real 2026-08-11: nem sempre é parágrafo grande --
um caso de 60 caracteres também esvaziou, o gargalo é o RACIOCÍNIO do modelo
sobre o conteúdo, não o tamanho do texto -- e como isso varia entre chamadas,
uma nova tentativa às vezes já resolve sozinha, sem precisar de teto maior).

Pra cada item: confere primeiro se "de" ainda existe no artigo atual (senão
está OBSOLETO -- já foi resolvido por outro caminho, marca e não mexe).
Senão, tenta de novo via `calcula_emenda` (teto normal); se ainda vazio,
tenta 1x com teto maior (24000, mesmo valor já testado e aprovado hoje pro
caminho de mesclagem). Aplica só o que passar pela guarda `contido()` real
(não decide sozinho por fora dela).

Uso:
    python3 scripts/retry_vazios.py            # ensaio
    python3 scripts/retry_vazios.py --aplicar
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
from aplica_no_artigo import janelas, SPEC_DIR  # noqa: E402
from repara_implanta_v2 import regenera_ancora  # noqa: E402
from implanta_semantico_v2 import (  # noqa: E402
    paragrafo, contido, emenda_v2, carrega_jp_por_obra, artigo_pt_para_contexto,
    para_efetivo_para_marcador, _extrai_insercao, MARCADOR_REMOCAO, MARCADOR_REMOCAO_DESCRITIVO,
    PT_FONTE, PT_STAGING,
)
import goshinsho.services.agentic_search as ag  # noqa: E402

CHECKPOINT = RAIZ / "reports/varredura_padronizacao/CHECKPOINT_IMPLANTA_V2.json"


def tenta_de_novo(jp, artigo_pt, par, de, para, tokens):
    system = None
    from implanta_semantico_v2 import SYSTEM_SUBSTITUI, SYSTEM_REMOVE, SYSTEM_INSERE, MAX_JP
    remover = bool(MARCADOR_REMOCAO.match(para.strip()) or MARCADOR_REMOCAO_DESCRITIVO.match(para.strip()))
    insercao = None if remover else _extrai_insercao(para)
    if remover:
        system = SYSTEM_REMOVE
        guia = MARCADOR_REMOCAO.match(para.strip())
        explicacao = "" if guia else para.strip()
        pedido = (f"=== JAPONÊS DO ARTIGO ===\n{jp[:MAX_JP]}\n\n"
                  f"=== ARTIGO INTEIRO EM PORTUGUÊS (contexto) ===\n{artigo_pt_para_contexto(artigo_pt)}\n\n"
                  f"=== PARÁGRAFO A EDITAR ===\n{par}\n\n"
                  f"=== TRECHO A REMOVER ===\n{de}\n\n"
                  + (f"=== ORIENTAÇÃO DE QUEM APROVOU A REMOÇÃO ===\n{explicacao}\n\n" if explicacao else "")
                  + "Devolva o parágrafo com esse trecho removido.")
    elif insercao:
        posicao, frase = insercao
        system = SYSTEM_INSERE
        pedido = (f"=== JAPONÊS DO ARTIGO ===\n{jp[:MAX_JP]}\n\n"
                  f"=== ARTIGO INTEIRO EM PORTUGUÊS (contexto) ===\n{artigo_pt_para_contexto(artigo_pt)}\n\n"
                  f"=== PARÁGRAFO A EDITAR ===\n{par}\n\n"
                  f"=== TRECHO DE REFERÊNCIA (permanece no parágrafo) ===\n{de}\n\n"
                  f"=== FRASE A INSERIR ({posicao} do trecho de referência) ===\n{frase}\n\n"
                  f"Devolva o parágrafo com a frase inserida {posicao} do trecho de referência, "
                  f"depois de confirmar contra o japonês que ela realmente falta.")
    else:
        para_eff = para_efetivo_para_marcador(para) or para
        system = SYSTEM_SUBSTITUI
        pedido = (f"=== JAPONÊS DO ARTIGO ===\n{jp[:MAX_JP]}\n\n"
                  f"=== ARTIGO INTEIRO EM PORTUGUÊS (contexto) ===\n{artigo_pt_para_contexto(artigo_pt)}\n\n"
                  f"=== PARÁGRAFO A EDITAR ===\n{par}\n\n"
                  f"=== CORREÇÃO APROVADA ===\n"
                  f"o trecho: {de}\n"
                  f"deve virar: {para_eff}\n\n"
                  f"Devolva o parágrafo corrigido.")
    r = ag._client().chat.completions.create(
        model="deepseek-v4-flash", max_tokens=tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": pedido}])
    return (r.choices[0].message.content or "").strip()


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    ck = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    vazios = [r for r in ck.values() if r.get("recusa", "").startswith("resposta vazia")]
    print(f"{len(vazios)} itens 'resposta vazia' a investigar\n")

    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    obsoletos, resolvidos, ainda_vazio, outra_recusa = [], [], [], []

    for it in vazios:
        obra, artigo, de, para = it["obra"], it["artigo"], it["de"], it["para"]
        f = PT_FONTE / obra
        if not f.exists():
            outra_recusa.append((it, "obra ausente"))
            continue
        texto = f.read_text(encoding="utf-8")
        jan = janelas(obra, texto)
        if jan is None or artigo >= len(jan):
            outra_recusa.append((it, "janela indisponível"))
            continue
        ini, fim = jan[artigo]
        lim = paragrafo(texto, ini, fim, de)
        if lim is None:
            obsoletos.append(it)
            print(f"  OBSOLETO  {obra[:35]:<37} art{artigo:<4} de já não existe mais no artigo")
            continue
        par = texto[lim[0]:lim[1]]
        if par.count(de) != 1:
            outra_recusa.append((it, f"{par.count(de)} ocorrências no parágrafo"))
            continue
        artigo_pt = texto[ini:fim]
        jps = carrega_jp_por_obra(obra)
        jp = jps[artigo] if jps and artigo < len(jps) else ""

        if MARCADOR_REMOCAO.match(para.strip()) or MARCADOR_REMOCAO_DESCRITIVO.match(para.strip()):
            para_delta = ""
        else:
            ins = _extrai_insercao(para)
            para_delta = (de + " " + ins[1]) if ins else (para_efetivo_para_marcador(para) or para)

        novo = None
        motivo_final = None
        for tokens in (8192, 24000):
            try:
                candidato = tenta_de_novo(jp, artigo_pt, par, de, para, tokens)
            except Exception as exc:
                motivo_final = f"erro de API: {exc!r}"[:100]
                break
            # achado real: pular contido() quando candidato vem vazio
            # escondia o caso legítimo (remover o parágrafo INTEIRO produz
            # resultado vazio de verdade) atrás do mesmo rótulo "ainda
            # vazio" dos casos genuinamente falhos -- contido() agora sabe
            # diferenciar (só aceita vazio quando trecho == parágrafo
            # inteiro), então sempre chamar, nunca decidir antes dela.
            motivo = contido(par, candidato, de, para_delta)
            if motivo is None:
                novo = candidato
                motivo_final = None
                break
            motivo_final = motivo
            # só vale insistir com teto maior quando a causa é genuinamente
            # falta de espaço de raciocínio ("resposta vazia") -- pra
            # qualquer outro motivo (mudou fora do vão, não mudou nada,
            # cresceu demais), o problema não é de token, tentar de novo
            # com mais teto não muda o resultado.
            if motivo != "resposta vazia":
                break
        if motivo_final is not None:
            outra_recusa.append((it, motivo_final))
        if novo is None:
            if not any(it is x[0] for x in outra_recusa):
                ainda_vazio.append(it)
                print(f"  AINDA VAZIO  {obra[:35]:<37} art{artigo}")
            continue

        resolvidos.append({**it, "novo_paragrafo": novo, "lim": lim})
        print(f"  RESOLVIDO  {obra[:35]:<37} art{artigo:<4} de={de[:40]!r}")

    print(f"\n{len(obsoletos)} obsoletos (de sumiu, já resolvido de outra forma)")
    print(f"{len(resolvidos)} resolvidos por retentativa")
    print(f"{len(ainda_vazio)} ainda vazios depois de 2 tentativas")
    print(f"{len(outra_recusa)} recusados por outro motivo na retentativa")
    for it, motivo in outra_recusa:
        print(f"    {it['obra'][:30]} art{it['artigo']}: {motivo}")

    if not aplicar or not resolvidos:
        print("\n(ensaio -- nada gravado; rode com --aplicar)" if not aplicar else "")
        return

    por_obra: dict[str, list[dict]] = {}
    for r in resolvidos:
        por_obra.setdefault(r["obra"], []).append(r)

    for obra, itens in por_obra.items():
        f = PT_FONTE / obra
        texto = f.read_text(encoding="utf-8")
        for r in sorted(itens, key=lambda x: x["lim"][0], reverse=True):
            gi, gf = r["lim"]
            if texto[gi:gf].count(r["de"]) != 1:
                print(f"  *** {obra[:35]} art{r['artigo']}: posição mudou, pulando")
                continue
            texto = texto[:gi] + r["novo_paragrafo"] + texto[gf:]

        sp = SPEC_DIR / f"{obra}.json"
        spec = json.loads(sp.read_text(encoding="utf-8"))
        limpo = clean_body(texto)
        # achado real: uma remoção pode apagar o trecho que É a própria
        # âncora do artigo (a "de" era o título/byline sozinho) -- sem
        # regenerar, split_by_anchors levanta ValueError (não devolve
        # False) e derrubava o script inteiro, perdendo o resto do lote.
        for a in spec["articles"]:
            velha = a.get("pt_anchor", "")
            if velha and velha not in limpo:
                cand = regenera_ancora(velha, limpo)
                if cand is not None and limpo.count(cand) == 1:
                    a["pt_anchor"] = cand
        anc = [a.get("pt_anchor", "") for a in spec["articles"]]
        try:
            ok = len(anc) <= 1 or len(split_by_anchors(limpo, anc, label=obra)) == len(anc)
        except ValueError as exc:
            ok = False
            print(f"  *** {obra[:35]}: {exc}")
        if not ok:
            print(f"  *** {obra[:35]}: split_by_anchors quebrou -- NÃO gravando")
            continue
        shutil.copy(f, f.with_suffix(f".txt.bak_retryvazios_{carimbo}"))
        f.write_text(texto, encoding="utf-8")
        (PT_STAGING / obra).write_text(texto, encoding="utf-8")
        shutil.copy(sp, sp.with_suffix(f".json.bak_retryvazios_{carimbo}"))
        sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  gravado: {obra[:35]} ({len(itens)} itens)")


if __name__ == "__main__":
    main()
