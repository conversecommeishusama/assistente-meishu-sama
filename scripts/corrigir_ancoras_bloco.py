#!/usr/bin/env python3
"""Corrige âncoras de spec que cortavam dentro da palavra ou deixavam o
marcador estrutural (`（お伺）`, `[`) para trás.

Cada alteração é verificada em duas frentes antes de gravar:
  1. o texto antigo existe exactamente uma vez na spec;
  2. a âncora nova resolve no corpus, em início de bloco.
Grava backup .bak_ancoras_<timestamp> ao lado do original.
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, '/var/www/goshinsho/scripts')
sys.path.insert(0, '/var/www/goshinsho')

import build_clean_large_indexes as B
from apply_manual_livros_segmentacao import (
    _eh_inicio_de_bloco, _find_anchor, inicio_do_corpo)

# (obra, idioma, artigo 1-based, prefixo antigo, prefixo novo)
CORRECOES = [
    # JP: a âncora perdeu o início do título e cortava dentro da palavra
    ('Medicina_do_Amanha.txt', 'jp', 30, 'の原因と罪穢れ', '病気の原因と罪穢れ'),
    ('Medicina_do_Amanha.txt', 'jp', 31, 'の本体は魂なり', '病気の本体は魂なり'),
    ('Medicina_do_Amanha.txt', 'jp', 32, '療法\n\n元来', '自然療法\n\n元来'),
    ('Medicina_do_Amanha.txt', 'jp', 33, '栄養学\n\n今日', '真の栄養学\n\n今日'),
    # JP: o marcador `（お伺）` abre a pergunta e tem de viajar com ela
    ('19510920-御教え集1号.txt', 'jp', 5, '現在腹部の大浄化', '（お伺）現在腹部の大浄化'),
    ('19520115-御教え集5号.txt', 'jp', 4, '丹久子（二十三才）', '（お伺）丹久子（二十三才）'),
    ('19520115-御教え集5号.txt', 'jp', 9, '藤川緑（三十四歳）', '（お伺）藤川緑（三十四歳）'),
    # PT: o cabeçalho da sessão está entre [ ]; o corte tem de ficar antes dele
    ('19520115 - Mioshie-shū nº 5.txt', 'pt', 8, '21º de dezembro', '[21º de dezembro'),
    # PT — Mioshie-shū nº 26: quatro fronteiras seguidas deslocadas uma sessão
    # à frente. Cada artigo absorvia a data do seguinte e o corpo da sua própria
    # sessão ficava no artigo anterior (art. 8 continha duas sessões; art. 9
    # abria no corpo da sessão de 25; art. 10 na data de 26). O título de cada
    # sessão passa a abrir o próprio artigo.
    ('19531015 - Mioshie-shū nº 26.txt', 'pt', 9, None,
     '24 de setembro\n\nEste ano, excepcionalmente, chove muito durante o '
     'Culto Especial, mas isso se deve, afinal, ao aumento da'),
    ('19531015 - Mioshie-shū nº 26.txt', 'pt', 10, None,
     '25 de setembro\n\nEste outono, excepcionalmente, chove quase todos os '
     'dias, mas há uma grande razão espiritual para isso'),
    ('19531015 - Mioshie-shū nº 26.txt', 'pt', 11, None,
     '26 de setembro\n\nEm 15 de junho deste ano, eu disse: "Daqui em '
     'diante, a purificação se tornará real'),
    ('19531015 - Mioshie-shū nº 26.txt', 'pt', 12, None,
     '27 de setembro\n\nO tufão desta vez também parece ter causado grandes '
     'danos.'),
    # PT — secção com o cabeçalho colado ao parágrafo seguinte: a âncora
    # apontava para a 1.ª frase do corpo, deixando o próprio cabeçalho (e, em
    # dois casos, a linha que o repete) no artigo anterior.
    ('19510815 - Terapia Revolucionária da Tuberculose.txt', 'pt', 9, None,
     'Respeite a Natureza\n\nRespeite a natureza. Na medicina, o repouso é '
     'considerado o mais importante'),
    ('19510815 - Terapia Revolucionária da Tuberculose.txt', 'pt', 13, None,
     'O Mundo Inorgânico\n\nMundo Inorgânico — Aqui, finalmente, escreverei '
     'sobre a ordem de surgimento'),
    ('19530505 - Explicação do Método da Agricultura Natural para o Aumento '
     'Extraordinário da Produção.txt', 'pt', 5, None,
     '(2) Desta vez, observando os resultados do ano passado relatados'),
    # PT — o corte caía DENTRO do próprio título: faltava o artigo "O" e, no
    # outro caso, o prefixo "Espíritos de". O pedaço que sobrava ficava no fim
    # do artigo anterior, e o artigo seguinte abria a meio do seu cabeçalho.
    ('19490825 - Coleção Jikan Volume 3 Conversas sobre o Mundo Espiritual.txt',
     'pt', 10, 'Espírito da Raposa e a Velha Senhora',
     'O Espírito da Raposa e a Velha Senhora'),
    ('19490825 - Coleção Jikan Volume 3 Conversas sobre o Mundo Espiritual.txt',
     'pt', 15, 'Pessoas Vivas', 'Espíritos de Pessoas Vivas'),
    # JP — Tijotengoku, `転向者の悩みに応う` (art. 86). O artigo existia três
    # vezes no ficheiro: a cópia de Tijotengoku (com `投書（省略）`) em @21713 e
    # em @142065, e a edição que restaura a carta do convertido em @129159.
    # A cópia de @142065 (byte-idêntica à de @21713) foi removida do corpus a
    # 21/10/2026, e o art. 86 passa a ancorar na edição com a carta — que é a
    # que o PT art. 86 traduz. Sem isto, o art. 85 (Prefácio nº 10) absorvia o
    # artigo inteiro e a carta (13 483 chars) e o art. 86 ficava com uma
    # segunda cópia sem par (1 628 chars).
    ('Tijotengoku.txt', 'jp', 86, None,
     '転向者の悩みに応う\n『地上天国』11号、昭和24(1949)年12月20日発行'),
    # PT — Fonte do Riso. O ficheiro tinha duas inserções que duplicavam versos e
    # deslocavam os títulos: (a) depois de `Título: "Larvas"` vinham os versos
    # 627 e 645 seguidos dos títulos `Sujeito Desagradável` e `Cheira Meu Peido`,
    # de modo que os versos 616-631 (Larvas) ficavam sob o título «Cheira Meu
    # Peido»; (b) depois de `Título: "Extraordinário"` vinha o verso 820 e um
    # segundo `Título: "Sujeito Cambaleante"`, deslocando 816-826. As 12 linhas
    # foram removidas do corpus a 21/10/2026, contra a versão publicada em
    # `livros_publicacao_pt/19510130-笑の泉.txt` (69 blocos, cada verso uma vez).
    # A âncora do art. 40 passa a apontar para o 1.º verso real do bloco.
    ('19510130 - Fonte do Riso.txt', 'pt', 40, None,
     'Título: "Larvas"'),
    # PT — Relatos de Milagres, art. 80 (C4 do handoff de 21/10). A âncora era a
    # própria fonte da citação (`Da revista "Eikou" nº 155…`), que está na MESMA
    # linha da citação; o artigo abria, portanto, a meio do próprio cabeçalho e o
    # título ficava no artigo anterior. Passa a abrir no título (linha 1816), que
    # é distinto do título do art. 79 (`Queimadura por Radiação Atômica Curada
    # pelo Johrei)` — este é `Queimadura causada pela radiação atômica…`; cada um
    # tem 1 ocorrência no ficheiro.
    ('19530910 - Relatos de Milagres da Igreja Messiânica Mundial.txt', 'pt', 80,
     None, 'Queimadura causada pela radiação atômica curada pelo Johrei'),
]


def main(aplicar: bool) -> int:
    marcador = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    tocados: dict[Path, dict] = {}
    falhas = 0

    for obra, lang, art, antigo, novo in CORRECOES:
        spec_path = B.SEGMENTACAO_MANUAL_DIR / f'{obra}.json'
        if not spec_path.exists():
            alt = B.RENOMEACAO_JP_PARA_PT.get(obra)
            if alt:
                spec_path = B.SEGMENTACAO_MANUAL_DIR / f'{alt}.json'
        spec = tocados[spec_path]['spec'] if spec_path in tocados else \
            json.loads(spec_path.read_text(encoding='utf-8'))
        arts = spec.get('articles') or []
        campo = 'jp_anchor' if lang == 'jp' else 'pt_anchor'
        atual = arts[art - 1].get(campo, '')
        if antigo is None:
            if atual == novo:
                print(f'  = [{lang}] {obra} art{art}: já corrigida')
                tocados.setdefault(spec_path, {'spec': spec, 'orig': None})
                continue
            arts[art - 1][campo] = novo
            tocados.setdefault(spec_path, {'spec': spec, 'orig': None})
            print(f'  ~ [{lang}] {obra} art{art}: âncora substituída por '
                  f'{novo.splitlines()[0]!r}')
            continue
        if atual.startswith(novo):
            print(f'  = [{lang}] {obra} art{art}: já corrigida')
            tocados.setdefault(spec_path, {'spec': spec, 'orig': json.loads(
                spec_path.read_text(encoding='utf-8'))})
            continue
        if not atual.startswith(antigo):
            print(f'  ! [{lang}] {obra} art{art}: prefixo inesperado '
                  f'{atual[:40]!r}')
            falhas += 1
            continue
        if atual.count(antigo) != 1:
            print(f'  ! [{lang}] {obra} art{art}: prefixo ambíguo')
            falhas += 1
            continue
        arts[art - 1][campo] = novo + atual[len(antigo):]
        tocados.setdefault(spec_path, {'spec': spec, 'orig': json.loads(
            spec_path.read_text(encoding='utf-8'))})
        print(f'  + [{lang}] {obra} art{art}: {antigo.splitlines()[0]!r} -> '
              f'{novo.splitlines()[0]!r}')

    # verificação: a âncora nova tem de resolver em início de bloco
    for spec_path, dados in tocados.items():
        spec = dados['spec']
        obra = spec_path.name[:-5]
        for lang, pasta, campo in (('pt', B.PT_DIR, 'pt_anchor'),
                                   ('jp', B.JP_DIR, 'jp_anchor')):
            arq = B._par_emparelhado(lang, obra)
            p = (pasta / arq.name) if (lang == 'jp' and arq) else (pasta / obra)
            if not p.exists():
                continue
            t = B.clean_body(B.read_text(p))
            ini = inicio_do_corpo(t)
            cursor = ini
            for i, a in enumerate(spec['articles'], start=1):
                x = a.get(campo, '')
                try:
                    q = _find_anchor(t, x, cursor, f'art{i}')
                except ValueError as exc:
                    print(f'  ! {obra} [{lang}] art{i}: {exc}')
                    falhas += 1
                    break
                cursor = q + max(1, len(x.strip().splitlines()[0]))

    if falhas:
        print(f'\n{falhas} falha(s) de verificação — nada gravado.')
        return 1
    if not aplicar:
        print(f'\n{len(tocados)} spec(s) verificadas; simulação (use --aplicar).')
        return 0
    for spec_path, dados in tocados.items():
        bak = spec_path.with_suffix(f'.json.bak_ancoras_{marcador}')
        shutil.copy2(spec_path, bak)
        spec_path.write_text(
            json.dumps(dados['spec'], ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8')
        print(f'  gravado {spec_path.name} (backup {bak.name})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main('--aplicar' in sys.argv))
