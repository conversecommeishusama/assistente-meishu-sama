#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ronda 6 — correções dos 94 achados BAIXOS da auditoria R3 (triagem completa).

Triagem: 90 achados procedentes, 4 falsos positivos documentados abaixo.
Cada substituição valida a contagem antes de gravar; se alguma falhar não se
grava nada.

Falsos positivos NÃO corrigidos (registados para não voltarem a ser reportados):
  * P4_Hikari_26_357 — "Tijotengoku" como nome da revista é convenção fixada
    do acervo (577 ocorrências), não romanização errada.
  * P2_Eiko_114_120 — "Igreja Média Shinshin": 真心中教会  -> 中教会 = "Igreja
    Média" é a convenção do acervo (cf. "Igreja Média Kaimei").
  * P1_Tijotengoku_28_60 — o título diz nº 27 porque a própria página-fonte
    (kantou28.html) traz esse rótulo no cabeçalho; o corpo e a fonte dizem 28.
    Corrigido apenas o português (fica coerente com a fonte_pt).
  * P2_Eiko_168_226 / P4_Hikari_22_354 — "Senhor Luz" para 御光/お光様 é
    convenção do acervo (89 ocorrências).

Uso:  .venv/bin/python scripts/aplicar_correcoes_auditoria_r6.py [--aplicar]
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_auditoria"

# (item, campo, antigo, novo, ocorrências esperadas)
SUBS: list[tuple[str, str, str, str, int]] = [
    # ------------------------------------------------- acrescimo indevido
    ("P2_Eiko_102_103", "texto_pt",
     "O cultivo natural é muito bom para folhas de mostarda e nabo",
     "O cultivo natural é muito bom para hortaliças de folha e nabo", 1),
    ("P2_Eiko_86_158", "texto_pt",
     'do livro de história chinês "Chunqiu", do século VI a.C., ao qual Confúcio',
     'do livro de história chinês "Chunqiu", da era pré-cristã, ao qual Confúcio', 1),
    ("P3_Kyusei_48_294", "texto_pt",
     "minha filha recém-nascida de seis meses teve",
     "minha filha de seis meses teve", 1),

    # ------------------------------------------------- degeneração de edição
    ("P1_Tijotengoku_11_4", "texto_pt",
     '"Hora é cristã, hora é da Igreja Kannon, vagueando.»',
     '«Hora é cristã, hora é da Igreja Kannon, vagueando.»', 1),
    ("P1_Tijotengoku_11_4", "texto_pt",
     "estudava o budismo com determinação,\n\nAlém disso, o fato de as afirmações",
     "estudava o budismo com determinação e, além disso, o fato de as afirmações", 1),
    ("P1_Tijotengoku_14_30", "texto_pt",
     "quatro ampolas de estreptomicina e várias de gluconato [de cálcio?*], "
     "entre outras injeções",
     "quatro ampolas de estreptomicina e várias dezenas de Gerubro, entre "
     "outras injeções", 1),
    ("P1_Tijotengoku_22_45", "texto_pt",
     "(Resposta Divina)\n\n — ", "(Resposta Divina)\n\n", 4),
    ("P1_Tijotengoku_22_45", "texto_pt",
     "(Pergunta)\n\n — ", "(Pergunta)\n\n", 3),
    ("P1_Tijotengoku_36_67", "texto_pt",
     "\n1. Meu pai e o casal de meu irmão mais velho não compreendem",
     "\n11. Meu pai e o casal de meu irmão mais velho não compreendem", 1),
    ("P2_Eiko_103_106", "texto_pt",
     "…Se eu disser que o ser humano de hoje não entra",
     "▽…Se eu disser que o ser humano de hoje não entra", 1),
    ("P2_Eiko_103_106", "texto_pt",
     "…Há um criminoso assassino que mata dezenas de milhares",
     "▽…Há um criminoso assassino que mata dezenas de milhares", 1),
    ("P2_Eiko_104_107", "texto_pt",
     "Há uma nação que, com empenho, tenta criar o inferno na Terra",
     "▽… Há uma nação que, com empenho, tenta criar o inferno na Terra", 1),
    ("P2_Eiko_104_107", "texto_pt",
     "Pelo visto, como o Pikadon não tem graça",
     "▽… Pelo visto, como o Pikadon não tem graça", 1),
    ("P2_Eiko_104_107", "texto_pt",
     "Do lado de lá, com tuberculose, disenteria, varíola, tifo e companhia",
     "▽… Do lado de lá, com tuberculose, disenteria, varíola, tifo e companhia", 1),
    ("P2_Eiko_104_107", "texto_pt",
     "Deus diz que todos os humanos de hoje são doentes mentais.",
     "▽… Deus diz que todos os humanos de hoje são doentes mentais.", 1),
    ("P2_Eiko_112_116", "texto_pt",
     "para mim, que, como missionário de fé frágil, sou fraco na fé —",
     "para mim, que sou um missionário de fé frágil —", 1),
    ("P2_Eiko_160_217", "titulo_pt",
     "Sun-Tetsu Katsujin 【Eikō nº 160】",
     "Sun-Tetsu Katsujin (Eikō nº 160)", 1),
    ("P2_Eiko_133_150", "titulo_pt",
     "Sun-Tetsu Katsujin 【Eikō 133号】",
     "Sun-Tetsu Katsujin (Eikō nº 133)", 1),
    ("P2_Eiko_136_155", "titulo_pt",
     "Sun-Tetsu Katsujin 【Eikō 136号】",
     "Sun-Tetsu Katsujin (Eikō nº 136)", 1),
    ("P2_Eiko_193_239", "texto_pt",
     "Com esse sentimento, passou-se mais ou cerca de um ano;",
     "Com esse sentimento, passou-se mais cerca de um ano;", 1),
    ("P2_Eiko_252_282", "texto_pt",
     "\nDespertando da superstição médica — Salva da tuberculose pulmonar\n",
     "\n**Despertando da superstição médica — Salva da tuberculose pulmonar**\n", 1),
    ("P2_Eiko_83_97", "texto_pt",
     "Ora, neste momento um ladrão quase entrou no Tibet",
     "▽… Ora, neste momento um ladrão quase entrou no Tibet", 1),
    ("P2_Eiko_85_157", "texto_pt",
     "Você conhece a religião que nega a religião?",
     "▽… Você conhece a religião que nega a religião?", 1),
    ("P2_Eiko_85_157", "texto_pt",
     "O mestre dos demolidores, o Sr. Stalin",
     "▽… O mestre dos demolidores, o Sr. Stalin", 1),
    ("P2_Eiko_99_187", "texto_pt",
     "A medicina também progrediu, hein?",
     "◇… A medicina também progrediu, hein?", 1),
    ("P2_Eiko_99_187", "texto_pt",
     "E essa língua que diz que Deus não existe —",
     "◇… E essa língua que diz que Deus não existe —", 1),
    ("P2_Eiko_99_187", "texto_pt",
     "O que falta ao Japão não é arroz, nem capital",
     "◇… O que falta ao Japão não é arroz, nem capital", 1),
    ("P2_Eiko_99_187", "texto_pt",
     "O Paraíso Terrestre, pela beleza, eleva o coração;",
     "◇… O Paraíso Terrestre, pela beleza, eleva o coração;", 1),
    ("P2_Eiko_99_187", "texto_pt",
     "Dizem que a disenteria é o triplo do ano passado;",
     "◇… Dizem que a disenteria é o triplo do ano passado;", 1),
    ("P3_Kyusei_54_311", "texto_pt",
     "Duas Calças (1) — Iwasaki Sakae",
     "**Duas Calças (Parte 1)** — Iwasaki Sakae", 1),
    ("P3_Kyusei_56_315", "texto_pt", "\n* * *\n", "\n＊ ＊ ＊\n", 2),
    ("P4_Hikari_12_340", "texto_pt",
     "**Erradicar os Males da Tragédia**\n\nNeste mundo,",
     "Neste mundo,", 1),
    ("P4_Hikari_20_353", "texto_pt",
     "**(三) Ultimamente, em diversas regiões têm ocorrido incêndios com "
     "frequência; deveríamos considerá-los como o reflexo transferido da "
     "purificação do mundo espiritual?**",
     "(3) Ultimamente, em diversas regiões têm ocorrido incêndios com "
     "frequência; deveríamos considerá-los como o reflexo transferido da "
     "purificação do mundo espiritual?", 1),
    ("P4_Hikari_20_353", "texto_pt",
     "**Resposta — (1)** Realizam-se os serviços memoriais",
     "Resposta: (1) Realizam-se os serviços memoriais", 1),
    ("P4_Hikari_20_353", "texto_pt",
     "**(2)** Isso, na verdade, também estaria bem;",
     "(2) Isso, na verdade, também estaria bem;", 1),
    ("P4_Hikari_20_353", "texto_pt",
     "**(3)** Naturalmente, as calamidades também são processo de purificação",
     "(3) Naturalmente, as calamidades também são processo de purificação", 1),
    ("P4_Hikari_20_353", "texto_pt",
     "**Pergunta:** Um menino de dezesseis anos",
     "Pergunta: Um menino de dezesseis anos", 1),
    ("P4_Hikari_20_353", "texto_pt",
     "**Resposta:** Se ele tinha três anos",
     "Resposta: Se ele tinha três anos", 1),
    ("P4_Hikari_20_353", "texto_pt",
     "**Pergunta:** Uma mulher de trinta e cinco anos",
     "Pergunta: Uma mulher de trinta e cinco anos", 1),
    ("P4_Hikari_20_353", "texto_pt",
     "**Resposta:** É melhor aplicar o Johrei do lado de fora do quarto",
     "Resposta: É melhor aplicar o Johrei do lado de fora do quarto", 1),
    ("P4_Hikari_32_371", "texto_pt",
     '(Nota) Nota: “O machado da louva-a-deus”',
     '(Nota) “O machado da louva-a-deus”', 1),

    # ------------------------------------------------- rótulos de falante
    ("P2_Eiko_191_237", "texto_pt", "**Suzuki:**", "Suzuki:", 2),
    ("P2_Eiko_191_237", "texto_pt", "**Presidente:**", "Presidente:", 2),
    ("P2_Eiko_191_237", "texto_pt", "**Sakai Mannosuke:**", "Sakai Mannosuke:", 1),
    ("P2_Eiko_191_237", "texto_pt", "**Furukawa:**", "Furukawa:", 1),
    ("P2_Eiko_191_237", "texto_pt", "**Senhor Presidente:**", "Senhor Presidente:", 2),
    ("P2_Eiko_191_237", "texto_pt", "**Sakami:**", "Sakami:", 1),
    ("P2_Eiko_191_237", "texto_pt", "**Moderador:**", "Moderador:", 1),
    ("P2_Eiko_191_237", "texto_pt", "**Futami:**", "Futami:", 1),
    ("P2_Eiko_191_237", "texto_pt", "**Nagatomo:**", "Nagatomo:", 1),
    ("P2_Eiko_191_237", "texto_pt", "**Sawamoto Zentarō:**", "Sawamoto Zentarō:", 1),
    ("P2_Eiko_193_238", "texto_pt",
     "\nAo senso religioso, em estilo Corbusier\n",
     "\n**Ao senso religioso, em estilo Corbusier**\n", 1),
    ("P2_Eiko_193_238", "texto_pt",
     "\nQuando concluído, [realizar] um grande concerto mundial\n",
     "\n**Quando concluído, [realizar] um grande concerto mundial**\n", 1),
    ("P2_Eiko_193_238", "texto_pt",
     "\nOs Jornais de Agora em Diante\n",
     "\n**Os Jornais de Agora em Diante**\n", 1),

    # ------------------------------------------------- glossário
    ("P1_Tijotengoku_12_20", "texto_pt",
     "pode entrar no mundo espiritual e, finalmente, chegar até o mundo divino",
     "pode entrar no mundo dos espíritos e, finalmente, chegar até o mundo divino", 1),
    ("P1_Tijotengoku_28_61", "texto_pt",
     "oferecer o Ofertório de Gratidão (tamagushi)",
     "oferecer o Ofertório (tamagushi)", 1),
    ("P1_Tijotengoku_37_68", "texto_pt",
     "e seu ihai também é cultuado,",
     "e sua tabuleta mortuária (ihai) também é cultuada,", 1),
    ("P1_Tijotengoku_37_68", "texto_pt",
     "cultuamos os ihai das famílias Imaru",
     "cultuamos as tabuletas mortuárias das famílias Imaru", 1),
    ("P1_Tijotengoku_37_68", "texto_pt",
     "atrás do ihai do marido no altar budista",
     "atrás da tabuleta do marido no altar budista", 1),
    ("P1_Tijotengoku_54_82", "texto_pt",
     "temos as tabuletas memoriais dos antepassados da família Maja ao centro",
     "temos as tabuletas mortuárias (ihai) dos antepassados da família Maja ao centro", 1),
    ("P1_Tijotengoku_54_82", "texto_pt",
     "as tabuletas mortuárias (ihai) dos antepassados da família Chinen",
     "as tabuletas mortuárias dos antepassados da família Chinen", 1),
    ("P1_Tijotengoku_54_82", "texto_pt",
     "tabuleta memorial do antigo marido de minha esposa também está cultuada",
     "tabuleta do antigo marido de minha esposa também está cultuada", 1),
    ("P2_Eiko_168_226", "texto_pt",
     "o grande poder do Senhor Luz",
     "o grande poder da Divina Luz", 1),
    ("P2_Eiko_193_238", "texto_pt",
     "Quando o Salão da Igreja Messiânica estiver concluído",
     "Quando o Templo Kyusei estiver concluído", 1),
    ("P2_Eiko_237_270", "texto_pt",
     "fio de algodão, hashi, tenazes, dedo mínimo",
     "fio de algodão, pauzinhos (hashi), tenazes, dedo mínimo", 1),
    ("P2_Eiko_97_182", "texto_pt",
     "uma marretada na moleira com um martelo de pedra",
     "uma marretada na moleira com uma marreta (gennō)", 1),
    ("P3_Kyusei_59_320", "texto_pt",
     "preferia comer o arroz semi-polido, a sopa de missô",
     "preferia comer o arroz com cevada, a sopa de missô", 1),

    # ------------------------------------------------- inversões
    ("P1_Tijotengoku_20_41", "texto_pt",
     "no caso de nomes próprios e outros, devemos aplicar a pronúncia",
     "também fora dos nomes próprios, devemos aplicar a pronúncia", 1),
    ("P1_Tijotengoku_28_61", "texto_pt",
     "não conseguiu, e o Sr. Murakami chegou acompanhado às uma e meia da tarde",
     "não conseguiu vir, e o Sr. Kaneko chegou acompanhado do Sr. Murakami às "
     "uma e meia da tarde", 1),
    ("P1_Tijotengoku_31_65", "texto_pt",
     "o Imperador Amaterasu é a divindade irmã mais nova de Izunome-no-Kami",
     "o Imperador Amaterasu é a divindade irmão mais novo de Izunome-no-Kami", 1),
    ("P2_Eiko_155_209", "texto_pt",
     'A "tribo da cultura", como mosquitos que picam zumbindo;',
     'A "tribo da cultura", que é picada por mosquitos que zumbem;', 1),
    ("P3_Kyusei_54_312", "texto_pt",
     "cheguei a decidir pelo suicídio diante da iminência da cegueira",
     "cheguei a decidir pelo suicídio após ter ficado cega", 1),

    # ------------------------------------------------- junções / anacolutos
    ("P2_Eiko_109_112", "texto_pt",
     "Foi quando, de fora, um homem gritando em voz alta:",
     "Foi quando, de fora, gritando em voz alta:", 1),
    ("P2_Eiko_169_228", "texto_pt",
     "Para o professor que vinha especialmente e para os fiéis, a criança que "
     "gritava coisas estranhas como:",
     "A criança, que diante do professor que vinha especialmente e dos fiéis "
     "gritava, uma após outra, coisas estranhas como:", 1),

    # ------------------------------------------------- nomes próprios
    ("P1_Tijotengoku_12_20", "texto_pt", "Elizabeth Cutham", "Elizabeth Catterham", 1),
    ("P1_Tijotengoku_12_20", "texto_pt", "Ela morava em Marleckby", "Ela morava em Marleckby", 0),  # controlo
    ("P1_Tijotengoku_12_20", "texto_pt",
     "Ela morou em Marlkby, em algum momento.",
     "Ela morou em Marleckby, em algum momento.", 1),
    ("P1_Tijotengoku_39_69", "texto_pt",
     'uma peça teatral de tema moralizante, algo como "Shōtarō", encenada num '
     "palco improvisado e sujo",
     'uma peça teatral de tema moralizante, representada por um homem chamado '
     "talvez Kōtarō, num palco improvisado e sujo", 1),
    ("P1_Tijotengoku_49_79", "texto_pt",
     "fui a passeio às termas de Ueyamada e Togura",
     "fui a passeio às termas de Kamiyamada e Togura", 1),
    ("P2_Eiko_163_222", "texto_pt", "Higashimura", "Shuttō-mura", 3),
    ("P2_Eiko_193_238", "texto_pt", "chegou ao Heikunsō", "chegou ao Hekiunsō", 1),
    ("P2_Eiko_85_156", "texto_pt",
     "o museu a ser construído sobre o Sekiundaidai",
     "o museu a ser construído sobre o Sekiundai", 1),
    ("P2_Eiko_89_165", "texto_pt",
     "Se o senhor Ishimatsu da floresta estivesse vivo",
     "Se o Mori no Ishimatsu estivesse vivo", 1),
    ("P2_Eiko_89_165", "titulo_pt",
     "Hendon Namonjai", 'Hen, Donna Monjai ("E daí?")', 1),
    ("P3_Kyusei_51_304", "texto_pt",
     "Tóquio\nIgreja Miroku\nNakada Yasu",
     "Tóquio\nIgreja Grande Miroku\nNakada Yasu", 1),
    ("P3_Kyusei_52_306", "texto_pt",
     "O nome da doença era tracoma e panoftalmia.",
     "O nome da doença era tracoma e pannus.", 1),
    ("P3_Kyusei_54_311", "texto_pt",
     "Resposta do Fundador de Jikan",
     "Resposta do Fundador Jikan", 1),
    ("P3_Kyusei_55_313", "texto_pt",
     "\nYamaguchi Fusa (50)\n", "\nFusa Yamaguchi (50)\n", 1),
    ("P4_Hikari_11_338", "titulo_pt",
     "Sinopse de Zuiunkyo", "Sinopse de Zuisenkyō", 1),

    # ------------------------------------------------- número / unidade
    ("P1_Tijotengoku_28_60", "titulo_pt",
     "Palavras de Abertura (Tijotengoku nº 27)",
     "Palavras de Abertura (Tijotengoku nº 28)", 1),

    # ------------------------------------------------- omissões
    ("P2_Eiko_171_232", "texto_pt",
     "Esposa: É o Dr. Ozaki?",
     "Esposa: É o Dr. Ozaki? (a consciência e os olhos ainda não estavam claros.)", 1),
    ("P2_Eiko_171_232", "texto_pt",
     "e minha mãe, com as lágrimas de tristeza transformadas em lágrimas de alegria",
     "e ela, com as lágrimas de tristeza transformadas em lágrimas de alegria", 1),

    # ------------------------------------------------- português
    ("P1_Tijotengoku_12_23", "texto_pt",
     "quando se vai ao ossetra e ele se une sobreposto",
     "quando se procura um ortopedista tradicional (osekkai) e o osso se une "
     "sobreposto", 1),
    ("P1_Tijotengoku_17_34", "texto_pt",
     "o predecessor de Shakyamuni era príncipe herdeiro",
     "a encarnação anterior de Shakyamuni era príncipe herdeiro", 1),
    ("P1_Tijotengoku_18_37", "texto_pt",
     "mas, forçando a dizer, Deus, sendo um terremoto muito grande, em lugares "
     "densamente povoados os danos seriam grandes;",
     "mas, forçando a dizer, se um terremoto fosse demasiado grande, em lugares "
     "densamente povoados os danos seriam grandes;", 1),
    ("P1_Tijotengoku_22_44", "texto_pt",
     "eu mesmo a vi, em ano passado, quando visitei Moto-Ise",
     "eu mesmo a vi, há alguns anos, quando visitei Moto-Ise", 1),
    ("P1_Tijotengoku_22_44", "texto_pt",
     "Quando visitei Izumo em ano passado",
     "Quando visitei Izumo há alguns anos", 1),
    ("P1_Tijotengoku_22_45", "texto_pt",
     "e aquilo que não compreendiam passarão a compreender",
     "e aquilo que não compreendiam passará a compreender", 1),
    ("P1_Tijotengoku_30_64", "texto_pt",
     'basta escrever "Tal-e-tall Myōjin"',
     'basta escrever "Fulano Myōjin"', 1),
    ("P1_Tijotengoku_36_67", "texto_pt",
     "b. Qual teria sido a causa principal da loucura da própria pessoa?",
     "a. Qual teria sido a causa principal da loucura da própria pessoa?", 1),
    ("P1_Tijotengoku_36_67", "texto_pt",
     "c. Por que motivo, de forma tão irreverente, ela quebrou a Imagem de Komyo-Nyorai",
     "b. Por que motivo, de forma tão irreverente, ela quebrou a Imagem de Komyo-Nyorai", 1),
    ("P1_Tijotengoku_36_67", "texto_pt",
     "d. Como deveríamos proceder de agora em diante?",
     "c. Como deveríamos proceder de agora em diante?", 1),
    ("P1_Tijotengoku_51_81", "texto_pt",
     "ele foi agraciado com poder andar apoiando-se em muletas",
     "ele foi agraciado com a capacidade de andar apoiando-se em muletas", 1),
    ("P2_Eiko_102_103", "texto_pt",
     "A seguir, sobre o assunto à direita, uma vez que houve uma advertência",
     "A seguir, sobre o assunto acima, uma vez que houve uma advertência", 1),
    ("P2_Eiko_109_113", "texto_pt",
     "os grillos-toupeira, os grilos, os esperanças",
     "os grilos-toupeira, os grilos, as esperanças", 1),
    ("P2_Eiko_169_228", "texto_pt",
     "e ela se levanta de manhã e brinca com o irmão mais novo",
     "e ele se levanta de manhã e brinca com o irmão mais novo", 1),
    ("P2_Eiko_169_228", "texto_pt",
     "E, para nossa gratidão, ela se tornou muito mais gentil do que antes.",
     "E, o que é ainda mais motivo de gratidão, ele se tornou muito mais gentil "
     "do que antes.", 1),
    ("P2_Eiko_250_280", "texto_pt",
     "Na manhã seguinte, por volta do meio-dia do dia 23",
     "No dia seguinte, por volta do meio-dia do dia 23", 1),
    ("P2_Eiko_252_282", "texto_pt",
     "e que isto é a verdade os fatos o demonstram sem margem para dúvidas",
     "e que isto é a verdade, os fatos o demonstram sem margem para dúvidas", 1),
    ("P2_Eiko_86_158", "texto_pt",
     "A inteligência da fundadora que criou isso é realmente admirável.",
     "A inteligência do fundador que criou isso é realmente admirável.", 1),
    ("P2_Eiko_88_164", "texto_pt",
     'o grito da galeria: "Iyo~, Grande Messias~!',
     'o grito da galeria: "Iyo~, Grande Messias~!"', 1),
    ("P2_Eiko_93_171", "texto_pt",
     '"ó venturoso aquele que não conhece este mundo duro deste mundo!"',
     '"ó venturoso aquele que não conhece este mundo duro!"', 1),
    ("P2_Eiko_97_182", "texto_pt",
     "um boneco com o pescoço quase solto, aos bamboleios",
     "um boneco com o pescoço quase solto, pele e osso", 1),
    ("P3_Kyusei_50_301", "texto_pt",
     '"Não posso deixar que eu confie a criança ao senhor; de qualquer maneira '
     'vou levá-la comigo"',
     '"Não posso continuar deixando a criança confiada ao senhor; de qualquer '
     'maneira vou levá-la comigo"', 1),
    ("P3_Kyusei_51_304", "texto_pt",
     "de um acolchoado de algodão cru para a cintura",
     "de um acolchoado de seda (mawata) para a cintura", 1),
    ("P3_Kyusei_55_313", "texto_pt",
     "Esta paciente é, por assim dizer, um exemplo-modelo das vítimas",
     "Este paciente é, por assim dizer, um exemplo-modelo das vítimas", 1),
    ("P3_Kyusei_59_320", "texto_pt",
     "Creio que de dez pessoas, nem dez teriam visto alguém assim ser salvo.",
     "Creio que não haverá ninguém que tenha visto todos os dez serem salvos.", 1),
    ("P3_Kyusei_61_321", "texto_pt",
     'Resumindo em uma só frase: "Ó infelizes, vós não conheceis o advento da '
     'Igreja Messiânica.',
     'Resumindo em uma só frase: "Ó infelizes, vós não conheceis o advento da '
     'Igreja Messiânica."', 1),
    ("P3_Kyusei_65_328", "texto_pt",
     'é de "não me diga!" o quanto isso se compreende',
     'é de "ah, sim, entendi!" o quanto isso se compreende', 1),
    ("P3_Kyusei_65_328", "texto_pt",
     '"Aqui é Kuwa-bara, que é vossa propriedade; portanto, por favor, aplacai '
     'a vossa ira.',
     '"Aqui é Kuwa-bara, que é vossa propriedade; portanto, por favor, aplacai '
     'a vossa ira."', 1),
    ("P4_Hikari_7_399", "texto_pt",
     'olhei bem, e era o Jornal Hikari.',
     'olhei bem, e era o Jornal Hikari."', 1),
    ("P4_Hikari__331", "texto_pt",
     "e o lugar de onde sempre argumenta — a frase",
     "e aquilo que ele sempre afirma — a frase", 1),
    ("P2_Eiko_244_274", "texto_pt",
     "esse espírito é purificado.",
     'esse espírito é purificado." — é o ensinamento que recebemos.', 1),
]

# Datas em Era Shōwa com formatos mistos (8 ocorrências) -> forma do acervo
DATAS_SHOWA = [
    ("P1_Tijotengoku_40_72", "texto_pt", "Showa 20 [1945]", "Shōwa 20 (1945)", 1),
    ("P1_Tijotengoku_40_72", "texto_pt", "Showa 21 [1946]", "Shōwa 21 (1946)", 1),
    ("P1_Tijotengoku_40_72", "texto_pt", "Showa 23 [1948]", "Shōwa 23 (1948)", 1),
    ("P1_Tijotengoku_40_72", "texto_pt", "Showa 24 [1949]", "Shōwa 24 (1949)", 1),
    ("P1_Tijotengoku_40_72", "texto_pt", "Showa 25 [1950]", "Shōwa 25 (1950)", 1),
    ("P1_Tijotengoku_40_72", "texto_pt", "Showa 26 [1951]", "Shōwa 26 (1951)", 1),
    ("P1_Tijotengoku_40_72", "texto_pt", "Showa 27 [1952]", "Shōwa 27 (1952)", 2),
]

# Notas finais do japonês que faltavam (omissao)
NOTAS = [
    ("P2_Eiko_78_94",
     "\n\nNotas:\n"
     "(1) アプレゲール (après-guerre): os “pós-guerra” — nova tendência "
     "artística surgida na França e arredores após a Primeira Guerra Mundial; "
     "sobretudo, após a Segunda Guerra, os jovens que agem de forma "
     "desinibida, sem se prenderem às ideias e à moral tradicionais.\n"),
    ("P2_Eiko_258_289",
     "\n\nNotas:\n"
     "(1) 国帑 (kokudo): bens do tesouro nacional; erário.\n"),
]

# Marcadores 問/答 do diálogo com o espírito (família distinta de お伺/御垂示)
MARCADORES_25_54 = [
    ("P1_Tijotengoku_25_54", "texto_pt", "（霊）", "(Espírito) ", 1),
    ("P1_Tijotengoku_25_54", "texto_pt", "（問）", "(Pergunta) ", 6),
    ("P1_Tijotengoku_25_54", "texto_pt", "（答）", "(Resposta Divina) ", 6),
    ("P1_Tijotengoku_25_54", "texto_pt", "（私）", "(Eu) ", 1),
]

# Unificação de marcadores dentro do mesmo artigo (família 【問】/【答】)
MARCADORES_BARRAS = [
    ("P1_Tijotengoku_11_6", "texto_pt", "Pergunta:", "【Pergunta】", 6),
    ("P1_Tijotengoku_11_6", "texto_pt", "Resposta:", "【Resposta】", 6),
    ("P1_Tijotengoku_13_27", "texto_pt", "Pergunta:", "【Pergunta】", 5),
    ("P1_Tijotengoku_13_27", "texto_pt", "Resposta:", "【Resposta】", 5),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cache: dict[str, dict] = {}
    falhas: list[str] = []
    ok = 0

    def carregar(item: str) -> dict:
        if item not in cache:
            cache[item] = json.loads((ITENS / f"{item}.json").read_text(encoding="utf-8"))
        return cache[item]

    todos = SUBS + DATAS_SHOWA + MARCADORES_25_54 + MARCADORES_BARRAS
    for item, campo, old, new, esperado in todos:
        if esperado == 0:
            continue
        d = carregar(item)
        atual = d.get(campo) or ""
        n = atual.count(old)
        if n != esperado:
            falhas.append(f"{item}.{campo}: {n} occ, esperado {esperado} — {old[:60]!r}")
            continue
        d[campo] = atual.replace(old, new)
        d.setdefault("reparos", []).append(
            {"tipo": "fix_auditoria_r6", "data": stamp, "campo": campo}
        )
        ok += 1

    for item, bloco in NOTAS:
        d = carregar(item)
        pt = d.get("texto_pt") or ""
        if "Notas:" in pt[-600:]:
            falhas.append(f"{item}: já tem bloco 'Notas:'")
            continue
        d["texto_pt"] = pt.rstrip("\n") + bloco
        d.setdefault("reparos", []).append(
            {"tipo": "fix_auditoria_r6", "data": stamp, "campo": "texto_pt"}
        )
        ok += 1

    print(f"\ncorreções aplicadas: {ok} | falhas: {len(falhas)}")
    for f in falhas:
        print("  [FALHA]", f)

    if args.aplicar and not falhas:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        for item, d in cache.items():
            arq = ITENS / f"{item}.json"
            shutil.copy2(arq, BACKUPS / f"{item}_r6_{stamp}.json")
            arq.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
        print(f"gravados {len(cache)} ficheiros")
    elif args.aplicar:
        print("NADA GRAVADO (resolver falhas primeiro)")
        return 1
    else:
        print("(dry-run; use --aplicar para gravar)")
    return 0 if not falhas else 1


if __name__ == "__main__":
    raise SystemExit(main())
