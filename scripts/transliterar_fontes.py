#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Traduz o aparto de citação do dossiê.

O capítulo «As fontes» fixa a convenção do volume:

    «O japonês aparece em caracteres apenas nos trechos citados no original.
     Na prosa, o termo vem em tradução portuguesa; quando não há tradução
     corrente, vem em transliteração, com a grafia japonesa registada no
     Glossário e na lista de Títulos citados.»

O aparelho de citação — as linhas que começam por «—» e as células de
referência das tabelas — não é trecho citado: é prosa. Estava, porém, cheio
de ideogramas: `— 「世界救世教秋季大祭に参拝して」, 『地上天国』nº 17`.

Este script corrige isso na origem, segundo duas regras:

  * veículo (periódico, coletânea) -> transliteração fixa do cap. 31
    (Tijotengoku, Eikō, Hikari, Kyūsei, Gosuiji-roku, Mioshie-shū,
     Gokōwa-roku, Kami no Hikari, Hōnan Shuki, Sekai Kyūseikyō);
  * obra, artigo, relato -> tradução portuguesa em itálico, tirada da
    tabela do cap. 31; quando o título não consta dela, fica registado
    aqui e é acrescentado à tabela.

Uso:
    python3 scripts/transliterar_fontes.py             # mostra o que faria
    python3 scripts/transliterar_fontes.py --aplicar   # grava
"""
import os
import re
import sys
import glob
import json

RAIZ = os.environ.get('GOSHINSHO_RAIZ', '/var/www/goshinsho/')
LOG = os.environ.get('REVISAO_LOG', RAIZ + 'docs/revisao_20261104_log.json')

FONTES = [
    'docs/LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md',
    'docs/DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md',
    'docs/DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md',
]

# as duas tabelas finais têm os ideogramas por função: são a chave do volume.
# O cap. 40 (Anexo H) fica fora por decisão do autor.
FONTES += [os.path.relpath(p, RAIZ) for p in sorted(
    glob.glob(RAIZ + 'docs/volume_novo/*.md'))
    if not any(p.endswith(x) for x in (
        '29b_titulos.md', '30_glossario.md', '47_anexo_kyoshu_yoko.md'))]

# --- veículos: transliteração fixa, sem itálico, sem aspas -----------------
VEICULOS = {
    '栄光': 'Eikō',
    '御教え集': 'Mioshie-shū',
    '御光話録': 'Gokōwa-roku',
    '御光話録（補）': 'Gokōwa-roku (suplemento)',
    '御垂示録': 'Gosuiji-roku',
    '御instrução descendente録': 'Gosuiji-roku',   # corrupção de uma substituição
    '光': 'Hikari',
    '救世': 'Kyūsei',
    '神の光': 'Kami no Hikari',
    '地上天国': 'Tijotengoku',
    '法難手記': 'Hōnan Shuki',
    '世界救世教': 'Sekai Kyūseikyō',
}

# --- obras publicadas em 『』 que não são periódicos ------------------------
OBRAS = {
    '病原と浄霊の原理': 'O princípio da doença e do Johrei',
    '信仰雑話': 'Conversas sobre a fé',
    '霊界叢談': 'Conversas sobre o mundo espiritual',
    '浄霊と医学との比較': 'O Johrei comparado à medicina',
    '日本観音教団講習要項': 'Programa do Curso da Igreja Kannon do Japão',
    '地上天国出来るまで': 'Até que o Paraíso Terrestre se realize',
    '革命的増産の自然農法解説': 'A Agricultura Natural da produção revolucionária',
}

# --- títulos de artigos, relatos e cartas --------------------------------
# Chave = ideogramas como aparecem na citação. Valor = tradução portuguesa.
TITULOS = {
    'ハワイ通信': 'Correspondência do Havaí',
    '世界救世教の機構整備について':
        'Sobre a organização da estrutura da Igreja Messiânica Mundial',
    '世界救世教秋季大祭に参拝して':
        'Visitando o Grande Culto de Outono da Igreja Messiânica Mundial',
    '五六七世界の建設': 'A construção do mundo de Miroku',
    '先生': 'Sensei',
    '光新聞の拡大は教線の強化':
        'Ampliar o jornal Hikari é fortalecer a linha da fé',
    '光明如来様御奉斎で盗難免る':
        'Livre de um roubo pela entronização da Komyo-Nyorai',
    '再教修を戴きました感謝の報告':
        'Relato de gratidão por ter recebido o re-Kyoshu',
    '問題の世界救世教とは何か':
        'Que é, afinal, a Igreja Messiânica Mundial?',
    '地上天国出来るまで': 'Até que o Paraíso Terrestre se realize',
    '大いに神書を読むべし': 'É preciso ler muito os Escritos Divinos',
    '大祭式典に参加して': 'Participando da cerimônia do Grande Culto',
    '奇蹟': 'Milagre',
    '巻頭言': 'Palavras de abertura',
    '布教座談会': 'Mesa-redonda de difusão',
    '布教定例座談会': 'Mesa-redonda periódica de difusão',
    '定例布教座談会': 'Mesa-redonda periódica de difusão',
    '御浄化物語': 'Histórias de purificação',
    '御説教': 'Sermão',
    '御講話': 'Palestra',
    '忘れかけた信仰に鞭うたれて':
        'Açoitado por uma fé que quase se esquecera',
    '支部の現状と発展の為に': 'Pela situação e o desenvolvimento das filiais',
    '支部長懇談会': 'Encontro de líderes de filial',
    '放送に対する抗議文': 'Protesto contra a emissão',
    '救世と自観明主様（一）': 'A salvação e Meishu-Sama Jikan (I)',
    '新宗教と世界の年齢': 'As novas religiões e a idade do mundo',
    '明主様御言葉 水晶殿御遷座':
        'Palavras de Meishu-Sama: a transferência do Palácio de Cristal',
    '明暗の隔り': 'A distância entre luz e trevas',
    '本教の収入に就て': 'Sobre a receita desta religião',
    '本部事務所奉仕者座談会':
        'Mesa-redonda dos servidores do escritório central',
    '死を覚悟した難病　わずか半年健康体へ':
        'Doença grave com a morte por certa: corpo são em meio ano',
    '法難裁判傍聴記（下）': 'Crônica das audiências do processo (II)',
    '泥棒に入られて': 'Assaltado por um ladrão',
    '注意': 'Aviso',
    '浄化のおかげ': 'Graças à purificação',
    '浄霊法変る': 'Muda o método de Johrei',
    '献金に就て': 'Sobre a contribuição',
    '真理と非真理': 'Verdade e não-verdade',
    '真理を説く': 'Ensinar a verdade',
    '私とサタンとの闘争史': 'História da minha luta com Satanás',
    '私の文章とその他': 'Os meus escritos e outras coisas',
    '私は真理を書く': 'Eu escrevo a verdade',
    '編集後記': 'Nota da redação',
    '花による天国化運動':
        'O movimento de fazer do mundo um paraíso pelas flores',
    '質問応答 御光話': 'Perguntas e respostas: palavras de luz',
    '質問応答 教えの光': 'Perguntas e respostas: a luz do ensinamento',
    '重症の筋炎治る': 'Cura de uma miosite grave',
    '鉱山においての奇蹟の数々': 'Os muitos milagres na mina',
    '霊界の不思議': 'As maravilhas do mundo espiritual',
    '妙智の鍵': 'A chave da sabedoria sutil',
    'ご存じですか': 'Sabia disto?',
    '秋季大祭お導き': 'Orientação para o Grande Culto de Outono',
    '生魚、洗米、塩などの正式のお供えの仕方':
        'O modo formal de oferecer peixe cru, arroz lavado e sal',
    '編集後記（地上天国nº 36）': 'Nota da redação (Tijotengoku nº 36)',
    '編集後記（地上天国 nº 36）': 'Nota da redação (Tijotengoku nº 36)',
    '自観大先生の御日常': 'O dia a dia do grande mestre Jikan',
    '自観大先生との対談': 'Conversa com o grande mestre Jikan',
    '出発': 'Partida',
    '発端': 'O começo',
    '黙示': 'Apocalipse',
    '真善美': 'Verdade, bem e beleza',
    '交通事故から救わる': 'Salvo de um acidente de trânsito',
    '説教者が本教罵倒': 'Um pregador difama esta religião',
    '祖霊との交わり': 'O convívio com os espíritos ancestrais',
    '地上天国建設の土台': 'O fundamento da construção do Paraíso Terrestre',
    '一人対一人では駄目だ': 'Um a um não serve',
    '家庭菜園と無肥料栽培': 'A horta doméstica e o cultivo sem adubo',
    '浄霊とは何か': 'O que é o Johrei',
    '黴菌の発生': 'A origem dos micróbios',
    '八王子の奇蹟': 'O milagre de Hachiōji',
    '村一番の悪田良化す': 'A pior lavoura da aldeia se recupera',
}


# veículos que às vezes aparecem entre 「」 por lapso de composição
VEICULOS_EM_ASPAS = {
    '御教え集': 'Mioshie-shū',
}


def substituir_titulos(texto, mudancas, onde):
    """Substitui as ocorrências de títulos japoneses por tradução/transliteração."""
    def troca_veiculo(m):
        ja = m.group(1)
        if ja in VEICULOS:
            novo = VEICULOS[ja]
        elif ja in OBRAS:
            novo = '*%s*' % OBRAS[ja]
        elif ja in TITULOS:      # artigo citado entre 『』 em vez de 「」
            novo = '*%s*' % TITULOS[ja]
        else:
            return m.group(0)
        mudancas.append((onde, m.group(0), novo))
        return novo

    def troca_titulo(m):
        ja = m.group(1)
        if ja in TITULOS:
            novo = '*%s*' % TITULOS[ja]
        elif ja in OBRAS:                      # obra citada entre 「」
            novo = '*%s*' % OBRAS[ja]
        elif ja in VEICULOS_EM_ASPAS:          # 『』 trocado por 「」 no original
            novo = VEICULOS_EM_ASPAS[ja]
        else:
            return m.group(0)
        mudancas.append((onde, m.group(0), novo))
        return novo

    texto = re.sub(r'『([^』]{1,80})』', troca_veiculo, texto)
    texto = re.sub(r'「([^」]{1,80})」', troca_titulo, texto)
    return texto


def normalizar_espacos(texto, mudancas, onde):
    """Repõe os espaços que os ideogramas dispensavam.

    `Eikōnº 84` -> `Eikō nº 84`;  `*Correspondência do Havaí*Eikō` ->
    `*Correspondência do Havaí*, Eikō` (a citação vinha sem separador).
    """
    for padrao, troca in (
            (r'(\*[^*\n]{1,90}\*)(?=[A-ZÀ-Þ])', r'\1, '),
            (r'(?<=[^\s,.;:(\[\-])(?=n[º°]\s*[0-9])', ' '),
            (r'(?<=[^\s,.;:(\[\-])(?=[0-9]+号)', ' ')):
        novo = re.sub(padrao, troca, texto)
        if novo != texto:
            mudancas.append((onde, texto, novo))
            texto = novo
    return texto


def _chave(s):
    """Compara títulos ignorando caixa, acentos, aspas e pontuação."""
    s = s.lower()
    for a, b in (('á', 'a'), ('à', 'a'), ('â', 'a'), ('ã', 'a'), ('é', 'e'),
                 ('ê', 'e'), ('í', 'i'), ('ó', 'o'), ('ô', 'o'), ('õ', 'o'),
                 ('ú', 'u'), ('ü', 'u')):
        s = s.replace(a, b)
    return re.sub(r'[^a-z0-9 ]', '', s).strip()


def limpar_glosa_orfa(texto, mudancas, onde):
    """Tira a glosa entre parênteses que ficou a repetir o título traduzido.

    `*Mesa-redonda de difusão* (mesa-redonda de difusão)` -> `*Mesa-redonda de
    difusão*`. Só se remove quando o conteúdo equivale ao título; uma glosa
    que acrescente informação fica.
    """
    def troca(m):
        titulo, glosa = m.group(1), m.group(2)
        if _chave(titulo) != _chave(glosa):
            return m.group(0)
        mudancas.append((onde, m.group(0), m.group(1)))
        return m.group(1)
    texto = re.sub(
        r'(\*[^*\n]{1,90}\*)\s*\((?:"|«)?([^()\n]{1,90}?)(?:"|»)?\)', troca, texto)
    # a mesma repetição em forma de citação: «*Sermão*, «sermão»»
    texto = re.sub(r'(\*[^*\n]{1,90}\*),\s*«([^»\n]{1,90})»', troca, texto)
    return texto


def main():
    aplicar = '--aplicar' in sys.argv
    mudancas = []
    relatorio = []

    for rel in FONTES:
        caminho = RAIZ + rel
        linhas = open(caminho, encoding='utf-8').read().split('\n')
        novas = []
        for i, linha in enumerate(linhas, 1):
            original = linha
            # bloco de citação e código ficam como estão: ali o japonês é o
            # original transcrito, que é onde a convenção o admite
            if linha.startswith('>') or linha.startswith('    '):
                novas.append(linha)
                continue
            onde = '%s:%d' % (rel, i)
            linha = substituir_titulos(linha, mudancas, onde)
            linha = limpar_glosa_orfa(linha, mudancas, onde)
            linha = normalizar_espacos(linha, mudancas, onde)
            if linha != original:
                relatorio.append((rel, i, original, linha))
            novas.append(linha)
        if aplicar and novas != linhas:
            open(caminho, 'w', encoding='utf-8').write('\n'.join(novas))

    print('linhas a alterar: %d   substituições: %d' % (len(relatorio), len(mudancas)))
    for rel, i, antes, depois in relatorio[:40]:
        print('\n%s:%d\n  - %s\n  + %s' % (rel.split('/')[-1], i, antes[:160], depois[:160]))
    if len(relatorio) > 40:
        print('\n... e %d linhas' % (len(relatorio) - 40))

    # o que fica por traduzir
    restantes = {}
    for rel, i, antes, depois in relatorio:
        for m in re.finditer(r'[『「]([^』」]{1,80})[』」]', depois):
            ja = m.group(1)
            if re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', ja):
                restantes.setdefault(ja, []).append('%s:%d' % (rel.split('/')[-1], i))
    if restantes:
        print('\n### por traduzir (%d):' % len(restantes))
        for k, v in sorted(restantes.items()):
            print('  %-40s %s' % (k, v[:2]))

    if aplicar:
        registo = json.load(open(LOG, encoding='utf-8'))
        for rel, i, antes, depois in relatorio:
            registo.append({
                'capitulo': 'Aparelho de citação — tradução das fontes',
                'arquivo': rel,
                'antes': antes.strip(),
                'depois': depois.strip()})
        json.dump(registo, open(LOG, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('\nlog: %d -> %d registos' % (len(registo) - len(relatorio), len(registo)))


if __name__ == '__main__':
    main()
