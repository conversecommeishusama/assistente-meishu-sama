#!/usr/bin/env python3
"""Uniformiza «acervo»/«corpus» -> «documentação», com concordância.

«Acervo» e «corpus» são masculinos; «documentação» é feminino. A troca cega
deixa «o documentação», «do acervo» -> «do documentação», etc. Aqui trata-se
artigo, contração e alguns adjectivos.
"""
import glob
import re
import sys

ALVOS = [
    '/var/www/goshinsho/docs/LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md',
    '/var/www/goshinsho/docs/DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md',
    '/var/www/goshinsho/docs/DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md',
] + sorted(glob.glob('/var/www/goshinsho/docs/volume_novo/*.md'))

# antes do substantivo: contrações e artigos
PRE = [
    (r'\bno acervo\b', 'na documentação'),
    (r'\bNo acervo\b', 'Na documentação'),
    (r'\bdo acervo\b', 'da documentação'),
    (r'\bDo acervo\b', 'Da documentação'),
    (r'\bao acervo\b', 'à documentação'),
    (r'\bAo acervo\b', 'À documentação'),
    (r'\bo acervo\b', 'a documentação'),
    (r'\bO acervo\b', 'A documentação'),
    (r'\bum acervo\b', 'uma documentação'),
    (r'\bUm acervo\b', 'Uma documentação'),
    (r'\beste acervo\b', 'esta documentação'),
    (r'\bEste acervo\b', 'Esta documentação'),
    (r'\besse acervo\b', 'essa documentação'),
    (r'\bEsse acervo\b', 'Essa documentação'),
    (r'\btodo o acervo\b', 'toda a documentação'),
    (r'\bTodo o acervo\b', 'Toda a documentação'),
    (r'\bno corpus\b', 'na documentação'),
    (r'\bdo corpus\b', 'da documentação'),
    (r'\bo corpus\b', 'a documentação'),
    (r'\bO corpus\b', 'A documentação'),
    (r'\bum corpus\b', 'uma documentação'),
    (r'\beste corpus\b', 'esta documentação'),
    (r'\besse corpus\b', 'essa documentação'),
]

# concordâncias soltas que a troca estraga
POS = [
    (r'\bo documentação\b', 'a documentação'),
    (r'\bno documentação\b', 'na documentação'),
    (r'\bdo documentação\b', 'da documentação'),
    (r'\bao documentação\b', 'à documentação'),
    (r'\bum documentação\b', 'uma documentação'),
    (r'\beste documentação\b', 'esta documentação'),
    (r'\besse documentação\b', 'essa documentação'),
    (r'\bpel[oa] documentação\b', 'pela documentação'),
    (r'\btodo a documentação\b', 'toda a documentação'),
    (r'\bdocumentação consultado\b', 'documentação consultada'),
    (r'\bdocumentação é composto\b', 'documentação é composta'),
    (r'\bdocumentação não documenta\b', 'documentação não cobre'),
    (r'\bdocumentação documenta\b', 'documentação registra'),
    (r'\bdocumentação é preciso\b', 'documentação é precisa'),
    (r'\bdocumentação conserva\b', 'documentação conserva'),
]

if __name__ == '__main__':
    escrever = '--dry' not in sys.argv
    for a in ALVOS:
        if a.split('/')[-1].startswith(('DOSSIE_DIFUSAO_COMPLETO', 'DOSSIE_DIFUSAO_MEISHU',
                                        'DOSSIE_DIFUSAO_2026102', 'RELATORIO_REVISAO')):
            continue
        t = open(a, encoding='utf-8').read()
        o = t
        for pat, novo in PRE + POS:
            t = re.sub(pat, novo, t)
        # resto: substantivo solto
        t = t.replace('acervo', 'documentação').replace('Acervo', 'Documentação')
        t = t.replace('corpus', 'documentação').replace('Corpus', 'Documentação')
        # a troca solta voltou a estragar as concordâncias acima: repetir
        for pat, novo in POS:
            t = re.sub(pat, novo, t)
        t = re.sub(r'\ba documentação da época\b', 'a documentação da época', t)
        if t != o:
            if escrever:
                open(a, 'w', encoding='utf-8').write(t)
            print('alterado:', a.split('/')[-1])
