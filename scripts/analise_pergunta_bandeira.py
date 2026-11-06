#!/usr/bin/env python3
"""Análise qualitativa das respostas da pergunta-bandeira (6 execuções já coletadas)."""
import re
import json
from pathlib import Path

# Respostas coletadas nas execuções anteriores (primeiros 700 chars capturados)
# Direta: 2555, 2484, 2782 chars | Aprofundar: 5075, 3898, 3877 chars
respostas = {
    "direta": [
        "A pergunta não tem uma resposta única e categórica no acervo: os textos sustentam duas leituras diferentes, e a diferença entre elas é exatamente o ponto que você pergunta. ### Ensinamento escrito (base doutrinária central) Nos escritos sobre o mundo espiritual, Meishu-Sama ensina que ele se divide em três grandes planos (Paraíso, Mundo Intermediário e Inferno), subdivididos em cento e oitenta camadas. Cada pessoa tem uma 'alma oculta' cujo registro se situa numa dessas camadas, ligada ao ser vivo por um elo espiritual. Sobre a mudança dessa posição, ele distingue destino predeterminado e des...",
        "A resposta a essa pergunta é matizada: depende do que se entende por 'plano espiritual', e o acervo sustenta leituras em níveis diferentes da hierarquia espiritual. Vejo dois enquadramentos distintos nos ensinamentos. ### A alma sobe e desce ao longo da vida Segundo Meishu-Sama, a posição da alma não é fixa: ela está constantemente subindo e descendo, pois quanto mais leve (menos pecados e impurezas) mais sobe, e quanto mais pesada mais desce — conforme as ações boas ou más. Isso não ocorre apenas após a morte: a posição da alma oculta nas camadas do mundo espiritual se reflete na vida presen...",
        "Não há nos ensinamentos uma resposta única e limpa: a formulação mais explícita diz que o plano espiritual é fixado ao nascer e não se troca dentro da mesma encarnação, mas outro texto fala em subir ao Paraíso ou cair ao Inferno conforme as ações, sem precisar quando isso ocorre. O que todos os trechos afirmam em comum é que a posição espiritual sobe ou desce (é um 'destino mutável'). ### O plano é fixado ao nascer Na exposição mais direta e deliberada (ensinamento escrito de 1954, já presente em obra de 1949), Meishu-Sama ensina que o mundo espiritual tem três grandes planos — Paraíso, Mundo..."
    ],
    "aprofundar": [
        "Com base nos trechos encontrados no acervo, a resposta não é um 'sim' ou 'não' simples: o acervo contém formulações que apontam em duas direções sobre se a posição espiritual pode mudar de plano durante a mesma vida. Apresento os enquadramentos conforme as próprias fontes. ### 1. O registro do espírito não é fixo: sobe e desce conforme as ações Meishu-Sama ensina que a posição do espírito nas cento e oitenta camadas do mundo espiritual funciona como um 'registro' que não é estático, e que essa posição se reflete já na vida material — não apenas após a morte. As pessoas comuns estariam no plano médio, podendo subir ou descer conforme suas ações. > 'Esse registro, porém, não é fixo: move-se...",
        "Pela doutrina de Meishu-Sama, a resposta é **sim, com uma ressalva importante**: durante a mesma vida, o espírito de uma pessoa pode subir ou descer entre os planos do mundo espiritual, mas há um limite de outra natureza (o 'destino predeterminado') que não deve ser confundido com a localização Paraíso/Inferno. ### O destino mutável: subir e descer durante a vida Segundo Meishu-Sama, a posição do espírito das pessoas comuns não é fixa. O registro espiritual de cada um 'move-se constantemente para cima e para baixo', acompanhado pelo chamado destino mutável — e é por isso que as boas ações fazem subir e as más fazem descer. > 'Esse registro, porém, não é fixo: move-se constantemente para c...",
        "A resposta a essa pergunta não é um 'sim' ou 'não' simples: o acervo sustenta, ao mesmo tempo, a ideia de que a alma oscila constantemente de posição no mundo espiritual e a ideia de que há um limite fixo -- o 'destino predeterminado' -- que aprisiona a pessoa a um dos três grandes planos durante a vida. Os dois enquadramentos precisam ser apresentados separadamente. ### A posição da alma não é fixa: ela sobe e desce Meishu-Sama ensina que o espírito de cada pessoa tem um 'registro' em algum ponto entre as 180 camadas do mundo espiritual, e que esse registro não é fixo: move-se constantemente para cima e para baixo, conforme as ações boas ou más tornam a alma mais leve ou mais pesada. > '..."
    ]
}

relatorio = []
relatorio.append("=" * 70)
relatorio.append("ANÁLISE QUALITATIVA — PERGUNTA-BANDEIRA (3x Direta + 3x Aprofundar)")
relatorio.append("Pergunta: 'segundo Meishu-Sama é possível mudar de plano espiritual na mesma reencarnação?'")
relatorio.append("=" * 70)

for modo in ["direta", "aprofundar"]:
    relatorio.append(f"\n### MODO {modo.upper()}")
    for i, resp in enumerate(respostas[modo], 1):
        tem_kanji = bool(re.search(r'[\u3040-\u30ff\u3400-\u9fff]', resp))
        nomes_arquivo = re.findall(r'\[([^\]]*\.txt)\]', resp)
        cita_literal = bool(re.search(r'"[^"]{40,}"', resp))
        tem_titulos = resp.count('### ')
        palavras = len(resp.split())
        relatorio.append(f"\n--- Exec {i} ---")
        relatorio.append(f"  chars: {len(resp)} | palavras: {palavras} | subtítulos (###): {tem_titulos}")
        relatorio.append(f"  kanji no texto: {tem_kanji} | citações [arquivo.txt]: {len(nomes_arquivo)}")
        relatorio.append(f"  citação literal em aspas (>40 chars): {cita_literal}")
        # Palavras-chave doutrinárias
        termos = ["plano espiritual","mudar","mesma","reencarnação","destino","subir","descer","camadas","Paraíso","Inferno"]
        encontrados = [t for t in termos if t.lower() in resp.lower()]
        relatorio.append(f"  termos doutrinários presentes: {len(encontrados)}/{len(termos)}")
        relatorio.append(f"  Abertura: {resp[:130]}")

relatorio.append("\n" + "=" * 70)
relatorio.append("PADRÕES ESTABELECIDOS (do SYSTEM_PROMPT)")
relatorio.append("=" * 70)
relatorio.append("MODO DIRETA:")
relatorio.append("  - Proibido mencionar nome de arquivo (nem [..], nem lista Fontes)")
relatorio.append("  - Sem citação literal entre aspas")
relatorio.append("  - Explicação por tema com subtítulos ###")
relatorio.append("MODO APROFUNDAR (com citações):")
relatorio.append("  - Citações literais com [arquivo.txt] permitidas e esperadas")
relatorio.append("  - Dividido por temas com subtítulos ###")

out = Path("reports/analise_pergunta_bandeira.txt")
out.write_text("\n".join(relatorio), encoding="utf-8")
print("\n".join(relatorio))
print(f"\n\nRelatório salvo em {out}")
