# Pipeline v2 — Goshinsho

Esta é a **nova arquitetura** do assistente, pensada para substituir os ramos especiais por assunto (Ohikari, Reisen, Insônia, etc.).

## O que mudou

| Antes (legacy) | Agora (v2) |
|----------------|------------|
| Vários caminhos de busca por tema | **Um caminho estrutural** (`buscar_trechos_core`) |
| Instruções diferentes por assunto | **Três modos**: doutrinário, pastoral, texto completo |
| Trecho errado do mesmo artigo | **Expansão por obra** — puxa o chunk certo da mesma publicação |
| Follow-up perde o assunto | **Contexto da pergunta anterior** na busca |
| Termos IM vs. tradução no acervo | **Glossário** liga elo↔linha espiritual, ohikari↔omamori, PT↔JP |

## Fluxo

```
Pergunta (+ histórico)
  → Modo: doutrinário | pastoral | texto completo
  → Busca estrutural (literal multi-termo + glossário + semântica + cross-encoder)
  → Diversificação de fontes + expansão de chunks vizinhos
  → Montagem de contexto (trechos maiores, centrados no ensinamento)
  → Resposta com instruções mínimas
```

## Ativação

Por padrão o chat usa **v2** (`GOSHINSHO_PIPELINE=v2` no `.env`).

Para voltar temporariamente ao sistema antigo: `GOSHINSHO_PIPELINE=legacy`

### Modo orientação (pastoral)

Pausável via `GOSHINSHO_ORIENTATION_MODE=false` no `.env` (reiniciar o app).
Para retomar depois: `GOSHINSHO_ORIENTATION_MODE=true`.

### Performance (preload)

`GOSHINSHO_PRELOAD_AI=true` no `.env` carrega modelos e índices PT/JP na inicialização,
evitando ~20 s de latência na primeira pergunta após reinício.

### Johrei Ho Koza (prioridade terapêutica)

Perguntas sobre Johrei, doença, pontos vitais, purificação, medicamentos e correlatos
priorizam trechos do **Curso de Johrei / 浄霊法講座** quando há match lexical —
sem excluir Gosuiji ou outras fontes.

## Quando a retradução terminar

1. Rebuild dos índices (`scripts/build_clean_large_indexes.py --install`)
2. Testar os roteiros de aceitação — **sem alterar código por tema**
3. Desativar definitivamente o pipeline legacy

## O que ainda depende do acervo

- Obras não indexadas (ex.: Kyoshu Yoko) **não podem ser citadas** — a pipeline responde honestamente.
- A qualidade da resposta depende da indexação e do chunking na construção dos índices.

## Testes

```bash
python3 -m unittest tests.test_pipeline_v2 -q
```
