import sys
sys.path.insert(0, '/var/www/goshinsho/scripts')
from revisar import aplicar

III = 'docs/DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md'
CAP = 'Capítulo 12 — A salvação e o Ohikari'

aplicar(CAP, [
    (III,
     '''Essa hierarquia do Ohikari é **distinta** da hierarquia das Imagens entronizadas, que
o capítulo 3.2 examina: são dois objetos
diferentes, com duas escadas diferentes.''',
     '''Essa hierarquia do Ohikari é **distinta** da hierarquia das Imagens entronizadas, que o
§3.2 examina: são dois objetos diferentes, com duas escadas diferentes.'''),

    (III,
     '''A outorga do Ohikari era indissociável do **Kyoshu** — o curso de formação (Parte
I §7). A sequência documentada nos relatos é constante: **cura → Kyoshu → Ohikari
→ entronização da Imagem**.''',
     '''A outorga do Ohikari era indissociável do **Kyoshu** — o curso de formação (§11). A
sequência documentada nos relatos é constante: **cura → Kyoshu → Ohikari → entronização da
Imagem**.'''),

    # reordenação: a conclusão passa para depois da citação
    (III,
     '''A leitura mais ajustada é, portanto: **um único pagamento, no ato do curso, com valor fixo
do objeto determinado pela Sede e embutido no montante que o fiel entregava** — e não uma
taxa de curso repassada à parte, mais um donativo separado. O que a documentação **não**
permite dizer é a composição interna desse montante, isto é, quanto do total correspondia ao
objeto e quanto ao curso: nenhum documento do período decompõe a cifra.

A lista é decisiva: o Ohikari **não aparece como item**. O que se cobrava era a
realização do curso — o instrutor, o material, o distintivo, a viagem e a
pousada —, e o Ohikari vinha ao fim, como conclusão. É por isso que os relatos
dizem "por mil ienes de oferta se recebe o Ohikari": o valor é do curso, e o
Ohikari é o que se recebe ao completá-lo.''',
     '''A lista é decisiva: o Ohikari **não aparece como item**. O que se cobrava era a realização
do curso — o instrutor, o material, o distintivo, a viagem e a pousada —, e o Ohikari vinha
ao fim, como conclusão. É por isso que os relatos dizem «por mil ienes de oferta se recebe o
Ohikari»: o valor é do curso, e o Ohikari é o que se recebe ao completá-lo.'''),

    (III,
     '''O mesmo valor aparece, distorcido, na acusação de um pregador adversário, que
fala em "dois mil ienes" pelo amuleto — cifra de fonte hostil, registrada apenas
como indício da ordem de grandeza (`search2/kikou2/sekkyo01.html`).''',
     '''O mesmo valor aparece, distorcido, na acusação de um pregador adversário, que fala em
«dois mil ienes» pelo amuleto — cifra de fonte hostil, registrada apenas como indício da
ordem de grandeza (`search2/kikou2/sekkyo01.html`).

A leitura mais ajustada é, portanto: **um único pagamento, no ato do curso, com valor fixo
do objeto determinado pela Sede e embutido no montante que o fiel entregava** — e não uma
taxa de curso repassada à parte, mais um donativo separado. O que a documentação **não**
permite dizer é a composição interna desse montante, isto é, quanto do total correspondia ao
objeto e quanto ao curso: nenhum documento do período decompõe a cifra.'''),
])
