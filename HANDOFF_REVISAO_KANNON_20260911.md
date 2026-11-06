# Handoff — Revisão literária do Curso Kannon (1–7)

> **Data:** 11/09/2026
> **Pedido:** *"gostaria de testar no primeiro arquivo de palavras escritas Curso
> Kannon (1-7), gostaria que vc fizesse a revisão desse texto no padrão do que
> foi feito nas aulas […]. Acabando coloque na página que criamos para a minha
> avaliação."*
> **Restrição dada pelo usuário:** trabalhar **na pasta de avaliação** —
> *"não se pode mexer no arquivo que está na leitura colaborativa"*.

---

## 1. Resultado

| | |
|---|---|
| **Original** (intocado) | `textos_leitura_colaborativa/19350000 - Curso Kannon (1~7).txt` |
| sha256 do original | `351a1d149d56af998e9f29ceae3aaa062d541b8b429b702278b14199ebfddfcb` |
| **Revisado** | `textos_avaliacao/19350000 - Curso Kannon (1~7) - REVISADO.txt` |
| **Original p/ comparação** | `textos_avaliacao/19350000 - Curso Kannon (1~7) - ORIGINAL.txt` |
| Backup + trilha | `backups/revlit_kannon_20260911/` |

O arquivo da Leitura Colaborativa **não foi tocado** — conferido por sha256 ao
final (hash idêntico ao do início).

---

## 2. Integridade (auditoria objetiva)

| Métrica | Original | Revisado |
|---|---:|---:|
| Blocos (parágrafos) | 772 | **772** (Δ 0) |
| Palavras | 26.773 | 26.754 (**−0,07%**) |
| Caracteres | 156.645 | 156.605 (−0,03%) |
| Aspas duplas | 312 | 312 ✅ |
| Blocos com kanji | 93 | 93 ✅ |
| Números | 92 | 92 ✅ |
| `[Ilustração omitida]` | 2 | 2 ✅ |
| Blocos alterados | — | 124 (16,1%) |

- **Zero artefatos**: sem espaços duplos, espaços no fim de linha, tabs ou
  linhas em branco duplas.
- **`se se` real**: 0 (as 9 ocorrências são falsos positivos tipo
  "ne**sse se**ntido").
- **"homem"**: 7 → 7, todas legítimas (citações entre aspas como *"O homem bom
  é salvo, quanto mais o homem mau"*; + "Jesus"/"homens e mulheres"). Correto
  **não** mexer.
- **Pendências classe D:** nenhuma.

---

## 3. Método usado (reproduzível para os próximos arquivos)

1. **Backup + sha256** do original **antes de tudo**.
2. **Split por aula** (`partes_orig/parte_01..07.txt`, ~20 k chars cada) —
   evita estouro de contexto e permite paralelizar.
3. **Parte 1 revisada à mão** para fixar o padrão-ouro, + `BRIEF_ESTILO.md`
   (briefing reutilizável: regras, formatação, capitalização, colchetes).
4. **Demais partes para subagentes em paralelo**, cada um apontando o par de
   referência `partes_orig/parte_01.txt` ↔ `revisado/parte_01.txt` para calibrar
   o grau de intervenção.
5. **Concatenação** com `"\n\n".join(p.strip("\n") …)` — **nunca `cat` direto**
   (perde as linhas em branco dos limites e funde blocos).
6. **Auditoria**: diff de blocos alinhados por índice + invariantes
   (aspas/kanji/números/`[Ilustração omitida]`) + varredura de artefatos.

### Armadilhas encontradas (evitar nas próximas)
- Subagentes **adicionaram o título do documento** no topo das partes 03 e 07 →
  conferir `head -1` de cada parte e remover.
- Um subagente trocou `"Konohana"` por `«Konohana»` (tipografia não autorizada)
  — detectado pela **contagem de aspas**. Revertido.
- `(do autor)` → `[do autor]`: intencional, previsto no guia §1.6.
- Usar caminho **absoluto** do Python (`/var/www/goshinsho/.venv/bin/python`).

---

## 4. Na página de avaliação

`https://goshinsho.com.br/avaliacao` — agora com **10 obras**:
8 aulas do ciclo + **Kannon ORIGINAL** + **Kannon REVISADO** (lado a lado, para
comparação direta).

Validado: `/avaliacao` → 200 (com admin), `/avaliacao/api/texto/…` → 200 com
**772 blocos / 812 trechos** (maior trecho 698 chars, sob o limite de 700),
`/avaliacao/api/tts` → 200 `audio/mpeg`.

---

## 5. Trilha de auditoria

- `backups/revlit_kannon_20260911/trilha/RELATORIO_MUDANCAS.md`
  → 45 primeiros blocos alterados, com antes/depois e diferenças destacadas.
- `backups/revlit_kannon_20260911/trilha/RELATORIO_REVISAO.json`
  → os 124 blocos alterados com similaridade, mais métricas e invariantes.
- `backups/revlit_kannon_20260911/BRIEF_ESTILO.md`
  → briefing reutilizável para os próximos arquivos.

---

## 6. O que **não** foi feito (de propósito)

- ❌ Nenhuma escrita em `textos_leitura_colaborativa/` (só leitura).
- ❌ Nenhuma escrita em `textos_portugues/` ou staging.
- ❌ Nenhum rebuild de índice, nenhum restart de serviço.
- ❌ Nenhum commit/push (o novo arquivo está em pasta ignorada pelo git).
- ❌ Nenhuma promoção — é passo posterior e explícito (regra `GOSHINSHO.md` §3).

---

## 7. Próximo passo (sua decisão)

Avaliar o resultado em `/avaliacao`. Conforme o veredito:
1. **Aprovado** → o método escala: aplicar aos demais escritos em batelada.
2. **Ajustes** → diz o que corrigir que eu recalibro o `BRIEF_ESTILO.md` e
   reprocesso.
3. **Promoção** (se aprovado) → copiar para o corpus + rebuild **sob sua
   autorização**.
