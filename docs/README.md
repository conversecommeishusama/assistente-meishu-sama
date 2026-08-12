# Documentação do Goshinsho

Índice de navegação. Esta pasta reúne a documentação **narrativa e de
arquitetura** do projeto — de onde veio, por que existe, o que a compõe e
como está organizado. Não são arquivos operacionais (scripts, regras de
hook, o system prompt de produção) — esses continuam onde estão hoje e não
foram tocados nesta reorganização.

## Ordem de leitura sugerida

0. **[08-MISSAO-E-VISAO.md](08-MISSAO-E-VISAO.md)** — por que o Goshinsho
   existe, no nível mais profundo, e a visão final que ele serve. Produzido
   em sessão de perguntas e respostas com o fundador (15/jul/2026) — leia
   isto primeiro, os arquivos numerados abaixo ainda não foram atualizados
   para refletir essa camada (a numeração/ordem final será ajustada quando
   todas as sessões de reconstrução terminarem).
1. **[01-VISAO-GERAL.md](01-VISAO-GERAL.md)** — o que é o Goshinsho, por
   que existe, para quem é, o que não é.
2. **[02-HISTORIA.md](02-HISTORIA.md)** — de onde viemos: linha do tempo
   desde o primeiro commit até hoje, cada fase com a dificuldade real que
   a motivou e a solução encontrada.
3. **[03-PRINCIPIOS-E-DIRETRIZES.md](03-PRINCIPIOS-E-DIRETRIZES.md)** —
   os princípios que hoje norteiam decisões no projeto. Rascunho de
   partida para revisarmos juntos.
4. **[04-ACERVO.md](04-ACERVO.md)** — do que o acervo é composto: séries,
   quantidades, idiomas, os dois glossários.
5. **[05-ARQUITETURA-APLICATIVO.md](05-ARQUITETURA-APLICATIVO.md)** — como
   o código do aplicativo está organizado: serviços, pipeline de busca,
   mapa de `goshinsho/services/`.
6. **[06-GLOSSARIO-DO-PROJETO.md](06-GLOSSARIO-DO-PROJETO.md)** —
   vocabulário/siglas usadas internamente para falar do processo (Fase G,
   tutela, Δ=0, shard, etc.) — não confundir com o glossário teológico do
   acervo.
7. **[07-ESTADO-ATUAL.md](07-ESTADO-ATUAL.md)** — fotografia do estado do
   projeto na data desta reorganização (15/jul/2026); desatualiza rápido
   por natureza.
8. **[09-ROADMAP.md](09-ROADMAP.md)** — visão de produto e próximas
   funcionalidades, capturada em sessão de Q&A; intenção futura, não
   estado atual.
9. **[10-ESTUDO-TEMPO-TRADUCAO.md](10-ESTUDO-TEMPO-TRADUCAO.md)** —
   estimativa de quanto tempo o acervo levaria para ser traduzido sem
   apoio de IA, com metodologia e premissas explícitas.
10. **[11-PACOTE-CORRECOES-APLICATIVO.md](11-PACOTE-CORRECOES-APLICATIVO.md)**
    — pacote consolidado de correções de código/infraestrutura do
    aplicativo levantadas em verificação e uso real (15/jul/2026);
    nenhum item executado ainda, aguarda autorização. Desatualiza rápido
    conforme itens forem corrigidos ou novos forem achados.
11. **[12-RELATORIO-PACOTE-APLICATIVO-TESTE.md](12-RELATORIO-PACOTE-APLICATIVO-TESTE.md)**
    — relatório do pacote acima já implementado e testado numa cópia
    isolada (`/var/www/goshinsho-test`), sem tocar produção. Inclui
    achado urgente sobre o índice `metadados_pt.pkl` de produção e o
    achado maior de 9/13 idiomas sem tradução real. Aguarda autorização
    para promover.

## O que fica de fora, de propósito

- `protocolo.txt` — o system prompt real da IA em produção. Mudar isso
  muda o comportamento do produto para usuários reais agora; fica fora do
  escopo de uma reorganização de documentação (ver
  [03-PRINCIPIOS-E-DIRETRIZES.md](03-PRINCIPIOS-E-DIRETRIZES.md) §7).
- `.cursor/rules/*.mdc` — continuam sendo a fonte operacional que um hook
  de editor de fato aplica; esta documentação sintetiza os princípios que
  elas expressam, mas não as substitui.
- Documentos operacionais do pipeline de corpus (`GOSHINSHO.md`,
  `PROTOCOLO_*.md`, filas `*_QUEUE.json`, `PENDENCIAS_REVISAO.json`) —
  continuam sendo lidos e escritos ao vivo pelos processos autônomos em
  execução; não foram tocados.
- `GOSHINSHO.md` na raiz continua sendo o documento de handoff operacional
  entre sessões de trabalho no pipeline de corpus — esta pasta `docs/` não
  o substitui, é um nível acima (a história e os princípios por trás do
  que o `GOSHINSHO.md` registra dia a dia).
