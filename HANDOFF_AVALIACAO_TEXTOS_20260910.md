# Handoff — Sistema de Avaliação de Textos (leitura independente)

> **Data:** 10/09/2026
> **Rota:** `https://goshinsho.com.br/avaliacao` (restrita ao login de administrador)
> **Pedido do usuário:** *"vc pode criar um link no meu login de administrador
> para a avaliação dos textos no mesmo perfil da leitura colaborativa, mas
> totalmente independente do sistema servido ao usuário atualmente"* e
> *"teria que criar uma pasta nova com os arquivos que vamos trabalhar e um
> sistema de leitura separado; não precisa ser com o audio de meishu-sama, pode
> ser com o audio da microsoft."*

---

## 1. O que foi criado

Um **sistema de leitura paralelo** à Leitura Colaborativa, para revisar os textos
do ciclo "Mundo Espiritual e Antepassados" com conferência por áudio, **sem
nenhum risco** para o que o usuário final vê.

| Peça | Arquivo | Papel |
|---|---|---|
| Página | `goshinsho/avaliacao_routes.py` | Blueprint `/avaliacao` (índice, leitura, API) |
| Serviço | `goshinsho/services/avaliacao_service.py` | Lê a pasta de trabalho, monta blocos/trechos |
| Prep. da pasta | `scripts/preparar_textos_avaliacao.py` | Converte a apostila (`.md`) em `.txt` de trabalho |
| Templates | `templates/avaliacao*.html` | Índice (`avaliacao.html`) + leitor (`avaliacao_texto.html`) |
| Estilo | `static/css/avaliacao.css` | Ajustes de apresentação |
| Leitor | `static/js/avaliacao.js` | Fila de áudio + destaque do trecho + prefetch |
| Link no admin | `templates/_developer_nav.html` | "Avaliação de Textos" no menu do desenvolvedor |

---

## 2. Como o isolamento é garantido

| Dimensão | Leitura Colaborativa (usuário) | Avaliação (você) |
|---|---|---|
| Pasta dos textos | `textos_leitura_colaborativa/` (135 arq) | **`textos_avaliacao/`** (8 arq) |
| Cache de áudio | `data/tts_cache/` (16 GB, voz clonada) | **`data/tts_cache_avaliacao/`** |
| Voz | clonada do Meishu-Sama (Fish/XTTS) | **Microsoft** (Antônio/Francisca/Thalita) |
| Rota | `/forum/leitura` (público) | **`/avaliacao`** (admin) |
| Git | ignorado (`.gitignore:36`) | **ignorado** (`.gitignore:78,82`) |

Verificado na prática: o MP3 gerado na avaliação **não** aparece no cache de
produção e vice-versa.

### Acesso
- A rota usa `require_developer_page` / `require_developer_json` — a **mesma**
  regra do `/admin` (e-mails em `DEVELOPER_EMAILS`).
- Sem login: página → `302` para o login; API → `401`.
- Com login comum (não-admin): `403`.

---

## 3. Como usar

1. **Preparar a pasta de trabalho** (só quando a apostila mudar):
   ```
   /var/www/goshinsho/.venv/bin/python scripts/preparar_textos_avaliacao.py
   ```
   - Lê `docs/leituras_integrais/Aula_*.md` e escreve em `textos_avaliacao/`.
   - **Nunca sobrescreve** um arquivo que já existe (preserva o trabalho em
     andamento). Para refazer um arquivo, apague-o e rode de novo.

2. **Abrir:** no menu de administrador → **Avaliação de Textos**, ou
   `https://goshinsho.com.br/avaliacao`.

3. **Ouvir:** botão **🔊 Ouvir**. Cada trecho é gerado on-demand (~2 s), com
   prefetch do próximo. Clicar num parágrafo começa a leitura dali. Trocar voz
   ou velocidade reinicia do trecho atual.

---

## 4. O que o sistema **não** faz (por decisão)

- **Não escreve** no corpus, no staging nem em qualquer pasta publicada —
  é somente leitura da pasta de trabalho.
- **Não promove** nada para a Leitura Colaborativa: isso é um passo posterior e
  explícito, sob autorização (regra `GOSHINSHO.md` §3).
- **Não usa** a voz clonada do Meishu-Sama: o acervo de áudio dela é material
  aprovado e fica intocado.

---

## 5. Pendências / decisões para o usuário

1. **Como editar o texto?** Hoje a página é **somente leitura** (a edição é feita
   no arquivo `.txt`/`.md`). Se quiser, o próximo passo é adicionar edição
   inline + anotação por trecho (a infraestrutura de colaborações já existe no
   projeto e pode ser reaproveitada com tabela própria).
2. **Conferência por áudio:** o áudio da Microsoft lê *colchetes* (`[de morrer]`)
   e parênteses normalmente; a voz clonada os removia. Vale conferir se esse é o
   comportamento desejado na conferência.
3. **Aprovação por arquivo:** ainda não há marcação de "arquivo conferido".
   Candidato natural para a próxima iteração.
4. **Publicação da rota:** o blueprint é registrado em `create_app`
   (`goshinsho/__init__.py`). Como o Caddy manda tudo para a porta 8000, a rota
   já responde no domínio — **não** foi preciso mexer no Caddyfile nem criar
   serviço systemd.

---

## 6. Validações executadas

| Verificação | Resultado |
|---|---|
| Rotas registradas | 7 (`/avaliacao`, `/avaliacao/`, `/avaliacao/texto/<arq>`, 4 APIs) |
| Acesso sem login | página `302` · API `401` ✓ |
| Acesso de administrador | índice `200` (8 obras) · leitura `200` (23 blocos) ✓ |
| Áudio das 3 vozes | `200 audio/mpeg` ✓ |
| Cache isolado | MP3 da avaliação ∉ produção, e vice-versa ✓ |
| Fila de trechos (Aula 01) | 31 trechos, maior 697 chars, 0 vazios ✓ |
| Geração real (amostra) | 6/6 OK, ~2 s por trecho ✓ |
| Suíte de testes | 178 passed, 1 skipped, **1 falha pré-existente** (`test_ohikari_filter`) |
