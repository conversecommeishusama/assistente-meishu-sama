# A voz clonada sai do Chat do Goshinsho

**Data:** 27 de outubro de 2026
**Regra do usuário:** «exclua a voz de Meishu-Sama do chat Goshinsho, pois ela
é para ser opção apenas nos escritos e nas palavras orais da leitura
colaborativa».

---

## 1. O que estava a acontecer

O chat e a Leitura Colaborativa partilham **o mesmo botão, o mesmo JS e a
mesma rota**. A preferência de voz da Leitura é guardada no `localStorage` da
origem:

```js
localStorage["goshinsho-leitura-voz-edge"]   // "antonio" | "meishu" | ...
```

O botão «Ouvir resposta» do chat lia essa preferência:

```js
var vozAtual = opts.voz || vozEscolhidaEdge();   // leitura_tts.js, tocarTrecho
```

Sem `opts.voz` definido no chat, `vozEscolhidaEdge()` devolvia o que estivesse
no `localStorage`. **Quem escolhesse «Meishu-Sama» na Leitura passava a ouvir o
chat na voz clonada — sem nunca o ter pedido ali.** O pedido saía ainda sem
`arquivo`, por isso o servidor não tinha como distinguir chat de Leitura.

## 2. A correção, em duas camadas

### 2.1 Servidor — a camada que conta

`POST /forum/api/tts` passou a recusar `voz: "meishu"` sem uma **obra real da
Leitura** em `arquivo`:

```python
if voz == tts_service.VOZ_MEISHU and not tts_service.voz_clonada_autorizada(arquivo):
    voz = "antonio"
```

`voz_clonada_autorizada()` assenta em `obra_da_leitura()`, que só devolve um
nome quando:

- não está vazio e termina em `.txt`;
- **não** traz caminho (`../.env` e `sub/obra.txt` são recusados);
- existe mesmo em `GOSHINSHO_TEXTOS_PT`.

Sem essas condições, a resposta sai na voz do narrador (Antônio). O corte fica
no servidor de propósito: um cliente HTTP não depende de JS para decidir a voz.

A recusa é registada com `_logger.warning` **uma vez por processo**. Ia ser
`info`, mas o nível efectivo da app é `WARNING` — um aviso que não aparece no
journal não serve de nada. O guarda existe porque o chat faz prefetch de um
pedido por trecho: sem ele, o log enchia-se de linhas iguais.

### 2.2 Front — a causa do pedido

- `VOZ_CHAT = "antonio"`, fixa, e **nunca** lida do `localStorage`;
- em `substituirSeExistir`, quando o alvo não é da Leitura
  (`!isLeitura`), faz-se `opts.voz = VOZ_CHAT` — o chat deixa de cair em
  `vozEscolhidaEdge()`;
- `verificarVozMeishu()` sai antes do `fetch` quando não existe
  `#leitura-voz-select` (só existe em `leitura_texto.html`): o chat deixou de
  pedir a lista de vozes para nada.

## 3. O que continua igual

| Onde | Voz clonada |
|---|---|
| Leitura Colaborativa — escritos | **sim** (seletor) |
| Leitura Colaborativa — palavras orais | **sim** (seletor) |
| Chat do Goshinsho | **não** — narrador |
| Avaliação de textos | **não** — só vozes Microsoft (`_VOZES_VALIDAS`) |

A regra de autoria de 23/10 continua por cima desta: dentro da Leitura, a voz
clonada só nos trechos atribuídos a ele.

## 4. Prova em produção (27/10, servidor real)

| Pedido | Bytes | Voz |
|---|---|---|
| `{voz: meishu}` | 15.984 | Antônio |
| `{voz: meishu, arquivo: "chat"}` | 15.984 | Antônio |
| `{voz: meishu, arquivo: "19510520 - Luz dos Ensinamentos.txt"}` | 25.029 | clonada |

O journal confirmou o aviso único:

```
TTS: voz 'meishu' pedida sem obra da Leitura (arquivo=None) — a partir daqui
responde o narrador. A voz clonada é opção só nos escritos e nas palavras orais
da Leitura.
```

## 5. Ficheiros

| Ficheiro | Mudança |
|---|---|
| `goshinsho/services/tts_service.py` | `obra_da_leitura()`, `voz_clonada_autorizada()` |
| `goshinsho/leitura_routes.py` | recusa de `meishu` sem obra + aviso único |
| `static/js/leitura_tts.js` | `VOZ_CHAT`, `opts.voz` fora da Leitura, `verificarVozMeishu` sai cedo |
| `tests/test_voz_clonada_so_na_leitura.py` | **novo** — 15 casos |

## 6. Testes

```bash
.venv/bin/python -m pytest tests/test_voz_clonada_so_na_leitura.py -q
node --check static/js/leitura_tts.js
```

Cobrem: obra real aceite; `None`/vazio/`.txt` ausente/caminho embutido/obra
inexistente recusados; a rota a forçar o narrador no caso do chat; a Leitura a
manter a voz clonada; as três vozes neurais intactas; o aviso de log uma única
vez; e três invariantes do JS (o chat força a voz, `VOZ_CHAT` não é clonada, o
seletor não é consultado fora da Leitura).

## 7. Armadilhas

- **Não repor `opts.voz` como opcional no chat.** Qualquer `opts.voz` ausente
  volta a cair em `vozEscolhidaEdge()`, e o `localStorage` é partilhado.
- **Não alargar `obra_da_leitura` a caminhos.** Aceitar `sub/obra.txt` abriria
  a porta a pedir a voz clonada com o nome de qualquer ficheiro existente.
- **Não baixar o aviso para `info`.** O nível efectivo é `WARNING`; voltaria a
  ser invisível.
