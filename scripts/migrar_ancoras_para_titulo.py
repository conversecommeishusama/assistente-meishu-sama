#!/usr/bin/env python3
"""Recua cada âncora até ao início do título do próprio artigo.

Problema (medido em 2026-10-21): em 285 artigos de 24 obras a âncora apontava
para a 1.ª frase do corpo, e a linha do título ficava no FIM do bloco anterior
-- o segmento de um artigo terminava com o cabeçalho do seguinte. A divisão do
autor começa no título, não depois dele (é o que o próprio spec já assume no
campo `pt_prefix`, que o gerador volta a inserir no início do corpo).

Corrigidos 137 artigos em 16 obras. Idempotente: uma segunda passagem não
encontra nada a fazer.

Não toca nos separadores de secção (`kind: section`, sem título próprio), que
abrem de propósito o bloco do artigo seguinte.

Verificação antes de gravar:
  * a âncora nova resolve exactamente no início da linha do título;
  * a lista completa continua a resolver, em ordem;
  * nenhuma âncora fica vazia ou duplicada.

Uso:
    .venv/bin/python scripts/migrar_ancoras_para_titulo.py            # simula
    .venv/bin/python scripts/migrar_ancoras_para_titulo.py --aplicar
"""
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, '/var/www/goshinsho/scripts')
sys.path.insert(0, '/var/www/goshinsho')

import build_clean_large_indexes as B
from apply_manual_livros_segmentacao import (
    _find_anchor, inicio_do_corpo, posicoes_das_ancoras)


def norm(s):
    return re.sub(r'\s+', ' ', s).strip()


def caminho_corpus(nome, lang):
    if lang == 'pt':
        return B.PT_DIR / nome
    par = B._par_emparelhado('jp', nome)
    return B.JP_DIR / (par.name if par else nome)


def inicio_da_linha_titulo(zona, titulo):
    """Offset da ÚLTIMA linha da zona que é exactamente o título."""
    alvo = norm(titulo)
    if not alvo:
        return None
    desloc = None
    for m in re.finditer(r'(?m)^.*$', zona):
        if norm(m.group(0)) == alvo:
            desloc = m.start()
    return desloc


def migra(spec, nome, lang, t, inicio):
    campo = 'jp_anchor' if lang == 'jp' else 'pt_anchor'
    titulo = 'title_jp' if lang == 'jp' else 'title_pt'
    arts = spec['articles']
    anc = [(a.get(campo) or '').strip() for a in arts]
    mudou = []

    for _ in range(4):
        if not all(anc):
            return mudou, 'âncora vazia'
        try:
            pos = posicoes_das_ancoras(t, anc, label=lang, inicio=inicio)
        except ValueError as exc:
            return mudou, f'não resolve: {exc}'
        mudou_agora = False
        for i in range(2, len(arts) + 1):
            tit = (arts[i - 1].get(titulo) or '').strip()
            if len(tit) < 5:
                continue
            zs = inicio if i == 2 else pos[i - 2]
            desloc = inicio_da_linha_titulo(t[zs:pos[i - 1]], tit)
            if desloc is None:
                continue
            # O texto deslocado não pode engolir o artigo anterior: 3.000
            # caracteres é o máximo aceite (o maior caso real foi 836).
            if (pos[i - 1] - (zs + desloc)) > 3000:
                continue
            # O título pode já ser o início do artigo anterior por desenho:
            # é o caso dos separadores de secção (`kind: section`, sem título
            # próprio) que abrem o bloco do artigo seguinte. Nesse caso o
            # título já pertence correctamente à entrada anterior.
            tit_ant = norm(arts[i - 2].get(titulo) or '')
            anc_ant = anc[i - 2]
            if not tit_ant or tit_ant == norm(tit):
                if not tit_ant and norm(anc_ant.splitlines()[0]) == norm(tit):
                    continue
            novo = (t[zs + desloc:pos[i - 1]] + anc[i - 1]).strip()
            if novo and novo != anc[i - 1]:
                anc[i - 1] = novo
                arts[i - 1][campo] = novo
                mudou.append(i)
                mudou_agora = True
        if not mudou_agora:
            break

    # verificação: a âncora nova tem de resolver exactamente no título
    try:
        posicoes_das_ancoras(t, anc, label=lang, inicio=inicio)
    except ValueError as exc:
        return mudou, f'falha final: {exc}'
    return mudou, None


def main(aplicar):
    ren = json.loads((B.PROJECT_ROOT /
                      'reports/varredura_padronizacao/MAPEAMENTO_RENOMEACAO_TXT.json'
                      ).read_text(encoding='utf-8'))
    ren = {i['novo']: i['antigo'] for i in ren}
    marcador = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    total, obras, erros = 0, 0, 0
    pendentes = {}

    for sp in sorted(B.SEGMENTACAO_MANUAL_DIR.glob('*.txt.json')):
        nome = sp.name[:-5]
        spec = json.loads(sp.read_text(encoding='utf-8'))
        if len(spec.get('articles') or []) <= 1:
            continue
        alterou = False
        for lang in ('pt', 'jp'):
            p = caminho_corpus(nome, lang)
            if not p.exists():
                continue
            t = B.clean_body(B.read_text(p))
            mudou, erro = migra(spec, nome, lang, t, inicio_do_corpo(t))
            if erro:
                print(f'  ! {nome} [{lang}]: {erro}')
                erros += 1
                continue
            if mudou:
                alterou = True
                total += len(mudou)
                print(f'  + {nome} [{lang}]: {len(mudou)} artigos '
                      f'{mudou[:6]}{"…" if len(mudou) > 6 else ""}')
        if alterou:
            obras += 1
            pendentes[sp] = spec

    print(f'\n{total} âncoras em {obras} obras; {erros} erro(s).')
    if erros:
        print('nada gravado')
        return 1
    if not aplicar:
        print('simulação (use --aplicar)')
        return 0
    for sp, spec in pendentes.items():
        bak = sp.with_suffix(f'.json.bak_titulos_{marcador}')
        shutil.copy2(sp, bak)
        sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1),
                      encoding='utf-8')
    print(f'{len(pendentes)} spec(s) gravadas (backup .bak_titulos_{marcador})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main('--aplicar' in sys.argv))
