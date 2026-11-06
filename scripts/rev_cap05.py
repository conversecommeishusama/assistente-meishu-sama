import sys
sys.path.insert(0, '/var/www/goshinsho/scripts')
from revisar import aplicar

II = 'docs/DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md'

aplicar('Capítulo 5 — A ordem do culto', [
    (II,
     '''Meishu-Sama para a ocasião. Depois o **retirada das oferendas** e a saída dos
oficiantes, encerrando-se às 10h45. Meishu-Sama entrou às 11h10, acompanhado da
esposa e da tia.''',
     '''Meishu-Sama para a ocasião. Depois a **retirada das oferendas** e a saída dos
oficiantes, encerrando-se às 10h45. Meishu-Sama entrou às 11h10, acompanhado da esposa e
da tia.'''),

    (II,
     '''Não há um rito distinto por tipo de unidade. O que varia é **quais unidades têm
obrigação de celebrar culto em data fixa**, questão tratada na Parte I (§3) a partir
do censo e das atribuições de cada nível: o Culto Mensal e o Culto Regular eram
incumbência de filiais, postos avançados e igrejas; unidades menores limitavam-se ao
culto doméstico diante da Imagem.

A **escala do culto** em três degraus — o 大祭 da Sede, o Culto Regular e o Culto Mensal das
igrejas, e o culto doméstico — está sistematizada no capítulo 17, que também
trata do que caracteriza cada degrau.''',
     '''Não há um rito distinto por tipo de unidade. O que varia é **quais unidades têm
obrigação de celebrar culto em data fixa**, questão tratada no capítulo 22 a partir do censo
e das atribuições de cada nível: o Culto Mensal e o Culto Regular eram incumbência de
filiais, postos avançados e igrejas; unidades menores limitavam-se ao culto doméstico
diante da Imagem.

A **escala do culto** em três degraus — o Grande Culto da Sede, o Culto Regular e o Culto
Mensal das igrejas, e o culto doméstico — está sistematizada no capítulo 6, que também
trata do que caracteriza cada degrau.'''),

    (II,
     '''É a resposta direta à pergunta sobre quem pendurava a caligrafia Komyo em vez da
Imagem: **sim, fazia-se culto matinal e vesperal diante da caligrafia**, e ela
funcionava explicitamente como substituta da Imagem. Sobre oferendas
nesse caso específico a documentação não se pronuncia; o relato menciona apenas
a visita
e a quietude do coração.''',
     '''É a resposta direta à pergunta sobre quem pendurava a caligrafia Kōmyō em vez da
Imagem: **sim, fazia-se culto matinal e vesperal diante da caligrafia**, e ela funcionava
explicitamente como substituta da Imagem. Sobre oferendas nesse caso específico a
documentação não se pronuncia; o relato menciona apenas a visita e a quietude do
coração.'''),

    (II,
     '''Três informações: o rito deve ser celebrado; usa-se **veste ceremonial**; e o
paramento exige **aprendizado** — não era de conhecimento comum. Isso qualifica
materialmente o que se registrou sobre a formação: o "saber ler o manual em
voz alta" não esgotava a instrução, havia protocolo ritual a transmitir.''',
     '''Três informações: o rito deve ser celebrado; usa-se **veste ceremonial**; e o paramento
exige **aprendizado** — não era de conhecimento comum. Isso qualifica materialmente o que
se registrou sobre a formação: o «saber ler o manual em voz alta» não esgotava a instrução;
havia protocolo ritual a transmitir.'''),

    (II,
     '''O contexto é notável: a resposta explica um sonho em que um ancestral, tendo
alcançado divindade menor, aparece de veste branca e capuz branco. A cor, portanto, não era
ornamento — **indicava grau**, e o código valia tanto no ritual quanto na hierarquia
espiritual.

**O que permanece em aberto:** não há inventário exaustivo de paramentos por tipo de
unidade, nem menção a traje de caça ou calças cerimoniais. Há veste prescrita, com escala cromática por grau
e exigência de aprendizado; não há catálogo.''',
     '''O contexto é notável: a resposta explica um sonho em que um ancestral, tendo alcançado
divindade menor, aparece de veste branca e capuz branco. A cor, portanto, não era ornamento
— **indicava grau**, e o código valia tanto no ritual quanto na hierarquia espiritual.

**O que permanece em aberto:** não há inventário exaustivo de paramentos por tipo de
unidade, nem menção a traje de caça ou calças cerimoniais. Há veste prescrita, com escala
cromática por grau e exigência de aprendizado; não há catálogo.'''),
])
