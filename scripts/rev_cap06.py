import sys
sys.path.insert(0, '/var/www/goshinsho/scripts')
from revisar import aplicar

F = 'docs/volume_novo/16b_cultos.md'

aplicar('Capítulo 6 — Os tipos de culto', [
    (F,
     '''Havia quatro espécies de culto, e a diferença entre elas é de **escala e de
calendário**, não de rito. O que se fazia diante do altar era o mesmo; o que
mudava era quem celebrava, para quantos, e com que frequência.''',
     '''Havia quatro espécies de culto, e a elas se somava o culto ocasional. A diferença entre
uma e outra é de **escala e de calendário**, não de rito. O que se fazia diante do altar era
o mesmo; o que mudava era quem celebrava, para quantos e com que frequência.'''),

    (F,
     '''celebradas nos recintos da Sede. A descrição mais completa é a do Culto Especial
de Outono de 1950, cuja ordem está no capítulo 5. Duas notas sobre esse degrau. A
primeira é **quem oficia**: o rito não era presidido por Meishu-Sama, que
comparecia depois, como o venerando diante de quem a assembleia se curvava
(capítulo 5.1); a condução cabia ao presidente e aos oficiantes nomeados. A
segunda é a
**natureza da oferenda**: no grande culto ela era solene e codificada — oferendas
de mar e montanha, dispostas diante da Imagem da Luz Divina, e o''',
     '''celebradas nos recintos da Sede. A descrição mais completa é a do Grande Culto de Outono
de 1950, cuja ordem está no §5.1. Duas notas sobre esse degrau. A primeira é **quem
oficia**: o rito não era presidido por Meishu-Sama, que comparecia depois, como o venerando
diante de quem a assembleia se curvava; a condução cabia ao presidente e aos oficiantes
nomeados. A segunda é a **natureza da oferenda**: no grande culto ela era solene e
codificada — oferendas de mar e montanha, dispostas diante da Imagem da Luz Divina, e o'''),

    (F,
     '''dia do Culto Regular; e a série que opõe 「一宮例祭、当地の例祭、臨時祭」 — *"o Culto Regular de
Ichinomiya, o Culto Regular local e os cultos ocasionais"* —, o que mostra que o Culto Regular
convivia com o **Culto Extraordinário** (rinji-sai), celebrado por motivo extraordinário.''',
     '''dia do Culto Regular; e a série que opõe 「一宮例祭、当地の例祭、臨時祭」 — *"o Culto Regular do
Santuário Ichinomiya, o Culto Regular local e o Culto Extraordinário"* —, o que mostra que o
Culto Regular convivia com o **Culto Extraordinário** (rinji-sai), celebrado por motivo
extraordinário.'''),

    (F,
     '''**O Culto Mensal** — o culto do ciclo mensal, em
data fixa de cada unidade. Era incumbência das unidades com instalação própria:
filial, posto avançado e igreja. O Culto Mensal tinha uma função institucional precisa:
**acompanhava a entronização da Imagem**. Um relato de 1950 descreve o que
sucedeu a quem recebeu a Imagem e foi adiando o culto mensal:''',
     '''**O Culto Mensal** — o culto do ciclo mensal, em data fixa de cada unidade. Era
incumbência das unidades com instalação própria: a Igreja Filial, o posto avançado e a
igreja. O Culto Mensal tinha uma função institucional precisa: **acompanhava a entronização
da Imagem**. Um relato de 1950 descreve o que sucedeu a quem recebeu a Imagem e foi adiando
o culto mensal:'''),

    (F,
     '''| **春季大祭** — Grande Culto da Primavera | março | nacional |
| **秋季大祭** — Grande Culto de Outono | setembro (equinócio) | nacional, **7 dias**, rotativo por igreja |
| **御生誕祭** — Festa do Nascimento | 23 de dezembro | no Templo Messiânico |
| **Culto Mensal** — Culto Mensal | mensal, em cada unidade | data fixa por unidade |
| **Culto Regular** — Culto Regular | no calendário de cada igreja | próprio da unidade |
| **culto ocasional** — Culto Extraordinário | por motivo extraordinário | conforme o caso |
| **特別audiência** — Audiência Especial | 1º e 5º de cada mês | Sede |
| **毎旬の御参拝** — visita a cada dez dias | a cada dez dias | Sede |''',
     '''| **春季大祭** — Grande Culto da Primavera | março | nacional |
| **秋季大祭** — Grande Culto de Outono | setembro (equinócio) | nacional, **7 dias**, rotativo por igreja |
| **御誕生祭** — Culto do Nascimento | 23 de dezembro | no Templo Messiânico |
| **月並祭** — Culto Mensal | mensal, em cada unidade | data fixa por unidade |
| **例祭** — Culto Regular | no calendário de cada igreja | próprio da unidade |
| **臨時祭** — Culto Extraordinário | por motivo extraordinário | conforme o caso |
| **特別参拝** — Audiência Especial | 1º e 5º de cada mês | Sede |
| **毎旬の御参拝** — visita a cada dez dias | a cada dez dias | Sede |'''),

    (F,
     '''todo o volume. A descrição do Culto de Outono de 1950 nomeia funções que **não
coincidem com o organograma administrativo**: oficiante-chefe, chefe das oferendas
(chefe das oferendas), ofertantes (ofertantes, em número de cinco) e representante dos fiéis
(representantes dos fiéis). Havia, portanto, uma **equipe litúrgica designada
para cada culto**, distinta da linha de comando administrativa. É um indício de
que existia uma hierarquia ritual própria, cuja documentação completa não foi
localizada.''',
     '''todo o volume. A descrição do Grande Culto de Outono de 1950 nomeia funções que **não
coincidem com o organograma administrativo**: o oficiante-chefe, o chefe das oferendas, os
cinco ofertantes e o representante dos fiéis. Havia, portanto, uma **equipe litúrgica
designada para cada culto**, distinta da linha de comando administrativa. É um indício de
que existia uma hierarquia ritual própria, cuja documentação completa não foi localizada.'''),

    (F,
     '''A caligrafia em questão é a que traz os dois caracteres **nikkō** — *nikkō*, "luz
do sol" —, e não se confunde com as três caligrafias do Ohikari (光, 光明
(Kōmyō), Daikōmyō (Daikōmyō), tratadas no capítulo 3.3). Era um objeto de devoção doméstica, pendurado no
tokonoma, que funcionava explicitamente como **substituto** da
Imagem enquanto a família não a recebia. Sobre oferendas nesse caso específico a
documentação não se pronuncia; o relato menciona apenas a saudação e a quietude do
coração.''',
     '''A caligrafia em questão traz os dois caracteres que se leem *nikkō*, «luz do sol», e não se
confunde com as três inscrições do Ohikari — Kō, Kōmyō e Daikōmyō —, tratadas no §3.3. Era
um objeto de devoção doméstica, pendurado no tokonoma, que funcionava explicitamente como
**substituto** da Imagem enquanto a família não a recebia. Sobre oferendas nesse caso
específico a documentação não se pronuncia; o relato menciona apenas a saudação e a
quietude do coração.'''),
])
