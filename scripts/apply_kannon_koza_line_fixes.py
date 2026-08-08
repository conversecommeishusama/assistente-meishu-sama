#!/usr/bin/env python3
"""Correções cirúrgicas linha a linha — 観音講座 PT (aulas 4–7). Não é reflow em massa."""
from pathlib import Path

PT = Path("/var/www/goshinsho/reports/livros_trabalho/pt/19350000-観音講座　（１～７）.txt")


def main() -> None:
    text = PT.read_text(encoding="utf-8")
    original = text

    replacements = [
        # Aula 4 — fim (神霊＝日本 / 科学＝外国)
        (
            "No final, os espíritos de divindades e a Ciência se unem.\n\n"
            "os espíritos de divindades está no Japão, e a Ciência também está no exterior. "
            "Os espíritos de divindades e a Ciência estão se aproximando a uma velocidade tremenda.\n\n"
            "espíritos de divindades = Japão = Amaterasu-Omikami = Origem do Sol = Extremamente Micro e Extremamente Macro\n"
            "Ciência = Exterior = Susanoo-no-Mikoto = Judá\n"
            "Quando a Judá se submeter ao Japão, será o início do 5, 6, 7, e o primeiro passo para o Mundo da Grande Luz.",
            "No final, espíritos de divindades e Ciência se unem.\n\n"
            "Espíritos de divindades estão no Japão, e a Ciência também está no exterior. "
            "Espíritos de divindades e Ciência estão se aproximando a uma velocidade tremenda.\n\n"
            "Espíritos de divindades = Japão = Amaterasu-Omikami = Origem do Sol = Extremamente Micro e Extremamente Macro\n"
            "Ciência = Exterior = Susanoo-no-Mikoto = Judá\n\n"
            "Quando a Judá se submeter ao Japão, será o início do 5, 6, 7, e o primeiro passo para o Mundo da Grande Luz.",
        ),
        # Aula 5 — truncamento ikiryō (JP 744)
        (
            "Como aquele espírito está ouvindo, aquela pessoa também, de alguma forma,\n"
            "Às vezes, compreendemos algo porque o espírito está ouvindo.",
            "Como aquele espírito está ouvindo, aquela pessoa também, de alguma forma, "
            "consegue compreender alguma coisa, porque o espírito está ouvindo.",
        ),
        # Aula 5 — parágrafo colapsado (JP 746–747): Kannon sentada / senhora Kunitokotachi
        (
            "Os espíritos de Yachimata (encruzilhada) também têm tamanho semelhante ao dos humanos, "
            "e tornam-se maiores à medida que adquirem divindade. A figura de Kannon, quando sentada, "
            "alcança até a altura do lintel da porta. Eu, ao ver essa figura, a desenhei, e essa imagem "
            "tornou-se o objeto de culto principal da antiga Sede, a chamada \"Kannon do Sol Nascente\".\n\n"
            "Ela está quase nua",
            "Os espíritos de Yachimata (encruzilhada) também têm tamanho semelhante ao dos humanos, "
            "e tornam-se maiores à medida que adquirem divindade.\n\n"
            "A figura de Kannon, quando sentada, alcança até a altura do lintel da porta. "
            "Eu, ao ver essa figura, a desenhei, e essa imagem tornou-se o objeto de culto principal "
            "da antiga Sede, a chamada \"Kannon do Sol Nascente\".\n\n"
            "Ela está quase nua",
        ),
        # Aula 5 fim — estrutura empresarial (JP ~820)
        (
            "As empresas, dentro do mesmo ramo, serão todas unificadas em uma só. "
            "O método de gestão será classificado nos três níveis a seguir. "
            "Estrutura Empresarial: Governo, Capitalistas, Trabalhadores (incluReview diretores, funcionários, técnicos) "
            "Desta forma, será dividido em três partes",
            "As empresas, dentro do mesmo ramo, serão todas unificadas em uma só. "
            "O método de gestão será classificado nos três níveis a seguir.\n\n"
            "**Estrutura Empresarial:**\n"
            "Governo, Capitalistas, Trabalhadores (incluindo diretores, funcionários, técnicos)\n\n"
            "Desta forma, será dividido em três partes",
        ),
        # typo fix in above - I had typo "incluiReview" - let me use correct old string
    ]

    # Fix typo in replacement - use correct old string
    replacements[-1] = (
        "As empresas, dentro do mesmo ramo, serão todas unificadas em uma só. "
        "O método de gestão será classificado nos três níveis a seguir. "
        "Estrutura Empresarial: Governo, Capitalistas, Trabalhadores (incluindo diretores, funcionários, técnicos) "
        "Desta forma, será dividido em três partes",
        "As empresas, dentro do mesmo ramo, serão todas unificadas em uma só. "
        "O método de gestão será classificado nos três níveis a seguir.\n\n"
        "**Estrutura Empresarial:**\n"
        "Governo, Capitalistas, Trabalhadores (incluindo diretores, funcionários, técnicos)\n\n"
        "Desta forma, será dividido em três partes",
    )

    replacements.extend([
        # Aula 6 — eletricidade (JP 846)
        (
            "Nesta era, a invenção da luz surgirá. Isto é eletricidade... Isso é algo como uma luz semelhante a uma chama.",
            "Nesta era, surgirá a invenção da luz. Trata-se de uma luz semelhante à eletricidade.",
        ),
        # Aula 6 — diagrama Japão/Coreia/China (JP 882–889)
        (
            "China: Banko Shin'ō (盤古神王) – Bem (Shakyamuni, Maomé, Confúcio) Os descendentes de Banko, o Bem, pereceram, e o pensamento do Ocidente, o mundo do Mal (os descendentes de Susanoo no Mikoto: judeus, Maçon, Jesus são todos ocidentais), tornou-se popular. Até agora,\n"
            "Porque realmente não conheciam a morte",
            "China: Banko Shin'ō (盤古神王) – Bem (Shakyamuni, Maomé, Confúcio)\n\n"
            "Os descendentes de Banko, o Bem, pereceram, e o pensamento do Ocidente, o mundo do Mal "
            "(os descendentes de Susanoo no Mikoto: judeus, Maçon, Jesus são todos ocidentais), tornou-se popular.\n\n"
            "Até agora, porque realmente não conheciam a morte",
        ),
        # Aula 7 — febre (JP 999)
        (
            "mesmo após mais de cem dias, a estado ligeiramente febril não baixava",
            "mesmo após mais de cem dias, a febre ligeira não baixava",
        ),
        # Aula 7 — origem medicina + tabela corrompida (JP 1009–1018)
        (
            "Se não estudarmos essa raiz, é natural que não cure. A Origem da Medicina Ocidental Em 1855 d.C., Virchow criou a patologia celular, e a medicina começou a partir daí. A partir desse momento, começou a medicina superficial. Atualmente, vários problemas estão surgindo entre as classes alta e baixa, capitalistas e trabalhadores, etc. Causa, {, Nobreza, Políticos, Líderes Religiosos, }, {, Doença, Infelicidade\n"
            "Capitalistas, Jornalistas, Classe Alta, Radicalização, Piora, Resultado\n"
            "Acadêmicos, Educadores, etc., Gangues violentas\n"
            "O resultado das ações dessas pessoas da classe alta é como descrito à direita.",
            "Se não estudarmos essa raiz, é natural que não cure.\n\n"
            "**A Origem da Medicina Ocidental**\n\n"
            "Em 1855 d.C., Virchow criou a patologia celular, e a medicina começou a partir daí. "
            "A partir desse momento, começou a medicina superficial.\n\n"
            "Atualmente, vários problemas estão surgindo entre as classes alta e baixa, capitalistas e trabalhadores, etc.\n\n"
            "Causa → Resultado\n\n"
            "Nobreza, Políticos, Líderes Religiosos → Doença, Infelicidade\n"
            "Capitalistas, Jornalistas, Classe Alta → Radicalização, Piora\n"
            "Acadêmicos, Educadores, etc. → Gangues violentas\n\n"
            "O resultado das ações dessas pessoas da classe alta é como descrito à direita.",
        ),
        # Aula 7 — diagrama espírito-corpo colapsado (JP 1023–1028)
        (
            "Espírito Corpo Espírito Corpo\n"
            "| | | |\n"
            "Deus Política Realização Culto Política Unificados Amaterasu Ōmikami Estão ignorando Amaterasu Ōmikami.",
            "Espírito    Corpo              Espírito    Corpo\n"
            "|           |                  |           |\n"
            "Deus        Política             Culto       Política\n"
            "            Realização                       Unificados\n\n"
            "**Amaterasu Ōmikami**\n\n"
            "Estão ignorando Amaterasu Ōmikami.",
        ),
        # Aula 7 — diagrama medicina colapsado (JP 1046–1064)
        (
            "Na doença pulmonar, surge febre. Grande Deusa Amaterasu Mundo Espiritual Mundo do Ar Mundo Manifesto\n"
            "| | | / Sentimento\n"
            "Fogo (Espírito da Lua) Água Terra O Sol é o calor do amor\n"
            "| | |\n"
            "Coração Pulmão Estômago = Matéria A Lua é a verdadeira fé\n"
            "\\ Razão Izanami-no-Mikoto Trindade Cinco Três\n"
            "| | | Cinco Três\n"
            "Mundo Divino Mundo Espiritual Mundo Manifesto Mundo Divino = Fogo principal, Água secundário Sol = Japão\n"
            "| | |\n"
            "Izanami-no-Mikoto Vida (Mikoto) Súditos (Pessoas) Mundo Espiritual = Água principal, Fogo secundário Lua = Países estrangeiros\n"
            "| | | Três Cinco\n"
            "Três Cinco O Sol e a Lua se unem e formam a civilização da Luz (Mei).\n\n"
            "Este é o Mundo da Luz.\n\n"
            "Tamagawa Futuramente, será construído o Santuário de Izanami-no-Mikoto.\n\n"
            "||\n"
            "Cinco Três Todos os deuses, exceto a Grande Deusa Amaterasu, são anjos (anjo).",
            "Na doença pulmonar, surge febre.\n\n"
            "Grande Deusa Amaterasu    Mundo Espiritual    Mundo do Ar    Mundo Manifesto\n"
            "|                         |                   |              /\n"
            "Fogo (espírito da Lua)    Água                Terra          Sentimento\n"
            "|                         |                   |\n"
            "Coração                   Pulmão              Estômago = matéria\n\n"
            "O Sol é o calor do amor; a Lua é a verdadeira fé / razão.\n\n"
            "Izanami-no-Mikoto    Trindade    Cinco Três\n\n"
            "Mundo Divino    Mundo Espiritual    Mundo Manifesto\n"
            "Mundo Divino = fogo principal, água secundária (Sol = Japão)\n"
            "Mundo Espiritual = água principal, fogo secundário (Lua = países estrangeiros)\n\n"
            "Izanami-no-Mikoto    Vida (Mikoto)    Súditos (pessoas)\n\n"
            "O Sol e a Lua se unem e formam a civilização da Luz.\n"
            "Este é o Mundo da Luz.\n\n"
            "Tamagawa — futuramente será construído o Santuário de Izanami-no-Mikoto.\n\n"
            "Cinco Três — todos os deuses, exceto a Grande Deusa Amaterasu, são anjos.",
        ),
        # Aula 6 — Ocidente/Japão colapsados (JP 899–907)
        (
            "Soberano humano – Governo humano – Hegemonia – Humanidade – Artificial – Igualdade – Liberal Japão\n"
            "Familiarismo – Harmonia – Pássaro (som) – Espiritual – É Deus / Centrado no coração – Dever – Discreto\n"
            "Árvore – Fogo – Esquerda – Deus / Patriarcado – Lealdade filial – Coexistência e prosperidade mútua – País que não levanta palavras (kotage senu kuni)\n"
            "Soberano divino – Governo celestial – Caminho Imperial – Caminho dos Deuses – Natural e Divino – Sistema hierárquico – Disciplinado Isso, sem se inclinar para nada, harmonizado, é a civilização futura, ou seja, a civilização japonesa.",
            "Soberano humano – Governo humano – Hegemonia – Humanidade – Artificial – Igualdade – Liberal\n\n"
            "Japão\n"
            "Familiarismo – Harmonia – Pássaro (som) – Espiritual – É Deus / Centrado no coração – Dever – Discreto\n"
            "Árvore – Fogo – Esquerda – Deus / Patriarcado – Lealdade filial – Coexistência e prosperidade mútua – País que não levanta palavras (kotage senu kuni)\n"
            "Soberano divino – Governo celestial – Caminho Imperial – Caminho dos Deuses – Natural e Divino – Sistema hierárquico – Disciplinado\n\n"
            "Isso, sem se inclinar para nada, harmonizado, é a civilização futura, ou seja, a civilização japonesa.",
        ),
    ])

    applied = 0
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new, 1)
            applied += 1
        else:
            print(f"WARN: patch not found ({old[:60]}...)")

    # Split chinkon mega-paragraph at JP 744/745 boundary
    chinkon_marker = (
        "tornam-se conforme os pensamentos. Neste local de reunião também estão vindo vários espíritos."
    )
    chinkon_split = (
        "tornam-se conforme os pensamentos.\n\n"
        "Neste local de reunião também estão vindo vários espíritos."
    )
    if chinkon_marker in text:
        text = text.replace(chinkon_marker, chinkon_split, 1)
        applied += 1

    # Split JP 745 — multitude in hall
    hall_marker = (
        "porque o espírito está ouvindo.\n\n"
        "Dessa forma, neste salão, há uma multidão tão grande"
    )
    if hall_marker not in text:
        alt = "porque o espírito está ouvindo.\n\nDessa forma, neste salão"
        if alt.replace("\n\n", "\n") in text.replace("\n\n", "\n"):
            pass  # already split

    if text == original:
        print("No changes applied")
    else:
        PT.write_text(text, encoding="utf-8")
        print(f"Applied {applied} patches; saved {PT}")


if __name__ == "__main__":
    main()
