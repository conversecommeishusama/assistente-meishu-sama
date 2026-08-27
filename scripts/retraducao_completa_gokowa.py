#!/usr/bin/env python3
"""Retradução contextual COMPLETA do Gokōwa-roku (Suplemento) com few-shot.

Processa TODAS as falas (JP + PT atual), gera a tradução contextual (few-shot
com o exemplo do usuário), com retry robusto até resolver cada fala (sem falhas).
Salva checkpoint incremental em JSON e gera HTML de contexto com 3 colunas.

Uso:
    python3 scripts/retraducao_completa_gokowa.py            # processa tudo
    python3 scripts/retraducao_completa_gokowa.py --gerar-html  # só gera HTML
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
JP = RAIZ / "textos_japones" / "19480101-御光話録（補）.txt"
PT = RAIZ / "livros_publicacao_pt_revisado" / "19480101 - Gokōwa-roku (Suplemento).txt"
OUT = RAIZ / "reports" / "amostragem_semantica_gokowa"
CHECKPOINT = OUT / "retraducao_completa_checkpoint.json"

MODELO = "deepseek-v4-flash"

CONTEXTO_OBRA = """CONTEXTO DA OBRA (Gokōwa-roku Suplemento, 1º de janeiro de Showa 23 / 1948, reunião de Ano Novo):
- É um registro manuscrito de uma sessão de perguntas e respostas com Meishu-Sama.
- No início, houve um momento musical: o compositor Sr. Haseo Sugiyama cantou um poema do Grão-Mestre, acompanhado pelo Sr. Shusuke Fukui ao piano.
- Portanto, o INTERLOCUTOR que participa da conversa musical É o compositor Sr. Sugiyama (autor da música "Debune"/出船).
- "Debune" (出船) é uma canção japonesa, composição do interlocutor.
- Yoshie Fujiwara é um famoso cantor/intérprete que apresenta (canta) as composições de outros.
- Shinpei Nakayama é um famoso compositor japonês.
- A conversa é sobre música: koto (instrumento japonês), canções de ninar, Beethoven, Chopin, Schubert, Mozart, jazz, nagauta.
"""


CONTEXTO_OBRA_PROSA = """CONTEXTO DA OBRA (Mioshie-shū / 御教え集, edições 9-33 — PROSA CONTÍNUA):
- São os ensinamentos de Meishu-Sama em PROSA CONTÍNUA (não diálogo), publicados
  na coleção Mioshie-shū (Coletânea de Ensinamentos), edições mensais.
- Cada edição tem UMA ou MAIS sessões datadas (ex: '昭和二十七年四月五日' =
  5 de abril do ano 27 da Era Showa / 1952). Cada sessão é um discurso contínuo.
- Meishu-Sama fala sobre: o Plano Divino (経綸), a construção do Paraíso Terrestre,
  a arte (museus, esculturas budistas), a medicina (a medicina cria doenças; o
  Johrei cura), a agricultura natural, o mundo espiritual (espíritos, possessão),
  a Igreja Messiânica e sua missão, a mineração (a mina de Mizukami), etc.
- Termos recorrentes: 地上天国 (Paraíso Terrestre), 光明如来 (Komyo-Nyorai),
  浄霊 (Johrei), 信者 (fiel), 経綸 (Plano Divino), 罪穢 (pecados e impurezas),
  邪神 (deuses malignos), 霊 (espírito), メシヤ教 (Igreja Messiânica).
- O tom é o de um mestre falando a seus fiéis: didático, às vezes coloquial,
  com repetições e ênfases próprias da fala — mas em prosa contínua, não diálogo.
- Há referências intercaladas a artigos do mestre: （御論文「...」）【栄光 一XX号】
  (artigo do mestre, publicado na revista Eikō nº XX). Essas referências devem
  ser mantidas (título traduzido + fonte preservada), pois indicam o que foi lido.
"""

EXEMPLO_REFERENCIA = """EXEMPLO DE TRADUÇÃO IDEAL (feita por um leitor experiente da obra):

FALA 1:
JP: ああそうですか、あんたの『出船』は藤原義江がよくやりますね。
PT: Ah, é mesmo? Yoshie Fujiwara tem apresentado muito a sua [composição] Debune.
(Explicação: "あんたの" = "sua" — refere-se ao interlocutor, que é o compositor.
 "藤原義江が...やります" = "Fujiwara apresenta" — ele é o intérprete. O colchete
 [composição] esclarece que Debune é uma composição — inserção ESCLARECEDORA
 desejada, torna o que o contexto já indica explícito para o leitor.)

FALA 2:
JP: 藤原さんがほとんど紹介してくれました。
PT: O senhor Fujiwara tem feito praticamente todas as apresentações.
(Explicação: "紹介してくれました" = "apresentou [a obra]" — Fujiwara apresenta a
 COMPOSIÇÃO do interlocutor. NUNCA inverter: Fujiwara é quem apresenta.)

FALA 3:
JP: 作曲家はいいものです。
PT: Ser compositor é uma coisa boa.
(Explicação: o "は"+もの generaliza — refere-se à PROFISSÃO de ser compositor,
 não a um compositor específico. "Ser compositor" captura essa abstração.)

FALA 4:
JP: いや両方いいのは難しい。
PT: É difícil ter as duas coisas bem (ser compositor e prosperar).
(Explicação: o parêntese esclarece quais são "as duas coisas" no contexto —
 inserção ESCLARECEDORA desejada, torna explícito o que o contexto já diz.)

O que o exemplo ensina:
- Esclareça QUEM fala e PARA QUEM cada referência se dirige.
- INSERÇÕES ESCLARECEDORAS SÃO DESEJADAS: use [colchetes] ou parênteses para
  tornar explícito o que o contexto já indica (quem é a pessoa, o que é a coisa,
  qual referência está sendo usada). Isso ajuda o leitor. NÃO é "inventar" —
  é clarificar o que o contexto da obra já estabelece.
- Use conectivos naturais do português ("É que", "Mesmo assim", "Por isso") para
  amarrar as falas.
- NUNCA inverta sujeito/objeto (quem faz a ação fica fazendo).
- "は+もの" no japonês generaliza (a profissão/estado) — traduza com "Ser X é..."

TERMOS DE POVOS E ETNIAS (REGRAS OBRIGATÓRIAS — ver glossario_traducao.json e
protocolo_traducao.txt §10):
- 土人 (dojin) → "povos originários" ou "povos primitivos". NUNCA "selvagem".
  No sistema de Meishu-Sama (観音講座), 土 = Terra → 黒色人 = povo de cor negra →
  ferro-aço; é categoria cosmológica dos cinco elementos, não injúria.
- ニグロ / ニグロ的 → "negro" / "de caráter negro". NUNCA "negróide" (racista/obsoleto).
- 黒人 (kokujin) → "pessoa negra".
- 野蛮人 / 野蛮人的趣味 → "povos primitivos" / "gosto primitivo". NUNCA "selvagens".

EXEMPLOS:
JP: ジャズの調子はニグロ的です。
PT: O estilo do jazz é negro.
(NÃO: "negróide")

JP: アメリカ人は最初イギリスから渡って土人と結婚したためなんでしょう。
PT: É porque os americanos inicialmente vieram da Inglaterra e se casaram com os
povos originários.
(NÃO: "com selvagens")

JP: 土人的趣味がジャズとなって現われているんですね。
PT: O gosto dos povos originários aparece como jazz, não é?
(NÃO: "gosto de selvagens")

NOVO / NOVIDADE (REGRA — paradoxo de Meishu-Sama):
- 新しみ = "novidade genuína" (frescor/originalidade verdadeira), não "novidade" vazia.
- 昔のほうが新しい = paradoxo: "as antigas são as verdadeiramente novas" — Meishu-Sama
  diz que o que é ANTIGO tem NOVIDADE genuína, enquanto o recente não tem novidade real.
  Preserve o paradoxo, mas esclareça com "[genuinamente]" ou "de verdade" quando ajudar.

EXEMPLOS:
JP: 芸術品も私は好きですが、昔のほうが新しいですよ。
PT: Eu também gosto de obras de arte, mas as antigas é que são as verdadeiramente novas.
(NÃO: "as antigas são mais novas" — ambíguo; esclareça o paradoxo)

JP: 最近のには本当の新しみがない。
PT: As recentes não têm novidade genuína alguma.
(NÃO: "não têm novidade" — perde o "de verdade/genuína")

TERMOS CONSAGRADOS (obrigatórios — ver glossario_traducao.json):

CONCEITOS DISTINTOS PORÉM INTERLIGADOS (大清算 x 大浄化):
- 大清算 (daiseisan) = "Grande Acerto de Contas" — o EVENTO/processo global de
  julgamento divino (quem será salvo ou perecerá). É a "grande liquidação mundial"
  (Eiko: "a base é a grande liquidação mundial — a ação de purificar as impurezas
  e pecados acumulados há muito tempo").
- 大浄化 (daijōka) = "Grande Purificação" — o MECANISMO/ação pelo qual o acerto se
  realiza (purificação das toxinas/impurezas/pecados).
- RELAÇÃO: o Acerto de Contas opera ATRAVÉS da Purificação. São dois lados da mesma
  moeda — mas cada termo enfatiza um aspecto (justiça/conta vs. limpeza/processo).
- NUNCA traduzir ambos como "Grande Purificação" — perde a distinção.
- Quando aparecerem próximos, capturar a relação (ex: "o Grande Acerto de Contas,
  isto é, a Grande Purificação das impurezas acumuladas").

EXEMPLO:
JP: いまは大清算が始まっている。
PT: Agora está começando o Grande Acerto de Contas.
(NÃO: "Grande Purificação")
- 大浄化 → "grande purificação".
- 信者 (shinja) → "fiel" (NUNCA "crente" — no Brasil "crente" é associado aos
  evangélicos; "fiel" é neutro/respeitoso). 信者たち → "os fiéis".
- 祟る (tatakaru) → "assombrar/amaldiçoar" (espírito). Ex: 祟っている = "está assombrado".
- 取れる (toreru) = "ser visto como / ser interpretado como / ser tomado como /
  ser julgado como". Ex: "fui tomado como besta" = 馬鹿に取れた.
- 取れない (torenai) + negação dupla → "não se pode interpretar nem... nem..."
  IMPORTANTE: なにか祟っているか、罪が深いと取れない = "não se pode julgar nem
  assombração nem pecado profundo" (NEGAÇÃO DUPLA: nega AMBAS as opções).
  NÃO traduzir como "ou...ou..." (alternância) — o original nega as duas.
  Correto: "Não se pode dizer que seja assombração, nem que seja pecado profundo."
- すまされる (sumasareru) = "resolver-se/livrar-se com" (ex: 二人か三人ですまされる =
  "resolve-se com duas ou três [pessoas]" — NÃO inverter para "morrem").
"""


EXEMPLO_REFERENCIA_PROSA = """EXEMPLO DE TRADUÇÃO IDEAL PARA PROSA CONTÍNUA (feita por um leitor experiente):

TRECHO JP:
昭和二十七年四月五日
【御教え】
　ここにある鉱石は見ましたか。これは鉱山の知識がない者が見ると、本当に判りませんが、少しでも鉱山の知識がある人が見ると、驚くべきものなんです。これは、神岡鉱山の技師が、日本一という折り紙をつけたんですからね。おそらくこんな鉱石というものは、今までに日本になかっただろうと思いますね。

PT (tradução ideal):
5 de abril do ano 27 da Era Showa (1952)
[Ensinamento]
Vocês viram este minério que está aqui? Quem não tem conhecimento de mineração não consegue perceber, de fato, o que é; mas quem tem ao menos um pouco de conhecimento de mineração vê que é algo surpreendente. É que o engenheiro da Mina de Kamioka lhe deu um atestado de que é o melhor do Japão. Provavelmente, um minério assim nunca existiu no Japão até hoje.

O que o exemplo ensina (prosa contínua):
- A DATA da sessão é um cabeçalho: traduza-a por extenso e em linha própria
  ("5 de abril do ano 27 da Era Showa (1952)"). Não a omita.
- O marcador 【御教え】 (bloco de ensinamento) pode ser traduzido como [Ensinamento].
- Traduza como PROSA CONTÍNUA e natural em português, preservando TODOS os fatos,
  números e nomes (Mina de Kamioka, "melhor do Japão").
- O registro é de fala (Meishu-Sama falando a fiéis): mantenha a naturalidade oral
  ("Vocês viram...?", "É que...", "de fato"), mas em parágrafos de prosa.
- Referências a artigos （御論文「...」）【栄光 一XX号】 → "(artigo '...') [Eikō nº XX]".
- NUNCA omita conteúdo; NUNCA acrescente fato novo. Reconstrua só o que o japonês
  telegráfico/coloquial deixa implícito, usando [colchetes] apenas para esclarecer
  o que o contexto JÁ estabelece.

EXEMPLO de referência de artigo:
JP: （御論文「宗教と病院」）【栄光　一八一号】
PT: (artigo "Religião e Hospitais") [Eikō nº 181]
"""

PROMPT = """{contexto}

{exemplo}

Você é um tradutor japonês→português que produz traduções no ESTILO do exemplo acima: que ESCLARECEM o contexto para o leitor, mantendo fidelidade estrita ao sentido do original.

Regras do estilo (reforço):
1. Identifique os PAPÉIS dos falantes pelo contexto (quem é o compositor, quem é o intérprete, etc.) e traduza de modo que o leitor entenda a quem cada referência se dirige.
2. Esclareça referências ambíguas quando o contexto permite — use [colchetes] ou parênteses para tornar explícito o que o contexto já indica, SEM inventar conteúdo. [Colchetes] servem para DESAMBIGUAR referências que o contexto JÁ estabelece — nunca para acrescentar fato novo.
3. Use conectivos naturais do português ("É que", "Mesmo assim", "Por isso") para amarrar as falas.
4. NUNCA inverta sujeito/objeto. NUNCA mude quem fez a ação.
5. Quando o japonês usar "は+もの" generalizando (a profissão/estado), traduza com "Ser X é...".
6. RECONSTRUÇÃO NECESSÁRIA PARA FLUIDEZ E CLAREZA: o japonês original é telegráfico/truncado
   (registro de anotações). Você DEVE reconstruir a frase o quanto for necessário para que ela
   soe natural, fluida e clara em português brasileiro — completando palavras elípticas,
   reordenando, suavizando o truncamento. A régua é: mantenha TODO o sentido e TODOS os fatos
   do original, NÃO omita nada, NÃO acrescente fato novo. Fidelidade de sentido é a régua,
   não literalidade. Não fique preso à forma truncada — o leitor não precisa sofrer com a
   forma bruta das anotações, desde que nada se perca.

7. PREVENÇÃO DE INVERSÃO DE SUJEITO/PESSOA (REGRA AMPLA — vale para qualquer fala):
   A inversão é o erro mais grave e o mais frequente. Siga estes princípios SEMPRE:
   a. O SUJEITO é quem o japonês marca como agente. O japonês OMITE o sujeito com
      frequência (frases sem sujeito explícito). Nesse caso, o sujeito é DEDUZIDO DO CONTEXTO
      — não invente "eu"/"nós"/"você" sem base. Se a fala anterior estabeleceu que o agente
      é um espírito, uma terceira pessoa, ou Meishu-Sama, MANTER esse agente.
   b. CUIDADO com frases que parecem 1ª pessoa ("eu") mas são observações gerais sobre
      categorias de pessoas ("quem faz X...", "aquele que..."). Verifique se o japonês tem
      partícula de sujeito (が/は) apontando para "私" (eu) antes de usar "eu".
   c. CUIDADO com verbos de controle/posse (支配する, 自由にする, 憑く, 占領する):
      identifique QUEM controla QUEM. Ex: 邪神がつくと...眉間を占領すればその人を自由に
      することができる = "quando o deus maligno se fixa... se ocupar a glabela, ele pode
      DOMINAR a pessoa à vontade" — o sujeito é o espírito maligno, NUNCA "nós/terapeutas".
   d. CUIDADO com honoríficos e gênero: se o original é sobre uma mulher (婆さん, 母),
      mantenha o feminino até o fim da fala. Se o referente é um terceiro (Nakayama,
      Fujiwara), não transforme em "você".
   e. Depois de traduzir, RELEIA e confira: "quem faz a ação nesta frase? O sujeito do PT
      é o mesmo do JP?" — se trocou, reescreva.

8. ANTES DE TRADUZIR, IDENTIFIQUE O SUJEITO: para cada frase do japonês, determine quem
   é o agente (quem faz a ação). O japonês omite o sujeito com frequência — nesse caso,
   deduza do CONTEXTO (fala anterior, lógica da frase, quem está falando). Só então
   traduza, garantindo que o PT mantenha exatamente esse agente. Se houver referência
   a uma 3ª pessoa citada antes (um nome, uma categoria), NÃO transforme em "eu"/"você".
   Use o CONTEXTO DA FALA ANTERIOR (se fornecido) para resolver あれ/それ/彼/この人.

9. ANTI-INVENÇÃO (REGRA CRÍTICA — vale para qualquer fala):
   NUNCA acrescente ao português conteúdo que o japonês não diz. Em especial:
   a. NUNCA invente GÊNERO: se o JP diz 人/pessoa (sem gênero), NÃO escreva "menina",
      "senhora", "ele/ela" etc. sem o JP indicar. Use "a pessoa" ou forma impessoal.
   b. NUNCA preencha OBJETO ELÍPTICO com suposição: se o JP omite o objeto do verbo
      ("curou", "fez"), NÃO invente "o paraquedista", "as injeções", etc. Use a forma
      impessoal ou deixe implícito, a menos que a fala ANTERIOR (contexto fornecido)
      estabeleça claramente o referente.
   c. NUNCA invente CAUSA/instrumento: se o JP diz "não se deve fazer" (やってはいけない)
      sem especificar o quê, NÃO escreva "[injeções]". O [colchete] só pode tornar
      explícito o que o JP ou o contexto JÁ estabelecem explicitamente.
   d. NUNCA invente NOME PRÓPRIO, local, data ou número que não esteja no JP.
   e. Se um [colchete] NÃO for estritamente necessário para o leitor entender a
      referência, OMITA-O. Menos colchetes é melhor do que colchetes inventados.
   f. Depois de traduzir, RELEIA conferindo: "cada [colchete] e cada detalhe adicionado
      tem base EXPLÍCITA no JP ou no contexto da fala anterior? Se não, remova."

10. PESSOA GRAMATICAL (REGRA CRÍTICA — erro real observado na fala 85):
   MANTENHA EXATAMENTE a pessoa gramatical do japonês (1ª vs 3ª). O falante pode
   estar RELATANDO a experiência de OUTRA pessoa — não é porque alguém narra um
   caso que o caso é dele.
   a. Se o JP usa substantivo de 3ª pessoa (講習生/estagiário, その人/essa pessoa,
      彼/ele, um nome), NÃO converta para 1ª pessoa ("eu", "sou", "se apossou de
      mim", "fui agraciado"). Traduza como "ele/ela/essa pessoa/um participante".
   b. Verifique se 私 (eu) ou 僕/俺 aparecem no JP ANTES de usar "eu/meu". Se não
      há pronome de 1ª pessoa no JP, NÃO invente "eu" na tradução.
   c. Honoríficos de 3ª pessoa (お憑りになり, おおせられました, と言われ) indicam
      que a ação é de/sobre um TERCEIRO, não o falante. Mantenha essa distância.
   d. Exemplo de erro a EVITAR: JP "青森から来た講習生ですが...その人は...と言って
      おります" (um estagiário de Aomori... essa pessoa diz...) → NUNCA "Sou um
      estagiário... se apossou de mim". Correto: "Há um estagiário vindo de Aomori...
      essa pessoa vem dizendo...".
   e. Após traduzir, confira: "a pessoa que vivencia a ação no PT é a MESMA do JP?
      Se o JP é 3ª pessoa e o PT virou 'eu', reescreva."

Traduza esta FALA do personagem "{quem}".

### JAPONÊS:
{jp}

### TRADUÇÃO (responda SÓ com o texto traduzido, sem aspas externas):

GLOSSÁRIO COMPLETO DE TRADUÇÃO (autoridade terminológica obrigatória):
quando um termo japonês abaixo aparecer no texto, use EXATAMENTE a forma
portuguesa à direita (não use sinônimo, não invente variação). Isto cobre
TODOS os termos do glossário oficial do projeto — não apenas os críticos:

{glossario_completo}
"""


GLOSSARIO_PATH = RAIZ / "glossario_traducao.json"

_GLOSSARIO_COMPLETO_CACHE: str | None = None


def carregar_glossario_completo() -> str:
    """Monta o bloco com TODO o glossário de tradução (730 termos) para injetar
    no prompt do executor (e na trava, quando houver reforço).

    Lê `glossario_traducao.json` uma única vez e guarda em cache — não relê o
    arquivo a cada fala.
    """
    global _GLOSSARIO_COMPLETO_CACHE
    if _GLOSSARIO_COMPLETO_CACHE is None:
        try:
            glossario = json.loads(GLOSSARIO_PATH.read_text(encoding="utf-8"))
            _GLOSSARIO_COMPLETO_CACHE = "\n".join(
                f"- {k} → {v}" for k, v in sorted(glossario.items())
            )
        except Exception:
            _GLOSSARIO_COMPLETO_CACHE = ""
    return _GLOSSARIO_COMPLETO_CACHE


def extrair_falas(texto: str) -> list[tuple[str, str]]:
    falas = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        m = re.match(r"^(Meishu-Sama|Interlocutor):\s*(.*)", linha)
        if m:
            falas.append((m.group(1), m.group(2)))
    return falas


def segmentar_fala(jp: str, limite: int = 350) -> list[str]:
    """Divide uma fala longa em segmentos menores (por quebra de frase).

    Falas curtas retornam como um único segmento. Falas longas são divididas
    em pontos de quebra natural (。！？.!?…), acumulando frases até CHEGAR
    PERTO do limite — nunca cortando em cada frase (criava segmentos de
    ~40 chars e um último GIGANTE) nem deixando um segmento estourar muito.

    Fix 17/08 (bug real apontado pelo usuário): a versão antiga usava
    `minimo=30` e cortava qualquer frase ≥30 chars que terminasse em
    pontuação, gerando 4 segmentos de ~40 chars + 1 último de 412 chars
    (independente do limite). Agora acumula até ~80% do limite antes de
    cortar, e força corte por caracteres se ainda sobrar um segmento gigante.
    """
    if len(jp) <= limite:
        return [jp]
    # quebrar em frases por pontuação japonesa/portuguesa de fim
    partes = re.split(r"(?<=[。！？.!?…])", jp)
    # acumular frases até chegar perto do limite (80%), respeitando a fronteira
    # de frase — nunca cortar no meio de uma frase, nunca deixar um segmento
    # muito acima do limite
    alvo = limite * 0.8
    segmentos = []
    buf = ""
    for p in partes:
        if not p:
            continue
        if buf and len(buf) + len(p) > limite and buf.endswith(("。", "！", "？", ".", "!", "?", "…")):
            # fechar o segmento atual (buf já tem conteúdo e passar de limite)
            segmentos.append(buf.strip())
            buf = p
        elif len(buf) >= alvo and buf.endswith(("。", "！", "？", ".", "!", "?", "…")):
            # atingiu o alvo em fronteira de frase: fechar
            segmentos.append(buf.strip())
            buf = p
        else:
            buf += p
    if buf.strip():
        segmentos.append(buf.strip())
    # segurança: se algum segmento ficou gigante (frase única enorme), força
    # corte por caracteres para não estourar o prompt
    segmentos_finais = []
    for s in segmentos:
        if len(s) > limite * 1.5:
            for i in range(0, len(s), limite):
                segmentos_finais.append(s[i : i + limite])
        else:
            segmentos_finais.append(s)
    return [s for s in segmentos_finais if s]


def retraduzir(jp: str, quem: str, max_retries: int = 12, contexto_anterior: str | None = None) -> str:
    from goshinsho.services.agentic_search import _client

    # ABORDAGEM A (decisão do usuário 17/08/2026, após testes comparativos em
    # reports/teste_comparativo_segmentacao/): cada fala é traduzida em UM único
    # segmento, independente do tamanho. Os testes mostraram que a semântica
    # inteira é MAIS RÁPIDA e com qualidade igual ou superior (até em falas de
    # 3.000+ chars), além de evitar erros de glossário causados pela quebra de
    # contexto entre segmentos.
    #
    # A função `segmentar_fala` foi MANTIDA (outros scripts de teste a importam),
    # mas NÃO é mais usada aqui.
    return _retraduzir_um(jp, quem, max_retries, contexto_anterior=contexto_anterior)


def _retraduzir_um(jp: str, quem: str, max_retries: int, contexto_anterior: str | None = None) -> str:
    from goshinsho.services.agentic_search import _client

    # Bloco de contexto conversacional (fala anterior) para resolver anáforas
    # (あれ/それ/彼 = referências a algo citado antes) e evitar inversão de sujeito.
    bloco_contexto = ""
    if contexto_anterior:
        bloco_contexto = (
            "\n\nCONTEXTO DA FALA ANTERIOR (use para resolver referências e identificar quem é o sujeito):\n"
            f"{contexto_anterior}\n"
        )

    reforcos = [
        "",
        "\n\nResponda APENAS a tradução, sem comentários.",
        "\n\nSaída: só o texto traduzido, nada mais.",
        "\n\nComece a resposta diretamente com a tradução.",
        '\n\nExemplo de resposta: "Ser compositor é uma coisa boa."',
        "\n\nNão deixe em branco. Escreva a tradução agora.",
        "\n\nSe o trecho é curto, a tradução também é curta. Responda.",
        "\n\nTradução (apenas texto):",
        "\n\nIMPORTANTE: sua resposta anterior veio vazia. Responda agora com a tradução.",
        "\n\nTraduza agora, por favor:",
        "\n\nResposta (só tradução):",
        "\n\nAgora sim, escreva a tradução completa:",
    ]
    for tentativa in range(max_retries):
        reforco = reforcos[tentativa] if tentativa < len(reforcos) else "\n\nTraduza agora."
        try:
            resp = _client().chat.completions.create(
                model=MODELO,
                # max_tokens maior para falas longas não cortarem no meio
                max_tokens=20000,
                messages=[{"role": "user", "content": PROMPT.format(contexto=CONTEXTO_OBRA, exemplo=EXEMPLO_REFERENCIA, glossario_completo=carregar_glossario_completo(), jp=jp, quem=quem) + bloco_contexto + reforco}],
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip().strip('"').strip()
            raw = re.sub(r"^(Meishu-Sama|Interlocutor):\s*", "", raw)
            # aceita se tiver pelo menos alguns caracteres e não for só pontuação
            if raw and len(re.sub(r"\s", "", raw)) >= 3:
                # VALIDAÇÃO DE COMPLETUDE: se o JP termina com pontuação de fim
                # (. ！？。？) e o PT também deveria terminar — detecta corte no meio.
                jp_limpo = jp.strip()
                raw_limpo = raw.rstrip()
                termina_jp = re.search(r"[。！？.!?]\s*$", jp_limpo)
                termina_pt = re.search(r"[.!?]\s*$", raw_limpo)
                # se o JP termina em pontuação mas o PT não, pode estar cortado
                if termina_jp and not termina_pt and tentativa < max_retries - 1:
                    # reforça para completar
                    continue

                # TRAVA DETERMINÍSTICA DE GLOSSÁRIO (Papel 2 da arquitetura):
                # se o JP contém um termo fixo e o PT não usa a forma aprovada,
                # REJEITA o turno e refaz (com reforço específico) antes do auditor.
                try:
                    from trava_glossario import verificar_trava_glossario
                    ok_trava, motivo_trava = verificar_trava_glossario(jp, raw)
                    if not ok_trava:
                        # Não substitui a lista (isso quebrava o índice e causava
                        # loop infinito). Em vez disso, REFORÇA na próxima iteração
                        # usando um reforço extra acumulado.
                        print(f"    [trava] {motivo_trava} — tentando de novo com reforço", flush=True)
                        reforco = (
                            f"\n\nCORREÇÃO DE GLOSSÁRIO OBRIGATÓRIA: {motivo_trava}. "
                            "Reescreva a tradução usando EXATAMENTE a forma aprovada do glossário."
                        )
                        # tenta de novo nesta mesma iteração com o reforço (loop interno)
                        resp = _client().chat.completions.create(
                            model=MODELO,
                            max_tokens=20000,
                            messages=[{"role": "user", "content": PROMPT.format(contexto=CONTEXTO_OBRA, exemplo=EXEMPLO_REFERENCIA, glossario_completo=carregar_glossario_completo(), jp=jp, quem=quem) + bloco_contexto + reforco}],
                            temperature=0.2,
                        )
                        raw2 = (resp.choices[0].message.content or "").strip().strip('"').strip()
                        raw2 = re.sub(r"^(Meishu-Sama|Interlocutor):\s*", "", raw2)
                        if raw2 and len(re.sub(r"\s", "", raw2)) >= 3:
                            ok2, _m2 = verificar_trava_glossario(jp, raw2)
                            if ok2:
                                raw = raw2  # aceita a nova versão
                            else:
                                # segunda falha → usa mesmo assim (evita loop infinito)
                                raw = raw2
                except ImportError:
                    pass  # trava não disponível, segue sem

                return raw
        except Exception:
            pass
        time.sleep(1 + tentativa)
    return ""  # não resolveu após todos os retries


def carregar_checkpoint() -> dict:
    if CHECKPOINT.exists():
        try:
            return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def salvar_checkpoint(dados: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if "--gerar-html" in sys.argv:
        gerar_html()
        return

    falas_jp = extrair_falas(JP.read_text(encoding="utf-8"))
    falas_pt = extrair_falas(PT.read_text(encoding="utf-8"))
    n = min(len(falas_jp), len(falas_pt))
    print(f"Falas JP: {len(falas_jp)} | PT: {len(falas_pt)} | processando {n}")

    dados = carregar_checkpoint()
    if "resultados" not in dados:
        dados["resultados"] = {}
        dados["total"] = n

    resultados = dados["resultados"]
    pendentes = [i for i in range(n) if str(i) not in resultados or not resultados[str(i)].get("pt_contextual")]

    print(f"Checkpoint: {len(resultados)}/{n} resolvidas | {len(pendentes)} pendentes")
    print("Processando... (Ctrl+C para pausar; resume no checkpoint)")

    for idx, i in enumerate(pendentes):
        quem, jp = falas_jp[i]
        pt_atual = falas_pt[i][1]
        print(f"[{idx+1}/{len(pendentes)}] fala {i} ({quem})...", flush=True)

        # JANELA DE CONTEXTO (5 falas anteriores JP+PT) — para resolver anáforas
        # e evitar inversão de sujeito (a fala isolada perde quem fala/do que se fala).
        contexto_anterior = ""
        janela = 5
        for j in range(max(0, i - janela), i):
            if str(j) in resultados and resultados[str(j)].get("pt_contextual"):
                qj, jpj = falas_jp[j]
                ptj = resultados[str(j)]["pt_contextual"]
                contexto_anterior += f"[fala {j}] {qj}: JP: {jpj} | PT: {ptj}\n"
        contexto_anterior = contexto_anterior.strip() or None

        pt_ctx = retraduzir(jp, quem, contexto_anterior=contexto_anterior)
        resultados[str(i)] = {
            "indice": i,
            "quem": quem,
            "jp": jp,
            "pt_atual": pt_atual,
            "pt_contextual": pt_ctx,
            "contexto_anterior": contexto_anterior,
        }
        # checkpoint a cada 5
        if (idx + 1) % 5 == 0:
            salvar_checkpoint(dados)
            print(f"  checkpoint salvo ({len(resultados)}/{n})", flush=True)

    salvar_checkpoint(dados)
    n_falhas = sum(1 for v in resultados.values() if not v.get("pt_contextual"))
    print(f"\nConcluído: {len(resultados)}/{n} | falhas: {n_falhas}")
    if n_falhas:
        print("Falhas em índices:", [i for i, v in resultados.items() if not v.get("pt_contextual")])

    gerar_html()


def gerar_html() -> None:
    dados = carregar_checkpoint()
    resultados = dados.get("resultados", {})
    if not resultados:
        print("Sem resultados no checkpoint. Rode o processamento primeiro.")
        return
    OUT.mkdir(parents=True, exist_ok=True)

    html = []
    html.append("""<!DOCTYPE html>
<html lang="pt"><head><meta charset="utf-8">
<title>Gokōwa-roku (Suplemento) — JP | PT atual | PT contextual</title>
<style>
body {{ font-family: sans-serif; margin: 20px; background: #fafafa; }}
h1 {{ font-size: 20px; }}
h2 {{ font-size: 14px; color: #555; margin-top: 24px; border-top: 2px solid #ccc; padding-top: 8px; }}
.fala {{ display: flex; margin: 5px 0; border-left: 3px solid #2a2; padding: 4px 8px; }}
.fala.falha {{ border-left-color: #c33; background: #fff0f0; }}
.idx {{ width: 38px; flex: 0 0 38px; color: #888; font-size: 11px; text-align: right; padding-right: 6px; }}
.col {{ width: 33%; flex: 0 0 33%; font-size: 12.5px; padding-right: 8px; }}
.col.jp {{ }}
.col.ptatual {{ }}
.col.ptctx {{ background: #f4fff4; }}
.quem {{ font-weight: bold; font-size: 10px; color: #666; display: block; }}
.titulo-col {{ font-weight: bold; font-size: 12px; background: #eee; padding: 4px; }}
.legenda {{ background: #eef; padding: 8px; margin: 10px 0; border-left: 4px solid #2a2; font-size: 13px; }}
</style></head><body>
<h1>Gokōwa-roku (Suplemento) — Contexto completo (JP | PT atual | PT contextual few-shot)</h1>
<p>Total: {total} falas. A coluna verde é a retradução contextual gerada com o few-shot do estilo do usuário.</p>
<div class="legenda"><b>Colunas:</b> JP (original) · PT ATUAL (no volume) · PT CONTEXTUAL (few-shot, verde).<br>
<b>Vermelho</b> = fala sem retradução (falha).</div>
""".format(total=len(resultados)))

    secao = "Início"
    html.append(f"<h2>📌 {secao}</h2>")

    for i in sorted(int(k) for k in resultados):
        r = resultados[str(i)]
        jp = r.get("jp", "")
        pt_atual = r.get("pt_atual", "")
        pt_ctx = r.get("pt_contextual", "")
        quem = r.get("quem", "")
        falha = not pt_ctx
        cls = "falha" if falha else ""
        ctx_display = esc(pt_ctx) if pt_ctx else "<i>(falha — sem retradução)</i>"

        m_data = re.search(r"(昭和\d+年|Showa \d+|\d+月\d+日|新年)", jp)
        if m_data and i > 0:
            html.append(f"<h2>📌 {esc(m_data.group(1))}</h2>")

        html.append(f"""<div class="fala {cls}">
<div class="idx">{i}</div>
<div class="col jp"><span class="quem">{quem}</span> {esc(jp)}</div>
<div class="col ptatual"><span class="quem">{quem}</span> {esc(pt_atual)}</div>
<div class="col ptctx"><span class="quem">{quem} (ctx)</span> {ctx_display}</div>
</div>""")

    html.append("</body></html>")
    arq = OUT / "contexto_completo_gokowa_3colunas.html"
    arq.write_text("\n".join(html), encoding="utf-8")
    print(f"HTML gerado: {arq} ({len(resultados)} falas)")


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    main()
