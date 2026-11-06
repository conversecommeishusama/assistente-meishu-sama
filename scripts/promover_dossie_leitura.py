#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Promove o dossiê da difusão para a Leitura Colaborativa (texto plano).

Contexto: o volume único do dossiê vive como Markdown (`docs/DOSSIE_DIFUSAO_20261020.md`,
39 capítulos), porque é montado por `montar_volume_unico.py` e exportado para PDF/DOCX.
A Leitura Colaborativa **não lê Markdown**: `goshinsho/services/leitura_service.py`
serve `.txt` de `textos_leitura_colaborativa/` e `leitura_routes._conteudo_leitura_html`
só entende `**negrito**` e `*itálico*`. Este script faz a ponte — sem tocar no `.md`,
que continua a ser a fonte da verdade.

O que a conversão faz (e por quê):

  · **desfaz a quebra de linha dura** de cada parágrafo. O `.md` está quebrado a ~80
    colunas; na Leitura cada linha seria um trecho de áudio separado. Junta-se com
    espaço — e **sem** espaço quando a fronteira é japonesa (kanji/kana/pontuação CJK),
    porque a escrita japonesa não tem espaços entre palavras;
  · **tabelas** (2 a 6 colunas) viram linhas legíveis: cabeçalho em negrito com ` · `
    e cada linha com ` — `. Ler `| Data | Fato |---|` em voz alta é ruído;
  · **organograma** (bloco ```mermaid) vira uma lista "Nível N — órgão", derivada das
    arestas do grafo — nada é interpretado à mão;
  · **imagens** viram `[Imagem: legenda]`: a página da Leitura não mostra imagens, mas
    as legendas carregam a proveniência (número, página, tipo de documento);
  · **`&nbsp;`** (usado como recuo no Estatuto) vira espaço; **`>`**, `#`, `|`, cercas
    de código, `<br/>`/`<i>` e `---` de separação de capítulo desaparecem;
  · mantêm-se `**negrito**`, `*itálico*`, `「」『』` e as remissões `§`/«capítulo N»,
    que são conteúdo do volume.

Uso:  .venv/bin/python scripts/promover_dossie_leitura.py [--aplicar]
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MD = RAIZ / "docs/DOSSIE_DIFUSAO_20261020.md"
DESTINO = RAIZ / "textos_leitura_colaborativa"
NOME_SAIDA = "20261020 - A difusão na época de Meishu-Sama.txt"

# Caracteres japoneses (e pontuação CJK): usados só para decidir se a junção de
# duas linhas leva espaço ou não.
_CJK = re.compile(r"[\u3000-\u30ff\u4e00-\u9fff\uff00-\uffef]")
_CJK_FIM = re.compile(r"[\u3000-\u303f\u3040-\u30ff\u4e00-\u9fff\uff00-\uffef]$")
_CJK_INICIO = re.compile(r"^[\u3000-\u303f\u3040-\u30ff\u4e00-\u9fff\uff00-\uffef]")

# Marcador de item de lista (`- x`, `* x`, `1. x`). O asterisco solto como
# marcador não aparece no volume, mas fica tratado.
_MARCA_ITEM = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(.*)$")


# ---------------------------------------------------------------------------
# Junção de linhas (desfazer a quebra dura do Markdown)
# ---------------------------------------------------------------------------

def juntar(a: str, b: str) -> str:
    """Junta duas linhas do mesmo parágrafo, com espaço — salvo fronteira japonesa."""
    a, b = a.rstrip(), b.lstrip()
    if not a:
        return b
    if not b:
        return a
    if _CJK_FIM.search(a) or _CJK_INICIO.search(b):
        return a + b
    return a + " " + b


def _asteriscos_equilibrados(texto: str) -> bool:
    """O parágrafo em curso tem os marcadores `*`/`**` fechados?

    Serve de guarda: se um itálico ou negrito ficou aberto no fim da linha, a
    linha seguinte é continuação DELE — nunca um novo parágrafo, senão o
    marcador de fecho cai noutro bloco e a página mostra asteriscos soltos.
    """
    sem_negrito = texto.replace("**", "")
    return sem_negrito.count("*") % 2 == 0


# Marcadores que o próprio volume deixou abertos (defeito do `.md`, não da
# conversão). Ficam registados para o relatório — o texto sai sempre limpo,
# porque na página da Leitura um `**` solto aparece literalmente e o áudio o
# pode ler.
_AJUSTES: list[str] = []


def equilibrar_marcadores(texto: str) -> str:
    """Remove o marcador sem par de um parágrafo (o último, que é o que sobra
    no emparelhamento não-guloso do renderizador)."""
    for marca in ("**", "*"):
        corpo = texto if marca == "**" else texto.replace("**", "\x00")
        while corpo.count(marca) % 2:
            corte = corpo.rfind(marca)
            corpo = corpo[:corte] + corpo[corte + len(marca):]
            _AJUSTES.append(texto[max(0, corte - 60):corte + 60].strip())
        texto = corpo if marca == "**" else corpo.replace("\x00", "**")
    return texto


# ---------------------------------------------------------------------------
# Blocos do Markdown
# ---------------------------------------------------------------------------

def blocos(linhas: list[str]) -> list[list[str]]:
    """Agrupa as linhas em blocos separados por linha em branco."""
    saida, atual = [], []
    for linha in linhas:
        if linha.strip():
            atual.append(linha)
        elif atual:
            saida.append(atual)
            atual = []
    if atual:
        saida.append(atual)
    return saida


def _limpar_inline(texto: str) -> str:
    """Resíduos de HTML e entidades que a página escaparia (e o áudio leria)."""
    texto = texto.replace("&nbsp;", " ")
    texto = re.sub(r"<br\s*/?>", " — ", texto)
    texto = re.sub(r"</?i>", "*", texto)
    texto = re.sub(r"</?[a-zA-Z][^>]*>", " ", texto)
    texto = re.sub(r"&amp;", "&", texto)
    # Espaço antes de pontuação japonesa (artefacto de junções anteriores no
    # volume) e depois de abrir colchete japonês: na escrita japonesa não há
    # espaço nenhum aí, e o áudio faz uma pausa onde não existe pausa.
    texto = re.sub(r"[ \t]+([、。，．：；！？）」』】〕])", r"\1", texto)
    texto = re.sub(r"([（「『【〔])[ \t]+", r"\1", texto)
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    return texto.strip()


def _paragrafos(linhas: list[str]) -> list[str]:
    """Converte as linhas de um bloco em parágrafos (sem quebra dura).

    Começa parágrafo novo quando a linha é: citação (`>`), recuo de `&nbsp;`,
    enumeração `(1)`, `(2)`…, linha de fonte (`— …`) ou abertura em negrito
    curta (`**Art. 4.º** …`). Fora isso, a linha continua a anterior.
    """
    saida: list[str] = []
    atual = ""
    for bruta in linhas:
        linha = _limpar_inline(bruta)
        if not linha:
            continue
        if linha.startswith(">"):
            linha = linha.lstrip(">").strip()
            if not linha:
                continue
        novo = False
        if atual and _asteriscos_equilibrados(atual):
            novo = bool(
                linha.startswith("—")
                or linha.startswith("&nbsp;")
                or re.match(r"^\(\d+\)", linha)
                or re.match(r"^\*\*[^*]{1,60}\*\*(\s|$)", linha)
                or _MARCA_ITEM.match(linha)
            )
        if novo:
            saida.append(equilibrar_marcadores(atual))
            atual = linha
        else:
            atual = juntar(atual, linha) if atual else linha
    if atual:
        saida.append(equilibrar_marcadores(atual))
    return saida


def _celulas(linha: str) -> list[str]:
    return [c.strip() for c in linha.strip().strip("|").split("|")]


def _e_separador(linha: str) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c) for c in _celulas(linha) if c) and "-" in linha


def converter_tabela(linhas: list[str]) -> list[str]:
    """Tabela Markdown → cabeçalho em negrito + uma linha por registro."""
    registros = [_celulas(l) for l in linhas]
    cabecalho = registros[0]
    corpo = [r for r in registros[1:] if not _e_separador("|" + "|".join(r) + "|")]
    saida = ["**" + " · ".join(c for c in cabecalho if c) + "**"]
    for linha in corpo:
        partes = [c for c in linha if c and c != "—"]
        if partes:
            saida.append(equilibrar_marcadores(" — ".join(partes)))
    return saida


def _ler_no(linha: str, pos: int):
    """Lê `X["…"]` a partir de `pos`. Devolve (id, texto, fim) ou None."""
    m = re.compile(r'([A-Z])\["').match(linha, pos)
    if not m:
        return None
    ini, idx = m.end(), m.end()
    while True:
        fim = linha.find('"]', idx)
        if fim == -1:
            return None
        resto = linha[fim + 2:].lstrip()
        if resto == "" or resto.startswith("-->") or resto.startswith("-.->"):
            return m.group(1), linha[ini:fim], fim + 2
        idx = fim + 1


def converter_mermaid(linhas: list[str]) -> list[str]:
    """Organograma (grafo `graph TD`) → lista "Nível N — órgão".

    A hierarquia vem das arestas, não de suposição: a raiz é o nó sem aresta de
    entrada e cada nó herda o nível do pai. O rótulo de uma aresta pontilhada
    (`-.->|orienta a fé e a doutrina|`) é acrescentado à linha do pai.
    """
    legenda = ""
    nos: dict[str, str] = {}
    filhos: dict[str, list[str]] = {}
    entradas: dict[str, int] = {}
    rotulos: dict[tuple[str, str], str] = {}

    for bruta in linhas:
        linha = bruta.strip()
        if linha.startswith("%% caption:"):
            legenda = linha.split(":", 1)[1].strip()
            continue
        if not linha or linha.startswith("graph") or linha.startswith("%%"):
            continue

        pos, origem, texto_origem = 0, None, None
        lido = _ler_no(linha, pos)
        if lido:
            origem, texto_origem, pos = lido
            nos[origem] = texto_origem
        else:
            m = re.match(r"([A-Z])\b", linha)
            if not m:
                continue
            origem, pos = m.group(1), m.end()

        m = re.compile(r"\s*(-\.->|-->)\s*").match(linha, pos)
        if not m:
            continue
        pontilhado, pos = m.group(1) == "-.->", m.end()

        rotulo = ""
        if pontilhado:
            m = re.compile(r"\|(.*?)\|").match(linha, pos)
            if m:
                rotulo, pos = m.group(1).strip(), m.end()

        alvo = None
        lido = _ler_no(linha, pos)
        if lido:
            alvo, texto_alvo, _ = lido
            nos.setdefault(alvo, texto_alvo)
        else:
            m = re.match(r"\s*([A-Z])\b", linha[pos:])
            if not m:
                continue
            alvo = m.group(1)

        filhos.setdefault(origem, []).append(alvo)
        entradas[alvo] = entradas.get(alvo, 0) + 1
        if rotulo:
            rotulos[(origem, alvo)] = rotulo

    raiz = next((n for n in nos if not entradas.get(n)), None)
    if raiz is None:
        return ["[Organograma: grafo não interpretável.]"]

    limpos = {no: _limpar_inline(txt) for no, txt in nos.items()}
    saida = [f"**{legenda}**" if legenda else "**Organograma**"]
    visitados: set[str] = set()

    def visitar(no: str, nivel: int) -> None:
        if no in visitados:
            return
        visitados.add(no)
        saida.append(f"Nível {nivel} — {limpos.get(no, no)}")
        for filho in filhos.get(no, []):
            if filho not in visitados:
                visitar(filho, nivel + 1)

    visitar(raiz, 1)

    # Rótulos das arestas pontilhadas: acrescentam-se à linha do pai, que é
    # quem pratica a relação (o Fundador é que «orienta a fé e a doutrina»).
    for (origem, alvo), rotulo in rotulos.items():
        pai = limpos.get(origem, origem)
        for i, l in enumerate(saida):
            if pai and pai in l:
                saida[i] = l.rstrip(".") + f" — {rotulo}."
                break
    return saida


# ---------------------------------------------------------------------------
# Conversão principal
# ---------------------------------------------------------------------------

def converter(markdown: str) -> tuple[str, dict]:
    """Markdown do dossiê → texto plano da Leitura Colaborativa."""
    linhas = markdown.split("\n")
    _AJUSTES.clear()
    stats = {"capitulos": 0, "secoes": 0, "tabelas": 0, "imagens": 0,
             "citacoes": 0, "organogramas": 0}

    titulo = ""
    subtitulo = ""
    indice: list[str] = []
    corpo: list[str] = []

    for bloco in blocos(linhas):
        primeiro = bloco[0].strip()

        # `---` de separação de capítulo: o cabeçalho já separa.
        if len(bloco) == 1 and re.fullmatch(r"-{3,}", primeiro):
            continue

        # Cerca de código: só há uma, o organograma.
        if primeiro.startswith("```"):
            if "mermaid" in primeiro:
                corpo.extend(converter_mermaid(bloco[1:-1]))
                stats["organogramas"] += 1
            else:
                corpo.extend(_limpar_inline(l) for l in bloco[1:-1] if l.strip())
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", primeiro)
        if m:
            nivel, texto = len(m.group(1)), m.group(2).strip()
            if nivel == 1:
                titulo = texto
            elif nivel == 2:
                stats["capitulos"] += 1
                # O índice lista os capítulos numerados. Os `##` sem número são
                # partes internas de um anexo («Propósito», «Estatuto»,
                # «Organização») e ficariam órfãos na lista, sem o anexo a que
                # pertencem.
                if re.match(r"^\d+\.\s", texto):
                    indice.append(texto)
                corpo.append(texto)
            else:
                stats["secoes"] += 1
                corpo.append(texto)
            continue

        if primeiro.startswith("|"):
            corpo.extend(converter_tabela(bloco))
            stats["tabelas"] += 1
            continue

        if primeiro.startswith("!["):
            m = re.match(r"^!\[(.*)\]\(([^)]*)\)$", primeiro)
            if m:
                legenda = _limpar_inline(m.group(1))
                legenda = legenda.replace("[", "(").replace("]", ")")
                corpo.append(f"[Imagem: {legenda}]")
                stats["imagens"] += 1
            continue

        if primeiro.startswith(">"):
            stats["citacoes"] += 1

        # Subtítulo do volume (`*Volume único*`), logo abaixo do `#`.
        if len(bloco) == 1 and re.fullmatch(r"\*[^*]+\*", primeiro) and not corpo:
            subtitulo = primeiro.strip("*").strip()
            continue

        corpo.extend(_paragrafos(bloco))

    cabeca = [titulo]
    if subtitulo:
        cabeca.append(subtitulo)
    cabeca += ["", "――― Estudo documental sobre a difusão ―――", "", "Índice", ""]
    cabeca += indice
    texto = "\n\n".join(cabeca + [""] + corpo) + "\n"

    texto = re.sub(r"[ \t]+\n", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    stats["ajustes"] = len(_AJUSTES)
    return texto, stats


def verificar(texto: str) -> list[str]:
    """Resíduos que não podem chegar à Leitura (apareceriam na tela e no áudio)."""
    problemas = []
    for marca, padrao in [
        ("linha de tabela", r"(?m)^\s*\|"),
        ("citação Markdown", r"(?m)^\s*>\s"),
        ("cerca de código", r"```"),
        ("título Markdown", r"(?m)^#{1,6}\s"),
        ("entidade HTML", r"&[a-z]+;"),
        ("tag HTML", r"</?[a-zA-Z][^>]*>"),
        ("separador de capítulo", r"(?m)^-{3,}$"),
        ("imagem Markdown", r"!\[[^\]]*\]\("),
    ]:
        achados = re.findall(padrao, texto)
        if achados:
            problemas.append(f"{marca}: {len(achados)} ocorrência(s)")
    return problemas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true",
                    help="escreve em textos_leitura_colaborativa/")
    args = ap.parse_args()

    if not MD.is_file():
        print(f"ERRO: {MD} não existe", file=sys.stderr)
        return 1

    markdown = MD.read_text(encoding="utf-8")
    texto, stats = converter(markdown)
    paragrafos = [p for p in texto.split("\n\n") if p.strip()]
    problemas = verificar(texto)

    print("=" * 72)
    print("DOSSIÊ → LEITURA COLABORATIVA")
    print("=" * 72)
    print(f"origem : {MD.relative_to(RAIZ)} ({len(markdown):,} caracteres)")
    print(f"destino: {NOME_SAIDA}")
    print(f"         {texto.count(chr(10)):,} linhas · {len(texto):,} caracteres "
          f"· {len(paragrafos):,} parágrafos")
    print(f"         {stats['capitulos']} capítulos · {stats['secoes']} secções · "
          f"{stats['tabelas']} tabelas · {stats['citacoes']} blocos de citação · "
          f"{stats['imagens']} imagens · {stats['organogramas']} organograma")
    print("\nresíduos de Markdown:", "nenhum" if not problemas else problemas)
    if _AJUSTES:
        print(f"marcadores sem par corrigidos: {len(_AJUSTES)}")
        for ajuste in _AJUSTES:
            print(f"   … {ajuste}")

    print("\n--- primeira página do ficheiro " + "-" * 40)
    print("\n".join(texto.split("\n")[:16]))

    if not args.aplicar:
        print("\n(dry-run — use --aplicar para escrever)")
        return 0 if not problemas else 2

    DESTINO.mkdir(parents=True, exist_ok=True)
    destino = DESTINO / NOME_SAIDA
    if destino.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        copia = destino.with_name(destino.name + f".bak_promocao_{stamp}")
        shutil.copy2(destino, copia)
        print(f"\nbackup: {copia.name}")
    destino.write_text(texto, encoding="utf-8")
    print(f"\nescrito: {destino}")
    return 0 if not problemas else 2


if __name__ == "__main__":
    raise SystemExit(main())
