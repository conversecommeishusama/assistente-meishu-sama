# Revisão Literária das Palavras Orais — Plano e Infraestrutura Pronta

## Contexto
- As **palavras escritas** (50 livros, 765 chunks) estão **100% concluídas**: revisadas, montadas e aprovadas em auditoria (DeepSeek).
- As **palavras orais** (83 arquivos: Gokōwa-roku, Gosuiji-roku, Mioshie-shū + Suplemento; 7.52M chars) estão em **retradução → auditoria → ajuste final** (outra frente de trabalho, em tmux).
- Esta fase prepara a **revisão literária das palavras orais** para começar **quando a frente atual terminar**.

## Decisão de arquitetura (2026-08-18)
Após teste comparativo validado, o executor das orais usará **reescrita SEMÂNTICA localizada** (não integral):

| Aspecto | Executor integral (usado nas escritas) | Executor semântico (orais) |
|---------|----------------------------------------|----------------------------|
| Método | Modelo devolve o chunk inteiro reescrito | Modelo propõe edições `{de, para}` |
| Risco | Perda de conteúdo + inflação de quantificador (57% dos achados) | Edições controladas com validação de âncora |
| Fidelidade (medida) | 0.898 similaridade | **0.937** |
| Texto bom | Reescreve por reescrever | **Fica intocado** |

## Configuração dimensionada (limite de 10 gunicorn)
**4 executors semânticos + 5 auditors = 9 gunicorn** (1 de folga).
- Execução: ~6,3h (100 chunks/h)
- Auditoria: ~6,9h (12 livros/h)
- **Tempo total estimado: ~7h**
- Custo estimado: **~US$ 0,40-0,60** (DeepSeek v4-flash @ $0,0424/1M tokens)

## Arquivos criados
| Arquivo | Função |
|---------|--------|
| `revisao_literaria/scripts/processar_chunk_semantico_deepseek.py` | Executor semântico (produção) |
| `revisao_literaria/scripts/run_fila_paralela.sh` | Laço stateless por fila (exec/aud) |
| `revisao_literaria/scripts/lancar_orais_paralelo.sh` | Sobe/derruba as 9 sessões tmux |
| `revisao_literaria/scripts/preparar_filas_orais.py` | Cria filas particionadas (4E + 5A) |
| `revisao_literaria/scripts/testar_execucao_semantica.py` | Teste comparativo (integral vs semântico) |

## Como iniciar (quando a frente atual terminar)
```bash
# 1. Gerar os chunks reais das orais (substitui os placeholders)
.venv/bin/python revisao_literaria/scripts/preparar_chunks.py --escopo orais

# 2. Atualizar as filas executor com os chunks reais (preparar_filas_orais já
#    distribui por arquivo; rodar de novo após preparar_chunks para pegar os chunks)
.venv/bin/python revisao_literaria/scripts/preparar_filas_orais.py 4 5

# 3. Lançar as 9 sessões tmux (4E semântico + 5A)
bash revisao_literaria/scripts/lancar_orais_paralelo.sh

# 4. Acompanhar
tail -f revisao_literaria/logs/executor_oral_semantico_0/loop.log
tmux ls | grep rev_oral

# 5. Parar (se necessário)
bash revisao_literaria/scripts/lancar_orais_paralelo.sh --parar
```

## Notas
- O montador (`montar_livro.py`) com lock de arquivo e re-enfileiramento (fix de 2026-08-18) se aplica às orais — o auditor reabre, o executor corrige, remonta e re-audita automaticamente.
- O auditor **permanece exaustivo** (como está) — decisão do usuário.
- O `preparar_filas_orais.py` distribui por arquivo (round-robin). Quando `preparar_chunks.py` gerar os chunks, pode-se distribuir por chunk para melhor balanceamento.
