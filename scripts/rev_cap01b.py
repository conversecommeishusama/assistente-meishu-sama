import sys
sys.path.insert(0, '/var/www/goshinsho/scripts')
from revisar import aplicar

aplicar('Capítulo 1 — O período e as fontes', [
    ('docs/volume_novo/01_fontes.md',
     'Deus**: é o que se chama Sabedoria Divina (Sabedoria Divina), o saber sem ter aprendido."*',
     'Deus**: é o que se chama Sabedoria Divina, o saber sem ter aprendido."*'),
])
