"""Base de conhecimento do PRÓPRIO site — para o chat responder dúvidas de uso.

Motivação (2026-09-11, achado real do painel de perguntas):
Uma usuária viu "📖 Leitura Colaborativa" no menu do app, ao lado do Chat, e
perguntou ao chat o que era. O chat — que só sabe interpretar os Escritos —
procurou "leitura colaborativa" no acervo doutrinário, não encontrou, e
respondeu que o termo "não é um conceito do acervo" e que "nada nas instruções
deste agente fala em leitura colaborativa". Na segunda vez foi mais enfático:
"qualquer coisa que eu dissesse aqui seria invenção".

As respostas estavam honestas e tecnicamente corretas — e inúteis. O produto
oferecia algo na tela e o assistente negava a existência disso.

Este módulo é a fonte única de verdade sobre o que o site OFERECE. O chat passa
a consultá-lo (ver `is_site_help_question`), em vez de buscar no acervo.

⚠️ MANUTENÇÃO: ao adicionar/renomear uma funcionalidade, atualize aqui. Se este
texto divergir da tela, o chat volta a mentir — só que de forma mais sutil.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Conteúdo institucional resumido. Descrições CURTAS de propósito: o prompt do
# chat precisa disto inline, e o objetivo é orientar (onde fica, para que
# serve), não substituir a leitura dos documentos completos.
# ---------------------------------------------------------------------------

SITE_FEATURES = """
**Chat (esta conversa).** Você faz perguntas sobre os Escritos de Meishu-Sama
e recebe respostas buscadas no acervo. Dois modos: resposta direta (por tema,
com uma citação confirmatória) e resposta aprofundada (com citações literais
mais extensas). Também é possível pedir o texto integral de um ensinamento
nomeado.

**Leitura Colaborativa (menu "📖").** Não é um chat — é uma BIBLIOTECA de
leitura. Reúne os ensinamentos publicados por Meishu-Sama em vida, em tradução
própria deste projeto. O que se faz lá:
- navegar por duas categorias: Palavra Oral e Palavra Escrita;
- ler o texto, ouvido em voz alta por um botão de áudio (🔊);
- o progresso de leitura é salvo e retomado de onde parou;
- o leitor pode selecionar um trecho e enviar uma observação para a equipe
  (é o lado "colaborativo": o leitor aponta erros de tradução ou dúvidas).
O nome diz respeito à COLABORAÇÃO DO LEITOR na revisão do texto — não a uma
leitura conjunta mediada por IA.

**Fórum de Estudos (quando habilitado).** Espaço de discussão entre leitores.

**Busca/favoritos/histórico.** O histórico das conversas fica associado à conta
(para retomar de qualquer aparelho); respostas podem ser marcadas como
favoritas.

**Conta.** O cadastro é gratuito. Hoje o acesso é gratuito com perguntas
ilimitadas — não há cobrança obrigatória.

**Doações.** Existem, são voluntárias e servem para cobrir o custo de
infraestrutura. Não bloqueiam nenhuma funcionalidade.
"""

SITE_DOCUMENTS = """
**Termos de Uso** (/termos-de-uso) — condições de uso do serviço, propriedade
intelectual e limites de responsabilidade. O item 7 trata do domínio público do
material usado.

**Política de Privacidade** (/privacidade) — o que é coletado e por quê. Em
resumo: e-mail e senha no cadastro (a senha é gerida pelo Supabase, este projeto
não a vê); as perguntas e respostas ficam salvas associadas à conta para manter o
histórico das conversas; dados técnicos de segurança são guardados como hash
(não o IP em texto legível); o cookie de publicidade (Meta Pixel) só é carregado
com consentimento explícito e pode ser recusado. Há contato de suporte para
pedidos relativos a dados.

**Aviso de Independência** (/aviso-independencia) — o Goshinsho é um projeto
pessoal e independente. Não é produto oficial e não é supervisionado,
autorizado, patrocinado ou endossado pela Igreja Messiânica Mundial (Sekai
Kyusei Kyo) nem por qualquer outra igreja ou entidade que siga os ensinamentos
de Meishu-Sama. A tradução é feita por IA com protocolo e glossário próprios e,
em muitos pontos, diverge das traduções institucionais; o critério adotado foi a
literalidade em relação ao original japonês. As respostas são geradas por IA e
podem conter imprecisões.
"""

_AVISO = (
    "Para os documentos institucionais completos, consulte as páginas do site "
    "(Termos de Uso, Política de Privacidade e Aviso de Independência)."
)


# ---------------------------------------------------------------------------
# Detecção. Conservadora: só dispara quando a pergunta é claramente SOBRE o
# produto/documentos, com termos que praticamente não ocorrem nas perguntas
# doutrinárias. Um falso positivo aqui desviaria uma pergunta legítima sobre os
# Escritos para a resposta sobre o site — por isso a lista de nomes próprios
# exige o contexto de "o que é / como funciona".
# ---------------------------------------------------------------------------

# Recursos do site, nomeados como na tela.
_RECURSO_NOMEADO = re.compile(
    r"leitura\s+colaborativa|leitura\s+cooperativa|"
    r"f[óo]rum\s+de\s+estudos|"
    r"bot[ãa]o\s+de\s+[áa]udio|"
    r"aviso\s+de\s+independ[êe]ncia|"
    r"pol[íi]tica\s+de\s+privacidade|"
    r"termos\s+de\s+uso|"
    r"meta\s+pixel",
    re.IGNORECASE,
)

# Documento institucional citado por caminho.
_ROTA_DOCUMENTO = re.compile(
    r"/privacidade|/termos-de-uso|/aviso-independencia|/doacao",
    re.IGNORECASE,
)

# Perguntas de uso do próprio produto.
_USO_DO_SITE = re.compile(
    r"como\s+(?:eu\s+)?(?:uso|utilizo|funciona|fa[çc]o)\s+(?:isso\s+)?"
    r"(?:aqui|o\s+(?:site|aplicativo|app|goshinsho|chat|agente))|"
    r"o\s+que\s+(?:voc[êe]|vc|esse\s+(?:site|agente|chat))\s+(?:oferece|faz)|"
    r"para\s+que\s+serve\s+(?:o\s+chat|a\s+leitura|isso)|"
    r"como\s+(?:eu\s+)?navego|"
    r"quais\s+(?:s[ãa]o\s+)?(?:as\s+)?funcionalidades|"
    r"o\s+que\s+(?:d[áa]|tem)\s+(?:para\s+)?(?:ler|ouvir)|"
    r"posso\s+baixar\s+(?:o\s+)?(?:[áa]udio|texto)|"
    r"como\s+(?:me\s+)?cadastro|"
    r"como\s+fa[çc]o\s+uma\s+doa[çc][ãa]o|"
    r"quem\s+(?:est[áa]\s+)?(?:por\s+tr[áa]s|fez|criou)\s+(?:o\s+)?(?:site|goshinsho)",
    re.IGNORECASE,
)

# Ouvir/baixar o áudio dos textos (recurso da Leitura).
# Cobre a forma direta ("áudio do texto") e a invertida ("ouço o texto").
#
# ⚠️ Conjugações: "ouço" é o-u-ç-o (NÃO tem "v" — foi um bug real: o padrão
# "ouv[çc]o" exigia um "v" inexistente). Inclui ouvir/ouve/escuto/toco.
_AUDIO = re.compile(
    r"(?:ou[çc]o|ouve|ouvir|escut[oa]|baixar|baixo|toc[oa]r?|download)"
    r"[^?\n]{0,30}\b[áa]udio\b|"
    r"\b[áa]udio\b[^?\n]{0,30}(?:ouvir|escutar|baixar|no\s+carro|celular)|"
    r"(?:ou[çc]o|ouve|ouvir|escut[oa])[^?\n]{0,20}\b(?:texto|escritos?|obra)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------
# Relação com a Igreja: pergunta que só faz sentido para o PRODUTO.
# Exige DOIS elementos — o produto (site/projeto/vocês) E o vínculo
# (oficial/vinculado/autorizado). Só "igreja" não basta: a Igreja é assunto
# doutrinário e histórico legítimo ("houve por parte da Igreja uma grande
# parcimônia..."), e capturá-la aqui tiraria a pergunta do acervo.
# ---------------------------------------------------------------
_PRODUTO = re.compile(
    r"\b(?:site|aplicativo|app|goshinsho|plataforma)\b|"
    r"\b(?:este|esse|o)\s+projeto\b|"
    r"\bvoc[êe]s?\b|\bvc\b",
    re.IGNORECASE,
)
_VINCULO = re.compile(
    r"\boficia(?:l|is|lmente)\b|\bvincul(?:o|ada|ado|ad[oa]s?)\b|"
    r"\bauthoriz|autorizad[oa]s?\b|\bendossad[oa]s?\b|\bpatrocinad[oa]s?\b|"
    r"\bda\s+igreja\b|\bcom\s+a\s+igreja\b|\bpertence\s+(?:à|a)\s+igreja\b",
    re.IGNORECASE,
)

# Metadados que o site guarda (privacidade) — pergunta sobre o próprio serviço.
_PRIVACIDADE = re.compile(
    r"(?:meus?|minhas?)\s+(?:dados|conversas?|perguntas?|hist[óo]rico)|"
    r"(?:voc[êe]s?|o\s+site|o\s+goshinsho)\s+(?:guarda|armazena|salva|coleta)|"
    r"excluir\s+(?:minha\s+)?conta|"
    r"apagar\s+(?:meu\s+)?hist[óo]rico",
    re.IGNORECASE,
)


def is_site_help_question(question: str) -> bool:
    """True se a pergunta é sobre o SITE (uso, documentos, dados), não sobre os Escritos.

    Conservadora de propósito: um falso positivo aqui tira a pergunta do acervo
    doutrinário, onde ela poderia ter resposta legítima. Por isso:
      - nomes próprios de recursos/documentos bastam (são inequívocos);
      - "relação com a Igreja" exige produto E vínculo na mesma pergunta;
      - perguntas longas (>600 chars) são ignoradas (são pedidos de conteúdo).
    """
    texto = (question or "").strip()
    if not texto or len(texto) > 600:
        return False
    if _RECURSO_NOMEADO.search(texto):
        return True
    if _ROTA_DOCUMENTO.search(texto):
        return True
    if _PRIVACIDADE.search(texto):
        return True
    if _AUDIO.search(texto):
        return True
    if _PRODUTO.search(texto) and _VINCULO.search(texto):
        return True
    return bool(_USO_DO_SITE.search(texto))


def site_help_context() -> str:
    """Bloco de contexto com o que o site oferece e os documentos existentes."""
    return (
        "O QUE ESTE SITE OFERECE (informação de referência sobre o PRÓPRIO "
        "produto — não é ensinamento e não vem do acervo):\n"
        f"{SITE_FEATURES.strip()}\n\n"
        f"DOCUMENTOS INSTITUCIONAIS DO SITE:\n{SITE_DOCUMENTS.strip()}"
    )


def site_help_instructions() -> str:
    """Instruções para responder dúvidas sobre o site (não sobre os Escritos)."""
    return """
**PERGUNTA SOBRE O PRÓPRIO SITE (uso, funcionalidades, documentos, dados)**

Esta pergunta NÃO é sobre os ensinamentos — é sobre o funcionamento deste site
e dos seus documentos. Portanto:

1. Responda usando SOMENTE o bloco "O QUE ESTE SITE OFERECE" e os "DOCUMENTOS
   INSTITUCIONAIS" fornecidos abaixo. Não faça busca no acervo doutrinário e não
   trate o assunto como se fosse ensinamento de Meishu-Sama.
2. **PROIBIDO** dizer que o recurso "não existe", "não é um conceito do acervo",
   ou que "nada nas instruções fala sobre isso". Se a pergunta cita uma
   funcionalidade da lista, ela EXISTE — descreva-a.
3. Se o que foi perguntado realmente não constar abaixo, diga com clareza que
   você não tem essa informação, sem inventar e sem sugerir que o recurso não
   existe.
4. Seja direto e útil: a pessoa quer saber como usar algo que está vendo na tela.
5. Não confunda os planos: o Chat responde perguntas sobre os Escritos; a Leitura
   Colaborativa é uma biblioteca de leitura com áudio e anotações, em que o
   leitor colabora apontando melhorias no texto. São espaços diferentes.
""".strip() + "\n\n" + site_help_context() + "\n\n" + _AVISO


def site_help_fallback(language: str = "Português") -> str:
    """Resposta mínima quando não há LLM disponível para elaborar.

    ⚠️ NUNCA devolve vazio. Uma resposta vazia é pior que uma resposta curta:
    o usuário fica sem nada e ainda pode concluir que o recurso não existe.
    Versões anteriores retornavam "" para idioma diferente de "Português" —
    e o nome do idioma chega com/sem acento conforme o chamador
    ("Português" vs "Portugues"), o que bastava para esvaziar a resposta.
    Como este texto é de apoio, mantemos o português como língua de segurança.
    """
    base = (
        "Este site tem duas partes principais:\n\n"
        "**Chat** — você pergunta sobre os Escritos de Meishu-Sama e recebe "
        "respostas buscadas no acervo.\n\n"
        "**Leitura Colaborativa** (menu 📖) — uma biblioteca para ler os "
        "ensinamentos, com áudio (🔊) e progresso salvo. Ali você também pode "
        "selecionar um trecho e enviar uma observação para a equipe; é esse "
        "apontamento do leitor que dá o nome \"colaborativa\".\n\n"
        "Há também os documentos institucionais: Termos de Uso, Política de "
        "Privacidade e Aviso de Independência — este último explica que o "
        "Goshinsho é um projeto pessoal e independente, sem vínculo com a Igreja "
        "Messiânica Mundial nem com qualquer outra instituição."
    )
    normalizado = (language or "").strip().lower()
    if normalizado.startswith("portugu"):
        return base
    # Outros idiomas: devolve o texto em inglês como ponte, em vez de nada.
    return (
        "This site has two main parts:\n\n"
        "**Chat** — you ask about the Writings of Meishu-Sama and get answers "
        "searched in the archive.\n\n"
        "**Collaborative Reading** (menu 📖) — a library for reading the "
        "teachings, with audio (🔊) and saved progress. There you can also "
        "select a passage and send a note to the team; that reader feedback is "
        "what gives it the name \"collaborative\".\n\n"
        "There are also the institutional documents: Terms of Use, Privacy "
        "Policy and Independence Notice — the latter explains that Goshinsho is "
        "a personal, independent project with no affiliation to any church."
    )
