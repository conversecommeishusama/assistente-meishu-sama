# Reestruturação do estudo — 20 e 21 de outubro de 2026

O estudo é **um volume único, organizado por tema**, e a ordem dos capítulos
segue a **importância do conteúdo**.

## Arquivos finais

| Formato | Arquivo |
|---|---|
| PDF para impressão | `DOSSIE_DIFUSAO_20261020.pdf` — 87 páginas, fontes embutidas |
| Word | `DOSSIE_DIFUSAO_20261020.docx` |
| Fonte única | `DOSSIE_DIFUSAO_20261020.md` — 4.666 linhas, 31 capítulos |

## Como regerar

```
.venv/bin/python scripts/montar_volume_unico.py
.venv/bin/python scripts/gerar_pdf_dossie_difusao.py \
    DOSSIE_DIFUSAO_20261020 "A difusão na época de Meishu-Sama"
DOCX_CABECALHO="A difusão na época de Meishu-Sama" \
.venv/bin/python scripts/gerar_docx_dossie_difusao.py DOSSIE_DIFUSAO_20261020
```

Os capítulos novos estão em `docs/volume_novo/`; a montagem lê esses arquivos e
os capítulos aproveitados das partes antigas, aplica a limpeza, renumera,
remapeia as remissões e grava o volume. Nada é editado à mão no arquivo final.

---

## A ordem de leitura

Os capítulos 1 e 2 são abertura: o período, as fontes e a cronologia. Do 3 em
diante, a sequência segue os sete blocos de importância.

| Bloco | Capítulos |
|---|---|
| **A Imagem, o culto e as oferendas** | 3. Os objetos de culto · 4. As imagens da Luz Divina · 5. A ordem do culto · 6. Os tipos de culto · 7. As oferendas do culto · 8. As oferendas diante do objeto de culto · 9. O sufrágio dos antepassados |
| **O trabalho de difusão** | 10. A difusão pós-guerra · 11. A formação de novos membros: o Kyoshu · 12. A salvação e o Ohikari · 13. O Johrei |
| **A formação do elemento humano** | 14. Os ministros até 1951 · 15. Os ministros de 1951 a 1955 · 16. As atribuições e o cotidiano dos dirigentes · 17. As atividades em torno de Meishu-Sama |
| **As unidades** | 18. Como se abria uma unidade · 19. As unidades até 1951 · 20. As unidades de 1951 a 1955 · 21. O que é cada unidade |
| **As ofertas e as dedicações** | 22. As ofertas e as dedicações |
| **A estrutura administrativa** | 23. A governança e a estrutura funcional · 24. Como a Sede acompanhava as igrejas · 25. A perseguição de 1950 e a reforma de 1951 |
| **A Agricultura Natural** | 26. A Agricultura Natural |
| **Temas conexos** | 27. Nutrição · 28. Os Paraísos Terrestres e a mineração · 29. Síntese · 30. Títulos citados · 31. Glossário |

---

## O valor do Ohikari — o que a documentação mostra

A hipótese de trabalho era: depois da guerra o Ohikari deixou de ser cobrado, e
passou-se a cobrar o Kyoshu; haveria uma passagem em que Meishu-Sama diz que não
se pode cobrar pelo que é de Deus. A pesquisa confirmou **a substância** e
corrigiu **um ponto**.

**O que se cobrava era o curso, com rubricas declaradas.** Em 1949, ao responder
a uma acusação de rádio, a instituição detalha a taxa de 1.300 ienes: honorário
do instrutor, taxa de admissão, quota de membro mantenedor, distintivo, livros,
despesas de deslocamento e hospedagem. **O Ohikari não é item da lista.** Ele era
conferido ao fim do curso — é por isso que os relatos dizem "por mil ienes de
oferta se recebe o Ohikari": o valor é do curso.

**A fala sobre não cobrar o que é de Deus existe, e é esta.** Em 『御光話録』15号,
de 20 de dezembro de 1949: 「以前、ただで治療しろって言う人がいましたが、
**勿論、観音様は御礼なんかいらないが、取り次ぎする人は家に住んでいるんだし、
まさかカスミを食って生きるわけには行かない**ですからね」 — *"antes havia quem
dissesse que se devia tratar de graça; naturalmente, **Kannon não precisa de
oferta alguma**, mas quem intercede mora numa casa e não vai viver comendo
névoa"*. A oferta é de quem transmite, não da divindade.

O princípio tem formulação anterior, de 1943, em 「神と悪魔」: "se der dinheiro,
curo a doença" é **condição de troca**, **transação entre Deus e o homem**,
**venda da graça** — e é por isso que o deus verdadeiro salva "por amor sem eu",
independentemente de recompensa.

**O que não se pode fazer com o objeto.** Cobrar acima do valor fixo é furto
(aviso de 1953). E o inverso também é falta: uma senhora devolveu dois ou três
ienes que recebera a mais, porque o papel sagrado era de um iene — e Meishu-Sama
qualifica o gesto como «insultar gravemente a Deus». Tratar a coisa como compra e
venda, nos dois sentidos, é o erro.

**A correção.** Não é exato dizer que o Ohikari passou a ser gratuito: ele manteve
**valor de referência fixo**, e em 1953 Meishu-Sama ainda fala desse valor
(「御守はじめその他の私のかいたものの値は一定している」). O que mudou não foi a
gratuidade do objeto, e sim **a natureza da cobrança**: do preço da peça para a
taxa do curso, e do pagamento à divindade para o sustento do intermediário. O
valor numérico de 1953 continua não documentado — o aviso fixa o princípio, não a
quantia.

O tratamento completo está no capítulo 12.3, com quadro-resumo das quatro
evidências.

---

## Outras mudanças

**Hierarquias separadas por período.** Capítulos 19 e 20 tratam as unidades de
1948 e de 1951; 14 e 15, os ministros de cada período. O capítulo 21 define cada
unidade, com quadro comparativo entre igreja e associação, e a distinção entre
Centro de Johrei, Centro de Ensino e filial.

**Tipos de culto.** O capítulo 6 distingue as quatro espécies e explica a
diferença entre Culto Mensal (ciclo comum, acompanha a vida da casa) e Culto
Regular (o culto próprio de cada igreja).

**Agricultura Natural num só contexto.** O capítulo 26 reúne a doutrina de 1950,
a horta caseira entre os membros, a produção de proteína animal orgânica e o
insumo biológico vendido ao produtor convencional como condicionador de solo.

**Água, sal e arroz.** O capítulo 8 apresenta a instrução de 23 de abril de 1949
como resposta direta: são a oferenda xintoísta (御神饌), são comida de
deus-dragão, e ao Kōmyō Nyorai oferta-se comida humana.

**Sem rastro de versões e sem trilha do acervo.** Nenhuma comparação com edições
anteriores; as citações indicam apenas veículo, número e data.

**Correções pontuais.** "Três anos" → "três meses"; Seijōdai → **Seiseidai**;
Anshoku → **Ajiki Haruhiko**; "caráter" → "caractere"; as três caligrafias do
Ohikari → **Hikari, Kōmyō e Dai-Kōmyō**; "sítios cênicos" → "paragens de grande
beleza"; 日光 identificada como **Nikkō, "luz do sol"**.

---

## O que ainda não foi feito

**Revisão de língua, capítulo a capítulo.** A montagem garante ordem, numeração,
remissões e ausência do rastro de versões, mas não reescreve o estilo dos trechos
herdados. Uma leitura corrida ainda encontrará frases de transição que pressupõem
a divisão antiga, e sobreposições entre capítulos vizinhos — 16 e 17, e 5 e 6.

**Japonês em prosa — resolvido.** `scripts/glossas_volume.py` reúne cerca de 270
termos e a função `glosar()`, em `montar_volume_unico.py`, insere a tradução
entre parênteses na primeira ocorrência de cada capítulo. A mesma glosa vale para
as células de tabela e para os títulos de artigo nas linhas de referência, uma
única vez no volume: 404 glosas.
Nenhuma citação longa em 「」 ou 『』 ficou sem tradução ao lado. A glosa não
entra dentro de citação, de tradução em itálico, de tabela, de organograma, de
título nem de parêntese já existente; títulos de artigo recebem a glosa uma única
vez no volume inteiro.

**Verificação.** O volume tem 4.631 linhas, 31 capítulos, 87 páginas e 9 imagens,
em PDF e em DOCX. `verificar.py` deixa de se aplicar ao volume, porque as citações
não indicam caminho. `verif_cit.py` continua aplicável e foi rodado sobre a Parte
III após a reescrita: 52 citações confirmadas, nenhuma não localizada; 54
caminhos, nenhum ausente.
