# HANDOFF — DIAGNÓSTICO do rebuild de índices: JP tem mais chunks que PT

> Criado em **2026-08-25** (fim de sessão — usuário saiu, computador online, sem
> resposta até voltar). Este handoff documenta o **diagnóstico completo** do
> problema "por que o rebuild tem mais chunks em JP do que em PT", com causa
> raiz confirmada. **Nenhuma ação destrutiva foi tomada** — aguarda decisão do
> usuário.

---

## 1. A PERGUNTA DO USUÁRIO
- "Por que tem mais chunks em JP (4067) do que em PT (3517)?"
- "Se cada chunk tem menos caracteres era para ter mais chunks e não menos."
- "Ou que não estão todos os arquivos sendo segmentados."
- "Confirmar se o JP está correto e aceitar o build do JP; verificar completude e
  correção do corpus/spec/segmentação do PT e refazer o build do zero."

## 2. NÚMEROS DO BUILD
| Build | PT | JP |
|---|---|---|
| Produção (14/08) | **6466** | 4076 |
| Build v2 (25/08) | 3538 | 4067 |
| Build final (25/08, em andamento) | 3517 | 4067 |

O **PT caiu de 6466 → ~3517** (quase metade). O JP ficou estável (~4067-4076).
**O JP está consistente** (não mudou entre builds). O problema é só no PT.

## 3. CAUSA RAIZ (CONFIRMADA — sem alterar nada)

### Mecanismo do build (`scripts/build_clean_large_indexes.py`)
Para cada arquivo:
1. `_load_spec_for(arquivo)` carrega a spec de segmentação
   (`reports/livros_trabalho/segmentacao_manual/<arquivo>.json`).
2. Se a spec tem **>1 artigo** e **todas as âncoras casam** com o texto
   (`article_entries_from_spec`), o arquivo é segmentado por artigo → MUITOS
   chunks (1 por artigo).
3. Se a spec tem ≤1 artigo, OU **qualquer âncora não casa**, cai para
   `file_entry` → **arquivo inteiro = POUCOS chunks**.

### O problema: âncoras PT desatualizadas
- O **corpus PT foi RETRADUZIDO/revisado** (orais retraduzidos — ver
  `docs/14`, `GOSHINSHO.md`; escritas revisadas literariamente).
- A retradução **removeu/alterou os cabeçalhos de data de seção** em muitos
  arquivos. Exemplo concreto — **Gokōwa-roku (Suplemento)**:
  - Spec tem 36 âncoras de data (ex.: `18 de maio do ano 23 da Era Showa (1948)`).
  - Texto PT atual só tem a 1ª data (`1º de janeiro do ano 23 da Era Showa (1948)`).
  - **34/36 âncoras NÃO casam** → cai para arquivo inteiro → 1 chunk (em vez de 36).
- Isso acontece em **41 arquivos PT** com spec multi-artigo; no **JP só 14**.

### Tabela de falhas de segmentação (PT vs JP)
| | Segmentados | Falham (caem p/ inteiro) | Spec ≤1 artigo |
|---|---|---|---|
| **PT** | 82 | **41** | 14 |
| **JP** | 109 | 14 | 14 |

Arquivos PT que falham (exemplos): Suplemento (36 arts), Coletânea de Salmos
(310), Poemas de Akemaro (487), Montanha e Água (224), Coleções Jikan (48, 35,
22...).

## 4. O QUE NÃO FOI FEITO (aguarda o usuário)
- **NÃO** aceitei/promovi o build JP (o JP está estável ~4067, mas promoção exige
  autorização explícita — GOSHINSHO.md §3).
- **NÃO** refiz o build do zero (processo ~5-10h; usuário ausente para validar).
- **NÃO** alterei specs, textos, nem índices.
- O build em andamento (PID 91004, iniciado 19:41, ~11h) usa corpus/specs
  desatualizados → **será DESCARTADO** (não esperar por ele).

## 5. DECISÕES PENDENTES (para quando o usuário voltar)
1. **Atualizar as specs de segmentação PT** para refletir o texto revisado:
   - Recriar as âncoras de data de seção que sumiram na retradução, OU
   - Re-extrair as âncoras automaticamente das seções existentes, OU
   - Decidir que os orais retraduzidos são "unidade inteira" (aceitar menos
     chunks — mas perde segmentação por data).
2. **Rebuild do zero** (PT + JP) após decidir a segmentação.
3. **Confirmar o JP** (estável; pode aceitar se quiser economizar tempo).

## 6. COMO REPRODUZIR O DIAGNÓSTICO (comandos)
```bash
cd /var/www/goshinsho
# Contagem PT vs JP de segmentados/falham
.venv/bin/python -c "
import sys; sys.path.insert(0,'scripts')
import build_clean_large_indexes as b
from pathlib import Path
for lang, d, lc in (('PT', b.PT_DIR, 'pt'), ('JP', b.JP_DIR, 'jp')):
    seg=falha=uni=0
    for p in sorted(d.glob('*.txt')):
        spec=b._load_spec_for(p.name)
        if not spec: continue
        arts=spec.get('articles', [])
        if len(arts)<=1: uni+=1; continue
        if b.article_entries_from_spec(p, lc, None, spec): seg+=1
        else: falha+=1
    print(lang, 'seg=', seg, 'falha=', falha, 'uni=', uni)
"
# Testar âncoras de um arquivo específico
.venv/bin/python -c "
import sys; sys.path.insert(0,'scripts')
import build_clean_large_indexes as b
nome='19480101 - Gokōwa-roku (Suplemento).txt'
spec=b._load_spec_for(nome); texto=b.clean_body(b.read_text(b.PT_DIR/nome))
arts=spec['articles']
nao=sum(1 for a in arts if a.get('pt_anchor') and a['pt_anchor'] not in texto)
print(f'{nome}: {nao}/{len(arts)} âncoras não casam')
"
```

## 7. CONTEXTO ADICIONAL
- O trabalho de **comunidade/leitura** (protótipo `/versao2`) está em outro
  handoff: `HANDOFF_ACOMPANHAMENTO_LEITURA_20260825.md`.
- Memórias: `/memories/repo/diagnostico-chunks-pt-jp-2026-08-25.md`,
  `/memories/repo/dificuldade-acompanhamento-leitura-2026-08-25.md`.
