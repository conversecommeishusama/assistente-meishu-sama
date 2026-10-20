# Reestruturação do estudo — 20 de outubro de 2026

O estudo passou a ser **um volume único, organizado por tema**. As três partes
de trabalho que o compunham (Parte I, Parte II, Parte III) foram dissolvidas e
os seus capítulos redistribuídos pela ordem temática, com numeração nova e
contínua.

**Arquivos finais**

| Formato | Arquivo |
|---|---|
| PDF para impressão | `DOSSIE_DIFUSAO_20261020.pdf` — 84 páginas, fontes embutidas |
| Word | `DOSSIE_DIFUSAO_20261020.docx` |
| Fonte única | `DOSSIE_DIFUSAO_20261020.md` — 4.616 linhas, 31 capítulos |

**Como regerar**

```
.venv/bin/python scripts/montar_volume_unico.py
.venv/bin/python scripts/gerar_pdf_dossie_difusao.py \
    DOSSIE_DIFUSAO_20261020 "A difusão na época de Meishu-Sama"
DOCX_CABECALHO="A difusão na época de Meishu-Sama" \
.venv/bin/python scripts/gerar_docx_dossie_difusao.py DOSSIE_DIFUSAO_20261020
```

Os capítulos novos estão em `docs/volume_novo/`; a montagem lê esses arquivos e
os capítulos aproveitados das partes antigas, aplica a limpeza, renumera e
grava o volume. Nada é editado à mão no arquivo final.

---

## O que mudou

**Hierarquias separadas por período.** As unidades e os ministros deixaram de ser
tratados num capítulo só. Agora há `6.` unidades até 1951 (grade decimal),
`7.` unidades de 1951 a 1955 (grade territorial), `8.` o que é cada unidade,
`9.` ministros até 1951, `10.` ministros de 1951 a 1955. O capítulo 8 responde
às perguntas que ficavam implícitas — o que é uma associação, se ela tem a mesma
hierarquia de uma igreja, e a diferença entre Centro de Johrei, Centro de Ensino
e filial —, com um quadro comparativo e uma tabela de conjunto de todas as
unidades.

**Culto mensal e culto regular.** Capítulo 17 distingue as quatro espécies de
culto e explica a diferença: o mensal pertence ao ciclo comum a todas as
unidades e acompanha a vida da casa; o regular é o culto **daquela igreja**.

**Agricultura Natural num só contexto.** Capítulo 22 reúne a doutrina de 1950 e
a configuração atual — a horta caseira entre os membros, a produção de proteína
animal orgânica, e o insumo biológico vendido ao produtor convencional como
condicionador de solo. A separação entre os três planos é o que evita confundir
a promessa dos anos 1950 com a prática de hoje.

**Oferendas diante do objeto de culto.** Capítulo 28 apresenta a instrução de 23
de abril de 1949 como o que ela é: uma resposta direta, que reconhece a prática
xintoísta (sal, água, arroz lavado como 御神饌), dá-lhe um destinatário — o
deus-dragão — e substitui a forma pela comida humana.

**Fim do rastro das versões.** Nenhuma passagem compara o texto com edições
anteriores; não há menção a "primeira versão", a revisões datadas, nem a notas de
trabalho. O leitor recebe apenas o texto final.

**Fim da trilha do acervo.** As citações passaram a indicar somente veículo,
número e data. Não se nomeia a coleção nem se indica de onde vieram os
documentos: são escritos, palavras registradas e documentos oficiais da época,
públicos e conservados por diversas instituições messiânicas.

**Capítulos suprimidos.** As antigas listas de lacunas e a nota sobre o acervo
saíram do volume; o que nelas era essencial foi incorporado ao texto dos
capítulos correspondentes. O volume termina com a síntese, a lista de títulos
citados e o glossário.

**Correções pontuais.** "Três anos depois" passou a "três meses depois" (outubro
de 1934 a janeiro de 1935); o nome do local em Atami passou de *Seijōdai* a
**Seiseidai**; o ministro assistente da ministra Higuchi passou a **Ajiki
Haruhiko**; "caráter" passou a "caractere"; as três caligrafias do Ohikari
passaram a **Hikari, Kōmyō e Dai-Kōmyō**; "sítios cênicos" passou a "paragens de
grande beleza"; a caligrafia 日光 ficou identificada como **Nikkō, "luz do sol"**.

**Valor do Ohikari.** O capítulo 19 não usa mais o preço de 1935 para explicar o
período estudado. Os valores documentados são de 1949 (mil ienes pelo curso com
o Ohikari; a cifra de dois mil ienes vem de fonte adversária) e, para 1953, o
aviso oficial fixa o **princípio** — o valor é fixo e cobrar acima dele é furto —
sem declarar a quantia. O valor de 1953, portanto, não está documentado, e o
texto diz isso.

---

## Estrutura do volume

1. O período e as fontes
2. A cronologia da institucionalização (1934–1955)
3. A difusão pós-guerra: método, instrumentos e escala
4. A formação de novos membros: o Kyoshu
5. Como se abria uma unidade
6. As unidades até 1951: a grade decimal
7. As unidades de 1951 a 1955: a grade territorial
8. O que é cada unidade
9. Os ministros até 1951
10. Os ministros de 1951 a 1955
11. As atribuições e o cotidiano dos dirigentes
12. Os objetos de culto
13. A governança e a estrutura funcional
14. Como a Sede acompanhava as igrejas
15. As imagens da Luz Divina e o critério de proporção
16. A ordem do culto
17. Os tipos de culto
18. As oferendas
19. A salvação e o Ohikari
20. O sufrágio dos antepassados
21. O ofertório: ofertas, quotas e taxas
22. A Agricultura Natural
23. O Johrei: prática, compreensão e desvios
24. Nutrição
25. As atividades em torno de Meishu-Sama
26. Os Paraísos Terrestres e a mineração
27. A perseguição de 1950 e a reforma de 1951
28. As oferendas diante do objeto de culto
29. Síntese em treze assertivas
30. Títulos citados
31. Glossário

---

## O que ainda não foi feito

**Revisão de língua, capítulo a capítulo.** A montagem garante a ordem, a
numeração, as remissões e a ausência do rastro de versões, mas não reescreve o
estilo de cada trecho herdado. Uma leitura corrida ainda encontrará frases de
transição que pressupõem a divisão antiga, e repetições entre capítulos que hoje
tratam do mesmo assunto por ângulos próximos — os capítulos 11 e 12, e os
capítulos 16 e 17.

**Japonês em prosa.** Os títulos dos ensinamentos e dos periódicos estão
traduzidos na lista de Títulos citados, e os termos de organização e de culto,
no Glossário. Restam, no corpo do texto, nomes próprios e designações
institucionais em caracteres que não receberam tradução junto ao primeiro uso.
Uma varredura manual desses casos é o trabalho seguinte.

**Verificação automática.** O verificador de caminhos não se aplica ao volume,
porque as citações deixaram de indicar caminho. O verificador de citações
(`verif_cit.py`) continua aplicável e deve ser rodado sobre os arquivos de
origem em `docs/volume_novo/` e sobre as partes antigas, que seguem sendo a
matéria-prima.
