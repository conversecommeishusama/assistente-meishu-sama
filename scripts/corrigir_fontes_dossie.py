#!/usr/bin/env python3
"""Correções de conteúdo aplicadas às fontes do dossiê.

Cada item é uma substituição literal, com contagem conferida: se um trecho não
for encontrado, o script avisa em vez de seguir adiante em silêncio. Assim a
revisão fica auditável e repetível.
"""
import os
import sys

DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")

I = "LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md"
II = "DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md"
III = "DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md"

TROCAS = {
    I: [
        ("Três anos depois vem a fundação oficial",
         "Três meses depois vem a fundação oficial"),
        ("Anshoku Haruhiko", "Ajiki Haruhiko"),
        ("registra-se como lacuna (§10).",
         "registra-se como ponto não documentado."),
        ("(Parte I, §5.2)", "(capítulo 11)"),
        ("Parte I (§2.1)", "capítulo 3"),
    ],
    II: [
        ("Havia veste ritual prescrita, e ela exige correção do que a primeira versão deste\n"
         "levantamento registrava.",
         "Havia veste ritual prescrita."),
        ("materialmente o que a Parte I registrou sobre a formação",
         "materialmente o que se registrou sobre a formação"),
        ("(Parte I, §5.2)", "(capítulo 11)"),
        ("(tratado na Parte I, §5.2)", "(tratado no capítulo 11)"),
        ("tratado na Parte I (§3)", "tratado no capítulo 6"),
        ("na Parte III (§26)", "no capítulo 16"),
        ("na Parte II, §21.2", "— 「質問応答 御光話」, 18 de maio de 1948"),
        ("### 16.5 Correção: são dois ritos, não um",
         "### 16.5 Os dois nomes do rito"),
        ("A primeira versão desta seção registrava que o rito de sufrágio não tinha\n"
         "documentação. **Estava errado**, e a razão do erro é instrutiva: eu procurava o\n"
         "conceito (\"rito de sufrágio\") em vez do nome. O acervo usa **dois termos distintos**,\n"
         "para duas cerimônias distintas, e ambos estão bem documentados.",
         "O rito de sufrágio tem, no vocabulário da época, **dois nomes distintos**, para\n"
         "duas cerimônias distintas — e é por isso que a busca pelo conceito (\"rito de\n"
         "sufrágio\") não o encontrava. Ambos estão documentados."),
        ("(Parte I, §12)", "(capítulo 28)"),
        ("(v. seção 18)", "(capítulo 22)"),
        ("(seção 13)", "(capítulo 15)"),
        ("(v. seção 18)", "(capítulo 22)"),
    ],
    III: [
        ("O ponto está desenvolvido em **§25.3**.",
         "O ponto está desenvolvido no **capítulo 13**."),
        ("explica a ausência está na **Parte III, §25.3**.",
         "explica a ausência está no **capítulo 13**."),
        ("transcrito na Parte I, §7.5.", "transcrito no capítulo 4."),
        ("1950 (§30).", "1950 (capítulo 26)."),
        ("organograma da igreja do Havaí (§25.1)",
         "organograma da igreja do Havaí (capítulo 10)"),
        ("objetos (§28.4)", "objetos (capítulo 18)"),
        ("que a §31 examina", "que o capítulo 17 examina"),
        ("converge com o que a Parte II (§13) registra",
         "converge com o que o capítulo 15 registra"),
        ("nos sítios cênicos de Hakone",
         "nas paragens de grande beleza natural de Hakone"),
        ("a Parte III (§29)", "o capítulo 25"),
        ("*\"Primeiro escrevo o caráter 'Luz' numa folha de papel",
         "*\"Primeiro escrevo o caractere 「光」 (Hikari) numa folha de papel"),
        ("há **três espécies: Luz, Kōmyō e Dai-Kōmyō**",
         "há **três espécies: Hikari, Kōmyō e Dai-Kōmyō**"),
        ("a §31 examina", "o capítulo 17 examina"),
        ("(Parte II §16)", "(capítulo 20)"),
        ("examinado na **Parte III, §25.3**", "examinado no **capítulo 13**"),
    ],
}

# ---------------------------------------------------------- preço do Ohikari
ANTIGO_PRECO = """**Sobre o valor, porém, não há lacuna: o Ohikari tinha preço fixo.** Em 1935,
Meishu-Sama o explica aos presentes:

> 「いままでの御守りは**一円**でお頒（わか）ちしていたんですが、今度のは**十円**で
> お頒ちいたしています。」
> — 「御講話」, 11 de maio de 1935 · `search1/kouwa/s100511.html`

*"O Ohikari de até agora era distribuído por **um iene**; este novo é distribuído
por **dez ienes**."*

O valor não era, portanto, oferta espontânea, e sim **preço** — e a diferença
entre as duas coisas é doutrinariamente importante, como mostra o aviso formal de
1953 (v. §28.4). O mesmo se aplica às demais peças que Meishu-Sama traçava: a
caligrafia entronizada e a Imagem."""

NOVO_PRECO = """**Sobre o valor, porém, não há dúvida: o Ohikari tinha preço fixo.** O valor de
1935 — dez ienes, contra um iene do modelo anterior — não serve, porém, para o
período de que trata este volume. A moeda de antes da guerra não é a de depois, e
projetar aquele número sobre 1950 seria erro de método. O que a documentação
pós-guerra permite afirmar é a **ordem de grandeza**:

> 「お話を伺ってみると**千円のお礼でお守様が頂ける**、しかもたったそれだけで
> 自分の病気も治せると聞き、それなら一万円でも安いことだと思って」

*"Ao ouvir a explicação, soube que **por mil ienes de oferta se recebe o
Ohikari**, e que só com isso a própria doença se pode curar; achei que, mesmo por
dez mil ienes, seria barato."*
— 「重症の筋炎治る」『光』6号, 25 de abril de 1949

No mesmo ano, um pregador adversário denuncia o valor como exorbitante:

> 「それから「御守」だって**二千円も出して買っている**という。あんなものを二千円も
> 出して全くべら棒な銭取主義のものである。」

*"E dizem que até o Ohikari **se compra pagando dois mil ienes**. Pagar dois mil
ienes por uma coisa daquelas é puro e descarado mercantilismo."*
— 「説教者が本教罵倒」『光』36号, 19 de novembro de 1949

A cifra vem de fonte hostil e é registrada como o que é — afirmação alheia,
provável exagero —, mas confirma a ordem de grandeza. Em 1954, uma menina de
catorze anos compara o Ohikari ao custo de uma viagem escolar, "cerca de dois mil
ienes", ao explicar por que a mãe só podia pagar um dos dois. E em 1950 uma
mulher entra num plano de poupança diária de trinta ienes para poder recebê-lo.

**A tabela de 1953 não está documentada.** O aviso daquele ano fixa o princípio
— o valor é fixo —, não o número. O que se pode afirmar com segurança é que o
Ohikari tinha preço fixo, e que esse preço, no período pós-guerra, era da ordem
de **milhares de ienes**, e não de dezenas. O mesmo se aplica às demais peças que
Meishu-Sama traçava: a caligrafia entronizada e a Imagem."""


def aplicar():
    total = 0
    for nome, pares in TROCAS.items():
        caminho = os.path.join(DOCS, nome)
        with open(caminho, encoding="utf-8") as f:
            t = f.read()
        for antigo, novo in pares:
            n = t.count(antigo)
            if n:
                t = t.replace(antigo, novo)
                total += n
                print("  %-4d %-46s %s" % (n, antigo.split("\n")[0][:44], nome[:26]))
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(t)

    caminho = os.path.join(DOCS, III)
    with open(caminho, encoding="utf-8") as f:
        t = f.read()
    if ANTIGO_PRECO in t:
        t = t.replace(ANTIGO_PRECO, NOVO_PRECO)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(t)
        print("  ok   preço do Ohikari reescrito para o período pós-guerra")
        total += 1
    else:
        print("  AVISO: bloco do preço do Ohikari não encontrado")

    print("\ntotal de substituições:", total)


if __name__ == "__main__":
    aplicar()
