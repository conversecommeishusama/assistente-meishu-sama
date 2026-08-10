#!/bin/bash
# Cadeia que roda sozinha até o agrupamento, e PARA ali.
#
# O que vem depois -- depurar o agrupamento antes de qualquer coisa chegar à
# mesa do usuário -- é o primeiro trabalho da sessão nova, por determinação
# dele. Nada é enviado automaticamente.
cd /var/www/goshinsho
R=reports/varredura_padronizacao

esperar_desafiador() {
  while :; do
    n=$(venv/bin/python3 - <<'PY' 2>/dev/null
import json, pathlib, sys
sys.path.insert(0, "/var/www/goshinsho"); sys.path.insert(0, "/var/www/goshinsho/scripts")
import desafiador as D
R = pathlib.Path("reports/varredura_padronizacao")
alvo = set(json.load(open(R / "FILA_REJULGAMENTO.json")))
ds = set(json.loads((R / "DESAFIADOR.json").read_text(encoding="utf-8")))
# alvos_pilha_a exige DS1 == DS2: o desafiador so examina CONSENSO. Contar
# "os dois ja julgaram" incluia os casos em que eles DISCORDAM, que nunca
# recebem parecer dele -- a contagem jamais chegaria a zero e o laco giraria
# para sempre, travando a cadeia inteira antes da atribuicao.
print(len((set(D.alvos_pilha_a()) & alvo) - ds))
PY
)
    [ "$n" = "0" ] && break
    sleep 90
  done
}

esperar_desafiador
echo "$(date -u +%FT%TZ) [1/3] desafiador fechou" >> $R/rejulgamento.log

venv/bin/python3 scripts/atribui_ocr.py >> $R/atribuicao.log 2>&1
echo "$(date -u +%FT%TZ) [2/3] atribuicao concluida" >> $R/rejulgamento.log

venv/bin/python3 scripts/triagem.py > $R/TRIAGEM_POS_OCR.txt 2>&1

# o agrupamento antigo foi calculado sobre vereditos feitos contra japonês
# adulterado: guarda e refaz
cp $R/DECISOES.json $R/DECISOES.json.bak_pre_ocr_$(date -u +%Y%m%dT%H%M%SZ) 2>/dev/null
venv/bin/python3 scripts/agrupar_decisoes.py >> $R/agrupamento.log 2>&1
echo "$(date -u +%FT%TZ) [3/3] agrupamento refeito -- PARA AQUI." >> $R/rejulgamento.log
echo "$(date -u +%FT%TZ) proximo passo e humano: depurar o agrupamento." >> $R/rejulgamento.log
