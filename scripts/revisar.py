#!/usr/bin/env python3
"""Registra alterações de revisão num log, para gerar o comparativo final.

Uso (a partir de um script de revisão):
    from revisar import aplicar
    aplicar('Capítulo 3', [
        ('docs/volume_novo/xx.md', 'antes', 'depois'),
    ])
"""
import json
import os
import sys

LOG = os.environ.get('REVISAO_LOG',
                     '/var/www/goshinsho/docs/revisao_20261104_log.json')
RAIZ = os.environ.get('GOSHINSHO_RAIZ', '/var/www/goshinsho/')


def carregar():
    if os.path.exists(LOG):
        return json.load(open(LOG, encoding='utf-8'))
    return []


def aplicar(capitulo, pares):
    """pares = [(caminho_relativo, texto_antigo, texto_novo)]"""
    log = carregar()
    aplicados, falhas = 0, []
    for caminho, velho, novo in pares:
        p = os.path.join(RAIZ, caminho)
        t = open(p, encoding='utf-8').read()
        if velho not in t:
            falhas.append((caminho, velho[:80]))
            continue
        t = t.replace(velho, novo, 1)
        open(p, 'w', encoding='utf-8').write(t)
        log.append({'capitulo': capitulo, 'arquivo': caminho,
                    'antes': velho, 'depois': novo})
        aplicados += 1
    json.dump(log, open(LOG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('%s: %d aplicadas, %d falhas' % (capitulo, aplicados, len(falhas)))
    for c, v in falhas:
        print('   FALHOU em %s: %s' % (c, v.replace('\n', ' ')[:90]))
    return len(falhas)
