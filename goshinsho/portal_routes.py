"""Rotas do Portal Goshinsho — protótipo montado em `/portal`.

Este blueprint pertence ao PROTÓTIPO (cópia em /var/www/goshinsho-portal),
não à produção. Ele reúne a página principal do portal (que agrega acervo,
fórum, artigos e o chat), a área de Artigos criada do zero, e a caixa de
pergunta que encaminha a pergunta do leitor para o Chat já existente.

Endpoints (namespace `portal.*`):
    GET  /portal                              página principal
    GET  /portal/artigos                      lista de artigos
    GET  /portal/artigos/novo                 formulário de publicação
    GET  /portal/artigos/<artigo_id>          artigo + comentários
    GET  /portal/aviso-artigos                aviso de responsabilidade
    GET  /portal/api/artigos                  lista (JSON)
    POST /portal/api/artigos                  publica um artigo
    POST /portal/api/artigos/<id>/comentarios comenta em um artigo

Reaproveita integralmente os serviços de produção (fórum, leitura, moderação
de conduta) por import — não duplica regra de negócio.
"""

import logging

from flask import Blueprint, jsonify, render_template, request

from .config import Config
from .services import artigo_service, forum_service
from .services.auth_service import current_user, is_email_confirmed
from .services.forum_moderation import moderar_mensagem
from .routes import _rate_limit_response, _require_confirmed_user_json

_logger = logging.getLogger(__name__)

# IMPORTANTE — prefixo de URL no PROTÓTIPO:
# aqui o blueprint é declarado SEM url_prefix porque o prefixo `/portal` já é
# injetado pelo dispatcher do web_app.py (SCRIPT_NAME). Com url_prefix="/portal"
# e o SCRIPT_NAME ao mesmo tempo, o Flask geraria `/portal/portal/...`.
# Quando o portal for promovido para a produção (servido direto pelo domínio,
# sem mount), este blueprint deve ser registrado COM url_prefix="/portal" —
# ver HANDOFF_PORTAL_20260929.md.
portal_bp = Blueprint("portal", __name__)


# ---------------------------------------------------------------------------
# Constantes de conteúdo
# ---------------------------------------------------------------------------

# Texto exato do consentimento do autor. Fica gravado no artigo
# (`autorizacao_texto`) para servir de prova do que foi aceito.
TEXTO_AUTORIZACAO = (
    "Declaro que sou o autor deste artigo, que o texto é de minha autoria e "
    "responsabilidade, e autorizo expressamente a sua publicação no Portal "
    "Goshinsho. Declaro também que li e aceito o aviso de que as ideias "
    "contidas nos artigos são de responsabilidade exclusiva de seus autores e "
    "não refletem o pensamento ou a posição do Portal Goshinsho."
)

AVISO_ARTIGOS = (
    "As ideias, opiniões e interpretações contidas nos artigos são de "
    "responsabilidade exclusiva de seus autores e NÃO refletem o pensamento, "
    "a posição ou a orientação do Portal Goshinsho. O Portal Goshinsho não se "
    "responsabiliza pelas ideias ali contidas, nem por eventuais consequências "
    "do seu uso. Todo artigo é publicado com identificação do autor (nome "
    "completo e CPF verificados), não sendo admitido artigo anônimo ou apócrifo."
)

# As coleções orais (Gokōwa-roku, Gosuiji-roku, Mioshie-shū) NÃO são
# declaradas aqui: vêm de `leitura_service.estrutura_por_categoria()`, que é a
# fonte de verdade do acervo. Duplicar a lista criaria duas verdades que
# divergem em silêncio.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _formatar_data_iso(iso_str):
    """ISO 8601 (UTC) -> dd/mm/aaaa hh:mm no fuso do servidor."""
    if not iso_str:
        return ""
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return dt.astimezone().strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(iso_str)


def _formata(artigos):
    """Acrescenta datas formatadas em pt-BR (ignora entradas None)."""
    for a in artigos or []:
        if not a:
            continue
        a["created_at_fmt"] = _formatar_data_iso(a.get("created_at"))
        a["ultimo_comentario_fmt"] = _formatar_data_iso(a.get("ultimo_comentario"))
    return artigos


def _topicos_recentes(limite=3):
    """Os `limite` tópicos do fórum com atualização mais recente.

    `list_topicos` já ordena por última atividade (mais recente primeiro) e
    devolve as 2 últimas postagens resumidas de cada tópico.
    """
    dados = forum_service.list_topicos(page=1, per_page=limite)
    topicos = dados.get("topicos") or []
    for t in topicos:
        t["ultima_atividade_fmt"] = _formatar_data_iso(t.get("ultima_atividade"))
        t["created_at_fmt"] = _formatar_data_iso(t.get("created_at"))
        # Nome de exibição: apelido quando houver; senão rótulo genérico
        # (o e-mail do autor nunca é exposto na página do portal).
        for p in t.get("ultimas_postagens") or []:
            p["created_at_fmt"] = _formatar_data_iso(p.get("created_at"))
    return topicos, dados.get("total") or 0


def _estrutura_acervo():
    """Estrutura do acervo (Palavra Oral / Palavra Escrita) e contagens."""
    try:
        from .services import leitura_service

        return leitura_service.estrutura_por_categoria()
    except Exception as exc:
        _logger.warning("portal: falha ao ler a estrutura do acervo (%s)", exc)
        return None


def _contagens_acervo(estrutura):
    """Contagens para os cartões da página principal (0 quando indisponível)."""
    if not estrutura:
        return {"oral": 0, "escrita": 0, "total": 0, "colecoes": []}
    oral = sum(len(c.get("obras") or []) for c in estrutura.get("palavra_oral", {}).get("colecoes", []))
    escrita = len(estrutura.get("palavra_escrita", {}).get("obras") or [])
    colecoes = [
        {
            "chave": c.get("chave"),
            "titulo": c.get("titulo"),
            "jp": c.get("jp"),
            "quantidade": len(c.get("obras") or []),
        }
        for c in estrutura.get("palavra_oral", {}).get("colecoes", [])
    ]
    return {"oral": oral, "escrita": escrita, "total": oral + escrita, "colecoes": colecoes}


def _contexto_base(user):
    """Contexto comum a todas as páginas do portal (cabeçalho e navegação)."""
    return {
        "user": user,
        "active_tab": "portal",
        "aviso_artigos": AVISO_ARTIGOS,
    }


# ---------------------------------------------------------------------------
# Página principal
# ---------------------------------------------------------------------------

@portal_bp.get("/")
def portal_home():
    """Página principal do portal — agrega acervo, fórum, artigos e o chat.

    Não existe aqui um decorador para a regra vazia (""): sem `url_prefix`, o
    Flask rejeita regra vazia ("URL rule '' must start with a slash") e o
    registro inteiro do blueprint falha em silêncio dentro do try/except do
    create_app — o portal ficaria com as rotas de páginas mas sem as de API.
    """
    user = current_user()
    estrutura = _estrutura_acervo()
    contagens = _contagens_acervo(estrutura)

    topicos = []
    total_topicos = 0
    forum_indisponivel = False
    if Config.FORUM_ENABLED:
        topicos, total_topicos = _topicos_recentes(limite=3)
    else:
        forum_indisponivel = True

    artigo_recente = artigo_service.artigo_mais_recente()
    artigo_comentado = artigo_service.artigo_ultimo_comentario()
    # Não repetir o mesmo artigo nos dois espaços da página.
    if artigo_recente and artigo_comentado and artigo_recente["id"] == artigo_comentado["id"]:
        artigo_comentado = None
    _formata([artigo_recente, artigo_comentado])

    return render_template(
        "portal.html",
        **_contexto_base(user),
        contagens=contagens,
        topicos=topicos,
        total_topicos=total_topicos,
        forum_indisponivel=forum_indisponivel,
        artigo_recente=artigo_recente,
        artigo_comentado=artigo_comentado,
    )


# ---------------------------------------------------------------------------
# Artigos — páginas
# ---------------------------------------------------------------------------

@portal_bp.get("/artigos")
def artigos_lista():
    """Lista de artigos publicados, com busca e paginação."""
    user = current_user()
    page = request.args.get("page", 1, type=int)
    busca = request.args.get("q", "").strip()
    dados = artigo_service.listar_artigos(page=page, per_page=10, busca=busca)
    artigos = _formata(dados["artigos"])
    total_paginas = max((dados["total"] + 9) // 10, 1)
    return render_template(
        "artigos.html",
        **_contexto_base(user),
        artigos=artigos,
        total=dados["total"],
        pagina=dados["pagina"],
        total_paginas=total_paginas,
        busca=busca,
    )


@portal_bp.get("/artigos/novo")
def artigos_novo():
    """Formulário de publicação de artigo (cadastro simples com nome e CPF)."""
    user = current_user()
    return render_template(
        "artigo_novo.html",
        **_contexto_base(user),
        texto_autorizacao=TEXTO_AUTORIZACAO,
    )


@portal_bp.get("/artigos/<artigo_id>")
def artigo_detalhe(artigo_id):
    """Página de um artigo, com os comentários aprovados."""
    user = current_user()
    artigo = artigo_service.get_artigo(artigo_id)
    if not artigo:
        return render_template(
            "artigos.html",
            **_contexto_base(user),
            artigos=[],
            total=0,
            pagina=1,
            total_paginas=1,
            busca="",
            flash_msg="Artigo não encontrado ou ainda não publicado.",
        ), 404
    artigo["created_at_fmt"] = _formatar_data_iso(artigo.get("created_at"))
    comentarios = artigo_service.listar_comentarios(artigo_id)
    for c in comentarios:
        c["created_at_fmt"] = _formatar_data_iso(c.get("created_at"))
    return render_template(
        "artigo.html",
        **_contexto_base(user),
        artigo=artigo,
        comentarios=comentarios,
    )


@portal_bp.get("/aviso-artigos")
def aviso_artigos():
    """Página dedicada ao aviso de responsabilidade dos artigos."""
    user = current_user()
    return render_template("artigo_aviso.html", **_contexto_base(user))


# ---------------------------------------------------------------------------
# Artigos — API
# ---------------------------------------------------------------------------

@portal_bp.get("/api/artigos")
def api_listar_artigos():
    page = request.args.get("page", 1, type=int)
    busca = request.args.get("q", "").strip()
    dados = artigo_service.listar_artigos(page=page, per_page=10, busca=busca)
    return jsonify({
        "artigos": _formata(dados["artigos"]),
        "total": dados["total"],
        "pagina": dados["pagina"],
    })


def _validar_nome_completo(nome):
    """Exige nome e sobrenome (mínimo duas palavras com letras)."""
    partes = [p for p in (nome or "").split() if len(p) >= 2]
    if len(partes) < 2:
        return False
    return all(any(ch.isalpha() for ch in p) for p in partes)


@portal_bp.post("/api/artigos")
def api_criar_artigo():
    """Publica um artigo — exige nome completo, CPF válido e autorização."""
    user, error = _require_confirmed_user_json()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    nome = (payload.get("autor_nome") or "").strip()
    cpf = (payload.get("cpf") or "").strip()
    titulo = (payload.get("titulo") or "").strip()
    subtitulo = (payload.get("subtitulo") or "").strip()
    conteudo = (payload.get("conteudo") or "").strip()
    autorizou = bool(payload.get("autorizacao"))

    if not _validar_nome_completo(nome):
        return jsonify({"error": "Informe seu nome completo (nome e sobrenome). Não são aceitos artigos anônimos."}), 400
    if len(nome) > 120:
        return jsonify({"error": "Nome muito longo (máx. 120 caracteres)."}), 400
    if not artigo_service.validar_cpf(cpf):
        return jsonify({"error": "CPF inválido. Confira os números digitados."}), 400
    if not titulo or len(titulo) < 8:
        return jsonify({"error": "Dê um título ao artigo (mínimo 8 caracteres)."}), 400
    if len(titulo) > 200:
        return jsonify({"error": "Título muito longo (máx. 200 caracteres)."}), 400
    if len(subtitulo) > 240:
        return jsonify({"error": "Subtítulo muito longo (máx. 240 caracteres)."}), 400
    if len(conteudo) < 200:
        return jsonify({"error": "O artigo está muito curto. Escreva ao menos 200 caracteres."}), 400
    if len(conteudo) > 60000:
        return jsonify({"error": "O artigo excede o tamanho máximo permitido."}), 400
    if not autorizou:
        return jsonify({"error": "É necessário autorizar expressamente a publicação do artigo."}), 400

    # O LIMITE DIÁRIO só é consumido depois de a requisição passar por TODA a
    # validação. Motivo (corrigido em teste, 2026-09-29): quando o contador era
    # consumido na entrada, três erros de digitação no CPF esgotavam a cota do
    # dia e a pessoa ficava impedida de publicar até o dia seguinte — punição
    # por erro de formulário, não por excesso de publicação.
    limited = _rate_limit_response(
        "portal_artigo", limit=3, window_seconds=86400,
        message="Você já publicou o máximo de artigos de hoje. Tente novamente amanhã.",
        identity=user["id"],
    )
    if limited:
        return limited

    # Moderação de CONDUTA (nunca doutrinária) — mesma política do fórum.
    moderacao = moderar_mensagem(f"Título: {titulo}\n\n{conteudo[:6000]}")
    if moderacao["decisao"] == "reprovada":
        return jsonify({
            "error": "O artigo não pôde ser publicado: " + (moderacao.get("motivo") or "viola as regras da comunidade.")
        }), 400

    artigo = artigo_service.criar_artigo(
        autor_id=user["id"],
        autor_nome=nome,
        autor_email=user.get("email"),
        cpf=cpf,
        titulo=titulo,
        subtitulo=subtitulo,
        conteudo=conteudo,
        autorizacao_texto=TEXTO_AUTORIZACAO,
    )
    if not artigo:
        return jsonify({
            "error": (
                "Não foi possível registrar o artigo agora. Se o problema persistir, "
                "avise a equipe pelo Contato."
            )
        }), 500

    if moderacao["decisao"] == "em_revisao":
        artigo_service.atualizar_status_artigo(artigo["id"], "em_revisao", moderacao.get("motivo"))
        artigo["status"] = "em_revisao"
        return jsonify({
            "artigo": artigo,
            "aviso": "Seu artigo foi recebido e está em análise pela equipe. Ele será publicado após a revisão.",
            "redirect": f"/portal/artigos/{artigo['id']}",
        }), 201

    artigo_service.atualizar_status_artigo(artigo["id"], "aprovada")
    artigo["status"] = "aprovada"
    return jsonify({
        "artigo": artigo,
        "redirect": f"/portal/artigos/{artigo['id']}",
    }), 201


@portal_bp.post("/api/artigos/<artigo_id>/comentarios")
def api_comentar_artigo(artigo_id):
    """Comenta em um artigo publicado."""
    user, error = _require_confirmed_user_json()
    if error:
        return error

    limited = _rate_limit_response(
        "portal_comentario", limit=20, window_seconds=600,
        message="Muitos comentários em pouco tempo. Aguarde alguns minutos.",
        identity=user["id"],
    )
    if limited:
        return limited

    artigo = artigo_service.get_artigo(artigo_id)
    if not artigo:
        return jsonify({"error": "Artigo não encontrado ou ainda não publicado."}), 404

    payload = request.get_json(silent=True) or {}
    nome = (payload.get("autor_nome") or "").strip()
    conteudo = (payload.get("conteudo") or "").strip()
    if not nome:
        return jsonify({"error": "Informe um nome ou apelido para comentar."}), 400
    if len(nome) > 60:
        return jsonify({"error": "Nome/apelido muito longo (máx. 60 caracteres)."}), 400
    if not conteudo:
        return jsonify({"error": "Escreva o seu comentário."}), 400
    if len(conteudo) > 5000:
        return jsonify({"error": "Comentário muito longo (máx. 5.000 caracteres)."}), 400

    moderacao = moderar_mensagem(conteudo)
    if moderacao["decisao"] == "reprovada":
        return jsonify({
            "error": "O comentário não pôde ser publicado: " + (moderacao.get("motivo") or "viola as regras da comunidade.")
        }), 400

    status = "em_revisao" if moderacao["decisao"] == "em_revisao" else "aprovada"
    comentario = artigo_service.criar_comentario(
        artigo_id=artigo_id,
        autor_id=user["id"],
        autor_nome=nome,
        conteudo=conteudo,
        status=status,
        motivo=moderacao.get("motivo"),
    )
    if not comentario:
        return jsonify({"error": "Não foi possível registrar o comentário agora. Tente novamente."}), 500
    comentario["created_at_fmt"] = _formatar_data_iso(comentario.get("created_at"))
    resposta = {"comentario": comentario}
    if status == "em_revisao":
        resposta["aviso"] = "Seu comentário está em análise pela moderação e ficará visível após a aprovação."
    return jsonify(resposta), 201
