"""Gera o comparativo da revisão (antes / depois) a partir do registro JSON."""
import json
import os
import re
from collections import OrderedDict

LOG = os.environ.get('REVISAO_LOG',
                     '/var/www/goshinsho/docs/revisao_20261104_log.json')
VOLUME = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs',
                      'DOSSIE_DIFUSAO_20261020.md')
SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs',
                     'COMPARATIVO_REVISAO_DOSSIE_20261104.md')

# títulos reais dos capítulos, lidos do volume montado
TITULOS = {}
for _l in open(VOLUME, encoding='utf-8'):
    _m = re.match(r'## (\d+)\.\s*(.+)', _l)
    if _m:
        TITULOS[int(_m.group(1))] = _m.group(2).strip()

registos = json.load(open(LOG, encoding='utf-8'))


def chave(r):
    """Ordena por número de capítulo; o que está fora do volume vem primeiro."""
    c = r['capitulo']
    m = re.search(r'Cap[íi]tulo (\d+)', c)
    if m:
        n = int(m.group(1))
        return (1, n, '')
    return (0, 0, c)


def rotulo(capitulo):
    """Rótulo canónico: número + título do volume, quando existir."""
    m = re.search(r'Cap[íi]tulo (\d+)', capitulo)
    if m:
        n = int(m.group(1))
        return f'Capítulo {n} — {TITULOS.get(n, "")}'.strip(' —')
    return capitulo


grupos = OrderedDict()
for r in sorted(registos, key=chave):
    grupos.setdefault(rotulo(r['capitulo']), []).append(r)

out = []
out.append('# Comparativo da revisão do dossiê — 2026-11-04')
out.append('')
out.append('Este documento reúne **todas as alterações** feitas na revisão linha a linha do '
           'volume *A difusão na época de Meishu-Sama*. Cada entrada mostra o texto **como '
           'estava** e **como ficou**, na íntegra e sem resumo, para dispensa de releitura do '
           'dossiê inteiro.')
out.append('')
out.append('A revisão seguiu duas regras fixas: **(1)** o `glossario_traducao.json` é '
           'autoritativo e prevalece sobre qualquer preferência estilística; **(2)** não se '
           'preenche lacuna documental por analogia — quando a documentação é silenciosa, o '
           'texto o diz.')
out.append('')

# ---------------------------------------------------------------- resumo
out.append('## Resumo')
out.append('')
out.append('| Grupo | Alterações |')
out.append('|---|---:|')
total = 0
for cap, itens in grupos.items():
    out.append(f'| {cap} | {len(itens)} |')
    total += len(itens)
out.append(f'| **Total** | **{total}** |')
out.append('')

out.append('### Correções de montagem (valem para o volume inteiro)')
out.append('')
for linha in [
    '**Linhas de referência esvaziadas.** A montagem apagava o trecho entre crases quando '
    'continha o caminho de um arquivo — e com ele ia a própria referência. Dez traduções '
    'ficaram seguidas de um travessão solto (`— `). Agora só o caminho é removido, e a '
    'referência bibliográfica permanece: `— 『御光話録』nº 12, 21 de setembro de 1949`.',
    '**Glosa nos títulos citados.** Títulos de artigos e de periódicos recebiam tradução '
    'entre parênteses nas linhas de referência, o que produzia «『地上天国』 (Paraíso '
    'Terrestre)nº 28» — ruído e, sobretudo, contradição com a decisão do glossário '
    '(Tijotengoku para o título, Paraíso Terrestre para o conceito). A glosa foi suprimida.',
    '**Remissão de subsecção.** Onde o texto dizia «capítulo 4.1» passou a dizer «§4.1», '
    'que é a forma usada no volume (16 ocorrências).',
    '**Medidas japonesas.** No Anexo H, «um shaku de largura» → «cerca de trinta '
    'centímetros» e «mil ri» → «cerca de quatro mil quilómetros», conforme a decisão do '
    'projeto de converter sempre as medidas.',
    '**Aspas japonesas.** Um título fechava com `»` em vez de `」` («浄霊法変る»), o que '
    'desequilibrava a citação.',
]:
    out.append(f'- {linha}')
out.append('')

# ---------------------------------------------------------------- detalhe
out.append('## Alterações, capítulo a capítulo')
out.append('')
for cap, itens in grupos.items():
    out.append(f'### {cap}')
    out.append('')
    for n, r in enumerate(itens, 1):
        out.append(f'**{n}.** *{r["arquivo"]}*')
        out.append('')
        out.append('> **Antes**')
        out.append('>')
        for l in r['antes'].split('\n'):
            out.append('> ' + l if l.strip() else '>')
        out.append('')
        out.append('> **Depois**')
        out.append('>')
        for l in r['depois'].split('\n'):
            out.append('> ' + l if l.strip() else '>')
        out.append('')
    out.append('')

open(SAIDA, 'w', encoding='utf-8').write('\n'.join(out))
print('gravado:', SAIDA)
print('grupos:', len(grupos), 'registos:', total)
