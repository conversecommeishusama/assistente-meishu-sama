#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Autoria dos trechos da Leitura: de quem é o texto que vai ser narrado.

Por que existe (2026-10-23):
    A voz clonada de Meishu-Sama é um bem escasso e, mais importante, uma
    AFIRMAÇÃO sobre o texto. Narrar com ela um comunicado da instituição ou o
    testemunho de um fiel atribui-lhe palavras que não são dele.

    A política de voz já vivia em três sítios (`sintetizar`,
    `caminho_em_cache` e os geradores) e divergiu uma vez — ver
    `tts_service.provedor_canonico`. Esta camada é o degrau ANTERIOR: decidir
    de QUEM é o trecho, antes de decidir com que voz se lê.

Regra (decisão do usuário, 23/10/2026 — "voz dele só nos trechos Dele"):
    · Obra inteiramente dele → voz dele.
    · Obra de terceiros (material institucional) → narrador.
    · Obra mista (periódicos, colectâneas) → artigo a artigo, pela
      classificação de `scripts/classificar_autoria_periodicos.py`.
    · Trecho que não se consegue localizar num artigo → o prior da obra.

O que se apurou e que justifica a simplicidade (23/10/2026):
    Os ficheiros PT dos periódicos foram montados a partir dos artigos
    atribuídos a ele. Verificado contra `work/autoria.json`: dos 2.506
    testemunhos (おかげばなし) e 514 contribuições (寄稿) do acervo, ZERO e 10
    respectivamente aparecem nas specs. Ou seja: Tijotengoku, Kyusei, Eiko e
    Hikari já são "só dele". O que de facto não é dele são os Relatos de
    Milagres (127 de 141 artigos são testemunhos assinados) e o material
    institucional.

Uso:
    from goshinsho.services import autoria_service
    autoria_service.autor_da_obra("Eiko.txt")        -> "meishu"
    autoria_service.autor_do_trecho("Eiko.txt", txt) -> "meishu"
"""
from __future__ import annotations

import functools
import json
import os
import re
import threading
from pathlib import Path

RAIZ = Path(os.environ.get("GOSHINSHO_RAIZ") or "/var/www/goshinsho")
CLASSIFICACAO = RAIZ / "reports/autoria_periodicos/AUTORIA_ARTIGOS.json"

MEISHU = "meishu"
OUTRO = "outro"

# Obras mistas — a mesma chave de `classificar_autoria_periodicos.MISTAS`.
# O prior só é usado se um trecho não for localizável num artigo.
PRIOR_DAS_MISTAS = {
    "Tijotengoku.txt": MEISHU,
    "Kyusei.txt": MEISHU,
    "19530910 - Relatos de Milagres da Igreja Messiânica Mundial.txt": OUTRO,
}

# Material de terceiros: não é texto dele, em nenhum trecho.
#
# ⚠️ A lista é curta de propósito. Em 23/10/2026 verificou-se uma a uma as obras
# que a política antiga (`sincronizar_audios.NAO_MEISHU`) tratava como
# "institucionais" e concluiu-se que quase todas são escritas por ele, em
# primeira pessoa:
#
#   · Manual da Igreja ......... "Este pequeno livreto foi compilado por mim"
#   · Doutrina da Igreja ....... "Prefácio — Okada Jikan" (assinado)
#   · HAKONE ART MUSEUM ........ "Sou Mokichi Okada, fundador da Igreja"
#   · A Story of Ukiyo-e ....... "Sou um amante da pintura desde a infância…
#                                 construí um pequeno museu"
#   · Guia Rápido, Jornais, Revista Asahi, Ensinamentos diversos,
#     Esboço da Medicina ...... doutrina e palestras dele
#
# Excluí-las tirava-lhe as próprias palavras — foi o erro que esta lista veio
# corrigir. Só entra aqui obra cujo REGISTO não é dele.
OBRAS_DE_OUTROS: set[str] = {
    # Decisão do usuário (23/10/2026): "no ítem 2 pode manter tudo na voz
    # normal". As palavras são dele (curso ditado em 1935), mas o registo é de
    # um discípulo — o ficheiro abre com "Transcrição do curso feita por um
    # discípulo". Narrar a transcrição na voz dele faria passar por fala
    # directa o que é apontamento de terceiro.
    "19350000 - Curso Kannon (1~7).txt",
}

# Sobreposições explícitas por artigo: {ficheiro: {índice do artigo: autor}}.
#
# Existe para obras cuja estrutura se conhece e cuja classificação automática
# não alcança (os índices de autoria vêm dos periódicos, não dos livros). É
# deliberadamente explícita — um mapa de excepções lê-se e audita-se; uma
# heurística sobre títulos inventaria autoria, que é exactamente o que não se
# quer.
SOBREPOSICOES: dict[str, dict[int, str]] = {
    # Manuscrito de um fiel (Kinji Miyamoto) publicado por ele. A spec tem 6
    # artigos; só o Prefácio (JP `自 観`) é dele — assinado.
    "19510615 - Confissão de um Fiel.txt": {
        0: "outro",   # 序文 — "Confissão de um Crente"
        1: "meishu",  # 自 観 — "Prefácio"
        2: "outro",   # poema do fiel
        3: "outro",   # narrativa do fiel ("Eu: …")
        4: "outro",   # "Povo do Japão"
        5: "outro",   # Ficha Técnica (奥付)
    },

    # 自観叢書 第4篇『奇蹟物語』 — decisão do usuário (23/10/2026): "o formato é
    # de relato do milagre com comentários de Meishu-Sama. O relato pode ser
    # deixado na voz normal e o comentário de Meishu-Sama na voz dele."
    #
    # Estrutura verificada (spec de 35 artigos):
    #   0–7   ensaios dele, em 1.ª pessoa — 序文, 観世音菩薩と私, 私の告白,
    #         本教救いの特異性, 入信後の神懸り, 霊写真, 黄泉比良坂の戦.
    #         («Como todos desejam saber do innen entre Kanzeon-Bosatsu e mim…»,
    #          «escreverei aqui as circunstâncias em que o vivenciei»)
    #   8–34  relatos assinados por fiéis — nome, idade, igreja e endereço.
    #
    # Ressalva registada: neste volume NÃO há comentário intercalado nos
    # relatos. Verificado no original japonês, que não tem nenhum marcador
    # (御教え/御垂示/（お伺）/明主/自観) a meio dos relatos — a única ocorrência
    # de `御教え` é o título do art. 34. Se aparecer comentário dele, o ponto
    # certo para o marcar é aqui (passa a ser preciso dividir DENTRO do artigo,
    # o que a estrutura actual de spans não faz — ver §6-G do handoff).
    "19491005 - Coleção Jikan Volume 4 Histórias de Milagres.txt": {
        **{i: "meishu" for i in range(0, 8)},   # ensaios e prefácio dele
        **{i: "outro" for i in range(8, 35)},   # relatos assinados por fiéis
    },
}

_lock = threading.Lock()
_cache_obras: dict[str, dict] = {}


def _normalizar(texto: str) -> str:
    """Colapsa espaços para permitir localizar trechos com quebras diferentes."""
    return re.sub(r"\s+", " ", texto or "").strip()


def _carregar_classificacao() -> dict:
    if not CLASSIFICACAO.exists():
        return {}
    try:
        return json.load(open(CLASSIFICACAO, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _por_obra() -> dict[str, list[dict]]:
    """{arquivo: [{titulo_jp, titulo_pt, autor, evidencia, ...}]}"""
    dados = _carregar_classificacao()
    return {v["arquivo"]: v["artigos"] for v in dados.values() if v.get("arquivo")}


def autor_da_obra(arquivo: str) -> str | None:
    """Autoria quando a obra é de um só autor; None quando é mista."""
    if arquivo in PRIOR_DAS_MISTAS or arquivo in SOBREPOSICOES:
        return None
    if arquivo in OBRAS_DE_OUTROS:
        return OUTRO
    return MEISHU


def _limites_dos_artigos(arquivo: str, texto: str) -> list[int] | None:
    """Posições (no texto normalizado) onde começa cada artigo.

    Usa as âncoras PT da spec oficial — a mesma segmentação do índice. Devolve
    None se alguma âncora não resolver: nesse caso é preferível cair no prior da
    obra a atribuir texto ao artigo errado.
    """
    spec_nome = _spec_da_obra(arquivo)
    if not spec_nome:
        return None

    caminho_spec = RAIZ / "reports/livros_trabalho/segmentacao_manual" / spec_nome
    try:
        artigos = json.load(open(caminho_spec, encoding="utf-8"))["articles"]
    except (OSError, ValueError, KeyError):
        return None

    normalizado = _normalizar(texto)
    posicoes: list[int] = []
    cursor = 0
    for artigo in artigos:
        ancora = (artigo.get("pt_anchor") or "").strip()
        primeira = _normalizar(ancora.split("\n")[0]) if ancora else ""
        if not primeira:
            return None
        pos = normalizado.find(primeira, cursor)
        if pos < 0:
            # Âncora fora de ordem ou ausente: não se adivinha.
            return None
        posicoes.append(pos)
        cursor = pos + 1
    return posicoes


def _spec_da_obra(arquivo: str) -> str | None:
    """Nome do ficheiro de spec (segmentação oficial) para uma obra."""
    dados = _carregar_classificacao()
    for v in dados.values():
        if v.get("arquivo") == arquivo:
            return v.get("spec")
    return _spec_de_sobreposicao(arquivo)


def _spec_de_sobreposicao(arquivo: str) -> str | None:
    """Spec da obra pelo nome, para as sobreposições explícitas."""
    base = arquivo[:-4] if arquivo.endswith(".txt") else arquivo
    candidato = RAIZ / "reports/livros_trabalho/segmentacao_manual" / f"{base}.txt.json"
    return candidato.name if candidato.exists() else None


def _estrutura(arquivo: str, texto: str) -> dict:
    """Cache por obra: spans de artigo, autoria de cada um e texto normalizado."""
    with _lock:
        if arquivo in _cache_obras:
            return _cache_obras[arquivo]

        normalizado = _normalizar(texto)
        artigos = _por_obra().get(arquivo) or []

        # Autoria por artigo: da classificação dos periódicos, ou da
        # sobreposição explícita. Sem nenhuma das duas, a obra é um só autor.
        autores: list[str] = [a["autor"] for a in artigos]
        sobreposicao = SOBREPOSICOES.get(arquivo)
        if sobreposicao:
            autores = [sobreposicao.get(i, MEISHU) for i in range(len(sobreposicao))]

        posicoes = _limites_dos_artigos(arquivo, texto) if autores else None

        spans: list[tuple[int, int, str]] = []
        if posicoes and len(posicoes) == len(autores):
            for i, inicio in enumerate(posicoes):
                fim = posicoes[i + 1] if i + 1 < len(posicoes) else len(normalizado)
                spans.append((inicio, fim, autores[i]))
        estrutura = {
            "normalizado": normalizado,
            "spans": spans,
            "prior": PRIOR_DAS_MISTAS.get(arquivo, MEISHU),
            "confiavel": bool(spans),
        }
        _cache_obras[arquivo] = estrutura
        return estrutura


def autor_do_trecho(arquivo: str, texto: str, *, texto_da_obra: str | None = None) -> str:
    """De quem é este trecho: "meishu" ou "outro".

    `texto_da_obra` evita reler o ficheiro quando o chamador já o tem (o lote
    percorre a obra inteira).
    """
    simples = autor_da_obra(arquivo)
    if simples is not None:
        return simples

    if texto_da_obra is None:
        try:
            from . import leitura_service
            texto_da_obra = leitura_service.obter_texto(arquivo) or ""
        except Exception:
            texto_da_obra = ""
    if not texto_da_obra:
        return PRIOR_DAS_MISTAS.get(arquivo, MEISHU)

    estrutura = _estrutura(arquivo, texto_da_obra)
    alvo = _normalizar(texto)
    if not alvo:
        return estrutura["prior"]

    pos = estrutura["normalizado"].find(alvo)
    if pos < 0:
        # O front pode enviar um trecho com pequenas diferenças; tentar por
        # prefixo reduz os falsos "não encontrado".
        pos = estrutura["normalizado"].find(alvo[:80]) if len(alvo) > 80 else -1
    if pos < 0:
        return estrutura["prior"]

    for inicio, fim, autor in estrutura["spans"]:
        if inicio <= pos < fim:
            return autor
    return estrutura["prior"]


def trechos_com_autor(arquivo: str, texto: str) -> list[tuple[str, str]]:
    """[(trecho, autor)] para uma obra inteira — usado pelo lote de geração."""
    simples = autor_da_obra(arquivo)
    if simples is not None:
        return [(t, simples) for t in _quebrar(texto)]

    estrutura = _estrutura(arquivo, texto)
    return [(t, autor_do_trecho(arquivo, t, texto_da_obra=texto)) for t in _quebrar(texto)]


def _quebrar(texto: str) -> list[str]:
    """Segmentação do front, importada do gerador (uma só definição)."""
    return _modulo_glf().quebrar_como_front(texto)


@functools.lru_cache(maxsize=1)
def _modulo_glf():
    """Importa `gerar_lote_fish` uma vez (tem a segmentação do front)."""
    import importlib.util

    caminho = RAIZ / "scripts/gerar_lote_fish.py"
    spec = importlib.util.spec_from_file_location("glf_autoria", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def limpar_cache() -> None:
    """Descarta a cache em memória (útil em testes e após reclassificar)."""
    with _lock:
        _cache_obras.clear()
