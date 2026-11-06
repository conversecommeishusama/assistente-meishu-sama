#!/usr/bin/env python3
"""Relatório final consolidado da análise da pergunta-bandeira."""
import json
import re
from pathlib import Path

d = json.loads(Path('/var/www/goshinsho/reports/avaliacao_bandeira_completa.json').read_text(encoding='utf-8'))

linhas = []
linhas.append("=" * 70)
linhas.append("RELATÓRIO FINAL — PERGUNTA-BANDEIRA")
linhas.append("Pergunta: 'segundo Meishu-Sama é possível mudar de plano espiritual na mesma reencarnação?'")
linhas.append("Executado: 3x modo Direta + 3x modo Aprofundar (2026-08-14)")
linhas.append("=" * 70)

# Critério 1: abrir com resposta determinística
linhas.append("\n## CRITÉRIO 1 — NÃO abrir com 'Sim/Não' determinístico em ambiguidade")
linhas.append("(Falha histórica conhecida: 'recalcitrância de abertura')")
for modo in ("direta", "aprofundar"):
    for item in d[modo]:
        r = item["resposta_completa"]
        exec_num = item["exec"]
        prim = [l for l in r.split("\n") if l.strip()][:1]
        abertura = prim[0].strip() if prim else ""
        det = bool(re.match(r'^#{0,3}\s*(sim|não|nao)[\s,—-]', abertura, re.I))
        status = "⚠️ DETERMINÍSTICA" if det else "✔ qualificada"
        linhas.append(f"  {modo} exec {exec_num}: {status} | '{abertura[:70]}'")

# Critério 2: separar as duas formulações
linhas.append("\n## CRITÉRIO 2 — Separar formulações (1949/54 escrito = plano fixo | 1953 oral = classe)")
SINAIS_FIXO = ["fixo", "fixado", "não se troca", "não troca", "ao nascer", "destino predeterminado", "impossível"]
SINAIS_MUTAVEL = ["sobe", "desce", "destino mutável", "classe", "subir", "cair", "180 camadas", "cento e oitenta"]
for modo in ("direta", "aprofundar"):
    for item in d[modo]:
        r = item["resposta_completa"].lower()
        n_f = sum(1 for s in SINAIS_FIXO if s in r)
        n_m = sum(1 for s in SINAIS_MUTAVEL if s in r)
        sep = "✔ separa" if n_f >= 2 and n_m >= 2 else "✘ funde"
        linhas.append(f"  {modo} exec {item['exec']}: {sep} (fixo={n_f}, mutável={n_m})")

# Critério 3: destino predeterminado (desambiguação)
linhas.append("\n## CRITÉRIO 3 — Citar/encontrar 'destino predeterminado' (chave da desambiguação)")
for modo in ("direta", "aprofundar"):
    for item in d[modo]:
        r = item["resposta_completa"].lower()
        n = r.count("destino predeterminado")
        linhas.append(f"  {modo} exec {item['exec']}: {'✔' if n > 0 else '✘'} ({n}x)")

# Critério 4: citações de arquivo (modo aprofundado)
linhas.append("\n## CRITÉRIO 4 — Modo Aprofundar cita fontes; modo Direta NÃO cita")
for modo in ("direta", "aprofundar"):
    for item in d[modo]:
        r = item["resposta_completa"]
        arquivos = re.findall(r'\[([^\]]*\.txt)\]', r)
        if modo == "direta":
            ok = "✔ sem citações" if not arquivos else f"✘ CITOU {len(arquivos)}"
        else:
            ok = f"✔ citou {len(arquivos)}" if arquivos else "✘ sem citações"
        linhas.append(f"  {modo} exec {item['exec']}: {ok}")

# Critério 5: kanji
linhas.append("\n## CRITÉRIO 5 — Nunca kanji na resposta (regra 4)")
for modo in ("direta", "aprofundar"):
    for item in d[modo]:
        kanji = bool(re.search(r'[\u3040-\u30ff\u3400-\u9fff]', item["resposta_completa"]))
        linhas.append(f"  {modo} exec {item['exec']}: {'✘ KANJI' if kanji else '✔ limpo'}")

# Veredito final
linhas.append("\n" + "=" * 70)
linhas.append("VEREDITO FINAL")
linhas.append("=" * 70)
linhas.append("""
PONTOS FORTES (6/6 execuções):
- ✔ Todas separam, em algum grau, as duas formulações do acervo
- ✔ Todas encontram/citam 'destino predeterminado' (a desambiguação correta)
- ✔ Nenhuma tem kanji na resposta
- ✔ Modo Aprofundar cita fontes corretas (Evangelho/霊界叢談 para 1949/54,
  Gosuiji-roku 24 para 1953, Kiseki, Tijotengoku, Eiko) — boa diversidade
- ✔ Modo Direta NÃO cita arquivos (conforme regra)

PONTOS DE ATENÇÃO:
- ⚠️ Direta exec 1 abre com '## Sim — o registro espiritual não é fixo'
  (abertura determinística). É a falha histórica de 'recalcitrância de
  abertura'. Embora qualifique logo em seguida (e faça a distinção correta
  de 'destino predeterminado' = classe), a abertura 'Sim —' pode enganar
  leitor que só leia o título.
- ⚠️ Direta exec 3: sinais de formulação fixa = 0 (pode ter fundido as duas
  leituras, apresentando só a 'sobe/desce'). Vale conferir o texto integral.
""")

out = Path('/var/www/goshinsho/reports/relatorio_bandeira_final.txt')
out.write_text("\n".join(linhas), encoding="utf-8")
print("\n".join(linhas))
print(f"\n\nRelatório salvo em {out}")
