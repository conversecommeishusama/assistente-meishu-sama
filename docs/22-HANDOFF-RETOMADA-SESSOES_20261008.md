# Handoff — Retomada de duas sessões (08/10/2026)

> Cole o bloco da sessão desejada no início de um novo chat para restaurar o contexto.
> Repositório: `conversecommeishusama/assistente-meishu-sama` (cwd `/var/www/goshinsho`)

---

## SESSÃO A — Curso de formação de novos membros (Kyōshu Yōkō)

**Objetivo:** preparar o curso de formação de novos membros baseado no livro *Kyōshu Yōkō*, em aulas escritas com palavras próprias.

### Estado atual (CONCLUÍDO — só falta decidir sobre commit pendente)

1. Preparei a **Aula 4** (práticas da fé: Johrei, alimentação, Agricultura Natural, o Belo/flores, cultos, leitura dos Escritos Divinos, dedicação, donativo de gratidão, Sorei-Saishi, cuidado com o Ohikari) — rascunho guardado em `_antigo/`.
2. **Consolidei as 4 aulas em 3** (o conteúdo da Aula 4 foi distribuído nas Aulas 2 e 3).
3. **Ajuste do "belo" + missão do homem:** o belo foi para a **Aula 1** (seção `## A beleza também faz parte`), e criei a seção `## A missão do ser humano` — o homem como **representante de Deus na construção do Paraíso Terrestre** ("ninguém está aqui por acaso", cada fiel é apóstolo da obra). Amarrei a missão também nas Aulas 2 e 3.
4. **Copiei a pasta para dentro do goshinsho** e commitei (commit isolado `90cb8202`).

### Resultado final das 3 aulas

| Aula | Palavras | Leitura | Págs |
|---|---|---|---|
| 1 — Como o universo funciona | 1.728 | ~12 min | 5 |
| 2 — Por que adoecemos e o que é o Johrei | 1.934 | ~13 min | 6 |
| 3 — O que vem depois, e a vida de fé | 2.221 | ~15 min | 7 |

### Arquivos

- **Versão versionada (edite AQUI):** `/var/www/goshinsho/docs/aulas_kyoshu_yoko/`
 - `Aula_01_Como_o_universo_funciona.md`, `Aula_02_Por_que_adoecemos_e_o_Johrei.md`, `Aula_03_O_que_vem_depois.md`
 - `gerar_aulas.py` (regenera os artefatos), `saida/` (TXT + DOCX + PDF), `_antigo/` (rascunho da Aula 4 descartada)
- **Origem (workspace rattail):** `/var/www/rattail/work/kyoshu_yoko/aulas_simples/`
- **Workspace multi-pasta:** `/var/www/rattail-goshinsho.code-workspace`

### PENDÊNCIA (única decisão em aberto)

- `HISTORICO.md` foi **atualizado com a entrada 08/10, mas NÃO commitado** — porque ele já tinha ~118 linhas de reestruturação de sessões antigas pendentes, e `GOSHINSHO.md` tem −414 linhas pendentes. Commitá-lo misturaria meu registro com essa reestruturação antiga (que não é minha e ainda não foi decidida).
- Opções: (a) commitar `HISTORICO.md` junto com a reestruturação num commit de docs separado; ou (b) reverter só a reestruturação antiga e commitar apenas a minha entrada.
- Regra importante: o manual de liturgia da IMMB tem restrição de direitos autorais — não reproduzir trechos literais.

---

## SESSÃO B — Periódicos (verificação + tradução + glossário)

**Objetivo:** verificar os textos de Meishu-Sama nos periódicos **Eiko, Hikari, Kyusei, Tijotengoku**, traduzir os ausentes e aplicar o glossário de tradução com rigor.

### Estado atual (quase pronto — tradução 99,3%)

1. **Verificação concluída:** conclusão corrigida — são **415 artigos ausentes** (a conclusão anterior "ausentes: 0" media séries/arquivos, não artigos).
 - 寸鉄/寸鉄活人 é **texto canônico de Meishu-Sama**.
 - 質問応答 e 巻頭言 **NÃO estão nas orais** do app.
2. **Tradução** (deepseek, 16 workers, tmux `trad_periodicos`): **412/415 (99,3%)**. 3 pendentes (`Eiko 250/256/98`) por timeout de 30s da API → corrigido para 240s, sendo retraduzidos.
 - Plano do Contabo confirmado: **14 vCPU / 49 GB RAM** (upgrade real).
 - Bug corrigido: glossário rigoroso gerava falso-positivos e lentidão.
3. **Consolidação dos achados do Claude:** 1.190 achados · 649 termos · 11 grupos → `docs/DECISOES_GLOSSARIO_CONSOLIDADO_20261008.md` (11 temas + 9 pontos de decisão).
4. **Ordem "pode fazer" executada** — corrigidos **6 defeitos**:
 - 2 linhas de cabeçalho vazando para o prompt do LLM (agora **833 entradas válidas**, 0 sem kanji);
 - notas editoriais `(...)` virando "forma exigida" — correção em duas camadas;
 - +3 defeitos encontrados na verificação.

### Arquivos principais

- `docs/DECISOES_GLOSSARIO_CONSOLIDADO_20261008.md` — artefato de decisão do glossário
- `glossario_traducao.json` — **835 entradas** (era 791)
- `glossario_traducao.json.bak_ajuste_consolidado_20261008T174955Z` — backup (791)
- `glossario_regras.json` — NOVO (2 proibições · 15 medidas · 12 "1ª ocorrência" · 27 isentos)
- `scripts/glossario_core.py` — NOVO motor do glossário
- `scripts/aplicar_ajuste_glossario_20261008.py`, `auditar_acervo_glossario.py`, `triar_regras_glossario.py`
- `scripts/traduzir_periodicos_meishu_sama.py`, `montar_fila_traducao_periodicos.py`, `run_traducao_periodicos.sh`, `refazer_traducao_periodicos_antigos.sh`
- `scripts/conferir_presenca_periodicos.py`, `confirmar_ausentes_periodicos.py`, `consolidar_achados_kowa.py`, `consolidar_periodicos_meishu_sama.py`, `finalizar_periodicos_meishu_sama.py`
- `docs/ANALISE_GLOSSARIO_QUESTOES_20261008.md`, `docs/ANALISE_SUGESTOES_LEITURA_20261007.md`, `docs/ORCAMENTO_TRADUCAO_PERIODICOS_20261007.md`
- tmux: `trad_periodicos` · logs: `logs/trad_periodicos_*.log`

### Próximos passos (após fechar a tradução)

1. Inserir os novos textos traduzidos nos **arquivos já existentes** do acervo: Tijotengoku, Hikari, Eiko, Kyusei.
2. Atualizar a **leitura colaborativa** e **promover** os textos.
3. Aproveitar a nova promoção para aplicar os **ajustes pendentes, incluindo os sugeridos pelos usuários na leitura colaborativa**.
4. Aplicação do glossário deve ser **dedicada e rigorosa** (instrução explícita do usuário).

---

### Notas de convenção do projeto

- Regra de finalização: commits isolados por entrega, com entrada em `HISTORICO.md`.
- Cuidado com direitos autorais (manual IMMB — não reproduzir literal).
- Periódicos: só textos de Meishu-Sama, triagem por script + conferência manual, entrega JSON/CSV.
