#!/bin/bash
# Espera DS1/DS2 esvaziarem a fila, MATA os dois, só então remove os vereditos
# e religa. Remover com o laço vivo não funciona: ele carrega o dicionário na
# memória ao iniciar e reescreve o arquivo inteiro a cada gravação, restaurando
# o que foi apagado. Isso já está documentado no projeto e eu repeti o erro.
cd /var/www/goshinsho
R=reports/varredura_padronizacao
while :; do
  n=$(venv/bin/python3 -c "
import json
alvo=set(json.load(open('/tmp/rejulgar.json')))
f=lambda p: set(json.load(open('$R/'+p)))
print(len(alvo-f('AUDITORIA_DEEPSEEK.json'))+len(alvo-f('AUDITORIA_DEEPSEEK2.json')))" 2>/dev/null)
  [ "$n" = "0" ] && break
  sleep 60
done
tmux kill-session -t auditor_ds 2>/dev/null; tmux kill-session -t auditor_ds2 2>/dev/null
sleep 5
venv/bin/python3 -c "
import json,pathlib,shutil,time
R=pathlib.Path('reports/varredura_padronizacao')
af=set(json.load(open('/tmp/afetados_kichi.json')))
car=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
for n in ('AUDITORIA_DEEPSEEK','AUDITORIA_DEEPSEEK2','DESAFIADOR'):
    fp=R/(n+'.json'); d=json.loads(fp.read_text(encoding='utf-8'))
    t=[k for k in d if k in af]
    shutil.copy(fp, fp.with_suffix('.json.bak_kichi2_'+car))
    for k in t: del d[k]
    fp.write_text(json.dumps(d,ensure_ascii=False,indent=1),encoding='utf-8')
    print(n, -len(t))"
echo "$(date -u +%FT%TZ) fecho dos 吉: vereditos removidos, religando" >> $R/rejulgamento.log
tmux new-session -d -s auditor_ds  "venv/bin/python3 scripts/auditor_deepseek.py  >> $R/ds1.log 2>&1"
tmux new-session -d -s auditor_ds2 "venv/bin/python3 scripts/auditor_deepseek2.py >> $R/ds2.log 2>&1"
