"""Segunda bateria de verificação: marcas desequilibradas, remissões
mal formadas e resíduos vocabulares que a montagem devia ter eliminado."""
import re

DOC = '/var/www/goshinsho/docs/DOSSIE_DIFUSAO_20261020.md'
texto = open(DOC, encoding='utf-8').read()
linhas = texto.split('\n')

problemas = []


def add(i, tipo, trecho):
    problemas.append((i, tipo, trecho.strip()[:120]))


for i, l in enumerate(linhas, 1):
    if l.count('「') != l.count('」'):
        add(i, '「」 desequilibrado', l)
    if l.count('『') != l.count('』'):
        add(i, '『』 desequilibrado', l)
    if l.count('*') % 2:
        add(i, 'negrito/itálico ímpar', l)
    if l.count('(') != l.count(')'):
        add(i, 'parênteses desequilibrados', l)
    if l.count('«') != l.count('»'):
        add(i, 'aspas «» desequilibradas', l)

for i, l in enumerate(linhas, 1):
    for padrao, rot in [
        (r'\bcapítulo \d+\.\d', 'capítulo com subsecção (usar §)'),
        (r'\bParte\s+I{1,3}\b', 'remissão a Parte (o volume é único)'),
        (r'\bacervo\b', 'resíduo: acervo'),
        (r'\bcorpus\b', 'resíduo: corpus'),
        (r'\brattail\b', 'resíduo: rattail'),
        (r'§\s*\d+\s*§', 'remissão dupla'),
        (r'\s{2,}\S', 'espaço duplo'),
        (r'\.\.\s', 'reticências malformadas'),
        (r'\band\b', 'resíduo de inglês'),
        (r'\bthe\b', 'resíduo de inglês'),
    ]:
        if re.search(padrao, l) and not l.lstrip().startswith('|'):
            add(i, rot, l)

# maiúscula depois de ponto final e minúscula no início de parágrafo
for i, l in enumerate(linhas, 1):
    if re.match(r'^[a-zà-ÿ]', l) and not l.startswith('|') and i > 1:
        anterior = linhas[i - 2].rstrip()
        if not anterior or anterior.endswith(('.', ':', '>', '—')) or anterior.startswith('>'):
            add(i, 'parágrafo começa em minúscula', l)

vistos, saida = set(), []
for p in problemas:
    if (p[0], p[1]) in vistos:
        continue
    vistos.add((p[0], p[1]))
    saida.append(f'{p[0]:6d}  {p[1]:40s}  {p[2]}')

open('/tmp/qa2_volume.txt', 'w', encoding='utf-8').write('\n'.join(saida))
print(len(saida), 'ocorrências -> /tmp/qa2_volume.txt')
for t in sorted(set(p[1] for p in problemas)):
    print(f'  {t}: {sum(1 for p in problemas if p[1] == t)}')
