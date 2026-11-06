import sys
sys.path.insert(0, '/var/www/goshinsho/scripts')
from revisar import aplicar

pares = [
    ('docs/volume_novo/01_fontes.md',
     'Deus**: é o que se chama Sabedoria Divina (Sabedoria Divina), o saber sem ter\naprendido."*',
     'Deus**: é o que se chama Sabedoria Divina, o saber sem ter aprendido."*'),

    ('docs/volume_novo/01_fontes.md',
     '''**O japonês** aparece em caracteres apenas onde a palavra original importa, e
vem sempre acompanhado de tradução. Quando um caractere não pôde ser lido com
segurança na fonte, ele aparece entre colchetes — por exemplo `教修が終ら〔れ〕た`
—, e o texto original não é alterado. Os termos de organização, de culto e de
qualificação estão reunidos no **Glossário**, e os títulos dos ensinamentos e
dos periódicos, na lista de **Títulos citados**, ambos no fim do volume.''',
     '''**O japonês** aparece em caracteres **apenas nos trechos citados no original**.
Na prosa, o termo vem em tradução portuguesa; quando não há tradução corrente,
vem em transliteração, com a grafia japonesa registada no **Glossário** e na
lista de **Títulos citados**, ambos no fim do volume. Por isso o leitor não
encontra ideogramas soltos no meio do texto: quem quiser conferir o original
encontra-o na citação e, para o vocabulário, nas duas listas finais. Quando um
caractere não pôde ser lido com segurança na fonte, ele aparece entre colchetes
dentro da própria citação — por exemplo `教修が終ら〔れ〕た` —, e o texto
original não é alterado.'''),

    ('docs/volume_novo/01_fontes.md',
     '''**As citações** indicam veículo, número e data. Quando o documento de origem
declara apenas mês e ano, também aqui se declara apenas mês e ano — não se
atribui dia que a fonte não informa.''',
     '''**As citações** indicam veículo, número e data, e transcrevem o original japonês
seguido de tradução. Quando o documento de origem declara apenas mês e ano,
também aqui se declara apenas mês e ano — não se atribui dia que a fonte não
informa.'''),
]

aplicar('Capítulo 1 — O período e as fontes', pares)
