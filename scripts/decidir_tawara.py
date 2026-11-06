#!/usr/bin/env python3
"""Decisão 俵 (saca/saco) - conferência JP ocorrência a ocorrência (Opção B).

Para cada ocorrência de 'saco'/'saca' no PT, o modelo lê o contexto PT + JP do
artigo correspondente e decide:
- TAWARA: a palavra corresponde a 俵 (medida de arroz) -> deve ser "saca (hyō)"
- SACO_LITERAL: é saco literal (embalagem) -> manter "saco"
- DUVIDA: não consegue decidir

NÃO edita nada. Gera relatório para aplicação posterior.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from harness_deepseek_corpus import _client, _jp_janelas

PT = RAIZ / "livros_publicacao_pt_revisado"
JP = RAIZ / "reports/livros_trabalho/jp"

MODELO = "deepseek-v4-flash"


def decidir(caso: dict) -> dict:
    obra = caso["obra"]
    palavra = caso["palavra"]
    ctx_pt = caso["ctx_pt"]
    art = caso.get("artigo")

    # JP do artigo
    ctx_jp = "(sem JP)"
    janelas = _jp_janelas(obra)
    if janelas and art is not None and 0 <= art < len(janelas):
        s, e, t = janelas[art]
        ctx_jp = f"[artigo {art}: {t}]\n" + (JP / obra).read_text(encoding="utf-8")[s:e][:1500]

    sys_msg = (
        "Você é um revisor de tradução do corpus Goshinsho (textos de Meishu-Sama), "
        "especialista em japonês e português.\n\n"
        "Você receberá: (a) o CONTEXTO PT onde aparece a palavra 'saco'/'saca', e "
        "(b) o CONTEXTO JP do mesmo artigo.\n\n"
        "DECIDA: a palavra 'saco(s)'/'saca(s)' no PT corresponde a 俵 (tawara = "
        "medida tradicional de arroz/colheita, ~60kg)? Ou é 'saco' literal (embalagem "
        "de estopa/saco de algo)?\n\n"
        "Responda APENAS JSON:\n"
        "{\"decisao\": \"TAWARA\"|\"SACO_LITERAL\"|\"DUVIDA\", "
        "\"justificativa\": \"...\"}\n\n"
        "- TAWARA: se o JP do artigo usa 俵 (ou unidade de medida de colheita) "
        "para a mesma ideia -> tradução correta é 'saca (hyō)'.\n"
        "- SACO_LITERAL: se é embalagem/saco de estopa/carregar em saco.\n"
        "- DUVIDA: se não conseguir confirmar pelo JP.\n"
        "Responda APENAS o JSON."
    )
    user_msg = (
        f"OCORRÊNCIA: '{palavra}' na obra {obra} (artigo {art}).\n\n"
        f"=== CONTEXTO PT ===\n{ctx_pt}\n\n"
        f"=== CONTEXTO JP (artigo) ===\n{ctx_jp}\n\n"
        "Decida e responda APENAS o JSON."
    )

    final = ""
    for tentativa in range(3):
        reforco = ""
        if tentativa == 1:
            reforco = "\n\nIMPORTANTE: responda APENAS o JSON puro, sem markdown."
        elif tentativa == 2:
            reforco = '\n\nATENÇÃO: resposta inválida. Responda exatamente: {"decisao": "TAWARA" ou "SACO_LITERAL" ou "DUVIDA", "justificativa": "..."}'
        resp = _client().chat.completions.create(
            model=MODELO, max_tokens=1500,
            messages=[{"role": "system", "content": sys_msg},
                      {"role": "user", "content": user_msg + reforco}],
        )
        final = resp.choices[0].message.content or ""
        # extrair JSON balanceado
        m = None
        i = final.find("{")
        while i != -1:
            prof = 0; em_str = False; esc = False
            for j in range(i, len(final)):
                ch = final[j]
                if em_str:
                    if esc: esc = False
                    elif ch == "\\": esc = True
                    elif ch == '"': em_str = False
                    continue
                if ch == '"': em_str = True
                elif ch == "{": prof += 1
                elif ch == "}":
                    prof -= 1
                    if prof == 0:
                        cand = final[i:j+1]
                        try:
                            json.loads(cand)
                            m = cand; break
                        except Exception:
                            break
            if m: break
            i = final.find("{", i+1)
        if m:
            try:
                r = json.loads(m)
                if r.get("decisao") in ("TAWARA", "SACO_LITERAL", "DUVIDA"):
                    return r
            except Exception:
                pass
    return {"decisao": "DUVIDA", "justificativa": "sem JSON após 3 tentativas"}


def main() -> None:
    lote_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    casos = json.loads(lote_path.read_text(encoding="utf-8"))
    print(f"tawara: {len(casos)} casos")

    resultados = []
    for i, caso in enumerate(casos, 1):
        r = decidir(caso)
        resultados.append({**caso, "decisao": r["decisao"], "justificativa": r["justificativa"]})
        if i % 10 == 0:
            # salvar parcial
            out_path.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  {i}/{len(casos)} processados")

    out_path.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    from collections import Counter
    print(f"concluído: {dict(Counter(r['decisao'] for r in resultados))}")


if __name__ == "__main__":
    main()
