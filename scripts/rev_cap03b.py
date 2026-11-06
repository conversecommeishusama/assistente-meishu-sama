import sys
sys.path.insert(0, '/var/www/goshinsho/scripts')
from revisar import aplicar

III = 'docs/DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md'

aplicar('Capítulo 3 — As Imagens da Luz Divina e os Ohikari', [
    (III,
     '''desse processo. Confundir um com o outro seria, no vocabulário do próprio
documentação, tomar a porta pelo caminho.''',
     '''desse processo. Confundir um com o outro seria, no vocabulário da própria casa,
tomar a porta pelo caminho.'''),

    (III,
     '''O Ohikari é uma **caligrafia de punho de Meishu-Sama**, dobrada e usada ao
pescoço. A documentação descreve sua natureza e sua função com precisão:''',
     '''O Ohikari é uma **caligrafia de punho de Meishu-Sama**, dobrada e usada ao pescoço. A
documentação descreve a sua natureza e a sua função com precisão:'''),
])
