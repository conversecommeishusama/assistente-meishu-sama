"""Serviço da AVALIAÇÃO DE TEXTOS — sistema de leitura INDEPENDENTE.

Separado de `leitura_service` de propósito (2026-09-10):

  - `leitura_service` serve a Leitura Colaborativa PÚBLICA e lê de
    `textos_leitura_colaborativa/` (base editável, promovida em bloco).
  - `avaliacao_service` serve a rota `/avaliacao`, restrita ao login de
    administrador, e lê de `textos_avaliacao/` — uma pasta de TRABALHO, onde os
    textos são revisados sem tocar no que o usuário final vê.

Nada aqui é compartilhado com a produção: pasta própria, cache de áudio próprio
e nenhuma escrita no corpus. Promover o resultado revisado para o corpus é um
passo POSTERIOR e explícito (fora do escopo deste módulo).

Configuração (variáveis de ambiente, com padrões seguros):
  GOSHINSHO_TEXTOS_AVALIACAO     pasta com os .txt a revisar
  GOSHINSHO_TTS_CACHE_AVALIACAO  pasta de cache dos MP3 gerados na avaliação
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

_logger = logging.getLogger(__name__)

TEXTOS_DIR = Path(
    os.environ.get("GOSHINSHO_TEXTOS_AVALIACAO", "/var/www/goshinsho/textos_avaliacao")
)

# Cache PRÓPRIO: o acervo de áudios da Leitura Colaborativa (16 GB, voz clonada
# aprovada) não deve ser poluído nem ter risco de colisão com o material em
# revisão.
CACHE_DIR = os.environ.get(
    "GOSHINSHO_TTS_CACHE_AVALIACAO",
    "/var/www/goshinsho/data/tts_cache_avaliacao",
)

# Limite de caracteres por trecho de áudio (o mesmo do front da Leitura e o
# teto aceito pela rota de TTS: 4000).
LIMITE_TRECHO = 700

_RE_SEPARADOR = re.compile(r"^[\s\-–—_=─━·*•]+$")
_RE_TEM_CONTEUDO = re.compile(r"[0-9A-Za-zÀ-ÿ]")
_RE_FONTE = re.compile(r"^\*{0,2}\s*Fonte\b", re.IGNORECASE)
_RE_FIM_FRASE = re.compile(r"(?<=[.!?…])\s+")
_RE_ESPACOS = re.compile(r"\s+")
_RE_NEGRITO = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_RE_ITALICO = re.compile(r"\*(.+?)\*", re.DOTALL)


def _texto_para_html(texto: str) -> str:
    """Escapa o bloco e converte a marcação leve (`**negrito**`, `*itálico*`).

    Mesma regra do leitor público (`_conteudo_leitura_html`): escapa TUDO
    primeiro e só depois aplica a marcação — assim nenhum texto do arquivo pode
    injetar HTML na página. A ordem importa: negrito antes do itálico, senão
    `**x**` vira `<em>*x*</em>`.
    """
    from markupsafe import escape

    html = str(escape(texto))
    html = _RE_NEGRITO.sub(r"<strong>\1</strong>", html)
    html = _RE_ITALICO.sub(r"<em>\1</em>", html)
    return html


def _arquivos() -> list[Path]:
    """Lista os .txt da pasta de avaliação (ignora .bak e ocultos)."""
    if not TEXTOS_DIR.is_dir():
        _logger.warning("avaliacao_service: pasta %s não encontrada", TEXTOS_DIR)
        return []
    arquivos = [
        p
        for p in sorted(TEXTOS_DIR.iterdir())
        if p.suffix.lower() == ".txt" and not p.name.startswith(".") and ".bak" not in p.name
    ]
    return arquivos


def listar_obras() -> list[dict]:
    """Lista os textos disponíveis para avaliação.

    Retorna [{arquivo, titulo, palavras}] — `titulo` é derivado do primeiro
    bloco de título do próprio texto (senão, do nome do arquivo).
    """
    obras: list[dict] = []
    for p in _arquivos():
        titulo = _titulo_do_arquivo(p)
        try:
            palavras = len(re.findall(r"[A-Za-zÀ-ÿ0-9]+", p.read_text(encoding="utf-8")))
        except OSError:
            palavras = 0
        obras.append({"arquivo": p.name, "titulo": titulo, "palavras": palavras})
    return obras


def _titulo_do_arquivo(p: Path) -> str:
    """Primeiro bloco de texto do arquivo (a linha de título) ou o nome dele."""
    try:
        with open(p, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha:
                    return linha
    except OSError:
        pass
    return p.stem


def obter_texto(nome_arquivo: str) -> str | None:
    """Lê o conteúdo de um texto da pasta de avaliação (str) ou None.

    Rejeita qualquer nome com path traversal — a rota recebe o nome pela URL.
    """
    if not nome_arquivo or ".." in nome_arquivo or "/" in nome_arquivo or "\\" in nome_arquivo:
        return None
    caminho = TEXTOS_DIR / nome_arquivo
    try:
        if not caminho.is_file() or caminho.suffix.lower() != ".txt":
            return None
        return caminho.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        _logger.warning("avaliacao_service: erro ao ler %s (%s)", nome_arquivo, exc)
        return None


def _quebrar_trechos(texto: str) -> list[str]:
    """Quebra um bloco em trechos de áudio (≤ LIMITE_TRECHO chars).

    Mesma regra do leitor público (quebrarEmFrases): junta frases inteiras até
    passar do limite. Trechos maiores que o teto da rota de TTS são divididos
    por espaço — assim nenhuma chamada é recusada por tamanho.
    """
    texto = _RE_ESPACOS.sub(" ", texto or "").strip()
    if not texto:
        return []
    if len(texto) <= LIMITE_TRECHO:
        return [texto]

    trechos: list[str] = []
    atual = ""
    for frase in _RE_FIM_FRASE.split(texto):
        if not frase:
            continue
        if len(atual) + len(frase) + 1 <= LIMITE_TRECHO and atual:
            atual = f"{atual} {frase}"
        elif len(frase) > LIMITE_TRECHO:
            if atual:
                trechos.append(atual.strip())
                atual = ""
            pedaco = ""
            for palavra in frase.split(" "):
                if len(pedaco) + len(palavra) + 1 <= LIMITE_TRECHO:
                    pedaco = f"{pedaco} {palavra}".strip()
                else:
                    if pedaco:
                        trechos.append(pedaco)
                    pedaco = palavra
            atual = pedaco
        else:
            if atual:
                trechos.append(atual.strip())
            atual = frase
    if atual.strip():
        trechos.append(atual.strip())
    return trechos


def _tipo_bloco(texto: str, primeiro: bool) -> str:
    """Classifica o bloco para a interface: titulo | fonte | texto."""
    if primeiro:
        return "titulo"
    if _RE_FONTE.match(texto):
        return "fonte"
    return "texto"


def estrutura_do_texto(nome_arquivo: str) -> dict | None:
    """Monta a estrutura de leitura de um texto.

    {
      "arquivo": "...", "titulo": "...",
      "blocos": [
        {"indice": 0, "tipo": "titulo|fonte|texto",
         "texto": "original (com a marcação **negrito** preservada)",
         "texto_audio": "versão corrida para o TTS",
         "trechos": ["...", "..."]},          # [] quando não é narrável
        ...
      ],
      "total_trechos": N
    }
    """
    bruto = obter_texto(nome_arquivo)
    if bruto is None:
        return None

    blocos: list[dict] = []
    total_trechos = 0
    primeiro = True
    for pedaco in re.split(r"\n\s*\n", bruto):
        texto = pedaco.strip()
        if not texto:
            continue
        # Separadores decorativos (`──────────`) não são conteúdo.
        if _RE_SEPARADOR.match(texto):
            continue
        # Bloco sem nenhuma letra/dígito (ex.: "| | |") não é narrável.
        if not _RE_TEM_CONTEUDO.search(texto):
            continue

        tipo = _tipo_bloco(texto, primeiro)
        primeiro = False

        # Versão para o TTS: sem a marcação `**` (o áudio não deve ler
        # asteriscos) e com os espaços normalizados.
        texto_audio = _RE_ESPACOS.sub(" ", texto.replace("**", "")).strip()

        # Títulos e a linha de fonte são lidos como narração curta; blocos de
        # texto viram fila de trechos.
        trechos = _quebrar_trechos(texto_audio)
        total_trechos += len(trechos)

        blocos.append(
            {
                "indice": len(blocos),
                "tipo": tipo,
                "texto": texto,
                "html": _texto_para_html(texto),
                "texto_audio": texto_audio,
                "trechos": trechos,
            }
        )

    if not blocos:
        return None

    return {
        "arquivo": nome_arquivo,
        "titulo": blocos[0]["texto"] if blocos[0]["tipo"] == "titulo" else Path(nome_arquivo).stem,
        "blocos": blocos,
        "total_trechos": total_trechos,
    }
