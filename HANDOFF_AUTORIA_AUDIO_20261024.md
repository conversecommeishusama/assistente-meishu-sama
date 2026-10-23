# Handoff — autoria do áudio e voz do Meishu-Sama

**Data:** 24 de outubro de 2026
**Commits desta frente:** `Áudio: relatos do Jikan v4 e Curso Kannon em voz normal`,
sobre `Voz do Meishu-Sama restrita ao texto que é dele` (`b3c4e037`)
**Estado:** regra em produção; lote a correr; **nada bloqueado**.

> **Esta frente é independente.** Outra sessão trabalha no dossiê da difusão
> (`docs/DOSSIE_DIFUSAO_*`, `docs/volume_novo/`, `scripts/glossas_volume.py`,
> `scripts/auditar_glossario_volume.py`). Os commits das duas frentes chegaram a
> ser fundidos num só por acidente; foram separados em 24/10, e cada handoff
> descreve agora apenas a sua. **Nenhum arquivo da frente do dossiê pertence a
> este trabalho, e vice-versa.** O que as duas partilham é só o `main`.
>
> Ficheiros modificados por uma **terceira** frente (aulas: `docs/leituras_*`,
> `GOSHINSHO.md`, `HISTORICO.md`, `scripts/gerar_docx_leituras.py`) continuam
> **por commitar de propósito** — não são desta frente nem da do dossiê.

Para o contexto anterior (segmentação do corpus e rebuild dos índices) ver
`HANDOFF_SEGMENTACAO_20261021.md` — em especial o §6-G, que descreve a camada
de autoria que este documento continua.

---

## 1. A regra em uma frase

A voz clonada do Meishu-Sama é uma **afirmação sobre o texto**, não um efeito
sonoro. Por isso há uma camada editorial — `autoria_service` — que decide **de
quem é cada trecho** antes de `tts_service.provedor_canonico` decidir **com que
voz se lê**.

```
artigo → autoria_service → "meishu" ou "outro"
                              ↓           ↓
                        Fish/XTTS      edge (Antônio)
```

---

## 2. O que a verificação mostrou (e que contrariou a hipótese inicial)

A suposição de partida era que os periódicos e o "material institucional" eram
de terceiros. **Os dados disseram o contrário.**

| Verificação | Resultado |
|---|---|
| Testemunhos (おかげばなし) do acervo que estão nas specs PT | **0 de 2.506** |
| Contribuições (寄稿) que estão nas specs PT | **10 de 514** |
| Manual da Igreja | «Este pequeno livreto foi compilado **por mim**» |
| Doutrina da Igreja | «Prefácio — **Okada Jikan**» (assinado) |
| HAKONE ART MUSEUM | «**Sou Mokichi Okada**, fundador da Igreja» |
| A Story of Ukiyo-e | «Sou um amante da pintura… **construí** um pequeno museu» |
| Ensinamentos diversos / Esboço da Medicina | doutrina dele, 1.ª pessoa |

**Consequência:** os periódicos PT já vinham só com artigos dele, e as obras
ditas institucionais foram escritas ou compiladas por ele. A política antiga
(`sincronizar_audios.NAO_MEISHU`) excluía-as da **geração**; aplicada à voz,
tirava-lhe as próprias palavras. Por isso a lista de exclusão ficou quase vazia.

---

## 3. Onde a regra incide (estado final)

| Obra | Regra | Justificação |
|---|---|---|
| Todas as 137 obras, excepto as abaixo | **voz dele** | escritas/compiladas por ele |
| `Relatos de Milagres` | **artigo a artigo** | 135 de 141 artigos são testemunhos assinados (igreja + nome + idade); os 6 iniciais são ensaios dele |
| `Confissão de um Fiel` | **artigo a artigo** | manuscrito de Kinji Miyamoto; só o Prefácio (JP `自 観`) é dele |
| `Coleção Jikan Volume 4 (Histórias de Milagres)` | **artigo a artigo** — arts. 0–7 dele, 8–34 narrador | 8 ensaios dele em 1.ª pessoa + 27 relatos assinados por fiéis |
| `Curso Kannon (1~7)` | **tudo narrador** | palavras dele, mas o registo é de um discípulo («transcrição do curso feita por um discípulo») |

Decisões do usuário que fixaram as duas últimas linhas (23/10/2026):

> «No ítem 1, o formato é de relato do milagre com comentários de Meishu-Sama.
> O relato pode ser deixado na voz normal e o comentário de Meishu-Sama na voz
> dele. No ítem 2 pode manter tudo na voz normal.»

### Ressalva honesta sobre o «comentário»

No `Jikan Volume 4` **não existe comentário intercalado** nos relatos.
Verifiquei o original japonês: não há nenhum marcador (`御教え`, `御垂示`,
`（お伺）`, `明主`, `自観`) a meio dos relatos — a única ocorrência de `御教え`
é o título do art. 34 («御教えに深き感謝»). O que existe são os 8 ensaios de
abertura, e é isso que fica na voz dele.

Se aparecer comentário dele dentro de um relato, **é preciso dividir dentro do
artigo** — o que `autoria_service` ainda não faz (os spans são por artigo, ver
§6).

---

## 4. Ficheiros e pontos de entrada

| Ficheiro | Papel |
|---|---|
| `goshinsho/services/autoria_service.py` | **novo** — decide a autoria por obra/artigo/trecho. Tem `OBRAS_DE_OUTROS` e `SOBREPOSICOES` |
| `scripts/classificar_autoria_periodicos.py` | gera `reports/autoria_periodicos/AUTORIA_ARTIGOS.json` (gitignored, regenerável) |
| `goshinsho/services/tts_service.py` | `provedor_canonico(texto, rate, *, arquivo)` — ponto único de decisão de voz |
| `goshinsho/leitura_routes.py` | `/forum/api/tts` aceita `arquivo` no corpo |
| `static/js/leitura_tts.js` + `templates/leitura_texto.html` | enviam `data-arquivo` |
| `scripts/gerar_texto_worker_v2.py`, `gerar_trechos_lista.py`, `sincronizar_audios.py` | passam `arquivo` |
| `scripts/montar_lista_audio.py` | monta a lista do lote, separando dele / narrador |
| `tests/test_autoria_audio.py` | **novo** — 15 casos, incluindo os que impedem a política de silenciar |

**Degradação segura:** sem `arquivo`, ou se a classificação não existir, o
comportamento é o prior da obra — que nos casos mistos manda para o narrador.
Uma falha da camada editorial nunca põe texto alheio na voz dele.

---

## 5. Estado operacional (24/10/2026)

| Item | Valor |
|---|---|
| Cobertura de áudio | **47.150 / 62.565 = 75,4 %** |
| Backlog | **15.415 trechos** em 28 obras |
| — voz dele (XTTS, ~30 s cada) | **12.262** |
| — narrador (edge, ~1 s cada) | **3.153** |
| `goshinsho-tts-pregen` | **active**, `--workers 2 --lista data/tts_lista_todos.txt` |
| Lote actual | Relatos → Curso Kannon → Jikan v4 → Tijotengoku → … |
| App / portal | `active`; `/` em ~3 ms, `/forum/leitura` ~27 ms |
| Tecto de CPU do lote | 600 % (drop-in `10-limites-cpu.conf`), memória 4,9 GB |

A fila é ordenada por **narrador primeiro**: a correção pedida (tirar a voz dele
do que não é dele) fica feita em ~1 h; o resto é trabalho de CPU (~12 mil
trechos de XTTS).

### Órfãos

Os mp3 que deixaram de corresponder ao texto **não são apagados** (TTL = 0,
acervo permanente). Isto inclui:
- os relatos do `Jikan v4` que estavam na voz dele e passam a narrador;
- o `Curso Kannon` inteiro, pela mesma razão;
- os testemunhos dos `Relatos` e da `Confissão`.

São recuperáveis a qualquer momento (a chave é o sha256 do texto) e podem ser
limpos mais tarde com um relatório de órfãos — não há pressa nem risco.

---

## 6. O que fica por fazer

### 6.1 Dividir DENTRO do artigo (só se aparecer comentário dele)

`autoria_service` atribui autoria **por artigo**. Um relato com comentário dele
ao fim não pode ser dividido hoje. Se for necessário:

1. marcar o início do comentário na spec (um campo novo, ex. `comentario_anchor`);
2. `_estrutura()` passa a produzir spans dentro do artigo;
3. teste: o trecho antes do marcador é "outro", o de depois é "meishu".

Não vale a pena construir isto «por precaução»: nenhuma obra verificada precisa
(ver §3).

### 6.2 Revisão humana das classificações

A classificação dos periódicos tem evidência registada por artigo
(`autor:自観`, `secao:御論文`, `assinatura-de-fiel`, `bloco-prefacial`,
`lista-dele`, `…+prior-da-obra`). As categorias com `confianca: nenhuma` são as
que mais merecem leitura:

```bash
.venv/bin/python scripts/classificar_autoria_periodicos.py --amostra 5
python3 -c "
import json; d=json.load(open('reports/autoria_periodicos/AUTORIA_ARTIGOS.json'))
from collections import Counter
for k,v in d.items():
    c=Counter(a['autor'] for a in v['artigos']); print(k, dict(c))
"
```

### 6.3 Trabalho de CPU (não é pendência de decisão)

12.262 trechos de XTTS ≈ 4 dias com 2 daemons. Acompanhar:

```bash
tail -f /var/www/goshinsho/logs/tts_pre_geracao.log
.venv/bin/python scripts/montar_lista_audio.py    # regenera a lista e as contagens
systemctl stop goshinsho-tts-pregen               # parar
```

Não subir para 3 workers: 3 daemons ≈ 7 GB contra `MemoryHigh=6G`, e o OOM
cairia no serviço web.

### 6.4 A chave Fish

Ausente do `.env` (`grep FISH` = 0). Sem ela, tudo o que for gerado sai em
**XTTS**, e os ~26 mil áudios pagos continuam encontráveis mas com voz
diferente dos novos. Basta pôr `GOSHINSHO_FISH_AUDIO_API_KEY` no `.env` e
reiniciar — a próxima geração já sai na voz aprovada.

### 6.5 Decisões editoriais registadas (não são bugs)

- `Curso Kannon` — narrador, por decisão do usuário (registo de discípulo).
- `Confissão de um Fiel` — só o Prefácio na voz dele.
- Os 4 poemas/colectâneas (`Coletânea de Salmos`, `Montanha e Água`,
  `Fonte do Riso`, `Poemas Recentes`) — dele, mesmo sendo verso.

---

## 7. Comandos de verificação rápida

```bash
# testes da frente de voz e autoria (45 casos)
.venv/bin/python -m pytest tests/test_autoria_audio.py tests/test_tts_roteamento_voz.py -q

# diagnóstico de áudio (não gera nada)
.venv/bin/python scripts/sincronizar_audios.py --dry-run

# provar a regra em texto real
.venv/bin/python -c "
import sys; sys.path.insert(0,'/var/www/goshinsho')
from goshinsho.services import leitura_service as l, autoria_service as a, tts_service as t
arq='19491005 - Coleção Jikan Volume 4 Histórias de Milagres.txt'
txt=l.obter_texto(arq)
for tr,au in a.trechos_com_autor(arq,txt)[:3]:
    print(au, t.provedor_canonico(tr, arquivo=arq), tr[:40])
"
```

---

## 8. Armadilhas encontradas nesta frente

- **Um nome de ficheiro errado silencia a política.** `OBRAS_DE_OUTROS` e
  `SOBREPOSICOES` usam o nome exacto; se um ficheiro for renomeado, a regra
  desaparece **sem erro**. Há teste (`PoliticaNaoSilenciosa`) que falha nesse
  caso — não o remover.
- **Um mapa de sobreposição desactualizado aponta para o artigo errado.** Se a
  spec ganhar/perder artigos, os índices deslocam-se; há teste que compara
  `len(artigos)` com `len(mapa)`.
- **`deploy/` e `/etc/systemd/system/` divergem com facilidade.** Sincronizar
  sempre os dois.
- **`PrivateTmp=true`** na unidade do pregen: listas em `/tmp` não são visíveis
  ao serviço. Ficam em `data/`.
- **Medir taxa de geração** com `find -newermt '-N minutes'` dá valores errados
  (a janela desliza). Usar marcador absoluto: `mark=$(( $(date +%s) - 1 ))`.
- **`reports/` é gitignored.** A classificação de autoria é regenerável por
  `scripts/classificar_autoria_periodicos.py`; não a versionar.
