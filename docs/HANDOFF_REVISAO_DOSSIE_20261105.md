# Handoff — revisão linha a linha do Dossiê da Difusão

**Data:** 05/11/2026
**Sessão anterior:** `dc5dceec-c4a2-4bb0-9f80-33937fda6fee` (1.874 linhas de transcrição, 1,4 MB)
**Motivo do handoff:** janela de contexto gasta a ~metade da tarefa; fronteira limpa entre
capítulos revistos e por rever.

---

## 1. Estado em uma frase

Os **capítulos 1 a 17** foram revistos linha a linha; **187 alterações** estão registadas,
o volume foi remontado e o PDF/DOCX regenerados. Faltam os **capítulos 18 a 40**.

| Artefacto | Caminho | Estado |
|---|---|---|
| Volume montado | `docs/DOSSIE_DIFUSAO_20261020.md` | 40 capítulos, 8.616 linhas, 18 imagens |
| PDF | `docs/DOSSIE_DIFUSAO_20261020.pdf` | 10,9 MB, gerado |
| DOCX | `docs/DOSSIE_DIFUSAO_20261020.docx` | 8,0 MB, gerado |
| Registo de alterações | `docs/revisao_20261104_log.json` | 187 registos `{capitulo, arquivo, antes, depois}` |
| Comparativo antes/depois | `docs/COMPARATIVO_REVISAO_DOSSIE_20261104.md` | 26 grupos, verbatim |
| Relatório do bloco 14-17 | `docs/RELATORIO_REVISAO_DOSSIE_20261105.md` | achados de atribuição |

---

## 2. Mapa capítulo → fonte (indispensável para retomar)

O volume **não** é cópia das partes: ele é montado por `scripts/montar_volume_unico.py`,
que extrai secções, funde capítulos e renumera. **Nunca editar o volume** — editar a fonte
e remontar.

| Cap. | Título no volume | Fonte |
|---:|---|---|
| 1 | O período e as fontes | `volume_novo/01_fontes.md` ✅ |
| 2 | A cronologia da institucionalização | Parte I §1 ✅ |
| 3 | As Imagens da Luz Divina e os Ohikari | I §5[1,2] + III §27[2] ✅ |
| 4 | As imagens da Luz Divina e o critério de proporção | Parte II §13 ✅ |
| 5 | A ordem do culto | II §14[1,3,4] ✅ |
| 6 | Os tipos de culto | `volume_novo/16b_cultos.md` ✅ |
| 7 | As oferendas do culto | II §15 ✅ |
| 8 | As oferendas diante da Imagem | III §31 ✅ |
| 9 | O sufrágio dos antepassados | II §16 ✅ |
| 10 | A difusão pós-guerra | Parte I §2 ✅ |
| 11 | A formação de novos membros: o Kyoshu | I §7 ✅ |
| 12 | A salvação e o Ohikari | III §27 ✅ |
| 13 | As ofertas de gratidão e o critério da retribuição | `volume_novo/12b_ofertas_gratidao.md` ⚠️ lido, **sem edições** |
| 14 | O Johrei: prática, compreensão e desvios | II §19 ✅ |
| 15 | Os ministros de 1948 a 1951 | `volume_novo/09_ministros_1948_1951.md` ✅ |
| 16 | Os ministros de 1951 a 1955 | `volume_novo/10_ministros_1952_1955.md` + I §5[7] ✅ |
| 17 | As atribuições e o cotidiano dos dirigentes | III §25[1,2] ✅ |
| **18** | As atividades em torno de Meishu-Sama | Parte I §8 |
| **19** | Como se abria uma unidade | I §4 |
| **20** | A grade de 1948 | `volume_novo/06_grade1948.md` |
| **21** | As unidades de 1951 a 1955 | `volume_novo/07_grade1951.md` 🔸 2 |
| **22** | O que é cada unidade | `volume_novo/08_quadro_unidades.md` 🔸 1 |
| **23** | As ofertas e as dedicações | II §21 🔸 1 |
| **24** | A governança e a estrutura funcional | Parte I §6 🔸 1 |
| **25** | Como a Sede acompanhava as igrejas | III §25[3] |
| **26** | A perseguição de 1950 e a reforma de 1951 | III §30 |
| **27** | A Agricultura Natural | `volume_novo/22_agricultura.md` |
| **28** | Nutrição | II §20 |
| **29** | Os Paraísos Terrestres e a mineração | I §9[1,2,3,5,6,7] + III §29 |
| **30** | Síntese | Parte I §12 |
| **31** | Títulos dos artigos | `volume_novo/29b_titulos.md` |
| **32** | Glossário | `volume_novo/30_glossario.md` |
| **33** | Anexo A — Estatuto de 1946 | `volume_novo/41_anexo_estatuto_1946.md` |
| **34** | Anexo B — Programa de 1947 | `volume_novo/40_anexo_programa_1947.md` |
| **35** | Anexo C — Grade de 1948 | `volume_novo/44_anexo_grade_1948.md` |
| **36** | Anexo D — Censo de 1950 | `volume_novo/45_anexo_censo_1950.md` |
| **37** | Anexo E — Regulamento de 1951 | `volume_novo/42_anexo_regulamento_1951.md` |
| **38** | Anexo F — Reforma de 1951 | `volume_novo/46_anexo_reforma_1951.md` |
| **39** | Anexo G — Aviso de 1953 | `volume_novo/43_anexo_aviso_1953.md` 🔸 2 |
| **40** | Anexo H — Manual do Curso | `volume_novo/47_anexo_kyoshu_yoko.md` 🔸 4 |

🔸 = já tem correções pontuais registadas, mas **não** passou por leitura integral.
Fontes das partes: `docs/LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md`,
`docs/DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md`,
`docs/DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md`.

---

## 3. Regras em vigor (não negociáveis)

1. **`glossario_traducao.json` é autoritativo.** Precede qualquer preferência de estilo:

   | JP | PT |
   |---|---|
   | 明主様 | Meishu-Sama |
   | 大先生 | Grão-Mestre |
   | 浄霊 | Johrei |
   | 御神体 | Imagem da Luz Divina |
   | 御守 | Ohikari |
   | 大教会 / 中教会 / 分教会 | Igreja Grande / Média / Filial |
   | 管長 | presidente |
   | 会長 | presidente de igreja |
   | 大教師 / 中教師 | Ministro Titular / Adjunto |
   | 教導師 / 教導師補 | Ministro Responsável / Assistente |
   | 御教修 | Kyoshu (**sem** macron) |
   | 地上天国 | **Tijotengoku** (título do periódico) · **Paraíso Terrestre** (conceito) |
   | 光明如来 | **Komyo-Nyorai** (sem macron) |
   | 位牌 | tabuleta (ihai) |
   | 御屏風観音 | Byōbu Kannon |
   | 大祭 / 例祭 / 月並祭 | Grande Culto / Culto Regular / Culto Mensal |
   | 型 / 浄化 | modelo / purificação |

2. **Nenhum ideograma em prosa portuguesa.** Só dentro de `「」`/`『』` (citação ou
   título) e nas tabelas de termos.
3. **Política de citação:** nada de `search2/kihara/bunsyo/` (`kami09`, `kami14`,
   `kami22`, `omichi*`, `kaiho*`, `ken16`, `kikouwa/`). Ver §5.
4. **Lacuna documental não se preenche por analogia.** Quando a documentação cala, o
   texto diz que cala.
5. **Medidas japonesas convertidas** (shaku, ri, ken, tsubo …).

---

## 4. Correções de pipeline já feitas — **não reverter**

`scripts/montar_volume_unico.py` foi alterado. Estas quatro correções resolvem defeitos
que afetavam o volume inteiro:

1. **`limpar()` apagava referências.** O regex removia o *span* inteiro em crases quando
   continha `search\d|pdf_rattail`. Dez traduções ficaram com um travessão solto (`— `)
   no lugar da fonte. Agora `_podar_caminho()` remove só o caminho e `_limpar_span()`
   preserva a referência; linha que fica só com `— ` é eliminada.
2. **`glosar_titulo()` desligada.** Glosava títulos em `『』`/`「」` nas linhas de
   referência: «『地上天国』 (Paraíso Terrestre)nº 28». Contradiz a regra 1 (Tijotengoku).
3. **Remissão de subsecção:** `capítulo N.M` → `§N.M`, aplicado **depois** do
   remapeamento.
4. **`CAP_MAP` / `REF_EXCECOES`:** entradas `14.3→5.2`, `14.4→5.3`, `14.5→5.2`.
5. **`guardar_tit()` glosava duas vezes.** Em célula de tabela com o termo entre 「」 e a
   tradução logo ao lado — «**「光明」 (Kōmyō)**» —, a glosa automática entrava à mesma e
   produzia «(Luz) (Kōmyō)». Agora, se vem parêntese depois do fecho, não se glosa
   (§3.2 do capítulo 3 era o caso visível).

Consequência prática: **na fonte, remeter com «capítulo N.M»**, nunca com `§N.M` — o
`remapear_refs` reescreve todo `§N` para a numeração do volume.

---

## 5. A descoberta mais importante da sessão

Duas citações de **fonte vedada** escaparam à auditoria de 13/10/2026 porque estavam
**sem linha de atribuição** — e a auditoria procurava o caminho `kihara/`:

| Onde | O que afirmava | Realidade | Correção aplicada |
|---|---|---|---|
| II §15.1 → cap. 7 | «no culto de 1954 a igreja abandonou a oferenda crua», em 1.ª pessoa, atribuído a Meishu-Sama | Ensaio 「秋季大祭お導き」 (`kami09.html`), **autoria do Rev. Kihara**: era decisão dele | Substituído pela palestra de **07/12/1953** (`search1/kouwa/s281207.html`) + relato de 『栄光』277 (`kikou2/shikiten01.html`) |
| II §16.4 e §16.6 → cap. 9 | doutrina do «espelho» (estado dos ancestrais determina o dos vivos) e a «festa de 15 de agosto» | `kami22.html` (「平和記念祭御導き」), mesmo autor | Removidas; §16.6 declara a exclusão e o que falta reancorar |

**Regra que daí resulta:** citação sem linha `— fonte` é o único modo de um texto vedado
passar. Ao retomar a leitura dos capítulos 18-40, **verificar a atribuição de cada
citação**, e não apenas a sua existência.

### 5.1 O segundo modo de errar — confirmado no capítulo 14

Na sessão de 05/11 apareceu uma variante que não é «fonte vedada», mas dá o mesmo
resultado: uma frase **verdadeira** do acervo, citada como palavra de Meishu-Sama quando
é palavra de outra pessoa. O §14.4 apresentava 「医者は病気を固めます…御浄霊をこれから
戴くのでしたら、注射や薬は廃めて下さい」 como doutrina dele. A frase está em
`search2/okage/shi/qsinoip.html` (testemunho de 清水くに, 『地上天国』nº 47, 25/04/1953),
e quem a diz é **o ministro que a atendeu**, o Sr. Uchida, em visita domiciliar.

O teste é o mesmo, e é barato: **toda citação tem de ter autor, veículo e data**. Quando
não tem, procurar a frase no acervo antes de a aceitar como palavra de Meishu-Sama. Em
§14 havia seis citações nessa situação; todas foram localizadas e ancoradas (ver
`RELATORIO_REVISAO_DOSSIE_20261105.md`).

---

## 6. Armadilhas já verificadas

- **cwd do terminal deriva.** Usar sempre caminhos absolutos; `cd` é removido pelo wrapper.
- **`revisar.aplicar` exige literal exato**, incluindo quebras de linha. Antes de editar,
  confirmar com `grep -n -A6` — o texto quebra em colunas estreitas e produz linhas de
  uma só palavra.
- **`glossas_volume.py` sobrepõe-se à fonte.** Correções de terminologia fazem-se lá
  (tem `EXCECOES_GLOSSARIO` com justificação obrigatória por termo).
- **Não usar `git add -A`.** Outras frentes de trabalho partilham `main`; commitar por
  caminho.
- **A tabela de lacunas (II §22) e a nota de método (III §32) NÃO entram no volume.**
  Edições aí são registadas no log como «Fora do volume» e não aparecem no PDF.

---

## 7. Alerta sobre a árvore de trabalho

`git status` mostra **370 ficheiros modificados**. Só ~85 têm diff de conteúdo, e destes
**56 estão fora do âmbito do dossiê** (`docs/09-ROADMAP.md`, `docs/leituras_*`,
`GOSHINSHO.md`, `HISTORICO.md`, etc.). O diff é uniforme: a indentação das linhas de
continuação passou de 2 para 1 espaço — **reformatação alheia**, não desta revisão.

Não reverter nem commitar esses 56. Se for preciso commitar o dossiê, listar os caminhos
um a um.

---

## 8. Comandos para retomar

```bash
# aplicar alterações (padrão de sempre)
python3 - <<'PY'
import sys; sys.path.insert(0, '/var/www/goshinsho/scripts')
from revisar import aplicar
aplicar('Capítulo 14 — O Johrei', [
    ('docs/DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md', 'antes exato', 'depois'),
])
PY

# remontar o volume
python3 /var/www/goshinsho/scripts/montar_volume_unico.py

# verificação mecânica (deve ficar sem saída nos tipos corrigidos)
python3 /var/www/goshinsho/scripts/qa_volume.py
python3 /var/www/goshinsho/scripts/qa2_volume.py

# PDF e DOCX (o python do sistema não tem reportlab)
cd /var/www/goshinsho && /var/www/goshinsho/.venv/bin/python \
  scripts/gerar_pdf_dossie_difusao.py DOSSIE_DIFUSAO_20261020 "A difusão na época de Meishu-Sama"
cd /var/www/goshinsho && DOCX_CABECALHO="A difusão na época de Meishu-Sama" \
  /var/www/goshinsho/.venv/bin/python scripts/gerar_docx_dossie_difusao.py DOSSIE_DIFUSAO_20261020

# comparativo
python3 /var/www/goshinsho/scripts/gerar_comparativo_revisao.py
```

### Estado da verificação mecânica (05/11/2026)

`qa_volume.py` e `qa2_volume.py` estão **limpos** nos defeitos que detetam de forma
fiável: ideogramas colados a texto latino, glosas duplicadas, linhas órfãs, remissões
para `§` inexistente, medidas não convertidas, aspas japonesas desequilibradas.

Falsos positivos conhecidos, **ignorar**: ideogramas dentro de citações e tabelas de
termos (esperado); «palavra repetida» quando é `se se` / `de o` (construção legítima);
«negrito ímpar» em tabelas com `*` literal.

---

## 9. Ordem sugerida para a nova sessão

Ler **3 a 4 capítulos por bloco**, remontar ao fim de cada bloco, e regenerar o
comparativo no fim de cada bloco — assim o trabalho fica sempre num estado publicável.

Bloco 1 (cap. 14-17) **concluído em 05/11**. Retomar no bloco 2:

1. ~~Cap. 14-17 (Johrei, ministros, dirigentes)~~ ✅
2. Cap. 18-22 (atividades, abertura de unidade, grades)
3. Cap. 23–26 (economia, governança, Sede, perseguição)
4. Cap. 27–30 (agricultura, nutrição, Paraísos, síntese)
5. Cap. 31–32 (títulos e glossário — **conferir contra `glossario_traducao.json`**)
6. Cap. 33–40 (anexos)

Ponto de atenção na leitura: os **anexos** (33-40) são traduções integrais de documentos
institucionais — a revisão aí é sobretudo de fidelidade ao original e de concordância, não
de estilo.
