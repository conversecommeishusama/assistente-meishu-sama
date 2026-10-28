# Portal vs produção — o que foi encontrado em 28/10/2026

## Resumo

`/var/www/goshinsho-portal/` **não é um espelho** do repositório. É uma
instalação de 29/09 que foi parcialmente convertida em symlinks, e o resto
ficou congelado em cópias.

- 65 ficheiros `.py`: **41 symlinks** para `/var/www/goshinsho/` e
  **24 cópias reais**.
- Destas 24, **9 divergem** do principal. Duas divergem no sentido inverso:
  o portal tem código que **nunca esteve no git**.

Público: **não afectado**. O `Caddyfile` manda `goshinsho.com.br` para
`localhost:8000` (produção, código actual); só `/portal*` vai para o 5092.

## O que o portal tem e o principal perdeu (nunca esteve no git)

Em `goshinsho/leitura_routes.py` do portal, datado de 30/09:

- `leitura_service.pode_ler(arquivo, user)` — restrição da **Palavra Oral**
  para quem não tem conta. O texto **não é enviado** ao browser
  (`conteudo=""`, `acesso_bloqueado=True`), não é uma camada de CSS.
- `exigem_conta` no `leitura.html` — o cadeado nos cartões.
- `motivo_restricao_oral()`.

Nada disto existe no principal: `grep -c exigem_conta` dá **0** em
`goshinsho/leitura_routes.py`, e `git log -S exigem_conta` não encontra
commit nenhum. Ou seja: o protótipo ganhou uma regra de acesso que a produção
nunca recebeu.

Também só no portal: `goshinsho/portal_routes.py` (17.359 B) e
`goshinsho/services/artigo_service.py`.

## O que o principal tem e o portal não (atraso normal, 27-28/10)

- `leitura_routes.py`: o corte da voz clonada no servidor
  (`voz_clonada_autorizada(arquivo)`) e o `arquivo=` passado ao
  `sintetizar()`.
- `routes.py` (83.767 B vs 82.308 B), `pipeline/{scoring,rank,jp_scoring,retrieve}.py`.

## Prova medida da consequência

`POST /forum/api/tts` com `"arquivo": "19510520 - Luz dos Ensinamentos.txt"`:

| porta | bytes | formato | voz |
|---|---|---|---|
| 8000 | 43.466 | MPEG v1, 128 kbps, **44,1 kHz** | aprovada (Fish) |
| 5092 | 15.984 | MPEG v2, 48 kbps, **24 kHz** | narrador (edge) |

O portal também serve a landing em **3,8 s e 11 KB**, contra **2 ms e 37 KB**
no 8000 — mas com o mesmo template, o que indica código antigo, não template
diferente.

## Recomendação

Não copiar nada às cegas: as divergências vão nos dois sentidos, e as do
portal têm trabalho que não está no git.

1. **Primeiro** trazer para o principal o que só existe no portal
   (restrição da Palavra Oral, `portal_routes.py`, `artigo_service.py`),
   com testes. É funcionalidade, não estilo.
2. **Depois** converter as restantes cópias em symlinks, ou alinhar o
   5092 com o 8000 — mas só depois do passo 1, senão apaga-se trabalho.
3. Antes de tudo: confirmar com o usuário se `/portal` ainda é um
   protótipo vivo ou se pode ser desligado. Se ninguém o usa, a opção mais
   barata é desligá-lo e remover o `handle /portal*` do Caddyfile — deixa de
   haver duas verdades.

## Como conferir sem se enganar

Comparar com `cmp`, nunca por tamanho ou data. `stat -c%s` com caminho
relativo deu valores trocados quando o `cwd` era o do portal.
