import sys
sys.path.insert(0, '/var/www/goshinsho/scripts')
from revisar import aplicar

I = 'docs/LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md'
III = 'docs/DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md'

pares = [
    (I,
     '''O degrau 4 tem um critério explícito de adequação à casa, que é simultaneamente
doutrinário e prático:''',
     '''A última linha da tabela tem um critério explícito de adequação à casa, que é
simultaneamente doutrinário e prático:'''),

    (I,
     '''*"Não se deve ter desproporção… num tokonoma pequeno não cabe um pergaminho grande.
Afinal é a 'razão da correspondência'; é preciso que haja correspondência."*''',
     '''*"Não se deve ter desproporção… num tokonoma pequeno não se deve pôr um pergaminho
grande. Afinal é a 'razão da correspondência'; é preciso que haja correspondência."*'''),

    (I,
     '''E o princípio que rege tudo isso é o de **princípio da correspondência**, a correspondência entre o objeto e
o continente:''',
     '''E o princípio que rege tudo isso é o da **correspondência** entre o objeto e o
continente:'''),

    (I,
     '''Daikōmyō Nyorai; em casas pequenas, no interior, entroniza-se a Komyo-Nyorai."*''',
     '''Daikōmyō Nyorai; em casas pequenas, no interior, entroniza-se o Kōmyō Nyorai."*'''),

    (III,
     '''A salvação, portanto, é o **processo** — a purificação, a cura, a prosperidade e
a elevação espiritual que se seguem; o Ohikari é a **condição de possibilidade**
desse processo. Confundir um com o outro seria, no vocabulário do próprio
acervo, tomar a porta pelo caminho.''',
     '''A salvação, portanto, é o **processo** — a purificação, a cura, a prosperidade e a
elevação espiritual que se seguem; o Ohikari é a **condição de possibilidade** desse
processo. Confundir um com o outro seria, no vocabulário da própria casa, tomar a porta
pelo caminho.'''),

    (III,
     '''O Ohikari é uma **caligrafia de punho de Meishu-Sama**, dobrada e usada ao
pescoço. O acervo descreve sua natureza e sua função com precisão:''',
     '''O Ohikari é uma **caligrafia de punho de Meishu-Sama**, dobrada e usada ao pescoço. A
documentação descreve a sua natureza e a sua função com precisão:'''),
]

aplicar('Capítulo 3 — As Imagens da Luz Divina e os Ohikari', pares)
