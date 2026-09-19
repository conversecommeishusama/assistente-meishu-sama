"""Triagem inicial da pergunta, ANTES do ciclo agenciado.

Motivo (2026-09-19, relato do usuário): *"Qualquer pergunta que se faz ao
aplicativo, ele faz todo o processo de ciclos de pesquisa agêntico e acaba
caindo na mensagem de múltiplas fontes. Se a pessoa falar 'Olá Goshinsho', vai
fazer todo o ciclo de buscas e mostrar a mensagem o que é estranho."*

Causa raiz: a triagem que existia em `conversation_mode.py` (identidade do
assistente, pergunta definicional) e `site_info.py` (perguntas sobre o próprio
site) só era chamada pelo pipeline ANTIGO (`pipeline/answer.py`,
`ai_service.answer_question`). Quando o agêntico foi promovido a motor único
(2026-07-30), essas funções ficaram órfãs -- todo mundo passou a entrar no laço
completo.

Medido antes de escrever isto (2026-09-19):

    "Olá Goshinsho"    21,8s   1 rodada    4.539 tokens   0 ferramentas
    "obrigado!"         1,2s   1 rodada    4.537 tokens   0 ferramentas

A saudação já não chamava ferramenta, mas enviava o system prompt inteiro
(regras 1-10 + 8a-8d) e pagava ~22s. A triagem devolve a resposta na hora.

Escopo deliberadamente estreito: só o que é **inequivocamente** conversa fiada
ou meta-pergunta. Um falso positivo aqui tira do acervo uma pergunta que poderia
ter resposta doutrinária -- exatamente o erro que `site_info.py` documenta ter
cometido ("o chat negou que a Leitura Colaborativa existisse").
"""

from __future__ import annotations

import re

from . import site_info
from .conversation_mode import (
    assistant_identity_response,
    is_assistant_identity_question,
)

# --------------------------------------------------------------------------
# Saudação / despedida / agradecimento / cortesia
#
# Checagem por PALAVRA, não por regex de string inteira: "Olá Goshinsho" (o
# exemplo exato relatado pelo usuário) tem uma palavra a mais e escapava de um
# regex ancorado em `^olá$`. Com a lista de palavras, basta que TODAS as
# palavras da mensagem sejam de cortesia -- o que também cobre
# "Oi, tudo bem?", "bom dia, obrigado" e "até logo".
# --------------------------------------------------------------------------
_PALAVRAS_CORTESIA = frozenset({
    # saudações (vários idiomas)
    "ola", "oi", "ois", "oie", "opa", "hey", "hi", "hello", "hola", "hallo",
    "bonjour", "salut", "ciao", "bom", "boa", "dia", "tarde", "noite",
    "good", "morning", "afternoon", "evening", "tudo", "bem", "como", "vai",
    "esta", "estao", "how", "are", "you", "vcs", "voces",
    # agradecimento
    "obrigado", "obrigada", "obrigados", "obrigadas", "valeu", "agradeco",
    "thanks", "thank", "gracias", "merci", "danke", "grazie",
    # resposta a agradecimento
    "de", "nada", "no", "problem", "welcome",
    # despedida
    "ate", "logo", "tchau", "bye", "goodbye", "adeus", "adios",
    "falou", "xau", "fui",
    # complemento de despedida ("até mais", "até breve")
    "mais", "breve", "amanha", "depois",
    # cortesia social / teste
    "teste", "test", "testando", "testing", "ping", "parabens",
    "congratulations", "favor",
    # complementos de cumprimento ("Olá, tudo bem com você?",
    # "Bom dia a todos vocês"). Artigos e preposições curtas entram aqui
    # porque só aparecem nesse contexto -- a contagem máxima de palavras e a
    # exigência de que TODAS pertençam à lista impedem que uma frase longa
    # passe por causa deles.
    "voce", "contigo", "tambem", "aqui", "ai", "por", "com", "sem",
    "todos", "todas", "a", "o", "os", "as", "e",
    # nome do próprio assistente (ex.: "Olá Goshinsho")
    "goshinsho", "assistente", "bot", "ia",
})

# Reconhecimentos AMBÍGUOS -- NUNCA triados, mesmo custando uma chamada de API.
#
# 2026-09-19, achado real medido na base: "sim" é a 2ª mensagem mais frequente
# (30 ocorrências) e SEMPRE é continuação de conversa -- o assistente termina
# com "quer que eu aprofunde?" e o usuário responde "sim". Triar isso
# devolveria "Olá! Sou o Goshinsho..." a quem acabou de pedir aprofundamento,
# quebrando a conversa e perdendo o contexto do turno anterior. O mesmo vale
# para "ok"/"entendi"/"certo" como resposta a uma oferta do assistente.
#
# Princípio: na dúvida entre triar e não triar, NÃO triar. O custo de errar
# para o lado da triagem é perder uma pergunta doutrinária; o custo de errar
# para o lado da busca é só uma chamada de API a mais.
_PALAVRAS_AMBIGUAS = frozenset({
    "sim", "simm", "siiim", "nao", "yes", "yep", "no", "nope",
    "ok", "okay", "blz", "beleza", "entendi", "certo", "ta", "isso",
    "imagina", "perfeito", "otimo", "legal",
})

# Agradecimento puro -- a resposta natural é "de nada", não uma saudação de
# boas-vindas. Sem isso, um "obrigado" no meio da conversa receberia
# "Olá! Sou o Goshinsho...", que soa desconexo.
#
# Só agradecimento EXPLÍCITO: "ok"/"blz"/"beleza"/"entendi"/"certo"
# ficaram de fora de propósito (ver `_PALAVRAS_AMBIGUAS`).
_PALAVRAS_AGRADECIMENTO = frozenset({
    "obrigado", "obrigada", "obrigados", "obrigadas", "valeu", "agradeco",
    "thanks", "thank", "gracias", "merci", "danke", "grazie",
})

# Teto de palavras: acima disso, quase certamente há pergunta de conteúdo
# colada na cortesia ("Olá, o que Meishu-Sama fala sobre Johrei?"). O teto é
# generoso o bastante para "bom dia a todos vocês" e
# "olá, tudo bem com você?".
_MAX_PALAVRAS_CORTESIA = 8


def _normalizar_palavra(palavra: str) -> str:
    """Minúsculas, sem acento e sem pontuação nas bordas."""
    import unicodedata

    limpa = palavra.strip(" \t!?.,;:…-—'\"").lower()
    sem_acento = unicodedata.normalize("NFKD", limpa)
    return "".join(c for c in sem_acento if not unicodedata.combining(c))


def _palavras_significativas(texto: str) -> list[str]:
    return [p for p in (_normalizar_palavra(w) for w in re.split(r"\s+", texto.strip())) if p]


def is_cortesia(question: str) -> bool:
    """True se a mensagem inteira é saudação/despedida/agradecimento.

    Todas as palavras precisam estar na lista de cortesia -- é o que impede
    que "Olá, o que é Johrei?" (pergunta de conteúdo com cortesia colada) seja
    tratada como conversa fiada e perca a busca no acervo.

    Qualquer palavra AMBÍGUA (`_PALAVRAS_AMBIGUAS`) derruba a triagem: "sim",
    "ok" e afins podem ser continuação de conversa, e silenciá-los quebraria o
    fio do diálogo.
    """
    texto = (question or "").strip()
    if not texto or len(texto) > 80:
        return False
    palavras = _palavras_significativas(texto)
    if not palavras or len(palavras) > _MAX_PALAVRAS_CORTESIA:
        return False
    if any(p in _PALAVRAS_AMBIGUAS for p in palavras):
        return False
    return all(p in _PALAVRAS_CORTESIA for p in palavras)


def _eh_agradecimento(question: str) -> bool:
    palavras = set(_palavras_significativas(question))
    return bool(palavras) and palavras <= _PALAVRAS_AGRADECIMENTO


# Pedido de ajuda sobre o PRÓPRIO assistente (como usar, o que dá para
# perguntar). Distinto de `is_assistant_identity_question` (que é o nome).
_AJUDA_GENERICA = re.compile(
    r"(?is)^\s*(?:"
    r"como\s+(?:eu\s+)?(?:uso|utilizo|funciona)|"
    r"como\s+(?:voc[êe]|vc)\s+funciona|"
    r"o\s+que\s+(?:voc[êe]|vc)\s+(?:faz|pode\s+fazer|sabe)|"
    r"o\s+que\s+(?:eu\s+)?(?:posso|poderia)\s+perguntar|"
    r"para\s+que\s+(?:voc[êe]|vc)\s+serve|"
    r"me\s+ajuda|preciso\s+de\s+ajuda|"
    r"how\s+do\s+(?:i|you)\s+use|what\s+can\s+you\s+do|help\s+me"
    r")\s*[?!.]*\s*$",
    re.IGNORECASE,
)

# Pergunta pelo NOME do assistente, em variantes que a regex do
# `conversation_mode` não cobre (lacuna real, 2026-09-19: "como você se
# chama?" devolvia False lá e por isso seguia para o ciclo agenciado inteiro).
_NOME_DO_ASSISTENTE = re.compile(
    r"(?is)(?:"
    r"como\s+(?:voc[êe]|vc|te)\s+(?:se\s+)?chama|"
    r"qual\s+(?:é\s+)?(?:o\s+)?(?:seu\s+)?nome|"
    r"what\s+should\s+i\s+call\s+you"
    r")",
)

_RESPOSTA_NOME = "Goshinsho."


# --------------------------------------------------------------------------
# Respostas fixas por idioma
#
# Escritas à mão (não geradas pelo modelo) de propósito: são justamente as
# mensagens em que a triagem existe para NÃO gastar uma chamada de API. Se a
# resposta viesse do modelo, o ganho seria só parcial.
# --------------------------------------------------------------------------
_SAUDACAO_POR_IDIOMA = {
    "Português": "Olá! Sou o Goshinsho. Pergunte o que quiser sobre os ensinamentos de Meishu-Sama — por exemplo, «o que é o Johrei?», «o que Meishu-Sama fala sobre a asma?» ou «quais são as três grandes calamidades?».",
    "English": "Hello! I'm Goshinsho. Ask me anything about Meishu-Sama's teachings — for example, \"what is Johrei?\", \"what does Meishu-Sama say about asthma?\" or \"what are the three great calamities?\".",
    "Español": "¡Hola! Soy Goshinsho. Pregunta lo que quieras sobre las enseñanzas de Meishu-Sama — por ejemplo, «¿qué es el Johrei?», «¿qué dice Meishu-Sama sobre el asma?» o «¿cuáles son las tres grandes calamidades?».",
    "日本語": "こんにちは。Goshinshoです。明主様の教えについて何でもお尋ねください — 例えば「浄霊とは何ですか」「明主様は喘息について何と仰っていますか」「三大災難とは何ですか」。",
    "中文": "您好！我是 Goshinsho。关于明主様的教导，欢迎随时提问 — 例如「什么是净灵？」「明主様关于哮喘有何开示？」「三大灾难是什么？」。",
    "हिन्दी": "नमस्ते! मैं Goshinsho हूँ। मीशु-सामा की शिक्षाओं के बारे में कुछ भी पूछें — जैसे «जोहरे क्या है?», «मीशु-सामा दमा के बारे में क्या कहते हैं?» या «तीन महान विपदाएँ क्या हैं?»।",
    "العربية": "مرحبًا! أنا Goshinsho. اسأل ما تشاء عن تعاليم ميشو-ساما — مثل «ما هو الجوهري؟» أو «ماذا يقول ميشو-ساما عن الربو؟» أو «ما هي المصائب الثلاث الكبرى؟».",
    "Français": "Bonjour ! Je suis Goshinsho. Posez-moi toutes vos questions sur les enseignements de Meishu-Sama — par exemple « qu'est-ce que le Johrei ? », « que dit Meishu-Sama sur l'asthme ? » ou « quelles sont les trois grandes calamités ? ».",
    "বাংলা": "নমস্কার! আমি Goshinsho। মেইশু-সামার শিক্ষা সম্পর্কে যা কিছু জানতে চান জিজ্ঞাসা করুন — যেমন «জোহরে কী?», «অ্যাজমা সম্পর্কে মেইশু-সামা কী বলেন?» বা «তিন মহাবিপদ কী?»।",
    "Русский": "Здравствуйте! Я Goshinsho. Спрашивайте что угодно об учениях Мэйсю-Самы — например, «что такое дзёрэй?», «что Мэйсю-Сама говорит об астме?» или «что такое три великие бедствия?».",
    "اردو": "السلام علیکم! میں Goshinsho ہوں۔ میشو-ساما کی تعلیمات کے بارے میں کچھ بھی پوچھیں — مثلاً «جوہرئی کیا ہے؟»، «دمہ کے بارے میں میشو-ساما کیا فرماتے ہیں؟» یا «تین عظیم آفتیں کیا ہیں؟»۔",
    "Indonesia": "Halo! Saya Goshinsho. Tanyakan apa saja tentang ajaran Meishu-Sama — misalnya «apa itu Johrei?», «apa kata Meishu-Sama tentang asma?» atau «apa tiga bencana besar itu?».",
    "Deutsch": "Hallo! Ich bin Goshinsho. Fragen Sie mich alles über die Lehren von Meishu-Sama — zum Beispiel „Was ist Johrei?“, „Was sagt Meishu-Sama über Asthma?“ oder „Was sind die drei großen Katastrophen?“.",
}

_AJUDA_POR_IDIOMA = {
    "Português": "Posso responder perguntas sobre os ensinamentos de Meishu-Sama, sempre citando os textos do acervo. Funciono melhor com perguntas sobre um tema específico — por exemplo: «o que é o Johrei?», «o que Meishu-Sama fala sobre a asma?», «o que é a linhagem do sol e da lua?». Se quiser o texto completo de um ensinamento, peça «na íntegra».",
    "English": "I can answer questions about Meishu-Sama's teachings, always citing the texts from the archive. I work best with specific topics — for example: \"what is Johrei?\", \"what does Meishu-Sama say about asthma?\", \"what is the sun and moon lineage?\". If you want the full text of a teaching, ask for it \"in full\".",
    "Español": "Puedo responder preguntas sobre las enseñanzas de Meishu-Sama, citando siempre los textos del acervo. Funciono mejor con temas específicos — por ejemplo: «¿qué es el Johrei?», «¿qué dice Meishu-Sama sobre el asma?», «¿qué es el linaje del sol y de la luna?». Si quieres el texto completo de una enseñanza, pide «íntegro».",
    "日本語": "明主様の教えについて、常に資料の原文を引用しながらお答えします。具体的なテーマのご質問が最も得意です — 例：「浄霊とは何ですか」「明主様は喘息について何と仰っていますか」「太陽系と月系の血統とは何ですか」。教えの全文をご希望の場合は「全文」とお伝えください。",
    "中文": "我可以回答关于明主様教导的问题，并始终引用文献原文。最擅长具体主题的提问 — 例如：「什么是净灵？」「明主様关于哮喘有何开示？」「日系与月系血统是什么？」。若需某篇教导的全文，请说「全文」。",
    "हिन्दी": "मैं मीशु-सामा की शिक्षाओं पर प्रश्नों का उत्तर दे सकता हूँ, और सदैव संग्रह के मूल पाठ उद्धृत करता हूँ। विशिष्ट विषयों पर सर्वोत्तम कार्य करता हूँ — जैसे: «जोहरे क्या है?», «मीशु-सामा दमा के बारे में क्या कहते हैं?», «सूर्य और चंद्र वंश क्या है?»। किसी शिक्षा का पूरा पाठ चाहिए तो «पूर्ण» कहें।",
    "العربية": "يمكنني الإجابة عن أسئلة حول تعاليم ميشو-ساما، مع الاستشهاد دائمًا بنصوص الأرشيف. أعمل بشكل أفضل مع موضوعات محددة — مثل: «ما هو الجوهري؟»، «ماذا يقول ميشو-ساما عن الربو؟»، «ما هو نسب الشمس والقمر؟». وإن أردت النص الكامل لتعليم ما، فاطلب «كامل».",
    "Français": "Je réponds aux questions sur les enseignements de Meishu-Sama, en citant toujours les textes de l'archive. Je fonctionne mieux avec des sujets précis — par exemple : « qu'est-ce que le Johrei ? », « que dit Meishu-Sama sur l'asthme ? », « qu'est-ce que la lignée du soleil et de la lune ? ». Pour le texte intégral d'un enseignement, demandez « en intégralité ».",
    "বাংলা": "আমি মেইশু-সামার শিক্ষা সম্পর্কে প্রশ্নের উত্তর দিতে পারি, এবং সর্বদা সংকলনের মূল পাঠ উদ্ধৃত করি। নির্দিষ্ট বিষয়ে সবচেয়ে ভালো কাজ করি — যেমন: «জোহরে কী?», «অ্যাজমা সম্পর্কে মেইশু-সামা কী বলেন?», «সূর্য ও চন্দ্রের বংশধারা কী?»। কোনো শিক্ষার সম্পূর্ণ পাঠ চাইলে «সম্পূর্ণ» বলুন।",
    "Русский": "Я отвечаю на вопросы об учениях Мэйсю-Самы, всегда цитируя тексты из архива. Лучше всего работаю с конкретными темами — например: «что такое дзёрэй?», «что Мэйсю-Сама говорит об астме?», «что такое род солнца и луны?». Если нужен полный текст учения, скажите «полностью».",
    "اردو": "میں میشو-ساما کی تعلیمات کے بارے میں سوالات کا جواب دے سکتا ہوں، اور ہمیشہ مجموعے کے اصل متن کا حوالہ دیتا ہوں۔ مخصوص موضوعات پر بہترین کام کرتا ہوں — مثلاً: «جوہرئی کیا ہے؟»، «دمہ کے بارے میں میشو-ساما کیا فرماتے ہیں؟»، «سورج اور چاند کی نسل کیا ہے؟»۔ کسی تعلیم کا مکمل متن چاہیں تو «مکمل» کہیں۔",
    "Indonesia": "Saya dapat menjawab pertanyaan tentang ajaran Meishu-Sama, selalu mengutip teks dari arsip. Saya paling baik dengan topik yang spesifik — misalnya: «apa itu Johrei?», «apa kata Meishu-Sama tentang asma?», «apa itu garis keturunan matahari dan bulan?». Jika ingin teks lengkap suatu ajaran, minta «selengkapnya».",
    "Deutsch": "Ich beantworte Fragen zu den Lehren von Meishu-Sama und zitiere dabei stets die Texte aus dem Archiv. Am besten funktioniere ich mit konkreten Themen — zum Beispiel: „Was ist Johrei?“, „Was sagt Meishu-Sama über Asthma?“, „Was ist die Sonnen- und Mondlinie?“. Für den vollständigen Text einer Lehre fragen Sie nach „vollständig“.",
}


_AGRADECIMENTO_POR_IDIOMA = {
    "Português": "De nada! Estou à disposição — se quiser, pergunte sobre um tema específico dos ensinamentos de Meishu-Sama.",
    "English": "You're welcome! I'm here whenever you need — feel free to ask about a specific topic from Meishu-Sama's teachings.",
    "Español": "¡De nada! Estoy a tu disposición — si quieres, pregunta sobre un tema específico de las enseñanzas de Meishu-Sama.",
    "日本語": "どういたしまして。いつでもどうぞ — 明主様の教えについて、特定のテーマをお尋ねください。",
    "中文": "不客气！随时为您服务 — 如有需要，请就明主様教导的某个具体主题提问。",
    "हिन्दी": "कोई बात नहीं! मैं सदा उपलब्ध हूँ — चाहें तो मीशु-सामा की शिक्षाओं के किसी विशिष्ट विषय पर पूछें।",
    "العربية": "على الرحب والسعة! أنا في خدمتك دائمًا — إن أردت، اسأل عن موضوع محدد من تعاليم ميشو-ساما.",
    "Français": "Je vous en prie ! Je reste à votre disposition — n'hésitez pas à poser une question sur un thème précis des enseignements de Meishu-Sama.",
    "বাংলা": "স্বাগতম! আমি সর্বদা উপলব্ধ — চাইলে মেইশু-সামার শিক্ষার কোনো নির্দিষ্ট বিষয়ে জিজ্ঞাসা করুন।",
    "Русский": "Пожалуйста! Я всегда к вашим услугам — при желании спросите о конкретной теме из учений Мэйсю-Самы.",
    "اردو": "کوئی بات نہیں! میں ہمیشہ حاضر ہوں — چاہیں تو میشو-ساما کی تعلیمات کے کسی مخصوص موضوع پر پوچھیں۔",
    "Indonesia": "Dengan senang hati! Saya siap kapan pun — silakan tanyakan topik tertentu dari ajaran Meishu-Sama.",
    "Deutsch": "Gern geschehen! Ich stehe jederzeit zur Verfügung — fragen Sie gern zu einem konkreten Thema aus den Lehren von Meishu-Sama.",
}


def _por_idioma(mapa: dict, idioma: str) -> str:
    return mapa.get(idioma) or mapa["Português"]


def resposta_de_triagem(question: str, *, language: str = "Português") -> str | None:
    """Resposta imediata para mensagens que NÃO precisam do acervo.

    Devolve `None` quando a pergunta deve seguir para o ciclo agenciado
    normal -- que é o caso da esmagadora maioria das mensagens.

    Ordem das checagens, da mais específica para a mais genérica:
      1. identidade/nome do assistente (reusa `conversation_mode`, que já era
         usado pelo pipeline antigo e tem resposta fixa por idioma);
      2. ajuda genérica sobre o próprio assistente;
      3. cortesia pura (saudação/despedida/agradecimento);
      4. dúvida sobre o funcionamento do SITE (reusa `site_info`).
    """
    texto = (question or "").strip()
    if not texto:
        return None

    # 1. "qual é o seu nome?", "como você se chama?", "o que significa Goshinsho?"
    if is_assistant_identity_question(texto):
        resposta = assistant_identity_response(texto, language=language)
        if resposta:
            return resposta
    if _NOME_DO_ASSISTENTE.search(texto):
        return _RESPOSTA_NOME

    # 2. "como você funciona?", "o que eu posso perguntar?"
    if _AJUDA_GENERICA.match(texto):
        return _por_idioma(_AJUDA_POR_IDIOMA, language)

    # 3. saudação/despedida/agradecimento puros. O agradecimento ganha uma
    #    resposta própria -- responder "Olá! Sou o Goshinsho..." a um
    #    "obrigado" no meio da conversa soaria desconexo.
    if is_cortesia(texto):
        if _eh_agradecimento(texto):
            return _por_idioma(_AGRADECIMENTO_POR_IDIOMA, language)
        return _por_idioma(_SAUDACAO_POR_IDIOMA, language)

    # 4. dúvida sobre o próprio site (privacidade, como usar um recurso,
    #    documentos institucionais). Reusa a checagem já existente, que é
    #    deliberadamente conservadora (ver docstring de `is_site_help_question`).
    if site_info.is_site_help_question(texto):
        return site_info.site_help_fallback(language)

    return None


def precisa_do_acervo(question: str) -> bool:
    """Inverso conveniente de `resposta_de_triagem`, para leitura no chamador."""
    return resposta_de_triagem(question) is None
