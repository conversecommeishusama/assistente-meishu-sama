"""Rotas da Leitura Colaborativa — Blueprint separado (produção v1.4.0).

Promovida do protótipo `/versao2` (2026-09-01, decisão do usuário): a Leitura
Colaborativa vai para a produção com todas as funcionalidades; o Fórum fica
para uma próxima versão.

Por isso este blueprint contém APENAS as rotas da Leitura (páginas, áudio
edge-tts, progresso e colaborações), com prefixo de URL `/forum` para manter
os mesmos caminhos usados pelo front-end (leitura.js / leitura_texto.js /
leitura_tts.js). O endpoint namespace é `leitura.*` (não `forum.*`) para não
colidir com o Fórum quando ele for promovido futuramente.

Funcionalidades:
- Página da Leitura com estrutura por categoria (Palavra Oral / Escrita).
- Página de leitura de um texto (com botão de áudio e destaque do trecho).
- Geração de áudio MP3 via edge-tts (`POST /forum/api/tts`).
- Colaborações: leitores selecionam trechos e enviam observações.
- Progresso de leitura sincronizado por usuário (login).
"""

import logging
import re as _re

from flask import Blueprint, jsonify, render_template, request
from markupsafe import escape

from .services.auth_service import current_user
from .routes import _is_developer_user, _require_confirmed_user_json

_logger = logging.getLogger(__name__)

leitura_bp = Blueprint("leitura", __name__, url_prefix="/forum")


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

@leitura_bp.get("/leitura")
def leitura_pagina():
    """Página da Leitura Colaborativa — proposta da comunidade para os
    colaboradores ajudarem a melhorar a tradução dos ensinamentos."""
    user = current_user()
    from .services import leitura_service
    estrutura = leitura_service.estrutura_por_categoria()
    obras = leitura_service.listar_obras()
    return render_template(
        "leitura.html", user=user, active_tab="leitura",
        obras=obras, estrutura=estrutura,
    )


@leitura_bp.get("/leitura/<path:nome_arquivo>")
def leitura_texto_pagina(nome_arquivo):
    """Página de leitura de um texto específico (com botão de áudio)."""
    user = current_user()
    from .services import leitura_service

    texto = leitura_service.obter_texto(nome_arquivo)
    if texto is None:
        estrutura = leitura_service.estrutura_por_categoria()
        return render_template(
            "leitura.html", user=user, active_tab="leitura", estrutura=estrutura,
            flash_msg="Texto não encontrado.",
        ), 404
    # Título limpo a partir do nome do arquivo
    data, titulo, numero = leitura_service._parse_nome(nome_arquivo)
    return render_template(
        "leitura_texto.html",
        user=user,
        active_tab="leitura",
        nome_arquivo=nome_arquivo,
        titulo=titulo or nome_arquivo,
        data=data.isoformat() if data else None,
        conteudo=_conteudo_leitura_html(texto),
    )


def _conteudo_leitura_html(texto):
    """Converte a marcação leve dos textos (negrito **x** e itálico *x*) em HTML,
    para não vazar asteriscos na página da Leitura Colaborativa.

    Ordem importa: negrito **antes** do itálico, senão **x** vira <em>*x*</em>.
    O restante do texto é escapado (colchetes [...] e demais caracteres passam
    intactos, já que não são Markdown).
    """
    if not texto:
        return ""
    html = escape(texto)  # escapa & < > " ' (o template usa |safe no final)
    html = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = _re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    return html


# ---------------------------------------------------------------------------
# API — áudio (edge-tts)
# ---------------------------------------------------------------------------

@leitura_bp.post("/api/tts")
def api_tts():
    """Gera áudio (MP3) do texto via edge-tts (vozes neurais gratuitas).

    Usado pela Leitura Colaborativa: o `<audio>` com este MP3 segue o perfil
    de mídia do bluetooth (carro) — diferente do speechSynthesis do navegador,
    que no Android não roteia para o bluetooth (fica mudo no carro).

    Body: {"texto": "...", "voz": "antonio|francisca|thalita", "rate": "+0%"}
    Retorna: o MP3 (audio/mpeg) com cache em disco.
    """
    try:
        from .services import tts_service

        dados = request.get_json(silent=True) or {}
        texto = (dados.get("texto") or "").strip()
        if not texto:
            return jsonify({"error": "texto vazio"}), 400
        if len(texto) > 4000:
            return jsonify({"error": "texto muito longo (máx 4000 chars)"}), 400
        caminho = tts_service.sintetizar(
            texto,
            voz=dados.get("voz") or "antonio",
            rate=dados.get("rate") or "+0%",
        )
        from flask import send_file

        return send_file(
            caminho,
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="goshinsho_tts.mp3",
        )
    except Exception as exc:  # pragma: no cover - defensivo
        _logger.warning("TTS falhou: %s", exc)
        return jsonify({"error": "falha ao gerar áudio"}), 500


@leitura_bp.get("/api/leitura/obras")
def api_leitura_obras():
    """API JSON com a estrutura por categoria da Leitura Colaborativa."""
    from .services import leitura_service
    return jsonify(leitura_service.estrutura_por_categoria())


# ---------------------------------------------------------------------------
# API — colaboração (observações dos leitores sobre os textos)
# ---------------------------------------------------------------------------

@leitura_bp.post("/api/leitura/colaboracoes")
def api_criar_colaboracao():
    """Salva uma observação de colaboração sobre um trecho de um texto.

    Exige login (usuário confirmado). Aceita:
      { arquivo, trecho?, observacao, autor_nome? }
    O autor_nome (apelido) é opcional — se não vier, não é exibido e-mail.
    """
    from .services import leitura_service

    # Garante a tabela (idempotente) na primeira escrita.
    leitura_service.garantir_tabelas_colaboracao()

    user, error = _require_confirmed_user_json()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    arquivo = (payload.get("arquivo") or "").strip()
    observacao = (payload.get("observacao") or "").strip()
    trecho = (payload.get("trecho") or "").strip()
    autor_nome = (payload.get("autor_nome") or "").strip()

    if not arquivo:
        return jsonify({"error": "Texto não identificado."}), 400
    if not observacao:
        return jsonify({"error": "Escreva sua observação/sugestão."}), 400
    if len(observacao) > 2000:
        return jsonify({"error": "Observação muito longa (máx. 2000 caracteres)."}), 400

    registro = leitura_service.criar_colaboracao(
        arquivo=arquivo,
        observacao=observacao,
        trecho=trecho,
        autor_id=user["id"],
        autor_nome=autor_nome or None,
    )
    if not registro:
        return jsonify({"error": "Não foi possível salvar sua observação agora. Tente novamente."}), 500

    return jsonify({"colaboracao": registro}), 201


@leitura_bp.get("/api/leitura/progresso/<path:arquivo>")
def api_ler_progresso(arquivo):
    """Lê o progresso de leitura de um arquivo (sincronizado por usuário).

    2026-08-27: o progresso era só localStorage (por dispositivo) — não
    retomava entre aparelhos. Agora fica no servidor, associado ao login.
    """
    from .services import leitura_progresso_service

    user = current_user()
    if not user or not user.get("id"):
        # Sem login: progresso local (localStorage) é o que vale.
        return jsonify({"progresso": None})

    progresso = leitura_progresso_service.carregar_progresso(user["id"], arquivo)
    return jsonify({"progresso": progresso})


@leitura_bp.put("/api/leitura/progresso/<path:arquivo>")
def api_salvar_progresso(arquivo):
    """Salva o progresso de leitura de um arquivo (sincronizado por usuário)."""
    from .services import leitura_progresso_service

    user = current_user()
    if not user or not user.get("id"):
        return jsonify({"error": "Login necessário para sincronizar progresso."}), 401

    payload = request.get_json(silent=True) or {}
    posicao = int(payload.get("posicao_audio") or 0)
    ok = leitura_progresso_service.salvar_progresso(user["id"], arquivo, posicao)
    if not ok:
        return jsonify({"error": "Falha ao salvar progresso."}), 500
    return jsonify({"ok": True, "posicao_audio": posicao})


@leitura_bp.get("/api/leitura/colaboracoes/pendentes")
def api_listar_colaboracoes():
    """Lista as observações pendentes (painel da equipe / developer)."""
    from .services import leitura_service

    user = current_user()
    if not _is_developer_user(user):
        return jsonify({"error": "Área restrita à equipe."}), 403

    status = request.args.get("status", "pendente")
    return jsonify({"colaboracoes": leitura_service.listar_colaboracoes(status=status)})
