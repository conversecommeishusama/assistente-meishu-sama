import sys
sys.path.insert(0, '/var/www/goshinsho/scripts')
from revisar import aplicar

II = 'docs/DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md'
CAP = 'Capítulo 9 — O sufrágio dos antepassados'

aplicar(CAP, [
    # --- 位牌 -> tabuleta (glossário) -------------------------------------
    (II,
     '''Culto Mensal, os ancestrais dos fiéis se manifestavam pedindo tábuas memoriais:''',
     '''Culto Mensal, os ancestrais dos fiéis se manifestavam pedindo tabuletas (ihai):'''),

    (II,
     '''salvação** […] dizendo «**mandai fazer a tábua memorial**» ou «**a disposição das tábuas
está torta, corrigi-a**»; e fazemos o que é possível…"*''',
     '''salvação** […] dizendo «**mandai fazer a tabuleta**» ou «**a disposição das tabuletas está
torta, corrigi-a**»; e fazemos o que é possível…"*'''),

    (II,
     '''*"O Sr. Miyazaki disse: **sufragai as almas de vossos ancestrais**; comprei
imediatamente as tábuas memoriais, e naquela noite não consegui de modo algum
dormir.''',
     '''*"O Sr. Miyazaki disse: **sufragai as almas de vossos ancestrais**; comprei
imediatamente as tabuletas, e naquela noite não consegui de modo algum
dormir.'''),

    (II,
     '''O caso ilustra a estrutura pastoral: o fiel é instruído a instalar o altar e as
tábuas memoriais **em casa**, e o ministro executa o rito.''',
     '''O caso ilustra a estrutura pastoral: o fiel é instruído a instalar o altar e as tabuletas
**em casa**, e o ministro executa o rito.'''),

    # --- 16.2: fontes -----------------------------------------------------
    (II,
     '''> 頗る厳格であって、ことごとく相応の秩序が保たれているのである。」

*"O espírito é elástico segundo o pensamento.''',
     '''> 頗る厳格であって、ことごとく相応の秩序が保たれているのである。」
> — 「輪廻転生」, `search1/ri/rinne.html`

*"O espírito é elástico segundo o pensamento.'''),

    (II,
     '''> よって、その家……」

*"Mesmo o espírito, se não come, sente fome.''',
     '''> よって、その家……」
> — 「霊界の構成」, `search1/re/reikai06.html`

*"Mesmo o espírito, se não come, sente fome.'''),

    # --- 16.3: frase partida + fontes -------------------------------------
    (II,
     '''Sobre lugar específico de consagração e sobre rito próprio na Sede Geral, a documentação
consultado **não contém documentação**. O que existe são orientações dispersas sobre
o calendário e sobre a atitude. Numa sessão de perguntas e respostas de 18 de maio
de 1948, Meishu-Sama é direto sobre a pontualidade dos ritos fúnebres:

> 「りや法事なぞは**早くするのはよいが遅れるのはいけない**。」

*"Funerais e serviços memoriais: **é bom fazê-los cedo; atrasá-los não é
admissível.**"*''',
     '''Sobre lugar específico de consagração e sobre rito próprio na Sede Geral, a documentação
consultada **é silenciosa**. O que existe são orientações dispersas sobre o calendário e
sobre a atitude. Numa sessão de perguntas e respostas de 18 de maio de 1948, perguntado
sobre o que fazer quando não se pode celebrar o dia de Kannon, Meishu-Sama responde e
estende a regra a todo rito:

> 「――毎月十八日のお観音様の日にお祀りできない場合は――**十七日にしたらよい。
> 神仏のお祀りや法事なぞは早くするのはよいが遅れるのはいけない。**」
> — 「質問応答 御光話」, 18 de maio de 1948 · `search1/situmon/m230518.html`

*"— E quando não se pode celebrar no dia de Kannon, o dia dezoito de cada mês? — **Faça-se
no dia dezessete. Os cultos às divindades e aos budas e os serviços memoriais: é bom
antecipá-los; atrasá-los não é admissível.**"*'''),

    (II,
     '''> イエスの側とかキリストの側など行きたい所へ行ける。」

*"Mas **com Kannon nada disso importa.''',
     '''> イエスの側とかキリストの側など行きたい所へ行ける。」
> — 御講話 (data não determinada) · `search1/kouwa/fusyo1.html`

*"Mas **com Kannon nada disso importa.'''),

    # --- 16.4: fonte do Bon; remoção da citação de fonte vedada -----------
    (II,
     '''> 祀ってやればいいでしょう。」

*"O Bon é **o dia de consolar os espíritos do inferno**, por isso é o melhor. Em
especial convém fazer as oferendas **no último dia do Bon**."*

E, num texto de uma publicação da igreja, a explicação da relação entre vivos e
ancestrais, tomada como razão de ser do rito:

> 「八月十五日というのはちょうどお盆になっている……**お盆には私共の御先祖は
> 全部集って、私共は御先祖祀りをする**という事になっていますが、その御先祖
> の方々も今日の御祭に参拝して御光を戴いておられる事と思われます。……ここで、
> 先祖と私共の関係について少しお話しておきますが、**これはちょうど鏡を見ている
> ようなもので、霊界にある先祖が地獄状態であれば、現界の私共も地獄の状態と
> なり、天国的であるならば、それが現界に写って私共も天国状態となる**のです。」

*"O dia quinze de agosto coincide justamente com o Bon. […] **No Bon todos os
nossos ancestrais se reúnem, e nós celebramos o culto aos ancestrais**; acredita-se
que esses ancestrais também compareçam ao culto de hoje e recebam a Luz. […] Aqui
cabe falar um pouco da relação entre os ancestrais e nós: **é exatamente como olhar
num espelho — se os ancestrais que estão no mundo espiritual se encontram em estado
infernal, nós, neste mundo, também ficamos em estado infernal; se estão em estado
paradisíaco, isso se reflete neste mundo e nós também ficamos em estado
paradisíaco.**"*

A explicação, portanto, tem três partes: o Bon é o momento em que os ancestrais se
reúnem; sua finalidade é **consolar os espíritos do inferno** (não homenagear os já
salvos); e o estado dos ancestrais determina, por correspondência especular, o
estado dos vivos — o que faz do sufrágio uma operação de interesse direto da
família, e não um dever de piedade.''',
     '''> 祀ってやればいいでしょう。」
> — 「質問応答 御光話」, 8 de setembro de 1948 · `search1/situmon/m230908.html`

*"O Bon é **o dia de consolar os espíritos do inferno**, por isso é o melhor. Em
especial convém fazer as oferendas **no último dia do Bon**."*

Duas coisas ficam ditas: o Bon é o momento em que se trata dos que estão no inferno, e
não a festa dos já salvos; e a data escolhida é o **último** dia, não o primeiro. O que
não há, nesta resposta, é doutrina sobre a relação entre o estado dos ancestrais e o dos
vivos — e é preciso dizê-lo, porque o dossiê a afirmou aqui com base num texto que foi
depois **excluído por política de citação** (era de autoria do Rev. Kihara). A
correspondência entre o mundo espiritual e o fenoménico é doutrina de Meishu-Sama e está
documentada noutros capítulos; o que não se pode atribuir a esta página é a formulação
que aqui estava.'''),

    # --- 16.5: ideogramas em prosa ---------------------------------------
    (II,
     '''**`御霊祭` (Culto de Entronização) — a entronização da Imagem.** O nome diz''',
     '''**O Culto de Entronização (「御霊祭」) — a entronização da Imagem.** O nome diz'''),

    (II,
     '''**`先祖祭` — o sufrágio dos antepassados.** 40 ocorrências, e a natureza é outra:''',
     '''**O Sosen-sai (「先祖祭」) — o sufrágio dos antepassados.** 40 ocorrências, e a natureza é
outra:'''),

    (II,
     '''Este documento merece atenção: descreve um fenômeno espiritual ocorrido **durante** um
`先祖祭`, com o protocolo que se adotou e a instrução que Meishu-Sama deu a respeito.''',
     '''Este documento merece atenção: descreve um fenômeno espiritual ocorrido **durante** um
Sosen-sai, com o protocolo que se adotou e a instrução que Meishu-Sama deu a respeito.'''),

    (II,
     '''**O que continua sem fonte:** que o `先祖祭` fosse celebrado **na Sede Geral**. As''',
     '''**O que continua sem fonte:** que o Sosen-sai fosse celebrado **na Sede Geral**. As'''),

    # --- 16.6: remoção do trecho de fonte vedada --------------------------
    (II,
     '''
### 16.6 A festa no dia 15 de agosto

Um dado institucional que merece registro: a igreja escolheu deliberadamente o 15 de
agosto para um de seus cultos, explorando a coincidência com o Bon. O mesmo texto
explica que a data foi escolhida também por ser o aniversário de algo maior — a
coincidência das duas efemérides foi lida como "grandemente significativa". O
calendário ritual, portanto, foi construído **sobre** o calendário popular dos
mortos, em vez de contra ele.
''',
     '''
### 16.6 A festa no dia 15 de agosto

Um dado institucional ficou de fora deste capítulo. Havia, na documentação, a indicação
de que a igreja escolhera deliberadamente o 15 de agosto — dia em que o Bon coincide com
o aniversário do fim da guerra — para um de seus cultos, lendo a coincidência das duas
efemérides como «grandemente significativa». A única fonte era, porém, de autoria do Rev.
Kihara, e o trecho foi **excluído por política de citação**. Fica registrado como ponto
a reancorar em fonte institucional, e não como lacuna da prática: o que falta é o
documento, não o rito.
'''),
])
