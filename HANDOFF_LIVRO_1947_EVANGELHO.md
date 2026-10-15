# Handoff — Livro 『天国の福音』 (O Evangelho do Paraíso, 1947)

> **Data:** 15/10/2026
> **Pedido original:** *"…na hora de promover, promova junto o livro Evangelho do
> Paraíso (tengoku no fukuin) que não foi colocado na leitura colaborativa, só foi
> colocado o de 1954. Coloque também o livro Kyoshu Yoko que foi traduzido."*
> e *"faça as ondas de revisão para evitar qualquer erro tradutório, de glossário
> e todos os outros que estamos trabalhando e corrigindo."*
> **Autorização expressa:** usar o original japonês eliminando os rastros de fonte
> (*"não tenho certeza"* quanto à data → confirmada **5/2/1947**, era Showa 22).

**Estado: CONCLUÍDO E PROMOVIDO.** Este documento existe para a sessão nova saber
o que foi feito e não repetir as correcções.

---

## 1. Obras promovidas para a leitura colaborativa

| Obra | Ficheiro | Estado |
|---|---|---|
| **天国の福音 1947** | `19470205 - O Evangelho do Paraíso.txt` (544 kB) | ✅ novo |
| 天国の福音書 1954 | `19540825 - Evangelho do Reino dos Céus.txt` | já existia |
| **教修要綱** (Kyōshu Yōkō) | `19541010 - Kyōshu Yōkō (Esboço do Curso de Preparação).txt` (203 kB) | ✅ novo |
| Periódicos | `Tijotengoku.txt` · `Eiko.txt` · `Kyusei.txt` · `Hikari.txt` | ✅ |

Presentes nos três directórios: `textos_leitura_colaborativa/` (o que o app lê),
`textos_portugues/` (produção) e `textos_japones/` (`19470205-天国の福音.txt`,
`19541010-教修要綱.txt`). Confirmado pelo próprio serviço do app:
`leitura_service.listar_obras()` → 137 obras, tipo «livro», Palavra Escrita.
⚠️ Os três directórios são **gitignored**.

## 2. Extração — `scripts/extrair_tengoku_no_fukuin_jp.py`

O extractor foi **reescrito**: a primeira versão produzia 103 secções com o corpo
colado num único parágrafo.

| Defeito | Correção |
|---|---|
| a secção final 総結論 ficava de fora (o intervalo terminava na última marca de metadados) | 103 → **104 secções** |
| corpo colado num parágrafo, com `\n` no meio das palavras (**49 achados `extracao`**) | **889 parágrafos** pela indentação do original |
| anotações `<…>` truncadas entre linhas (10 casos) | resolvidas **depois** de juntar as linhas |

O ficheiro de referência é uma transcrição em que **cada linha é uma linha da
composição** (~34 caracteres), não um parágrafo: linha **com** indentação abre
parágrafo, linha **sem** indentação continua a palavra. Anotações `<…>`: só
hiragana = furigana (remover); com kanji/katakana = **correcção da edição**
(substitui o último bloco de kanji antes dela — nunca consome kana nem pontuação,
senão perde o `、` de `…を主とし、淋巴腺<リンパ腺>部…`).

**Integridade medida contra o original: 146.506 caracteres CJK extraídos de
146.504 (+2, só o efeito das correcções da edição), 104 marcas de secção, 0
resíduos de metadados/separadores/páginas.**

## 3. Tradução — `scripts/traduzir_tengoku1947.py`

104/104 secções, **0 erros**, 527.003 caracteres. Duas mudanças que resolveram a
maioria dos achados de glossário:

- **memória de continuidade entre blocos**: cada bloco recebe o fim do bloco
  anterior (JP + PT) e a ordem de manter os termos. Sem isto, o mesmo termo
  japonês recebia traduções diferentes em blocos diferentes — **era a causa
  dominante dos 75 achados `glossario` da R1**;
- **título traduzido depois do corpo**, para o corpo governar a terminologia
  (o caso 精神作用 = «efeito psíquico» no título vs «ação mental» no corpo).

Regras acrescentadas ao prompt: coerência terminológica dentro da secção, siglas
do autor (`以下略して…`) e três falsos cognatos médicos — 化膿 = **purulento**
(não «caseoso»), ラッセル = **estertores** (não «corpúsculos»), 精神作用 = **ação
mental**.

## 4. As 5 ondas de revisão (convergiu)

| ronda | o que | achados | correcções |
|---|---|---|---|
| R1 | auditoria na extração defeituosa | 178 (11 de gravidade alta) | — |
| **M1** | unidades métricas + aspa da secção 101 | — | 10 |
| R2 | após extração corrigida + re-tradução | 29 | — |
| **M2** | | — | 30 |
| **M3** | 43 títulos → Title Case do acervo | — | 43 |
| R3 | 104 artigos | 31 | — |
| **M4** | | — | 27 |
| R4 | 104 artigos | 21 | — |
| **M5** | | — | 19 |
| R5 | 104 artigos | **13, todos baixa/leve** | — |
| **M6** | | — | 8 |

Scripts: `corrigir_tengoku1947_m1..m6.py`,
`normalizar_titulos_tengoku1947.py`.

**A partir da R3, a maioria dos achados são FALSOS POSITIVOS** — o auditor não
conhece o `glossario_traducao.json` e denuncia como invenção o que é entrada
oficial: `然毒`=«toxina hereditária», `運命`=«destino mutável», `逆理`=«Princípio
Inverso», `理屈`=«Lógica», `大光明世界`=«Mundo da Grandiosa Luz», `御利益`=«benefício
material», `正守護神`=«espírito protetor guardião», `下熱`, `叡智`, `経綸`,
`同化霊`. **Consultar `glossario_traducao.json` e os docstrings dos scripts M
antes de «corrigir».** Ver também `/memories/repo/glossario-falsos-positivos.md`.

## 5. A única ambiguidade que gerou correcções repetidas: 道理

O glossário fixa `道理 -> Caminho Perfeito`, mas em 007, 016, 021 e 078 o sentido
é o **comum** («razão/conclusão lógica») e a substituição literal produzia frases
sem sentido («chegar-se-ia ao seguinte Caminho Perfeito»). Corrigido nos quatro.
**Pendente:** anotar no glossário que a entrada é sensível ao contexto.

## 6. Verificação e montagem

- `scripts/verificar_tengoku1947_mecanico.py` → **0 achados**. As exigências de
  forma literal do glossário passaram a **lista de apoio** (258 entradas, não
  contam como defeito): termos genéricos com alternativas livres davam centenas
  de falsos positivos.
- O teste de unidades japonesas só acusa se houver **numeral antes** (senão «quem
  fica alegre, ri ou sente sono», «o go e o shogi», «ba-bi-bu-be-bo» dão 20+
  falsos) e aceita equivalência métrica antes **ou** depois do termo.
- O artefacto confere com as convenções medidas no acervo publicado: kanji 3,6 vs
  4,9 por 100k caracteres; colchetes 13,5 vs 15,4; aspas retas 97 vs 169.
- `scripts/montar_tengoku1947.py [--aplicar]` monta com cabeçalho no formato dos
  livros publicados e índice das 104 secções.

## 7. Commits

`469e2f3d` (extração/tradução/M1/M2) → `d6048cbd` (M3/M4) → `c6f5613b` (M5) →
`bf70ca01` (M6 + promoção).

## 8. O que fica pendente neste livro

1. Anotar no glossário que `道理` é sensível ao contexto (§5).
2. `reports/` e `reports/auditoria_tengoku1947/` estão gitignored — se o
   histórico das ondas importar, preservar à parte.
3. O livro de 1947 **não** entrou no índice do projecto `/var/www/rattail`
   (é outro projecto, com o seu próprio índice).
