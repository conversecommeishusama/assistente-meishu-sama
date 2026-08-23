"""Rotas do Fórum Goshinsho (piloto) -- Blueprint separado.

Área de comunidade: usuários logados abrem tópicos de discussão sobre os
ensinamentos, postam mensagens (cada postagem passa por moderação
automática de CONDUITA) e podem chamar a IA do Goshinsho para responder
no contexto do tópico com base no corpus (mesmo motor do chat, mesmas
regras de fidelidade -- sem tutela).

Padrão do projeto: nenhuma tutela por tema/doença/obra; a moderação é de
conduta (discurso de ódio, assédio, spam, fora do tema), nunca de doutrina.
"""

import logging
import threading
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request, session

from .config import Config
from .services import forum_service
from .services.forum_moderation import moderar_mensagem
from .services.auth_service import current_user, is_email_confirmed
from .services.deepseek_usage_service import (
    record_deepseek_usage_totals,
    reset_deepseek_usage_context,
    set_deepseek_usage_context,
)
from .services.cost_guard_service import cost_cap_status, maybe_send_cap_alert, maybe_send_warning_alert
from .routes import (
    _friendly_error,
    _is_developer_user,
    _rate_limit_response,
    _require_confirmed_user_json,
    _require_user_json,
    _quota_status,
    EMAIL_NOT_CONFIRMED_MESSAGE,
)

_logger = logging.getLogger(__name__)

forum_bp = Blueprint("forum", __name__, url_prefix="/forum")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mask_email(email):
    """Máscara simples de e-mail para exibição no fórum (privacidade)."""
    if not email:
        return "Membro"
    local, _, dominio = email.partition("@")
    if not dominio:
        return email[:3] + "***"
    if len(local) <= 2:
        visivel = local[:1] + "***"
    else:
        visivel = local[:2] + "***"
    return f"{visivel}@{dominio}"


def _nome_exibicao(registro, email=None):
    """Nome de exibição: usa autor_nome (apelido) quando presente; senão
    mascara o e-mail. Nunca expõe o e-mail completo."""
    nome = (registro or {}).get("autor_nome") if isinstance(registro, dict) else None
    if nome and nome.strip():
        return nome.strip()
    if email:
        return _mask_email(email)
    return "Membro"


def _resolve_autores(registros):
    """Preenche autor_email/display name para uma lista de dicts com autor_id.
    Prioriza autor_nome (apelido) sobre o e-mail mascarado — nunca expõe o
    e-mail completo."""
    ids = {r.get("autor_id") for r in registros if r.get("autor_id")}
    emails = forum_service.get_emails_por_usuario(list(ids)) if ids else {}
    for r in registros:
        aid = r.get("autor_id")
        email = emails.get(aid) if aid else None
        if aid:
            r["autor_email"] = _nome_exibicao(r, email)
        else:
            r["autor_email"] = "Goshinsho (IA)"


def _formatar_data_iso(iso_str):
    """Converte ISO 8601 (UTC) para formato ocidental legível
    (dd/mm/aaaa hh:mm), no fuso local do servidor."""
    if not iso_str:
        return ""
    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt = dt.astimezone()  # fuso local do servidor
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso_str


def _formatar_topicos(topicos):
    """Aplica formatação de data ocidental e nome de exibição aos tópicos."""
    _resolve_autores(topicos)
    for t in topicos:
        t["created_at_fmt"] = _formatar_data_iso(t.get("created_at"))
        t["ultima_atividade_fmt"] = _formatar_data_iso(t.get("ultima_atividade"))
        for p in (t.get("ultimas_postagens") or []):
            p["created_at_fmt"] = _formatar_data_iso(p.get("created_at"))
    return topicos


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

@forum_bp.get("")
def forum_pagina():
    user = current_user()
    page = request.args.get("page", 1, type=int)
    busca = request.args.get("q", "").strip()
    dados = forum_service.list_topicos(page=page, per_page=5, busca=busca)
    topicos = _formatar_topicos(dados["topicos"])
    total_paginas = max((dados["total"] + 4) // 5, 1)
    return render_template(
        "forum.html",
        user=user,
        topicos=topicos,
        total=dados["total"],
        pagina=dados["pagina"],
        por_pagina=dados["por_pagina"],
        total_paginas=total_paginas,
        busca=busca,
        active_tab="forum",
    )


@forum_bp.get("/novo")
def forum_novo_pagina():
    """Página de criação de tópico — link dedicado na página principal."""
    user = current_user()
    return render_template("forum_novo.html", user=user, active_tab="forum")


@forum_bp.get("/regras")
def forum_regras_pagina():
    """Página com as normas de bom comportamento do fórum."""
    user = current_user()
    return render_template("forum_regras.html", user=user, active_tab="forum")


@forum_bp.get("/leitura")
def leitura_pagina():
    """Página da Leitura Colaborativa — proposta da comunidade para os
    colaboradores ajudarem a melhorar a tradução dos ensinamentos."""
    user = current_user()
    return render_template("leitura.html", user=user, active_tab="leitura")


@forum_bp.get("/<topico_id>")
def topico_pagina(topico_id):
    user = current_user()
    topico = forum_service.get_topico(topico_id)
    if not topico:
        return render_template(
            "forum.html", user=user, topicos=[], active_tab="forum",
            flash_msg="Este tópico não foi encontrado ou foi fechado.",
        )
    mensagens = forum_service.list_mensagens_aprovadas(topico_id)
    # 2026-08-23 (protótipo versão 2): o autor vê as próprias mensagens
    # mesmo quando estão em revisão (cobertas com o aviso de análise), para
    # saber que a postagem foi recebida e está aguardando moderação.
    if user and user.get("id"):
        do_autor = forum_service.list_mensagens_autor(topico_id, user["id"])
        ids_aprovadas = {m["id"] for m in mensagens}
        for m in do_autor:
            if m["id"] not in ids_aprovadas and m["status"] == "em_revisao":
                mensagens.append(m)
        mensagens.sort(key=lambda m: m.get("created_at") or "")
    _resolve_autores(mensagens)
    for m in mensagens:
        m["created_at_fmt"] = _formatar_data_iso(m.get("created_at"))
    topico["created_at_fmt"] = _formatar_data_iso(topico.get("created_at"))
    topico["ultima_atividade_fmt"] = _formatar_data_iso(topico.get("ultima_atividade"))
    return render_template(
        "forum_topico.html",
        user=user,
        topico=topico,
        mensagens=mensagens,
        active_tab="forum",
    )


# ---------------------------------------------------------------------------
# API — tópicos
# ---------------------------------------------------------------------------

@forum_bp.get("/api/topicos")
def api_listar_topicos():
    user = current_user()
    if not user:
        return jsonify({"error": "Faça login para acessar o fórum."}), 401
    page = request.args.get("page", 1, type=int)
    busca = request.args.get("q", "").strip()
    dados = forum_service.list_topicos(page=page, per_page=5, busca=busca)
    topicos = _formatar_topicos(dados["topicos"])
    return jsonify({
        "topicos": topicos,
        "total": dados["total"],
        "pagina": dados["pagina"],
        "por_pagina": dados["por_pagina"],
    })


@forum_bp.post("/api/topicos")
def api_criar_topico():
    user, error = _require_confirmed_user_json()
    if error:
        return error
    limited = _rate_limit_response(
        "forum_topico", limit=5, window_seconds=3600,
        message="Você criou muitos tópicos em pouco tempo. Aguarde um pouco.",
        identity=user["id"],
    )
    if limited:
        return limited

    payload = request.get_json(silent=True) or {}
    titulo = (payload.get("titulo") or "").strip()
    descricao = (payload.get("descricao") or "").strip()
    autor_nome = (payload.get("autor_nome") or "").strip()
    if not autor_nome:
        return jsonify({"error": "Para criar um tópico, informe um nome ou apelido (sua privacidade é preservada — seu e-mail nunca é exibido)."}), 400
    if len(autor_nome) > 60:
        return jsonify({"error": "Nome/apelido muito longo (máx. 60 caracteres)."}), 400
    if not titulo:
        return jsonify({"error": "Dê um título ao tópico."}), 400
    if len(titulo) > 200:
        return jsonify({"error": "Título muito longo (máx. 200 caracteres)."}), 400

    # O título/descrição do tópico também passa por moderação de conduta
    moderacao = moderar_mensagem(f"Título: {titulo}\nDescrição: {descricao}" if descricao else titulo)
    if moderacao["decisao"] == "reprovada":
        return jsonify({"error": "Este tópico não pôde ser criado: " + (moderacao["motivo"] or "viola as regras da comunidade.")}), 400

    topico = forum_service.create_topico(user["id"], autor_nome, titulo, descricao)
    if not topico:
        return jsonify({"error": "Não foi possível criar o tópico agora. Tente novamente."}), 500

    # 2026-08-23 (protótipo versão 2): ao criar o tópico, o Goshinsho dá as
    # boas-vindas como primeira mensagem, se colocando à disposição para
    # ajudar na discussão com base nos Escritos. Sem custo de API (mensagem
    # fixa, já aprovada).
    boas_vindas = (
        f"Olá, {autor_nome}! 👋 Seja bem-vindo(a) ao tópico \"{titulo}\".\n\n"
        "Sou o assistente Goshinsho, e estou à disposição para ajudar nesta "
        "discussão. Você pode me perguntar qualquer coisa sobre os ensinamentos "
        "de Meishu-Sama — responderei sempre com base nos Escritos, citando as "
        "fontes. Também fico feliz em ver a troca entre os estudiosos da "
        "comunidade. Vamos conversar!"
    )
    forum_service.save_mensagem(topico["id"], None, "assistente", boas_vindas, status="aprovada")

    topico["autor_nome"] = autor_nome
    topico["created_at_fmt"] = _formatar_data_iso(topico.get("created_at"))
    return jsonify({"topico": topico, "redirect": "/forum?criado=1"}), 201


# ---------------------------------------------------------------------------
# API — mensagens de um tópico
# ---------------------------------------------------------------------------

@forum_bp.get("/api/topicos/<topico_id>/mensagens")
def api_listar_mensagens(topico_id):
    user, error = _require_user_json()
    if error:
        return error
    topico = forum_service.get_topico(topico_id)
    if not topico:
        return jsonify({"error": "Tópico não encontrado."}), 404
    mensagens = forum_service.list_mensagens_aprovadas(topico_id)
    _resolve_autores(mensagens)
    return jsonify({"mensagens": mensagens})


@forum_bp.post("/api/topicos/<topico_id>/mensagens")
def api_postar_mensagem(topico_id):
    user, error = _require_confirmed_user_json()
    if error:
        return error
    limited = _rate_limit_response(
        "forum_msg", limit=20, window_seconds=600,
        message="Muitas postagens em pouco tempo. Aguarde alguns minutos.",
        identity=user["id"],
    )
    if limited:
        return limited

    payload = request.get_json(silent=True) or {}
    conteudo = (payload.get("conteudo") or "").strip()
    autor_nome = (payload.get("autor_nome") or "").strip()
    if not autor_nome:
        return jsonify({"error": "Para postar, informe um nome ou apelido (sua privacidade é preservada — seu e-mail nunca é exibido)."}), 400
    if len(autor_nome) > 60:
        return jsonify({"error": "Nome/apelido muito longo (máx. 60 caracteres)."}), 400
    if not conteudo:
        return jsonify({"error": "Escreva sua mensagem."}), 400
    if len(conteudo) > 5000:
        return jsonify({"error": "Mensagem muito longa (máx. 5000 caracteres)."}), 400

    topico = forum_service.get_topico(topico_id)
    if not topico or topico.get("status") != "aberto":
        return jsonify({"error": "Este tópico não está aberto para novas mensagens."}), 400

    # Moderação automática de CONDUITA (nunca doutrina)
    moderacao = moderar_mensagem(conteudo)
    decisao = moderacao["decisao"]
    motivo = moderacao["motivo"]
    if decisao == "reprovada":
        return jsonify(
            {"error": "Sua mensagem não foi publicada: " + (motivo or "viola as regras da comunidade."),
             "moderacao": "reprovada"}
        ), 400

    salva = forum_service.save_mensagem(topico_id, user["id"], "usuario", conteudo, status=decisao, motivo=motivo, autor_nome=autor_nome)
    if not salva:
        return jsonify({"error": "Não foi possível publicar agora. Tente novamente."}), 500

    salva["created_at_fmt"] = _formatar_data_iso(salva.get("created_at"))
    salva["autor_email"] = autor_nome
    resposta = {"mensagem": salva}
    if decisao == "em_revisao":
        resposta["aviso"] = (
            "Sua mensagem está em análise pela moderação e ficará visível aos outros após a aprovação. "
            "Você a vê aqui com o status 'Em análise'."
        )
    return jsonify(resposta), 201


# ---------------------------------------------------------------------------
# API — IA participando do fórum
# ---------------------------------------------------------------------------

@forum_bp.post("/api/topicos/<topico_id>/perguntar-ia")
def api_perguntar_ia(topico_id):
    """A IA do Goshinsho responde no contexto do tópico, com base no corpus
    (mesmo motor agenciado do chat -- regras de fidelidade, citação, sem
    tutela). A resposta da IA entra como mensagem papel='assistente' e já
    nasce 'aprovada' (não é conteúdo de usuário sujeito a moderação)."""
    user, error = _require_confirmed_user_json()
    if error:
        return error
    topico = forum_service.get_topico(topico_id)
    if not topico or topico.get("status") != "aberto":
        return jsonify({"error": "Tópico não encontrado ou fechado."}), 404

    # Freio de custo diário (mesmo do chat) antes de gastar API
    cap_status = cost_cap_status()
    if cap_status["exceeded"]:
        maybe_send_cap_alert(cap_status)
        return jsonify({"error": "O Goshinsho atingiu o limite diário de uso da IA. Tente novamente amanhã.", "cost_cap_reached": True}), 503
    maybe_send_warning_alert(cap_status)

    limited = _rate_limit_response(
        "forum_ia", limit=5, window_seconds=600,
        message="Muitas perguntas à IA no fórum em pouco tempo. Aguarde alguns minutos.",
        identity=user["id"],
    )
    if limited:
        return limited

    payload = request.get_json(silent=True) or {}
    pergunta = (payload.get("pergunta") or "").strip()
    if not pergunta:
        return jsonify({"error": "Digite a pergunta para a IA."}), 400

    # Contexto do tópico: últimas mensagens aprovadas para a IA situar a discussão
    contexto = forum_service.list_mensagens_aprovadas(topico_id)
    resumo_topico = f"Tópico: {topico['titulo']}"
    if contexto:
        linhas = [f"{m['papel']}: {m['conteudo'][:500]}" for m in contexto[-6:]]
        resumo_topico += "\nContexto recente da discussão:\n" + "\n".join(linhas)

    pergunta_completa = (
        f"{pergunta}\n\n[Contexto do tópico do fórum: {resumo_topico}]"
    )

    from .services import agentic_search

    try:
        r = agentic_search.responder_agentico_deepseek(
            pergunta_completa,
            [],
            system_prompt=agentic_search.SYSTEM_PROMPT,
        )
    except Exception as exc:
        _logger.warning("api_perguntar_ia: erro (%s)", exc)
        return jsonify({"error": _friendly_error(exc)}), 500

    resposta_texto = r.get("resposta", "")
    if not resposta_texto:
        return jsonify({"error": "A IA não conseguiu gerar uma resposta agora. Tente novamente."}), 502

    record_deepseek_usage_totals(r.get("tokens_entrada"), r.get("tokens_saida"), "forum_ia", model=r.get("modelo", "deepseek-v4-flash"))

    salva = forum_service.save_mensagem(topico_id, None, "assistente", resposta_texto, status="aprovada")
    if not salva:
        return jsonify({"error": "Resposta gerada, mas não foi possível salvá-la no tópico. Tente novamente."}), 500

    salva["autor_email"] = "Goshinsho (IA)"
    return jsonify({"mensagem": salva, "meta": {"tempo": r.get("tempo"), "rodadas": r.get("rodadas"), "custo": r.get("custo")}})


# ---------------------------------------------------------------------------
# API — painel de moderação (equipe / developer)
# ---------------------------------------------------------------------------

@forum_bp.get("/api/moderacao/pendentes")
def api_moderacao_pendentes():
    user = current_user()
    if not _is_developer_user(user):
        return jsonify({"error": "Área restrita à equipe."}), 403
    pendentes = forum_service.list_mensagens_pendentes()
    # inclui também tópicos cujo título ficou retido (não há tópico criado --
    # retido na criação; mantemos aqui só mensagens por enquanto)
    _resolve_autores(pendentes)
    return jsonify({"pendentes": pendentes})


@forum_bp.post("/api/moderacao/<mensagem_id>/decidir")
def api_moderacao_decidir(mensagem_id):
    user = current_user()
    if not _is_developer_user(user):
        return jsonify({"error": "Área restrita à equipe."}), 403
    payload = request.get_json(silent=True) or {}
    decisao = (payload.get("decisao") or "").strip()
    motivo = (payload.get("motivo") or "").strip() or None
    if decisao not in ("aprovada", "reprovada"):
        return jsonify({"error": "Decisão inválida (use aprovada ou reprovada)."}), 400
    ok = forum_service.update_mensagem_status(mensagem_id, decisao, motivo)
    if not ok:
        return jsonify({"error": "Mensagem não encontrada."}), 404
    return jsonify({"ok": True})
