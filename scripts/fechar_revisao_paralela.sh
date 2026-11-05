#!/usr/bin/env bash
# Fecha a revisão paralela: junta os logs das sete worktrees, faz merge das sete
# branches e só então remonta o volume e regenera os binários.
#
# Uso:  bash scripts/fechar_revisao_paralela.sh [--sem-merge]
#
# Só corre na árvore principal (/var/www/goshinsho). Não correr nas worktrees.
set -euo pipefail

RAIZ=/var/www/goshinsho
cd "$RAIZ"
PY="$RAIZ/.venv/bin/python"
[ -x "$PY" ] || PY=python3

BRANCHES=(p1 p2 p3 p4 p5 p6 p7)
SEM_MERGE=0
[ "${1:-}" = "--sem-merge" ] && SEM_MERGE=1

echo "== 1/4  recolher os logs das worktrees =="
for b in "${BRANCHES[@]}"; do
  src="/var/www/goshinsho-$b/docs/revisao_log_$b.json"
  if [ -f "$src" ]; then
    cp "$src" "docs/revisao_log_$b.json"
    echo "   $b: $(python3 -c "import json,sys;print(len(json.load(open(sys.argv[1],encoding='utf-8'))))" "$src") registos"
  else
    echo "   $b: sem log (sessão não produziu alterações?)"
  fi
done

echo "== 2/4  juntar ao log central =="
"$PY" - <<'PY'
import glob, json, os
central = 'docs/revisao_20261104_log.json'
log = json.load(open(central, encoding='utf-8'))
antes = len(log)
vistos = {(r['capitulo'], r['arquivo'], r['antes']) for r in log}
novos = 0
for f in sorted(glob.glob('docs/revisao_log_p*.json')):
    for r in json.load(open(f, encoding='utf-8')):
        chave = (r['capitulo'], r['arquivo'], r['antes'])
        if chave in vistos:
            continue
        vistos.add(chave)
        log.append(r)
        novos += 1
json.dump(log, open(central, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('   %d -> %d registos (+%d)' % (antes, len(log), novos))
PY

if [ "$SEM_MERGE" = "0" ]; then
  echo "== 3/4  merge das branches =="
  for b in "${BRANCHES[@]}"; do
    if git rev-parse --verify -q "rev/$b" >/dev/null; then
      printf '   %-4s ' "$b"
      git merge --no-ff --no-edit "rev/$b" >/dev/null 2>&1 \
        && echo ok \
        || { echo "CONFLITO — resolver e voltar a correr com --sem-merge"; exit 1; }
    fi
  done
else
  echo "== 3/4  merge saltado (--sem-merge) =="
fi

echo "== 4/4  remontar e regenerar =="
python3 scripts/montar_volume_unico.py
python3 scripts/gerar_comparativo_revisao.py
"$PY" scripts/gerar_pdf_dossie_difusao.py DOSSIE_DIFUSAO_20261020 "A difusão na época de Meishu-Sama"
DOCX_CABECALHO="A difusão na época de Meishu-Sama" \
  "$PY" scripts/gerar_docx_dossie_difusao.py DOSSIE_DIFUSAO_20261020

echo
echo "Pronto. Verificar:"
echo "  python3 scripts/qa_volume.py; python3 scripts/qa2_volume.py"
echo "  git status --porcelain -- docs/ scripts/"
