#!/usr/bin/env python3
"""Análise das respostas completas da pergunta-bandeira contra critérios históricos.

Critérios do HISTORICO.md:
1. Separar as DUAS formulações: (a) 1949/54 escrito = plano FIXO ao nascer,
   não se troca na mesma encarnação; (b) 1953 oral = destino é classe,
   alma sobe/desce.
2. Encontrar/citar o trecho de desambiguação ("destino predeterminado").
3. Não abrir com resposta determinística ("Sim —"/"Não —") em ambiguidade.
4. Modo Aprofundar: citar fontes corretas ([arquivo]).
5. Não ser recalcitrante (rodadas excessivas sem resultado).
"""
import json
import re
from pathlib import Path

d = json.loads(Path('/var/www/goshinsho/reports/avaliacao_bandeira_completa.json').read_text(encoding='utf-8'))

# Sinais de cada formulação no texto
SINAIS_FIXO = ["fixo", "fixado", "não se troca", "não troca", "ao nascer", "destino predeterminado", "não pode mudar de plano", "impossível"]
SINAIS_MUTAVEL = ["sobe", "desce", "destino mutável", "classe", "subir", "cair", "mudar de classe", "180 camadas", "cento e oitenta"]
SINAIS_RECONCILIA = ["depende", "distinção", "diferente", "não é simples", "matizada", "dois", "duas leituras", "separadamente"]

# Fontes esperadas (nomes de arquivo no modo aprofundado)
FONTES_1953 = ["御垂示録24", "Gosuiji-roku nº 24"]
FONTES_1949_54 = ["霊界叢談", "天国の福音書", "Caminho para a Luz", "Evangelho do Reino"]

print("=" * 70)
print("ANÁLISE COMPLETA — PERGUNTA-BANDEIRA (respostas integrais)")
print("=" * 70)

for modo in ("direta", "aprofundar"):
    print(f"\n{'='*70}\nMODO {modo.upper()}\n{'='*70}")
    for item in d[modo]:
        r = item["resposta_completa"]
        exec_num = item["exec"]
        print(f"\n--- Exec {exec_num} ({len(r)} chars) ---")

        # 1. Separou as duas formulações?
        n_fixo = sum(1 for s in SINAIS_FIXO if s.lower() in r.lower())
        n_mut = sum(1 for s in SINAIS_MUTAVEL if s.lower() in r.lower())
        n_rec = sum(1 for s in SINAIS_RECONCILIA if s.lower() in r.lower())
        print(f"  [1] Separa formulações: sinais fixo={n_fixo}/7 | sinais mutável={n_mut}/8 | reconciliação={n_rec}/7")
        print(f"      {'✔ SEPARA' if n_fixo >= 2 and n_mut >= 2 else '✘ possivelmente funde'}")

        # 2. Abre com resposta determinística?
        abertura = r[:60].strip()
        det = bool(re.match(r'^(sim|não|nao)\b', abertura, re.I))
        print(f"  [2] Abertura determinística ('Sim/Não'): {'⚠️ SIM — ' + abertura[:50] if det else '✔ não (abertura qualificada): ' + abertura[:50]}")

        # 3. Cita [arquivo]?
        arquivos = re.findall(r'\[([^\]]*\.txt)\]', r)
        print(f"  [3] Citações [arquivo.txt]: {len(arquivos)}")
        for a in arquivos[:4]:
            print(f"      - {a}")

        # 4. Fontes específicas (só aprofundar)
        if modo == "aprofundar":
            tem_1953 = any(f.lower() in r.lower() for f in FONTES_1953)
            tem_1949 = any(f.lower() in r.lower() for f in FONTES_1949_54)
            print(f"  [4] Fontes: 1953 (Gosuiji 24)={'✔' if tem_1953 else '✘'} | 1949/54 (霊界叢談/福音書)={'✔' if tem_1949 else '✘'}")

        # 5. Kanji (regra 4 - proibido)
        kanji = bool(re.search(r'[\u3040-\u30ff\u3400-\u9fff]', r))
        print(f"  [5] Kanji no texto: {'⚠️ SIM' if kanji else '✔ não'}")

        # tokens
        print(f"  [tokens] {item['tokens_entrada']}/{item['tokens_saida']} | ferramentas: {item['ferramentas']}")

print("\n" + "=" * 70)
print("RESUMO DOS CRITÉRIOS HISTÓRICOS (HISTORICO.md)")
print("=" * 70)
print("""
1. A resposta CORRETA separa: (a) escrito 1949/54 = plano FIXO ao nascer,
   impossível sair; (b) oral 1953 = destino é classe, alma sobe/desce.
2. Deve citar/encontrar 'destino predeterminado' (desambiguação).
3. NUNCA abrir com 'Sim —'/'Não —' em pergunta ambígua (recalcitrância de
   abertura foi falha histórica).
4. Modo Aprofundar: citar fontes corretas ([御垂示録24] para 1953, etc.).
5. Regra 4: nunca kanji na resposta.
""")
