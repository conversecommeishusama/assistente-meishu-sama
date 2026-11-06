"""Normaliza a grafia do nome da Imagem para a forma do glossário.

O `glossario_traducao.json` fixa 光明如来 -> «Komyo-Nyorai» (sem macrónsculos),
forma usada em todo o acervo traduzido. A revisão do dossiê tinha introduzido
«Kōmyō Nyorai» em alguns pontos, criando duas grafias para o mesmo termo.
Este script repõe a forma do glossário e registra cada parágrafo alterado.
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
    'volume_novo/16b_cultos.md',
    'volume_novo/29b_titulos.md',
    'volume_novo/30_glossario.md',
    'volume_novo/40_anexo_programa_1947.md',
]

# ordem: as formas compostas primeiro, para não serem parcialmente apanhadas
TROCAS = [
    ('Dai-Kōmyō Nyorai', 'Daikōmyō Nyorai'),
    ('do Kōmyō Nyorai', 'da Komyo-Nyorai'),
    ('ao Kōmyō Nyorai', 'à Komyo-Nyorai'),
    ('o Kōmyō Nyorai', 'a Komyo-Nyorai'),
    ('Kōmyō Nyorai', 'Komyo-Nyorai'),
    ('Kōmyō-Nyorai', 'Komyo-Nyorai'),
]

registos = []
for rel in FICHEIROS:
    caminho = os.path.join(BASE, rel)
    if not os.path.exists(caminho):
        print('  ! ausente:', rel)
        continue
    texto = open(caminho, encoding='utf-8').read()
    blocos = re.split(r'(\n\s*\n)', texto)
    alterados = 0
    for i, bloco in enumerate(blocos):
        if 'Kōmyō' not in bloco:
            continue
        novo = bloco
        for de, para in TROCAS:
            novo = novo.replace(de, para)
        if novo != bloco:
            blocos[i] = novo
            registos.append({
                'capitulo': 'Normalização de grafia — Komyo-Nyorai',
                'arquivo': rel,
                'antes': bloco.strip(),
                'depois': novo.strip(),
            })
            alterados += 1
    if alterados:
        open(caminho, 'w', encoding='utf-8').write(''.join(blocos))
    print(f'{rel}: {alterados} blocos')

log = []
if os.path.exists(LOG):
    log = json.load(open(LOG, encoding='utf-8'))
log.extend(registos)
json.dump(log, open(LOG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'{len(registos)} registos acrescentados ao log')
