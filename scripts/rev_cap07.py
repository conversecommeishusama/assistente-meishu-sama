import sys
sys.path.insert(0, '/var/www/goshinsho/scripts')
from revisar import aplicar

II = 'docs/DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md'

ANTES = '''A documentação permite datar com precisão uma **mudança de prática**. Na descrição do
Culto de Outono de 1954, lemos que a igreja abandonou o costume tradicional: (a
transformação é a mesma que a Parte III (§31) examina a partir da consulta de abril de
1949, em que Meishu-Sama nomeia os três elementos da oferenda xintoísta — peixe cru,
arroz lavado e sal — e os substitui pela comida humana.)

> 「ところで献饌物ですが、これも**今までの生米生魚…という風習を破って、
> すべて口に入れられる物に料理して御供えした**のですが、極めて常識的に行った
> までの事です。これらの事は、**神様を空なものとして、あまりにも人間離れ
> した**今までのあり方を打破しようという意味もあります」

*"Quanto aos alimentos ofertados: rompendo com o costume anterior de arroz cru,
peixe cru etc., passou-se a oferecer tudo **cozinhado, na forma em que entra na
boca** — e isso é apenas o que se fez de mais comum e sensato. Há aí também o
sentido de romper com o modo anterior, que **tomava as divindades como algo vazio e
demasiado apartado do humano**."*

Essa passagem é notável porque Meishu-Sama aparece do lado da **des-sacralização da
oferenda crua** e da aproximação do rito à vida doméstica. Noutro ponto, o mesmo
texto descreve o aparato: as oferendas eram dispostas em cinco grandes bandejas
lacadas de preto, carregadas sucessivamente pelo responsável das
oferendas e por quatro auxiliares, com os produtos da montanha e do mar. Registra
ainda, como novidade, que **as mulheres carregavam as oferendas** — o que, comenta
o cronista, não é contraditório, "pois servir à mesa sempre foi ofício feminino".

Sobre água, sal e arroz lavado como oferendas à Imagem, **há doutrina específica**, e
ela é de 23 de abril de 1949: Meishu-Sama nomeia os três elementos, reconhece que são as
oferendas sagradas do Xintó (go-shinsen) e declara que **a Imagem não as quer** — porque a
Imagem «é a figura de um ser humano», e o que se lhe oferta é o que os humanos comem;
água e arroz cru são «o que come o deus-dragão». A consulta inteira, com a tradução, está
no capítulo 8. Não é lacuna: é prescrição em contrário.'''

DEPOIS = '''A documentação permite datar com precisão uma **mudança de prática**, e a mudança começa
por uma crítica de Meishu-Sama à forma arcaica da oferenda:

> 「**なにしろお祭りと言えば千年から二千年ぐらい前の形式なのです。素焼の入れ物に
> 生米を入れたり、水を入れたり**し、浄衣なども、麻が本当なのですが、麻は絹などが
> ない時分の二千年以上前の形式で、相変わらずこれを採っているのです。**どうしても
> 小さい頭にできあがっている**のです。」
> — 御講話, 7 de dezembro de 1952 · `search1/kouwa/s281207.html`

*"Ora, quando se fala em culto, é a forma de mil a dois mil anos atrás. **Colocar arroz
cru em recipiente de barro, colocar água**, e a veste de purificação, cujo material
verdadeiro seria o linho — mas o linho é uma forma de mais de dois mil anos atrás, de
quando não havia seda —, e isso se continua adotando como está. **De todo modo, a cabeça
ficou pequena.**"*

Para ele, a oferenda crua não é prescrição divina: é resíduo de uma mentalidade estreita.
A consequência prática está documentada na descrição do Grande Culto de Outono de 1954,
publicada em 『栄光』nº 277: aberto o culto, **oito oficiantes** tomaram assento diante da
Imagem e a oferenda foi apresentada «em ordem», com **os produtos preciosos do mar e da
montanha** dispostos diante dela.

Sobre água, sal e arroz lavado como oferendas à Imagem, **há doutrina específica**, e ela é
de 23 de abril de 1949: Meishu-Sama nomeia os três elementos, reconhece que são as
oferendas sagradas do Xintó (go-shinsen) e declara que **a Imagem não as quer** — porque a
Imagem «é a figura de um ser humano», e o que se lhe oferta é o que os humanos comem; água
e arroz cru são «o que come o deus-dragão». A consulta inteira, com a tradução, está no
capítulo 8. Não é lacuna: é prescrição em contrário.'''

aplicar('Capítulo 7 — As oferendas do culto', [(II, ANTES, DEPOIS)])
