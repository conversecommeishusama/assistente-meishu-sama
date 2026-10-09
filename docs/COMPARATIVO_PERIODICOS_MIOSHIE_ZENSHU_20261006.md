# Comparativo final: periódicos, Mioshie-shū e lacuna real de conteúdo canônico

> ## ⚠️ CORREÇÃO — 07/10/2026
>
> A conclusão deste documento ("periódicos reais ausentes: 0" e "lacuna de só 1
> trecho") **estava errada**. Ela media **arquivos/séries de periódico**, não os
> **artigos individuais** de Meishu-Sama.
>
> Verificação item a item (07/10/2026, `PERIODICOS_MEISHU_SAMA_FINAL.csv`):
> dos **1.187 textos de autoria de Meishu-Sama** publicados nos quatro periódicos
> (Eiko, Hikari, Kyusei, Tijotengoku), **415 estão ausentes do acervo** do app
> (**694.625 caracteres JP**). Inclui séries inteiras: **寸鉄/寸鉄活人** (134),
> **質問応答** (38) e **巻頭言** (27).
>
> Os números de §1 (65 arquivos de periódico, 0 série inteira faltando) seguem
> corretos; o que cai é a **conclusão** de que "não há lacuna". Ver
> `reports/periodicos_trabalho/README_PERIODICOS_MEISHU_SAMA.md`.


## Resumo executivo

O cruzamento real entre o corpus do Goshinsho, a pasta de periódicos em trabalho e a referência do Zenshū não aponta lacuna de séries periódicas completas.

O resultado verificado foi:

- Periódicos reais em trabalho: 65 arquivos
- Periódicos reais ausentes do app: 0
- Mioshie-shū / 御教え集: presente no acervo do app
- Trecho canônico específico ausente do app: 1 ocorrência confirmada

A lacuna relevante não é “um periódico inteiro faltou”, e sim um trecho específico do conteúdo publicado por Meishu-Sama, presente na referência do Zenshū e não promovido ao corpus do app.

## 1. Verificação dos periódicos reais

A pasta de trabalho dos periódicos reais foi comparada com o corpus atual do app.

Resultado verificado:

- `REAL_PERIODICAL_FILES = 65`
- `REAL_PERIODICAL_MISSING = 0`

O que apareceu antes como diferença não era lacuna documental, mas variação de nome e normalização entre arquivos equivalentes.

Exemplo de equivalência de nome/arquivo:

- [reports/periodicos_trabalho/jp](../reports/periodicos_trabalho/jp)
- [textos_japones](../textos_japones)

A comparação mostrou que o conjunto de publicações periódicas reais está representado no app; o problema não era ausência de série.

## 2. Verificação do Mioshie-shū / 御教え集

A série Mioshie-shū também foi incluída no cruzamento e está presente no corpus do app.

Exemplos confirmados no app:

- [textos_japones/19510920-御教え集1号.txt](../textos_japones/19510920-御教え集1号.txt)
- [textos_japones/19511025-御教え集2号.txt](../textos_japones/19511025-御教え集2号.txt)
- [textos_japones/19511125-御教え集3号.txt](../textos_japones/19511125-御教え集3号.txt)

Conclusão: a série não é um vazio de corpus; ela está na base do acervo.

## 3. Lacuna real: conteúdo específico ausente

O caso verificável e inequívoco que apareceu na referência do Zenshū foi a pergunta sobre “ミカエルの吾”.

Fonte documental:

- [referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS/kowa_full.txt](../referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS/kowa_full.txt)

Trecho exato:

> 【質問者】『地上天国』第二九号御讚歌中の「ミカエルの吾」を御教示くださいませ。
>
> 【明主様】ミカエルの意味は、言霊学上からいうと、身を変える、すなわち応身ということであって、つまり、私の働きであるからである。

A verificação direta foi feita em três grupos:

- app: sem ocorrências de `ミカエル`, `mikaeru`, `miguel`
- pasta de periódicos em trabalho: sem ocorrências
- referência Zenshū: ocorrência confirmada em [referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS/kowa_full.txt](../referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS/kowa_full.txt)

Os agregados centrais do app também não possuem a expressão:

- [textos_japones/Eiko.txt](../textos_japones/Eiko.txt)
- [textos_japones/Hikari.txt](../textos_japones/Hikari.txt)
- [textos_japones/Tijotengoku.txt](../textos_japones/Tijotengoku.txt)
- [textos_japones/Kyusei.txt](../textos_japones/Kyusei.txt)
- [textos_japones/Jornais.txt](../textos_japones/Jornais.txt)

## 4. Conclusão final (CORRIGIDA em 07/10/2026)

> A conclusão original abaixo ("não há lacuna") **está superada** — ver o aviso
> no topo. O correto é: **não falta periódico como série, mas faltam 415
> artigos de Meishu-Sama** (694.625 chars JP).

O acervo do app não está faltando periódicos completos, nem a série Mioshie-shū como conjunto. A ausência real é de conteúdo específico, do tipo:

- pergunta/trecho publicado por Meishu-Sama em um periódico ou coleção
- preservado na referência do Zenshū
- não promovido ao corpus atual do app

O caso de “ミカエルの吾” é o exemplo confirmado e demonstrável.

Em termos práticos, a falha de resposta não está em “o periódico não entrou”; está em “uma passagen específica do material de referência não foi promovida para o corpus canônico do app”.
