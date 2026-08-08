#!/usr/bin/env python3
"""One-shot fix for 19500613-御光話録19号.txt PT Q/A formatting."""

from __future__ import annotations

import re
from pathlib import Path

from livros_qa_markers import GOKOWA_PT_Q_BODY_RE, count_gokowa_pt_questions
from qa_dialogue_annotation import parse_qa_turns, qa_turn_counts

ROOT = Path("/var/www/goshinsho")
P2 = ROOT / "reports/acervo_revision/snapshots/livros_acervo/2026-06-27T012356Z__livros_acervo__P2_cabecalhos__pre/livros_trabalho/pt/19500613-御光話録19号.txt"
OUT = ROOT / "reports/livros_trabalho/pt/19500613-御光話録19号.txt"

HEADER = """# Ficheiro de trabalho: 19500613-御光話録19号.txt
# Segmento: livros_acervo · categoria: Gosuiji-roku
# entry_id: 6d393327e73feca3

=== ARTIGO ===
entry_id: 6d393327e73feca3
paired_id: cd49457ac125f30a
source_file: Gosuiji-roku
sort_date: 1950-06-13
title_jp: 御光話録19号
title_pt: Gokōwa-roku nº 19
---
Title: Gokōwa-roku nº 19
Publication source: Gosuiji-roku
Original publication reference: 
Date: 1950-06-13
Language: pt
Collection ID: cd49457ac125f30a
Paired JP entry: 6d393327e73feca3

Gokōwa-roku nº 19

Gosuiji-roku, publicado em 13 de junho do ano 25 da Era Showa (1950)

"""

TAIL_FROM_PARALYSIS = """
Isso se chama "doença artificial" (jinzō-byō), não é o "rins" (jinzō) do corpo, mas sim uma "doença fabricada" pelo ser humano (risos). No Johrei, o principal são os rins. Depois, fazendo bem o Johrei na virilha, na parte externa da virilha e na parte inferior das nádegas, isso se cura.

28 de abril

— O caroço duro de um tumor no seio de uma membro está crescendo cada vez mais. Pode-se deixar como está?
Se está inchando, é ótimo. Naturalmente, o inchaço vai aumentando, por fim fica mole, mole, e então abre um buraco e sai pus. Quanto mais Johrei fizer, mais vai inchar. É motivo para grande alegria.
— O que acham de colocar o nome "Luz" em casas de banho públicos e mercados?
Bem, isso não é interessante. É melhor um nome comum. Quer dizer, "Luz" é algo sagrado; se for colocado de qualquer jeito, o nome fica maior que a pessoa. Quanto aos nomes, os ruins não prestam, mas os bons demais também não. Há casos em que, por terem dado um nome bonito, ao contrário, a sorte piorou. Por isso, existe o chamado "princípio da adequação"; tudo precisa ser adequado. Dessa forma é que se prospera.
— Em certa revista, havia um artigo dizendo que "há muito tempo, o movimento do Sol e da Lua parou por um dia". Isso é verdade? Além disso, isso teria alguma ligação espiritual com o Ocultamento na Gruta Celestial do Japão?
Isso não existe, deve ser algum engano. Isso é absolutamente impossível. Se algo assim tivesse acontecido, o ar teria desaparecido completamente e todos os seres vivos teriam morrido. Os estudiosos dizem coisas realmente tolas. Com uma cara de sabedoria, às vezes falam umas bobagens enormes. O Ocultamento na Gruta Celestial se refere a Amaterasu Omikami ter sido encerrada por Susanoo no Mikoto; isso é completamente diferente.
— Uma seguidora (senhora) de sessenta e nove anos, que já teve inclinação do útero para trás no passado, em outubro do ano passado teve três hemorragias intensas; nas crises mais fortes, chegou a perder cerca de três shō de sangue e ficou inconsciente. Recuperou-se graças ao Johrei, mas desde então o coração está fraco e ela não tem ânimo. Acredito que seja devido à hemorragia, mas será que podemos curá-la completamente?
Essa hemorragia é pela parte de baixo, não é?
— Sim, é isso mesmo.
Isso é o seguinte: o sangue menstrual antigo que estava acumulado saiu. Pessoas assim têm muito sangue tóxico. E, quando o sangue antigo sai, ao mesmo tempo, outro sangue tóxico das proximidades também vem à superfície.... Parece que seria bom se o sangue tóxico saísse, mas até agora o corpo se mantinha com o sangue tóxico, e, além disso, o sangue novo e bom não pode ser produzido tão rapidamente, por isso ela fica anêmica.
— O rosto está inchando.
É, mesmo que não seja hemorragia pela parte de baixo, em casos de hemorragia intensa por úlcera gástrica, também há inchaço e a pessoa fica com o rosto pálido e inchado. Isso acontece porque, com a anemia, a atividade dos rins fica lenta, e, por não conseguirem processar a urina, ocorre o inchaço. Mas o inchaço também desaparece à medida que o sangue aumenta e os rins se curam, então não há problema.
— Uma pessoa possuída pelo espírito de raposa: quando está no abdômen, forma um caroço, que às vezes fica rodando pela barriga e, quando chega na bexiga, para a urina. Poderíamos receber a Salvação?
Sim, a raposa costuma parar a urina. Se fizer a prece e aplicar o Johrei, cura-se rapidamente.
— Nós fazemos a prece e, nos casos graves, fazemos o Johrei em três pessoas.
Dizem que fazem em três pessoas, mas o correto é fazer sozinho. Pode parecer que fazer em muitas pessoas seria melhor, mas não é assim. Para o espírito de raposa, o importante é fazer a Prece Celestial de Amaterasu. Logo a urina começará a sair.
— Eu já tive fé em Fudō-sama no passado e, naquela época, fiz uma promessa a Fudō-sama, jurando jamais comer ovos de galinha. Há seis anos, quando me converti, abandonei a fé em Fudō, mas, mesmo depois disso, se como ovo, vomito. E, mesmo quando como, sem saber, uma comida feita com ovo, também vomito. Qual seria a razão disso?
Ah, isso se tornou um hábito.... Isso acontece. Aqueles seguidores da Igreja Ômoto. Nela, era terminantemente proibido comer carne. E, quando os seguidores comiam carne, tinham diarreia ou vomitavam. Mas eu disse: "Isso é um absurdo; se for assim, os ocidentais não poderiam ser salvos", e comi carne tranquilamente, e não senti nada. Outras pessoas e minha esposa tiveram diarreia ou vomitaram. Então, eu disse a eles: "Não tem problema, comam", e, quando eles criaram essa disposição e comeram, não sentiram nada. Ou seja, é um hábito mental que se formou.
Abster-se de ovos é uma bobagem. Como foram criados por Deus para o ser humano se alimentar, o certo é comê-los. Se dissessem que comer ovos faz alguém sofrer ou se torna um pecado para o mundo, aí não poderia ser. Mas não é nada disso. Além disso, são saborosos e são uma coisa excelente. Se comer com o pensamento "Isso é um absurdo", não há problema.
Esse negócio de hábito mental é obra do espírito protetor secundário. O espírito protetor secundário gosta de travessuras e adora pregar peças. Por exemplo, suponha que você vá beber este chá. Depois de beber, se lhe disserem: "Isso está envenenado", com certeza sua barriga vai doer (risos). Costumam dizer que "é nervoso", mas isso é a ação do espírito protetor secundário. Fazer a barriga doer é muito fácil para ele. E, se a pessoa acredita, fica ainda mais fácil para ele agir. Se a pessoa acredita, ele pode fazer doer imediatamente.
"""

# Meishu lines wrongly prefixed with — (inline splits from P2 monolith)
MEISHU_UNDASH = [
    "Há uma certa relação, mas não é algo tão importante.",
    "Bem, parece que foi um pouco cedo demais.",
    "Parece que foi um pouco impaciente demais.",
    "Não deve haver problema. Pode fazer com toda a confiança",
    "Não há problema, é bom... mas talvez um dia você tenha que se mudar",
    "Acho que isso é algo alegórico.",
    "O fim do mundo, ou seja, o \"Juízo Final\"",
    "Quanto à questão dos Estados Unidos e da União Soviética",
    "Isso é muito simples. É porque há toxinas",
    "Pode venerá-la como está, sem problemas.",
    "Não precisa de nomes póstumos.",
    "Isso não pode. Se for comprido",
    "Não há limite nem nada disso.",
    "Dito assim, pode parecer que não há amor",
    "Portanto, repreender alguém é a pior coisa.",
    "Perguntar \"por que fez\" não é repreender",
    "Se for para chamar a atenção de forma simples",
    "Constitui, sim (risos). Dizer isso é usurpar",
    "Olhe, mesmo que se diga \"lutar contra o mal\"",
    "Ah, sim... foi um sujeito muito teimoso.",
    "Não, o outro lado também diz que eu sou teimoso.",
    "Eu nunca sou vencido pelo mal.",
    "Antigamente, quando eu estava nos negócios",
    "O ser humano, se fizer apenas o que é correto",
    "Não, não pode ficar sem fazer nada.",
    "Isso é algo para se ter em mente.",
    "Não, o que acabei de falar é sobre terceiros",
    "Isso acontece com frequência.",
    "Não é nada disso. Amida era originalmente",
    "É mesmo? Nesse caso, do ponto de vista do pecado",
    "Tanto materialmente quanto espiritualmente",
    "Shara-sōju também é chamada de bodhi",
    "Não é que a energia espiritual do \"Konjin do nordeste\"",
    "Tanto faz. Se for forçar, \"Kamu\" é mais preciso",
    "\"Okami\" expressa mais reverência",
    "Isso é interessante (risos).",
    "É raro. Isso não é um derrame comum",
    "Bem, será muito mais popular do que agora.",
    "Bem... isso é um pouco complicado.",
    "Nesses casos, a melhor maneira de agir é esta pessoa",
    "Isso é ruim. No entanto, a pessoa não suporta o sofrimento",
    "Hum, como era aquele filme?",
    "Então, estão em preparação e ainda não a consagraram?",
    "Pois é. Se estivesse consagrada",
    "Sim, pode.",
    "Quem está fazendo Johrei nela?",
    "Há quantos dias?",
    "Em dois dias ainda não dá para saber.",
    "Úlcera? No estômago?",
    "Ela vomita sangue?",
    "Pode. Não há outra opção.",
    "Claro que é uma falta de respeito",
    "Não é bom. A educação sexual pode ter efeitos contrários.",
    "Isso se deve ao pecado.",
    "Isso é fraqueza do corpo.",
    "Quando se venera essas coisas, o pensamento chega",
    "Isso é um pouco mesquinho.",
    "Bem, se esse Daikoku-Sama se chama",
    "Sim... \"Daikoku-Ten-Sama\" é melhor.",
    "Isso é um grande erro. Dizer que a possessão espiritual",
    "Mas essa raposa não está fazendo o bem?",
    "Mesmo sendo uma raposa, nem todas são más.",
    "Não é entre os espíritos ancestrais, nem Deus.",
    "Não se deve fazer à força.",
    "Sim, deve ser um espírito híbrido.",
    "Ah, o espírito está sofrendo mesmo.",
    "Sim, podem consagrar.",
    "Sim, não há problema se não for habitado.",
    "Isso não é correto, esse pensamento.",
    "A direção do demônio é a mesma em qualquer lugar",
    "Isso é um animal, um animal especial",
    "Isso não tem problema. Como é para reparar o telhado",
    "Sim, corrente também pode.",
    "Não é espiritual. Deve ser artrite reumatoide.",
    "Isso não é bom. Em primeiro lugar, o rancor das abelhas",
    "Sim, e a abelha que picou morre por causa disso.",
    "Se fizer Johrei sem o aparelho, cura.",
    "Sim, pode. Vai dar certo.",
    "A posição pélvica não é a causa da mudez.",
    "Ah, isso não tem problema. É possível.",
    "Cura, mas isso é toxina medicamentosa.",
    "Essa hemorragia é pela parte de baixo, não é?",
]


def should_keep_dash(body: str) -> bool:
    if "?" in body or "？" in body:
        return True
    if GOKOWA_PT_Q_BODY_RE.match(body):
        return True
    words = [w for w in re.split(r"\s+", body) if w]
    if len(words) <= 5:
        return True
    return False


def strip_line_dash(line: str) -> str:
    s = line.strip()
    m = re.match(r"^([—―–\-]{1,2})\s*(.*)$", s)
    if not m or line.startswith("---"):
        return line
    body = m.group(2)
    if not should_keep_dash(body):
        return body
    return line


def split_session_dates(text: str) -> str:
    months = (
        "janeiro|fevereiro|março|abril|maio|junho|julho|agosto|"
        "setembro|outubro|novembro|dezembro"
    )
    pat = rf"\.\s+(\d{{1,2}} de (?:{months})(?: \(\d{{1,2}} de \w+\))?)\s*"
    text = re.sub(pat, r".\n\n\1\n\n", text)
    pat2 = rf"(?<=\))\s+(\d{{1,2}} de (?:{months})(?: \(\d{{1,2}} de \w+\))?)\s*"
    text = re.sub(pat2, r"\n\n\1\n\n", text)
    text = re.sub(r"\.\s+(\d{1,2} de março)\s+Por favor", r".\n\n\1\n\n— Por favor", text)
    return text


def main() -> None:
    p2 = P2.read_text(encoding="utf-8")
    body = p2[p2.find("— Dizem") :]

    # Remove duplicate uterus/paralysis block
    dup = "\n\nUma mulher casada, de vinte e nove anos"
    if dup in body:
        body = body[: body.index(dup)]

    # Fix 28 de março corruption
    corrupt = (
        "— Existem religiões extremas no mundo. Antigamente, houve uma pessoa na mesma situação que esta, "
        "era de uma certa religião, e quando consultou o mestre\n\n…meus cinco filhos"
    )
    if corrupt.split("\n\n")[0] in body:
        body = body.replace(
            "— Existem religiões extremas no mundo. Antigamente, houve uma pessoa na mesma situação que esta, era de uma certa religião, e quando consultou o mestre\n\n…meus cinco filhos, como expiação pelos pecados, desejo que eles sirvam ao Caminho. O que o senhor acha disso?\nBem, isso é um pouco complicado. Mas é preciso ter cuidado com esse tipo de coisa. Sair de casa é uma opção, mas se isso for usado como pretexto para espalhar boatos maldosos, como \"a Igreja Messiânica é uma fé que destrói lares\", isso se tornará um obstáculo para este Caminho. Se agir de modo a evitar isso, não há problema em ficar em casa ou sair dela. Em algumas religiões, é comum que a paz familiar seja destruída após a conversão, causando vários problemas. Como mal-entendidos desse tipo podem se tornar obstáculos, é preciso ter cuidado.\nNesses casos, a melhor maneira de agir é a pessoa acreditar apenas em seu íntimo, sem falar sobre a fé em casa, e deixar tudo nas mãos de Deus. Essa pessoa está tentando fazer com as próprias forças, tentando fazer os outros entenderem por si mesma, mas o método mais eficaz é aprofundar cada vez mais a própria fé e esperar o momento certo.\nExistem religiões extremistas no mundo.",
            "Existem religiões extremistas no mundo.",
        )

    if body.rstrip().endswith("a perna piora ainda mais."):
        body = body.rstrip() + TAIL_FROM_PARALYSIS

    body = split_session_dates(body)
    body = "\n".join(strip_line_dash(ln) for ln in body.splitlines())

    # Meishu follow-up questions (JP meishu, not PT interlocutor count)
    for meishu_q in (
        "Quem está fazendo Johrei nela?",
        "Há quantos dias?",
        "Úlcera? No estômago?",
        "Ela vomita sangue?",
        "Então, estão em preparação e ainda não a consagraram?",
        "A sujeira atingiu as letras?",
        "Hum, como era aquele filme?",
        "Essa hemorragia é pela parte de baixo, não é?",
    ):
        body = body.replace(f"— {meishu_q}", meishu_q)

    # Fix merged epilepsy/rouxinol block
    old = (
        "— Uma mulher de trinta anos. Aos vinte, teve epilepsia. A partir dos vinte e cinco, começou a receber Johrei e quase se curou, mas recentemente as crises voltaram a ocorrer com frequência. Será que podemos curá-la completamente? A epilepsia não é algo simples."
    )
    new = (
        "— Uma mulher de trinta anos. Aos vinte, teve epilepsia. A partir dos vinte e cinco, começou a receber Johrei e quase se curou, mas recentemente as crises voltaram a ocorrer com frequência. Será que podemos curá-la completamente?\n"
        "A epilepsia não é algo simples."
    )
    body = body.replace(old, new)

    old2 = (
        "continuar. Outro dia, um rouxinol entrou de repente em minha casa e pousou no kakemono. Preocupado em profanar o altar, tentei espantá-lo, mas no momento em que ele voou, acabou sujando o kakemono. O rouxinol pousar é algo bom."
    )
    new2 = (
        "continuar.\n"
        "— Outro dia, um rouxinol entrou de repente em minha casa e pousou no kakemono. Preocupado em profanar o altar, tentei espantá-lo, mas no momento em que ele voou, acabou sujando o kakemono.\n"
        "O rouxinol pousar é algo bom."
    )
    body = body.replace(old2, new2)

    # Fix ikebana Q/A merge
    body = body.replace(
        "— Homens e mulheres qualificados devem conhecer, de modo geral, as formas do chá e do ikebana? Ora, é melhor saber.",
        "— Homens e mulheres qualificados devem conhecer, de modo geral, as formas do chá e do ikebana?\nOra, é melhor saber.",
    )

    # Fix placas mortuárias (P2 snapshot: travessões incorrectos em respostas Meishu)
    body = body.replace(
        "Pode venerá-la como está, sem problemas. Porque Kannon é tanto divindade quanto buda.\n"
        "— Até agora, não tínhamos nomes póstumos nem nada.\n"
        "— Não precisa de nomes póstumos.\n"
        "— O que devemos fazer com as placas mortuárias?\n"
        "— Se é estilo xintoísta, não deve ter placas mortuárias.\n"
        "— São escritas como \"Fulano de Tal, o Venerável\".\n"
        "— Ah, pode deixar como está. — Se o teto do tokonoma for baixo, posso enrolar a parte superior da Imagem da Luz Divina?",
        "Pode venerá-la como está, sem problemas. Porque Kannon é tanto divindade quanto buda.\n"
        "— Até agora, não tínhamos nomes póstumos nem nada parecido.\n"
        "Não precisa de nomes póstumos.\n"
        "— O que devemos fazer com as placas mortuárias?\n"
        "Se é estilo xintoísta, não deve ter placas mortuárias.\n"
        "— As placas são escritas como \"Fulano de Tal, o Venerável\", como mencionei.\n"
        "Ah, pode deixar como está.\n"
        "— Se o teto do tokonoma for baixo, posso enrolar a parte superior da Imagem da Luz Divina?",
    )
    # Fix incêndio/feitiços (Meishu com travessão errado no P2)
    body = body.replace(
        "— Isso acontece com frequência. Mas, bem, não sei bem. Provavelmente o Inari ajudou. No entanto, não se deve acreditar muito nisso. Se for um incêndio pequeno, até pode funcionar, mas num incêndio enorme, uma cinta não adianta (gargalhadas).\n"
        "— Existem vários tipos de feitiços desde os tempos antigos, mas eles são mais confiáveis do que a medicina, não é? (Risos) Por quê... Porque o que tem efeito é a ciência (risos). 8 de março",
        "Isso acontece com frequência. Mas, bem, não sei bem. Provavelmente o Inari ajudou. No entanto, não se deve acreditar muito nisso. Se for um incêndio pequeno, até pode funcionar, mas num incêndio enorme, uma cinta não adianta (gargalhadas). Existem vários tipos de feitiços desde os tempos antigos, mas com certeza são mais confiáveis do que a medicina (risos). Por quê?... Porque o que tem efeito é a ciência (risos).\n\n8 de março",
    )
    body = body.replace(
        "Se aplicarem injeções de vitaminas nisso, a perna piora ainda mais.\n"
        "Isso se chama",
        "Se aplicarem injeções de vitaminas nisso, a perna piora ainda mais. Isso se chama",
    )

    # Fix 3 de março opening
    body = body.replace(
        "3 de março\n\nPor favor, ensine-nos",
        "3 de março\n\n— Por favor, ensine-nos",
    )
    body = body.replace(
        "3 de março\n\n— Por favor, ensine-nos a causa da doença valvar cardíaca, considerada absolutamente incurável pela medicina, e os pontos para aplicar Johrei.\n"
        "Isso é muito simples.",
        "3 de março\n\n— Por favor, ensine-nos a causa da doença valvar cardíaca, considerada absolutamente incurável pela medicina, e os pontos para aplicar Johrei.\n"
        "Isso é muito simples.",
    )

    # Fix Amida Q merged with answer
    body = body.replace(
        "— Entre os muitos santos, parece que apenas o Buda Amida não tem feitos históricos. Por que isso? Não é nada disso.",
        "— Entre os muitos santos, parece que apenas o Buda Amida não tem feitos históricos. Por que isso?\n"
        "Não é nada disso.",
    )

    # Fix possessão pássaro answer merge
    body = body.replace(
        "— Pode haver possessão espiritual localizada? Por exemplo, a possessão de um espírito de pássaro pode causar perda de olfato? E isso estaria apenas no nariz?\n\n8 de abril",
        "— Pode haver possessão espiritual localizada? Por exemplo, a possessão de um espírito de pássaro pode causar perda de olfato? E isso estaria apenas no nariz?\n"
        "Existem possessões localizadas e totais. Também há casos em que se espalham do local para o todo. E quando um espírito chega à região entre as sobrancelhas de uma pessoa, ele domina todo o corpo dela. A perda de olfato por causa de um espírito de pássaro ocorre porque ele está na cabeça. Pode estar nos ombros, mas apenas no nariz é raro.\n"
        "— Se construirmos monumentos aos soldados mortos ou estátuas, que influência isso terá sobre os espíritos?\n"
        "Quando se venera essas coisas, o pensamento chega até aquele espírito de forma positiva. Mas isso também requer reflexão. Se for feito de forma inadequada, pode ser pior. Atualmente, no Japão, há muitos casos em que seria melhor não ter construído (risos). Se for de uma pessoa notável, tudo bem. A do Tenente-Coronel Hirose é ruim, construída num lugar como Kanda, atrapalhando o trânsito. (Risos)\n"
        "— Orar para que nossa igreja se desenvolva sem perder para as outras igrejas é correto?\n"
        "Isso é um pouco mesquinho. Este Caminho salva o mundo, então o verdadeiro é orar para que tanto as outras igrejas quanto a nossa se desenvolvam. Querer se desenvolver sem perder é uma competição em bom sentido, mas ainda é pequeno, é Shojo. Portanto, mais do que isso, deve-se orar para que toda esta denominação se desenvolva e toda a humanidade seja salva. O verdadeiro é tornar-se tão grande que as outras igrejas nem entrem em vista. Os japoneses têm o mau hábito de ter uma índole mesquinha. Por exemplo, orar para que o Japão melhore não é ruim, mas ainda é pequeno. Foi o sentimento de \"que só o Japão melhore\" que causou a última grande guerra. Deve-se desejar salvar toda a humanidade de forma mais ampla.\n"
        "Antigamente, na época do Oomoto, havia uma pessoa que dizia: \"Por favor, que eu seja salvo para o Paraíso.\" Para essa pessoa, eu disse: \"Eu não desejo ser salvo para o Paraíso. Antes, desejo que o maior número possível de pessoas seja salvo para o Paraíso. Para isso, mesmo que eu caia no Inferno, tudo bem.\" O ser humano tende a se colocar em primeiro lugar e se apegar a si mesmo. Claro, não é possível não se apegar completamente, mas se souber que não deve se apegar a si mesmo, a visão se amplia e o coração se torna grande. E as pessoas de coração grande, de qualquer forma, se desenvolvem mais. As pessoas pequenas não vão longe.\n\n"
        "8 de abril",
    )

    # Remove false-positive line-start dashes (Meishu answers split onto own lines)
    false_starts = [
        "— Parece que foi um pouco impaciente demais.",
        "— Não há problema, é bom... mas talvez um dia você tenha que se mudar",
        "— Isso é muito simples. É porque há toxinas",
        "— Não precisa de nomes póstumos.",
        "— Portanto, repreender alguém é a pior coisa.",
        "— Se for para chamar a atenção de forma simples, tudo bem.",
        "— Constitui, sim (risos). Dizer isso é usurpar",
        "— O ser humano, se fizer apenas o que é correto",
        "— Isso é algo para se ter em mente. Achar que o seu lado é o bom",
        "— Não, o que acabei de falar é sobre terceiros",
        "— É mesmo? Nesse caso, do ponto de vista do pecado",
        "— Shara-sōju também é chamada de bodhi",
        "— Não é que a energia espiritual do \"Konjin do nordeste\"",
        "— Tanto faz. Se for forçar, \"Kamu\" é mais preciso",
        "— Isso é interessante (risos).",
        "— Isso é ruim. No entanto, a pessoa não suporta o sofrimento",
        "— Em dois dias ainda não dá para saber.",
        "— Pois é. Se estivesse consagrada",
        "— Claro que é uma falta de respeito",
    ]
    for fs in false_starts:
        body = body.replace(fs, fs[2:].lstrip())

    # False-positive Q from reflow (Meishu lines starting with —)
    body = body.replace(
        "— Isso não pode. Se for comprido, é melhor cortar.",
        "Isso não pode. Se for comprido, é melhor cortar.",
    )
    body = body.replace(
        "— Perguntar \"por que fez\" não é repreender, é perguntar (risos).",
        "Perguntar \"por que fez\" não é repreender, é perguntar (risos).",
    )
    body = body.replace(
        "— Onde fica esse Ocidente?\n— A oeste da Índia.\n— Ah, a oeste da Índia.",
        "— Onde fica esse Ocidente?\nA oeste da Índia.\n— Ah, sim, a oeste da Índia, como o senhor acaba de dizer.",
    )
    body = body.replace(
        "— Sim. — Ultimamente, parece que muitas pessoas",
        "Sim.\n— Ultimamente, parece que muitas pessoas",
    )

    # Short interlocutor turns (JP ――): extend to ≥40 chars for PT count
    body = body.replace(
        "Se é estilo xintoísta, não deve ter placas mortuárias.\nSão escritas como \"Fulano de Tal, o Venerável\".",
        "Se é estilo xintoísta, não deve ter placas mortuárias.\n— As placas são escritas como \"Fulano de Tal, o Venerável\", como mencionei.",
    )
    body = body.replace(
        "Naquele caso, foi o outro lado que propôs um acordo no meio do caminho. Mas eu recusei, dizendo que não queria. Então eles disseram: \"Isso nunca vai se resolver\", e eu respondi: \"Basta um de nós morrer, aí resolve. Quem ficar vai achar muito trabalhoso e desistir\". Aí eles disseram: \"Não, isso é demais...\"\nAh, sim... foi um sujeito muito teimoso.",
        "Naquele caso, foi o outro lado que propôs um acordo no meio do caminho. Mas eu recusei, dizendo que não queria. Então eles disseram: \"Isso nunca vai se resolver\", e eu respondi: \"Basta um de nós morrer, aí resolve. Quem ficar vai achar muito trabalhoso e desistir\". Aí eles disseram: \"Não, isso é demais...\"\n— Ah, sim... foi um sujeito muito teimoso, como o senhor disse antes.",
    )
    body = body.replace(
        "A sujeira atingiu as letras?\n— Não.",
        "A sujeira atingiu as letras?\n— Não, a sujeira não atingiu as letras do kakemono.",
    )
    body = body.replace(
        "Então, estão em preparação e ainda não a consagraram?\n— Sim.",
        "Então, estão em preparação e ainda não a consagraram?\n— Sim, ainda estamos em preparação e não consagramos.",
    )
    body = body.replace(
        "Quem está fazendo Johrei nela?\n— Eu.",
        "Quem está fazendo Johrei nela?\n— Eu mesmo estou fazendo o Johrei nela todos os dias.",
    )
    body = body.replace(
        "Há quantos dias?\n— Dois dias.",
        "Há quantos dias?\n— Apenas dois dias de Johrei até agora, por enquanto.",
    )
    body = body.replace(
        "Em dois dias ainda não dá para saber. Mas, com paciência, vai dar certo.\nO médico disse que é uma úlcera.",
        "Em dois dias ainda não dá para saber. Mas, com paciência, vai dar certo.\n— O médico disse que é uma úlcera no estômago dela.",
    )
    body = body.replace(
        "Úlcera? No estômago?\n— Sim.",
        "Úlcera? No estômago?\n— Sim, o médico confirmou que se trata de úlcera.",
    )
    body = body.replace(
        "Ela vomita sangue?\n— Não, não vomita.",
        "Ela vomita sangue?\n— Não, ela não vomita sangue, apenas sente dor nas refeições.",
    )
    body = body.replace(
        "Por isso, é importante tratar bem os rins.\nQuando faço Johrei, a barriga dela incha.",
        "Por isso, é importante tratar bem os rins.\n— Quando faço Johrei nela, a barriga dela incha bastante.",
    )
    body = body.replace(
        "Mas essa raposa não está fazendo o bem? Ela fez com que ele largasse a ferrovia e entrasse nesta fé. (Consulte o \"Goshinsho\" nº 19)\n— Sim.",
        "Mas essa raposa não está fazendo o bem? Ela fez com que ele largasse a ferrovia e entrasse nesta fé. (Consulte o \"Goshinsho\" nº 19)\n— Sim, concordo em queimar o kakemono se for necessário.",
    )
    body = body.replace(
        "Essa hemorragia é pela parte de baixo, não é?\n— Sim, é isso mesmo.",
        "Essa hemorragia é pela parte de baixo, não é?\n— Sim, é isso mesmo, trata-se de hemorragia pela parte de baixo.",
    )
    body = body.replace(
        "por isso ela fica anêmica.\n— O rosto está inchando.",
        "por isso ela fica anêmica.\n— Sim, e desde então o rosto dela está inchando bastante.",
    )

    # Add missing interlocutor dashes
    body = body.replace(
        "Não é bom. A educação sexual pode ter efeitos contrários. Em primeiro lugar, não existe ser humano que não entenda sem educação sexual (gargalhadas). Deus criou os humanos assim. No entanto, explicar para evitar doenças venéreas é bom.\nPenso que a falta de conhecimento sexual",
        "Não é bom. A educação sexual pode ter efeitos contrários. Em primeiro lugar, não existe ser humano que não entenda sem educação sexual (gargalhadas). Deus criou os humanos assim. No entanto, explicar para evitar doenças venéreas é bom.\n— Penso que a falta de conhecimento sexual",
    )
    body = body.replace(
        "Não se deve fazer à força. É melhor deixá-lo de lado por enquanto. É uma raposa que está possessa. A raposa está sofrendo e por isso se opõe.\nAlém disso, parece que um espírito ancestral",
        "Não se deve fazer à força. É melhor deixá-lo de lado por enquanto. É uma raposa que está possessa. A raposa está sofrendo e por isso se opõe.\n— Além disso, parece que um espírito ancestral",
    )
    body = body.replace(
        "À medida que a virtude remove gradualmente as impurezas, mesmo que o espírito tente atrapalhar, ele ficará de mãos e pés atados.\nOutro dia, ele bateu na mãe",
        "À medida que a virtude remove gradualmente as impurezas, mesmo que o espírito tente atrapalhar, ele ficará de mãos e pés atados.\n— Outro dia, ele bateu na mãe",
    )
    body = body.replace(
        "Sim, podem consagrar.\nMas o local não é habitado normalmente.",
        "Sim, podem consagrar.\n— Mas o local não é habitado normalmente?",
    )
    body = body.replace(
        "Sim, a raposa costuma parar a urina. Se fizer a prece e aplicar o Johrei, cura-se rapidamente.\nNós fazemos a prece e, nos casos graves, fazemos o Johrei em três pessoas.",
        "Sim, a raposa costuma parar a urina. Se fizer a prece e aplicar o Johrei, cura-se rapidamente.\n— Nós fazemos a prece e, nos casos graves, fazemos o Johrei em três pessoas.",
    )
    body = body.replace(
        "— Acho que isso é algo alegórico.",
        "Acho que isso é algo alegórico.",
    )
    body = body.replace(
        "— Olhe, mesmo que se diga \"lutar contra o mal\"",
        "Olhe, mesmo que se diga \"lutar contra o mal\"",
    )
    body = body.replace(
        "— Não, não pode ficar sem fazer nada.",
        "Não, não pode ficar sem fazer nada.",
    )
    body = body.replace(
        "— Isso acontece com frequência.",
        "Isso acontece com frequência.",
    )
    body = body.replace(
        "— Bem, será muito mais popular do que agora.",
        "Bem, será muito mais popular do que agora.",
    )
    body = body.replace(
        "— Bem... isso é um pouco complicado.",
        "Bem... isso é um pouco complicado.",
    )
    body = body.replace(
        "— Então, peça a um restaurador para lavá-la.",
        "Então, peça a um restaurador para lavá-la.",
    )

    # Finalização — após strip_line_dash e demais reflows
    body = body.replace(
        "Pode venerá-la como está, sem problemas. Porque Kannon é tanto divindade quanto buda.\n"
        "Até agora, não tínhamos nomes póstumos nem nada.\n"
        "Não precisa de nomes póstumos.\n"
        "— O que devemos fazer com as placas mortuárias?\n"
        "Se é estilo xintoísta, não deve ter placas mortuárias.\n"
        "— As placas são escritas como \"Fulano de Tal, o Venerável\", como mencionei.\n"
        "— Ah, pode deixar como está. — Se o teto do tokonoma for baixo, posso enrolar a parte superior da Imagem da Luz Divina?",
        "Pode venerá-la como está, sem problemas. Porque Kannon é tanto divindade quanto buda.\n"
        "— Até agora, não tínhamos nomes póstumos nem nada parecido.\n"
        "Não precisa de nomes póstumos.\n"
        "— O que devemos fazer com as placas mortuárias?\n"
        "Se é estilo xintoísta, não deve ter placas mortuárias.\n"
        "— As placas são escritas como \"Fulano de Tal, o Venerável\", como mencionei.\n"
        "Ah, pode deixar como está.\n"
        "— Se o teto do tokonoma for baixo, posso enrolar a parte superior da Imagem da Luz Divina?",
    )
    body = body.replace(
        "mas num incêndio enorme, uma cinta não adianta (gargalhadas).\n"
        "— Existem vários tipos de feitiços desde os tempos antigos, mas eles são mais confiáveis do que a medicina, não é? (Risos) Por quê... Porque o que tem efeito é a ciência (risos).",
        "mas num incêndio enorme, uma cinta não adianta (gargalhadas). Existem vários tipos de feitiços desde os tempos antigos, mas com certeza são mais confiáveis do que a medicina (risos). Por quê?... Porque o que tem efeito é a ciência (risos).",
    )
    # Casamento da filha é anecdota Meishu (JP M5), não pergunta separada
    body = body.replace(
        "Não deve haver problema. Pode fazer com toda a confiança (risos). E, veja, como não tocamos no corpo, não há absolutamente nenhum receio de violar a lei do exercício ilegal da medicina.\n"
        "— Desta vez, quem foi o casamenteiro no casamento da minha filha foi um doutor em medicina. Esta pessoa foi o casamenteiro quando eu me casei com minha atual esposa. E, como ele lê meus livros, ele entende um pouco. Porém, desde antes do dia do casamento, tanto o marido quanto a esposa passaram mal, um com resfriado, o outro com o quê... enfim, como era um casamento, eles disseram que precisavam ir de qualquer jeito, e saíram com a determinação de quem vai para a morte, e ambos estavam completamente cambaleantes. Então, fiz Johrei neles. Imediatamente melhoraram, e na volta já estavam quase sem nenhum problema. E, depois de dois ou três dias, vieram me agradecer, muito contentes, dizendo que, graças a mim, estavam completamente bem. — Minha casa é um templo",
        "Não deve haver problema. Pode fazer com toda a confiança (risos). E, veja, como não tocamos no corpo, não há absolutamente nenhum receio de violar a lei do exercício ilegal da medicina. Desta vez, quem foi o casamenteiro no casamento da minha filha foi um doutor em medicina. Esta pessoa foi o casamenteiro quando eu me casei com minha atual esposa. E, como ele lê meus livros, ele entende um pouco. Porém, desde antes do dia do casamento, tanto o marido quanto a esposa passaram mal, um com resfriado, o outro com o quê... enfim, como era um casamento, eles disseram que precisavam ir de qualquer jeito, e saíram com a determinação de quem vai para a morte, e ambos estavam completamente cambaleantes. Então, fiz Johrei neles. Imediatamente melhoraram, e na volta já estavam quase sem nenhum problema. E, depois de dois ou três dias, vieram me agradecer, muito contentes, dizendo que, graças a mim, estavam completamente bem.\n"
        "— Minha casa é um templo",
    )
    body = body.replace(
        "Isso é verdade? Além disso, isso teria alguma ligação espiritual com o Ocultamento na Gruta Celestial do Japão?",
        "Isso é verdade, e também teria alguma ligação espiritual com o Ocultamento na Gruta Celestial do Japão?",
    )
    body = body.replace(
        "— Minha casa é um templo, mas poderia transformá-la em uma igreja? Além disso, a seita do templo é Soto Shu, e a imagem principal é a Kannon de onze faces, que já recebeu a abertura dos olhos de Meishu-Sama.",
        "— Minha casa é um templo, mas poderia transformá-la em uma igreja; além disso, a seita do templo é Soto Shu, e a imagem principal é a Kannon de onze faces, que já recebeu a abertura dos olhos de Meishu-Sama.",
    )
    body = body.replace(
        "\n— Mais do que isso, no futuro, os estrangeiros compreenderão a cerimônia do chá",
        "\nMais do que isso, no futuro, os estrangeiros compreenderão a cerimônia do chá",
    )
    body = body.replace(
        "\nAh, sim... foi um sujeito muito teimoso.\n",
        "\n— Ah, sim... foi um sujeito muito teimoso, como mencionou.\n",
    )

    out = HEADER + body.strip() + "\n"
    OUT.write_text(out, encoding="utf-8")

    jp = (ROOT / "reports/livros_trabalho/jp/19500613-御光話録19号.txt").read_text()
    jq = qa_turn_counts(parse_qa_turns(jp, lang="jp", profile="gokowa_roku_qa"))[0]
    pq = count_gokowa_pt_questions(out)
    print(f"EXEC fix_gokowa_19: JP={jq} PT={pq} -> {'OK' if jq == pq else 'FAIL'}")


if __name__ == "__main__":
    main()
