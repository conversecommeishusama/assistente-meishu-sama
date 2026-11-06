#!/usr/bin/env python3
"""Gera visualização HTML do texto COMPLETO do Gokōwa-roku (Suplemento).

Mostra o texto todo em paralelo (JP + PT), falas numeradas, com destaque
para os pontos problemáticos detectados na amostragem semântica.

Uso:
    python3 scripts/gerar_html_contexto_gokowa.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
JP = RAIZ / "textos_japones" / "19480101-御光話録（補）.txt"
PT = RAIZ / "livros_publicacao_pt_revisado" / "19480101 - Gokōwa-roku (Suplemento).txt"
OUT = RAIZ / "reports" / "amostragem_semantica_gokowa"

# Pontos problemáticos conhecidos da amostragem (índices de fala)
PROBLEMATICOS = {
    3: "erro_sentido: sujeito/objeto invertido",
    14: "erro_sentido: vazamento de conteúdo (texto de outra fala)",
    12: "ambiguo: 'antigas mais novas' (paradoxo fiel do original)",
    2: "ambiguo: 'Debune'/'senhor' sem contexto (nome da música e compositor)",
    4: "ambiguo: 'compositor' sem contexto (quem é o compositor)",
    5: "ambiguo: 'sofro com a pobreza' (quem fala)",
}


def extrair_falas(texto: str) -> list[tuple[str, str]]:
    falas = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        m = re.match(r"^(Meishu-Sama|Interlocutor):\s*(.*)", linha)
        if m:
            falas.append((m.group(1), m.group(2)))
    return falas


def esc(html: str) -> str:
    return html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> None:
    falas_jp = extrair_falas(JP.read_text(encoding="utf-8"))
    falas_pt = extrair_falas(PT.read_text(encoding="utf-8"))
    n = min(len(falas_jp), len(falas_pt))
    OUT.mkdir(parents=True, exist_ok=True)

    # Verificar se há resultado da amostragem para enriquecer
    res_path = OUT / "resultado_amostragem.json"
    classificacoes = {}
    if res_path.exists():
        try:
            for r in json.loads(res_path.read_text(encoding="utf-8")):
                if isinstance(r, dict) and "indice" in r:
                    classificacoes[r["indice"]] = r.get("classificacao", "")
        except Exception:
            pass

    html = []
    html.append("""<!DOCTYPE html>
<html lang="pt"><head><meta charset="utf-8">
<title>Gokōwa-roku (Suplemento) — Comparação JP vs PT</title>
<style>
body {{ font-family: sans-serif; margin: 20px; background: #fafafa; }}
h1 {{ font-size: 20px; }}
h2 {{ font-size: 15px; color: #555; margin-top: 30px; border-top: 2px solid #ccc; padding-top: 10px; }}
.fala {{ display: flex; margin: 6px 0; border-left: 3px solid transparent; padding: 4px 8px; }}
.fala:hover {{ background: #eef; }}
.fala.meishu {{ }}
.fala.interlocutor {{ }}
.fala.problema {{ border-left-color: #c33; background: #fff0f0; }}
.fala.ambiguo {{ border-left-color: #c90; background: #fff8e6; }}
.fala.ok {{ border-left-color: #2a2; }}
.idx {{ width: 40px; flex: 0 0 40px; color: #888; font-size: 12px; text-align: right; padding-right: 8px; }}
.jp {{ width: 45%; flex: 0 0 45%; font-size: 13px; padding-right: 12px; }}
.pt {{ width: 45%; flex: 0 0 45%; font-size: 13px; }}
.quem {{ font-weight: bold; font-size: 11px; color: #666; }}
.badge {{ font-size: 10px; padding: 1px 6px; border-radius: 8px; color: #fff; margin-left: 6px; }}
.badge.problema {{ background: #c33; }}
.badge.ambiguo {{ background: #c90; }}
.badge.ok {{ background: #2a2; }}
.nota {{ background:#ffe; padding: 8px; margin: 10px 0; border-left: 4px solid #ca0; font-size: 13px; }}
</style></head><body>
<h1>Gokōwa-roku (Suplemento) — Comparação JP original ↔ PT atual</h1>
<p>Total: {n} falas. Fonte JP: textos_japones/19480101-御光話録（補）.txt · PT: livros_publicacao_pt_revisado/19480101 - Gokōwa-roku (Suplemento).txt</p>
""".format(n=n))

    # Agrupar por "seção" (datas no meio do texto) para orientação
    secao_atual = "Início (Ano Novo — Poemas)"
    html.append(f"<h2>📌 {esc(secao_atual)}</h2>")

    for i in range(n):
        quem, jp = falas_jp[i]
        _, pt = falas_pt[i]

        # detectar nova data/seção no JP
        m_data = re.search(r"(昭和\d+年|Showa \d+|\d+月\d+日|新年)", jp)
        if m_data and i > 0:
            html.append(f"<h2>📌 {esc(m_data.group(1))}</h2>")

        # classificação
        classe = "problema" if i in PROBLEMATICOS and "erro" in PROBLEMATICOS[i] else "ok"
        if i in PROBLEMATICOS:
            if "erro" in PROBLEMATICOS[i]:
                classe = "problema"
            else:
                classe = "ambiguo"
        badge = ""
        if i in PROBLEMATICOS:
            badge = f'<span class="badge {classe}">{esc(PROBLEMATICOS[i])}</span>'
        elif i in classificacoes and classificacoes[i] == "erro_sentido":
            badge = '<span class="badge problema">erro_sentido</span>'
            classe = "problema"
        elif i in classificacoes and classificacoes[i] == "ambiguo":
            badge = '<span class="badge ambiguo">ambíguo</span>'
            classe = "ambiguo"

        quem_cls = "meishu" if quem == "Meishu-Sama" else "interlocutor"
        html.append(f'''<div class="fala {classe}">
<div class="idx">{i}</div>
<div class="jp"><span class="quem">{quem}</span> {esc(jp)}</div>
<div class="pt"><span class="quem">{quem}</span> {esc(pt)} {badge}</div>
</div>''')

    # Legendas
    html.append("""
<div class="nota"><b>Legenda:</b>
  <span class="badge problema">vermelho</span> = erro de sentido na tradução (corrigir)
  <span class="badge ambiguo">laranja</span> = ambíguo/contexto faltante (avaliar nota editorial)
  <span class="badge ok">verde</span> = fiel (ok)
</div>
<div class="nota"><b>Nota:</b> Este é um registro manuscrito de sessões de perguntas — o original é naturalmente truncado (falas curtas, saltos de tópico). A maioria das falas "curtas" é fiel ao original.</div>
</body></html>""")

    arq = OUT / "contexto_completo_gokowa.html"
    arq.write_text("\n".join(html), encoding="utf-8")
    print(f"Gerado: {arq}")
    print(f"Falas: {n} | Problemas destacados: {len(PROBLEMATICOS)}")


if __name__ == "__main__":
    main()
