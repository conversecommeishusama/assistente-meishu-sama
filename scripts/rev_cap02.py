import sys
sys.path.insert(0, '/var/www/goshinsho/scripts')
from revisar import aplicar

F = 'docs/LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md'

pares = [
    (F,
     '''inicia o que chama de **movimento Kannon** sob o nome de **Associação Kannon do Grande Japão** (Dai-Nippon Kannon-kai, Associação Kannon do Grande Japão), a partir do Ōjin-dō (Ōjin-dō). O que ele próprio dirá depois sobre esse começo é revelador do modo como
entendia a relação entre carisma e instituição:''',
     '''inicia o que chama de **movimento Kannon**, sob o nome de **Associação Kannon do Grande
Japão** (Dai-Nippon Kannon-kai), a partir do Ōjin-dō. O que ele próprio dirá depois sobre
esse começo é revelador do modo como entendia a relação entre carisma e instituição:'''),

    (F,
     '''Três meses depois vem a fundação oficial, em 1º de janeiro de 1935, em Kōjimachi
Hanzōmon, num subsede do Oomoto que ele utilizava (`search1/ko/kojimach.html`). A década''',
     '''Três meses depois vem a fundação oficial, em 1º de janeiro de 1935, em Kōjimachi
Hanzōmon, numa subsede do Oomoto que ele utilizava (`search1/ko/kojimach.html`). A década'''),

    (F,
     '''A reorganização pós-guerra é rápida e se faz por camadas. Em 1946 constitui-se a
**Associação de Difusão da Terapêutica de Purificação** (Nihon Jōka Ryōhō Fukyū-kai), associação civil com estatuto próprio
(`search1/ni/nihon12.html`). Em 1º de julho de 1947 aparece o **Programa do Curso da Igreja Kannon do Japão**,
primeiro currículo de formação do movimento (`search1/ni/nihon07.html`). Em agosto de
1947 vem a personalidade jurídica religiosa:''',
     '''A reorganização pós-guerra é rápida e faz-se por camadas. Em 1946 constitui-se a
**Associação de Difusão da Terapêutica de Purificação** (Nihon Jōka Ryōhō Fukyū-kai),
associação civil com estatuto próprio (`search1/ni/nihon12.html`). Em 1º de julho de 1947
aparece o **Programa do Curso da Igreja Kannon do Japão**, primeiro currículo de formação
do movimento (`search1/ni/nihon07.html`). Em agosto de 1947 vem a personalidade jurídica
religiosa:'''),

    (F,
     '''ansiosamente?''', '''ansiosamente?'''),

    (F,
     '''*"Essa jóia, que até então era somente a força da própria jóia, naquele 15 de junho do
ano passado — a jóia que desde a Antiguidade se chama no Japão Mani-no-tama […] —, como
jóia que é, é alma: e essa alma, na data e hora referidas, **desceu do céu e alojou-se
dentro da delegacia de Shimizu, Anahara, província de Shizuoka.** Na ocasião anunciei-o
brevemente, mas **a isso chamei frutificação **."*
— 『病原と浄霊の原理』, 『地上天国』nº 27, 25 de agosto de 1951''',
     '''*"Essa jóia, que até então era somente a força da própria jóia, naquele 15 de junho do
ano passado — a jóia que desde a Antiguidade se chama no Japão Mani-no-tama […] —, como
jóia que é, é alma: e essa alma, na data e hora referidas, **desceu do céu e alojou-se
dentro da delegacia de Shimizu, Anahara, província de Shizuoka.** Na ocasião anunciei-o
brevemente, mas **a isso chamei frutificação**."*
— 『病原と浄霊の原理』, 『地上天国』, nº 27, 25 de agosto de 1951'''),

    (F,
     '''Em 10 de outubro publica-se o **Regulamento da pessoa jurídica religiosa「世界救世教」**,
o documento legal mais completo do período, cujos capítulos sobre administração e
finanças serão examinados no capítulo 24 (`search2/sanko/kisoku.html`).''',
     '''Em 10 de outubro publica-se o **Regulamento da pessoa jurídica religiosa** da Igreja
Messiânica Mundial, o documento legal mais completo do período, cujos capítulos sobre
administração e finanças serão examinados no capítulo 24 (`search2/sanko/kisoku.html`).'''),

    (F,
     '''Os últimos anos são de obras e de tensão. Em **15 de junho de 1952** conclui-se o
**神仙郷** — o Paraíso de Hakone — e inaugura-se o museu, em cerimônia reservada aos''',
     '''Os últimos anos são de obras e de tensão. Em **15 de junho de 1952** conclui-se o
**Shinsenkyō** — a Terra Divina, o Paraíso de Hakone — e inaugura-se o museu, em cerimônia
reservada aos'''),

    (F,
     '''> 「**神仙郷はいつも言う通り霊界なのです。**それで神仙郷が完成したということは、
> **霊界に地上天国ができた**わけです。今度熱海が完成すると**現界にできる**のですから」
> — 『御教え集』14号, 15 de outubro de 1952''',
     '''> 「**神仙郷はいつも言う通り霊界なのです。**それで神仙郷が完成したということは、
> **霊界に地上天国ができた**わけです。今度熱海が完成すると**現界にできる**のですから」
> — 『御教え集』, nº 14, 15 de outubro de 1952'''),

    (F,
     '''> — 「巻頭言」, 『地上天国』57号, 25 de fevereiro de 1954''',
     '''> — 「巻頭言」, 『地上天国』, nº 57, 25 de fevereiro de 1954'''),

    (F,
     '''Em **4 de fevereiro de 1954**, no culto do início da primavera, a igreja anuncia
que o Juízo Final começava ali — e que começava **pelo mundo material**:''',
     '''Em 16 de dezembro de 1953 realiza-se a cerimônia de fundação do Templo Messiânico, no
Zuiunkyo (`search1/ne/nento03.html`).

Em **4 de fevereiro de 1954**, no culto do início da primavera, a igreja anuncia
que o Juízo Final começava ali — e que começava **pelo mundo material**:'''),

    (F,
     '''Em 16 de dezembro de 1953 realiza-se a
cerimônia de fundação do Templo Messiânico, no Zuiunkyo (`search1/ne/nento03.html`).
Em 15 de junho de 1954, a cerimônia provisória do advento de Messias, no Messias
Kaidō — ocasião em que o presidente Ōkusa comunicou aos fiéis que, a partir
daquele culto, passariam a tratá-lo por **Messias-Sama** (`search2/kikou/mesiya1.html`,
『栄光』nº 263, 30 de junho de 1954). Em outubro sai a terceira edição do **Kyōshu Yōkō**,
o manual de formação. Em 11 de dezembro de 1954, a entronização no Palácio de Cristal, quando Meishu-Sama anuncia que "o Trabalho Divino finalmente entrou no
eixo principal". Em
fevereiro de 1955, sua morte (`search2/kikou2/kanto68.html`, 『地上天国』nº 68, 15 de
março de 1955).''',
     '''Em 15 de junho de 1954 realiza-se a cerimônia provisória do advento de Messias, no
Messias Kaidō — ocasião em que o presidente Ōkusa comunicou aos fiéis que, a partir
daquele culto, passariam a tratá-lo por **Messias-Sama** (`search2/kikou/mesiya1.html`,
『栄光』, nº 263, 30 de junho de 1954). Em outubro sai a edição revista do **Kyōshu Yōkō**,
o manual de formação. Em 11 de dezembro de 1954 vem a entronização no Palácio de Cristal,
quando Meishu-Sama anuncia que «o Trabalho Divino finalmente entrou no eixo principal»
(『栄光』, nº 289, 1º de janeiro de 1955). Em fevereiro de 1955, sua morte
(`search2/kikou2/kanto68.html`, 『地上天国』, nº 68, 15 de março de 1955).'''),

    (F,
     '''| 1954-12-11 | Entronização no Palácio de Cristal (entronização no Palácio de Cristal) |''',
     '''| 1954-12-11 | Entronização no Palácio de Cristal |'''),

    (F,
     '''período áureo de produção documental acompanha esse movimento: no acervo, 1948 tem 64
textos, 1949 salta para 348, 1950 tem 158, 1951 tem 172, 1952 chega a 203, e depois
declina — 134 em 1953 e 42 em 1954. O pico de 1949 corresponde ao ciclo Igreja Miroku; o
de 1952, ao programa de construção dos Paraísos Terrestres.''',
     '''período áureo de produção documental acompanha esse movimento: na documentação, 1948
tem 64 textos, 1949 salta para 348, 1950 tem 158, 1951 tem 172, 1952 chega a 203, e
depois declina — 134 em 1953 e 42 em 1954. O pico de 1949 corresponde ao ciclo Igreja
Miroku; o de 1952, ao programa de construção dos Paraísos Terrestres.'''),
]

aplicar('Capítulo 2 — A cronologia da institucionalização', pares)
