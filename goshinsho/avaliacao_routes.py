"""Blueprint da AVALIAÇÃO DE TEXTOS — sistema de leitura para revisão,
INDEPENDENTE do que é servido ao usuário final.

Contexto (2026-09-10)
---------------------
O trabalho de revisão de qualidade exige ler cada texto em voz alta e conferir
o áudio antes de aprovar. Fazer isso dentro da Leitura Colaborativa pública
seria arriscado: qualquer edição apareceria para os leitores. Este blueprint
oferece o MESMO tipo de leitura, mas:

  - **restrito ao login de administrador** (mesma regra do `/admin`);
  - lê de uma **pasta de trabalho própria** (`textos_avaliacao/`);
  - usa **cache de áudio próprio** (`data/tts_cache_avaliacao/`);
  - **não escreve nada** no corpus, no staging nem em qualquer pasta publicada.

Rotas (prefixo `/avaliacao`):
  GET  /avaliacao                     → índice dos textos em avaliação
  GET  /avaliacao/texto/<nome>        → página de leitura com áudio
  GET  /avaliacao/api/obras           → JSON com a lista de textos
  GET  /avaliacao/api/texto/<nome>    → JSON com a estrutura (blocos/trechos)
  POST /avaliacao/api/tts             → gera MP3 (edge-tts / vozes Microsoft)
  GET  /avaliacao/api/tts/vozes       → vozes disponíveis (só as da Microsoft)

Nota sobre a voz: aqui usamos apenas as vozes neurais da **Microsoft**
(edge-tts, gratuitas) — decisão do usuário em 10/09/2026. A voz clonada do
Meishu-Sama (Fish/XTTS) fica fora deste sistema de propósito: o cache dela é
acervo aprovado da Leitura Colaborativa e não deve ser misturado com material
em revisão.
"""
from __future__ import annotations

import logging

from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
    send_file,
)

from .services import avaliacao_service
from .services.dev_auth import require_developer_page, require_developer_json

_logger = logging.getLogger(__name__)

avaliacao_bp = Blueprint("avaliacao", __name__, url_prefix="/avaliacao")

# Vozes neurais da Microsoft (edge-tts). Só as PT-BR entram neste sistema.
VOZES_EDGE = [
    {"id": "antonio", "nome": "Antônio (masculino)"},
    {"id": "francisca", "nome": "Francisca (feminino)"},
    {"id": "thalita", "nome": "Thalita (feminino, multilíngue)"},
]
_VOZES_VALIDAS = {v["id"] for v in VOZES_EDGE}
_VOZ_PADRAO = "antonio"


class _cache_proprio:
    """Usa o cache de áudio da avaliação durante a chamada e restaura depois.

    O `tts_service` guarda o diretório de cache num global do módulo. Trocar
    aqui (e devolver no `finally`) mantém os MP3 da avaliação fora do acervo de
    16 GB da Leitura Colaborativa, sem alterar o comportamento da produção.
    """

    def __enter__(self):
        import os

        from .services import tts_service

        self._modulo = tts_service
        self._anterior = tts_service._CACHE_DIR
        # `tts_service._cache_dir()` só cria o diretório quando ele mesmo o
        # inicializa. Como aqui a troca é direta, criamos explicitamente —
        # sem isso, a síntese falha com "No such file or directory".
        os.makedirs(avaliacao_service.CACHE_DIR, exist_ok=True)
        tts_service._CACHE_DIR = avaliacao_service.CACHE_DIR
        return self

    def __exit__(self, *exc):
        self._modulo._CACHE_DIR = self._anterior
        return False


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

@avaliacao_bp.get("")
@avaliacao_bp.get("/")
def avaliacao_pagina():
    """Índice da avaliação: os textos da pasta de trabalho."""
    user, erro = require_developer_page()
    if erro:
        return erro

    obras = avaliacao_service.listar_obras()
    return render_template(
        "avaliacao.html",
        user=user,
        obras=obras,
        pasta=str(avaliacao_service.TEXTOS_DIR),
    )


@avaliacao_bp.get("/texto/<path:nome_arquivo>")
def avaliacao_texto_pagina(nome_arquivo):
    """Página de leitura de um texto da avaliação (com áudio)."""
    user, erro = require_developer_page()
    if erro:
        return erro

    estrutura = avaliacao_service.estrutura_do_texto(nome_arquivo)
    if estrutura is None:
        obras = avaliacao_service.listar_obras()
        return (
            render_template(
                "avaliacao.html",
                user=user,
                obras=obras,
                pasta=str(avaliacao_service.TEXTOS_DIR),
                flash_msg="Texto não encontrado.",
            ),
            404,
        )

    return render_template(
        "avaliacao_texto.html",
        user=user,
        arquivo=nome_arquivo,
        titulo=estrutura["titulo"],
        estrutura=estrutura,
        total_trechos=estrutura["total_trechos"],
        vozes=VOZES_EDGE,
        voz_padrao=_VOZ_PADRAO,
    )


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@avaliacao_bp.get("/api/obras")
def api_obras():
    user, erro = require_developer_json()
    if erro:
        return erro
    return jsonify({"obras": avaliacao_service.listar_obras(), "pasta": str(avaliacao_service.TEXTOS_DIR)})


@avaliacao_bp.get("/api/texto/<path:nome_arquivo>")
def api_texto(nome_arquivo):
    user, erro = require_developer_json()
    if erro:
        return erro
    estrutura = avaliacao_service.estrutura_do_texto(nome_arquivo)
    if estrutura is None:
        return jsonify({"error": "texto não encontrado"}), 404
    return jsonify(estrutura)


@avaliacao_bp.get("/api/tts/vozes")
def api_vozes():
    """Vozes disponíveis — apenas as neurais da Microsoft (edge-tts)."""
    return jsonify({"vozes": VOZES_EDGE, "padrao": _VOZ_PADRAO})


@avaliacao_bp.post("/api/tts")
def api_tts():
    """Gera o MP3 de um trecho com voz neural da Microsoft (edge-tts).

    Body: {"texto": "...", "voz": "antonio|francisca|thalita", "rate": "+0%"}
    Retorna: o MP3 (audio/mpeg), com cache em disco próprio da avaliação.
    """
    user, erro = require_developer_json()
    if erro:
        return erro

    dados = request.get_json(silent=True) or {}
    texto = (dados.get("texto") or "").strip()
    if not texto:
        return jsonify({"error": "texto vazio"}), 400
    # A rota de TTS do projeto tem teto de 4000 chars; o front já quebra antes.
    if len(texto) > 4000:
        return jsonify({"error": "texto muito longo (máx 4000 chars)"}), 400

    voz = (dados.get("voz") or _VOZ_PADRAO).strip().lower()
    if voz not in _VOZES_VALIDAS:
        voz = _VOZ_PADRAO
    rate = (dados.get("rate") or "+0%").strip() or "+0%"

    try:
        from .services import tts_service

        with _cache_proprio():
            if tts_service._sem_conteudo_narravel(texto):
                return jsonify({"error": "trecho sem conteúdo narrável"}), 400
            caminho = tts_service.sintetizar(texto, voz=voz, rate=rate)

        return send_file(
            caminho,
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="avaliacao_tts.mp3",
        )
    except Exception as exc:  # pragma: no cover - defensivo
        _logger.warning("TTS da avaliação falhou: %s", exc)
        return jsonify({"error": "falha ao gerar áudio"}), 500
