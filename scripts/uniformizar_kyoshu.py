"""Uniformiza o nome do curso: «Kyoshu», forma do glossário (御教修 -> Kyoshu).

O volume usava as duas grafias, com e sem macron, em capítulos diferentes.
"""
import json
import os
import re
import sys

sys.path.insert(0, '/var/www/goshinsho/scripts')
from revisar import LOG

BASE = '/var/www/goshinsho/docs'
FICHEIROS = [
    'LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md',
    'DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md',
    'DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md',
] + ['volume_novo/' + f for f in sorted(os.listdir(os.path.join(BASE, 'volume_novo'))) if f.endswith('.md')]

registos = []
for rel in FICHEIROS:
    caminho = os.path.join(BASE, rel)
    texto = open(caminho, encoding='utf-8').read()
    blocos = re.split(r'(\n\s*\n)', texto)
    n = 0
    for i, bloco in enumerate(blocos):
        if 'Kyōshu' not in bloco:
            continue
        novo = bloco.replace('Kyōshu', 'Kyoshu')
        if novo != bloco:
            blocos[i] = novo
            registos.append({'capitulo': 'Normalização de grafia — Kyoshu',
                             'arquivo': rel, 'antes': bloco.strip(), 'depois': novo.strip()})
            n += 1
    if n:
        open(caminho, 'w', encoding='utf-8').write(''.join(blocos))
    print(f'{rel}: {n}')

log = json.load(open(LOG, encoding='utf-8')) if os.path.exists(LOG) else []
log.extend(registos)
json.dump(log, open(LOG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(registos), 'registos')
