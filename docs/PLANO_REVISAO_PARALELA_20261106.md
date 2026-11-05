# Plano de revisão paralela — capítulos 18 a 40

**Criado em 06/11/2026.** Sete sessões em paralelo, uma por worktree, sobre o estado
commitado em `1df4a1de` («dossiê: revisão dos capítulos 1-17»).

O que está feito: capítulos 1-17, 187 registos. O que falta: **5.195 linhas em 23
capítulos**, mais o capítulo 29, que fica para o fecho.

---

## 1. Por que worktrees, e não sete abas na mesma pasta

Três colisões tornam o trabalho na mesma árvore destrutivo:

| Colisão | Efeito |
|---|---|
| `montar_volume_unico.py` lê **todas** as fontes | um rebuild numa sessão publica as edições a meio das outras |
| `revisao_20261104_log.json` (único) | escritas concorrentes perdem registos — o `revisar.py` relê e reescreve o ficheiro inteiro |
| mesmos ficheiros-fonte | o último a gravar apaga o trabalho do primeiro |

`git worktree` dá a cada sessão um directório e uma branch próprios. O acervo
`/var/www/rattail` é partilhado, e é só de leitura.

Para isso funcionar, `scripts/revisar.py` e `scripts/gerar_comparativo_revisao.py`
deixaram de ter caminhos fixos e passaram a ler `GOSHINSHO_RAIZ` e `REVISAO_LOG`, com os
valores da árvore principal como omissão. Sem variáveis, o comportamento é o de antes.

---

## 2. A divisão é por ficheiro, não por capítulo

Os blocos por assunto partilham ficheiros: os capítulos 18, 19, 23, 24, 25, 26, 28 e 30
saem todos das três partes, e três sessões estariam a editar o mesmo ficheiro. Agrupando
por **posse de ficheiro**, cada sessão fica com um conjunto disjunto:

| Sessão | Branch | Detém | Capítulos | Linhas |
|---|---|---|---|---:|
| P1 | `rev/p1` | `LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA` | 18, 19, 24, 30 | 607 |
| P2 | `rev/p2` | `DOSSIE_PARTE_II_CULTO_E_VIDA` | 23, 28 | 446 |
| P3 | `rev/p3` | `DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA` | 25, 26 | 400 |
| P4 | `rev/p4` | `volume_novo/06`, `07`, `08` | 20, 21, 22 | 429 |
| P5 | `rev/p5` | `volume_novo/22`, `29b`, `30` | 27, 31, 32 | 503 |
| P6 | `rev/p6` | `volume_novo/40`, `41`, `42`, `43`, `44`, `45`, `46` | 33-39 | 914 |
| P7 | `rev/p7` | `volume_novo/47` (Anexo H) | 40 | 1.554 |
| — | fecho | I §9 + III §29 | **29** | 342 |

Soma exacta: **5.195 linhas**. O capítulo 29 não é paralelizável: a fonte vive em
`LEVANTAMENTO_…PARTE_I` (§9) e em `DOSSIE_PARTE_III` (§29), que pertencem a sessões
diferentes. Faz-se no fecho, quando os dois ramos já estão em `main`.

Cada worktree recebeu um `TAREFA.md` na raiz com o seu mapa capítulo → fonte, a lista de
ficheiros que pode editar e as regras. A sessão começa por ler esse ficheiro.

---

## 3. Montagem

```bash
cd /var/www/goshinsho
for b in p1 p2 p3 p4 p5 p6 p7; do
  git worktree add -b rev/$b /var/www/goshinsho-$b main
done
git worktree list
```

Cada sessão corre, no seu terminal:

```bash
export GOSHINSHO_RAIZ=$PWD/
export REVISAO_LOG=$PWD/docs/revisao_log_p1.json     # p2 … p7 conforme a árvore
```

E abre a pasta `/var/www/goshinsho-pN` numa janela do VS Code. O `TAREFA.md` é o prompt de
arranque: basta pedir «lê o `TAREFA.md` e começa».

---

## 4. Fecho

```bash
cd /var/www/goshinsho
bash scripts/fechar_revisao_paralela.sh
```

O script, por esta ordem: junta os sete `revisao_log_pN.json` ao log central, faz merge das
sete branches com `--no-ff`, e — **só no fim** — remonta o volume, regenera o comparativo,
o PDF e o DOCX.

Duas regras que o script não pode violar:

1. **Volume e binários só se geram aqui.** `DOSSIE_DIFUSAO_*.md/.pdf/.docx` e
   `COMPARATIVO_*` não podem ser editados nas worktrees: dois PDFs em conflito é um
   conflito binário que não se resolve.
2. **Nenhuma sessão commita.** O merge é feito a partir dos ficheiros de trabalho.

---

## 5. Defeito herdado, distribuído pelas sessões

Na sessão de 04/11, um *strip* mecânico de ideogramas apagou **156 parênteses** em vez de
os traduzir. Muitos eram redundantes («Igreja Grande (大教会)»); outros eram informação —
nomes próprios, notas estruturais, termos sem tradução ao lado. Dois deixaram frases
quebradas (Parte III, §24 e §24.1), já reparadas em 06/11.

Distribuição por ficheiro:

| Ficheiro | Parênteses apagados | Sessão |
|---|---:|---|
| `DOSSIE_PARTE_III_…` | 47 | P3 |
| `LEVANTAMENTO_…PARTE_I` | 29 | P1 |
| `DOSSIE_PARTE_II_…` | 26 | P2 |
| `volume_novo/08_quadro_unidades` | 18 | P4 |
| `volume_novo/06_grade1948` | 9 | P4 |
| `volume_novo/16b_cultos` | 8 | — (cap. 6, revisto) |
| `volume_novo/45_anexo_censo_1950` | 8 | P6 |
| `volume_novo/40_anexo_programa_1947` | 3 | P6 |
| `volume_novo/46_anexo_reforma_1951` | 3 | P6 |
| `volume_novo/22_agricultura` | 2 | P5 |
| `volume_novo/41`, `43`, `47` | 1 cada | P6 / P7 |

Cada sessão decide, parêntese a parêntese, entre remover (era redundante) e restaurar
(era informação), e registra a decisão no seu log. O `16b_cultos.md` (capítulo 6) fica
para o fecho, porque já foi revisto.

---

## 6. Ordem de arranque sugerida

Nem todas ao mesmo tempo. A primeira vaga são as quatro de melhor retorno e menor
dependência:

1. **P7** — Anexo H, 1.554 linhas; é o mais longo e o que mais cedo precisa de correr.
2. **P6** — anexos A-G, 914 linhas; mesma natureza, fidelidade ao original.
3. **P4** — as três grades, 429 linhas; tabelas, onde a montagem já criou defeitos.
4. **P1** — Parte I, 607 linhas; o grosso da prosa narrativa.

Segunda vaga: P2 (446), P3 (400), P5 (503), depois do merge da primeira. O capítulo 29
fecha o volume.
