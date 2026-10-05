#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Junta as Partes I e II do dossiê num volume único para impressão.

Lê os dois .md de docs/, remove o cabeçalho próprio de cada parte e escreve
DOSSIE_DIFUSAO_COMPLETO_20261002.md — que é a fonte do PDF e do .docx de
impressão.

Uso:
    python3 scripts/juntar_dossie_difusao.py
"""
import re
D = '/var/www/goshinsho/docs/'
saida = D + 'DOSSIE_DIFUSAO_COMPLETO_20261002.md'
p1 = open(D + 'LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md', encoding='utf-8').read()
p2 = open(D + 'DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md', encoding='utf-8').read()

# Remove o cabeçalho próprio de cada parte e renumera a Parte II
p2 = re.sub(r'^#\s.*?\n', '', p2, count=1)
p2 = re.sub(r'^\*\*Data:.*?\n(\*\*.*\n)*', '', p2, count=1, flags=re.M)
# desloca as seções 13..23 -> continuam (a Parte I vai até 12)
corpo = (
    "# A difusão na época de Meishu-Sama\n\n"
    "**Edição para impressão — Parte I e Parte II**  \n"
    "**Data:** 2 de outubro de 2026  \n"
    "**Corpus:** acervo textual rattail (`/var/www/rattail/`), exclusivamente.  \n"
    "**Convenção de citação:** `『veículo』nº, data · caminho`\n\n"
    "> **Nota de licenciamento.** Os documentos citados são material de terceiros\n"
    "> protegido por direitos autorais. Este dossiê é nota de pesquisa interna — não é\n"
    "> publicação.\n\n"
    "---\n\n"
    "# PARTE I — unidades, formação e hierarquia\n\n"
)
corpo += p1.split('\n', 1)[1].lstrip('\n')
corpo += "\n\n---\n\n# PARTE II — culto, vida religiosa e administração\n\n"
corpo += p2.lstrip('\n')
open(saida, 'w', encoding='utf-8').write(corpo)
print('gravado:', saida)
print('linhas:', corpo.count(chr(10)))
for m in re.finditer(r'^(#{1,2})\s+(.*)$', corpo, re.M):
    if len(m.group(1)) <= 2:
        print(' ', m.group(1), m.group(2)[:70])
