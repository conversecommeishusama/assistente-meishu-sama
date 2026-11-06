"""Verificação mecânica do volume único.

Detecta os defeitos recorrentes da montagem automática: ideogramas em prosa,
glosas duplicadas, concordâncias quebradas por substituição mecânica,
referências a secções inexistentes e linhas órfãs.
"""
import re
import sys

DOC = '/var/www/goshinsho/docs/DOSSIE_DIFUSAO_20261020.md'
texto = open(DOC, encoding='utf-8').read()
linhas = texto.split('\n')

CJK = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]')


def dentro_de_citacao(linha):
    """Ideograma entre 「」 ou 『』 conta como citação."""
    limpa = re.sub(r'「[^」]*」', '', linha)
    limpa = re.sub(r'『[^』]*』', '', limpa)
    return not CJK.search(limpa)


problemas = []

# 1. ideogramas em prosa (fora de citação, fora de tabela)
for i, l in enumerate(linhas, 1):
    if l.lstrip().startswith('|'):
        continue
    if l.startswith('>'):
        continue
    if CJK.search(l) and dentro_de_citacao(l):
        problemas.append((i, 'ideograma em prosa', l.strip()[:110]))

# 2. glosas duplicadas do tipo "Termo (Termo)"
for i, l in enumerate(linhas, 1):
    for m in re.finditer(r'\*\*([^*]{2,40})\*\* \(([^)]{2,40})\)', l):
        a, b = m.group(1).strip().lower(), m.group(2).strip().lower()
        if a == b:
            problemas.append((i, 'glosa duplicada', l.strip()[:110]))

# 3. concordância quebrada típica
padroes = [
    (r'\bo documentação\b', 'o documentação'),
    (r'\ba acervo\b', 'a acervo'),
    (r'\bdo caligrafia\b', 'do caligrafia'),
    (r'\bda objeto\b', 'da objeto'),
    (r'\bdo unidade\b', 'do unidade'),
    (r'\bda altar\b', 'da altar'),
    (r'\bnum subsede\b', 'num subsede'),
    (r'\bo retirada\b', 'o retirada'),
    (r'\ba princípio\b', 'a princípio'),
    (r'\bde o\b', 'de o'),
    (r'\bem o\b', 'em o'),
    (r'\bde a\b', 'de a'),
]
for i, l in enumerate(linhas, 1):
    if l.lstrip().startswith('|'):
        continue
    for rx, rot in padroes:
        if re.search(rx, l):
            problemas.append((i, 'concordância: ' + rot, l.strip()[:110]))

# 4. ideograma colado a palavra latina
for i, l in enumerate(linhas, 1):
    if re.search(r'[A-Za-zÀ-ÿ][\u3040-\u30ff\u4e00-\u9fff]|[\u3040-\u30ff\u4e00-\u9fff][A-Za-zÀ-ÿ]', l):
        problemas.append((i, 'ideograma colado a texto latino', l.strip()[:110]))

# 5. linha órfã (só um travessão)
for i, l in enumerate(linhas, 1):
    if l.strip() in ('—', '–', '-', '— —'):
        problemas.append((i, 'linha órfã', repr(l)))

# 6. referências a secções inexistentes
existentes = set()
for l in linhas:
    m = re.match(r'#{2,3} (\d+(?:\.\d+)?)[. ]', l)
    if m:
        existentes.add(m.group(1))
    m = re.match(r'#{2,3} (\d+)\.\s', l)
    if m:
        existentes.add(m.group(1))
for i, l in enumerate(linhas, 1):
    for m in re.finditer(r'§(\d+(?:\.\d+)?)', l):
        if m.group(1) not in existentes:
            problemas.append((i, 'remissão para § inexistente: ' + m.group(1), l.strip()[:110]))

# 7. espaços e repetições
for i, l in enumerate(linhas, 1):
    if re.search(r'\b(\w+) \1\b', l) and not l.lstrip().startswith('|'):
        m = re.search(r'\b(\w+) \1\b', l)
        if m.group(1).lower() not in ('que', 'no', 'a', 'o', 'e'):
            problemas.append((i, 'palavra repetida: ' + m.group(1), l.strip()[:110]))

vistos = set()
saida = []
for p in problemas:
    chave = (p[0], p[1])
    if chave in vistos:
        continue
    vistos.add(chave)
    saida.append(f'{p[0]:6d}  {p[1]:42s}  {p[2]}')

open('/tmp/qa_volume.txt', 'w', encoding='utf-8').write('\n'.join(saida))
print(f'{len(saida)} ocorrências -> /tmp/qa_volume.txt')
for k in sorted(set(p[1].split(':')[0] for p in problemas)):
    print(f'  {k}: {sum(1 for p in problemas if p[1].startswith(k))}')
