"""Serviço da Leitura Colaborativa (piloto).

Lista e serve os textos do corpus em `textos_portugues/` para a área de
Leitura Colaborativa da comunidade, organizados em duas categorias:

- PALAVRA ORAL: as coleções de registros orais — Gokōwa-roku (御光話録),
  Gosuiji-roku (御垂示録) e Mioshie-shū (御教え集).
- PALAVRA ESCRITA: os livros e periódicos publicados.

ESCOPO (decisão do usuário, 2026-08-24):
- O corpus do app tem 137 textos. A Leitura Colaborativa cobre 135 —
  EXCLUINDO `Medicina_do_Amanha` e `Palavras de Meishu-Sama no Palácio de
  Cristal` (decisão do usuário: ficam fora da Leitura Colaborativa, mas
  continuam no corpus do app).

Segurança: apenas LEITURA de arquivos .txt dentro de `textos_portugues/`.
Nenhuma escrita. O conteúdo é lido do disco a cada requisição (arquivos
pequenos/médios; leitura sob demanda é mais simples do que manter um índice
em memória — o corpus já é servido assim por outras partes do app).
"""

import logging
import os
import re
from datetime import date
from pathlib import Path

_logger = logging.getLogger(__name__)

# Raiz dos textos em português (protótipo tem symlink para produção).
TEXTOS_DIR = Path(os.environ.get("GOSHINSHO_TEXTOS_PT", "/var/www/goshinsho/textos_portugues"))

# Fora da Leitura Colaborativa (decisão do usuário), mas presentes no corpus.
FORA_LEITURA = {
    "Medicina_do_Amanha.txt",
    "19541211 - Palavras de Meishu-Sama no Palácio de Cristal.txt",
}

# Regex de nome de arquivo: data opcional (AAAAMMDD ou AAAAMM) + título.
_TITULO_RE = re.compile(r"^(?P<ano>\d{4})(?P<mes>\d{2})(?P<dia>\d{2})?\s*[- ]?\s*(?P<titulo>.+?)\.txt$")

# Chaves usadas para identificar as 3 coleções orais (no nome do arquivo).
_COLECOES_ORAIS = [
    ("gokowa", "Gokōwa-roku", "御光話録"),
    ("gosuiji", "Gosuiji-roku", "御垂示録"),
    ("mioshie", "Mioshie-shū", "御教え集"),
]


def _arquivos_textos():
    """Lista os arquivos .txt de textos_portugues (sem os .bak)."""
    if not TEXTOS_DIR.is_dir():
        _logger.warning("leitura_service: diretório %s não encontrado", TEXTOS_DIR)
        return []
    arquivos = []
    for p in sorted(TEXTOS_DIR.iterdir()):
        if p.suffix.lower() != ".txt" or ".bak" in p.name:
            continue
        arquivos.append(p)
    return arquivos


def _parse_nome(nome_arquivo):
    """Extrai (data, titulo_limpo, numero) do nome do arquivo.

    Retorna (data, titulo, numero) onde:
    - data: datetime.date ou None
    - titulo: string limpa (sem a data nem a extensão)
    - numero: int extraído de "nº N" no título (para ordenar as coleções),
      ou None.
    """
    m = _TITULO_RE.match(nome_arquivo)
    if m:
        ano = int(m.group("ano"))
        mes = int(m.group("mes")) if m.group("mes") else None
        dia = int(m.group("dia")) if m.group("dia") else None
        try:
            data = date(ano, mes or 1, dia or 1)
        except ValueError:
            data = None
        titulo = m.group("titulo").strip()
    else:
        data = None
        titulo = Path(nome_arquivo).stem.strip()

    # Extrai o número da coleção (ex.: "Gokōwa-roku nº 10" → 10)
    numero = None
    nm = re.search(r"n[º°]?\s*(\d+)", titulo, re.IGNORECASE)
    if nm:
        numero = int(nm.group(1))
    # Suplemento/extra da Gokōwa: "Gokōwa-roku (Suplemento)" → número 0
    if "suplemento" in titulo.lower():
        numero = 0

    return data, titulo, numero


def _chave_colecao(nome_arquivo):
    """Retorna a chave da coleção oral se o arquivo é oral, senão None."""
    base = nome_arquivo.lower()
    for chave, _rotulo, _jp in _COLECOES_ORAIS:
        if chave in base or _rotulo.lower() in base:
            return chave
    return None


def _tipo_obra(nome_arquivo, titulo):
    """Classifica de forma simples: 'oral', 'periodico' ou 'livro'."""
    if _chave_colecao(nome_arquivo):
        return "oral"
    if nome_arquivo in ("Eiko.txt", "Hikari.txt", "Kyusei.txt", "Tijotengoku.txt",
                        "Jornais.txt", "Revista_Asahi.txt", "Esboco_da_Medicina.txt",
                        "Ensinamentos_diversos.txt"):
        return "periodico"
    return "livro"


def _listar_todas():
    """Lista todas as obras (dentro do escopo da Leitura Colaborativa) com
    metadados completos, ordenadas por data."""
    obras = []
    for p in _arquivos_textos():
        if p.name in FORA_LEITURA:
            continue
        data, titulo, numero = _parse_nome(p.name)
        obras.append({
            "arquivo": p.name,
            "titulo": titulo,
            "data": data.isoformat() if data else None,
            "ano": data.year if data else None,
            "numero": numero,
            "tipo": _tipo_obra(p.name, titulo),
            "colecao": _chave_colecao(p.name),
        })
    # Ordena por data (None no fim), depois por título.
    obras.sort(key=lambda o: (o["data"] is None, o["data"] or "", o["titulo"].lower()))
    return obras


def listar_obras():
    """Lista plana das obras (135) com metadados (compatível com a API atual)."""
    return _listar_todas()


def estrutura_por_categoria():
    """Retorna a estrutura hierárquica da Leitura Colaborativa.

    {
      "palavra_oral": {
        "titulo": "Palavra Oral",
        "colecoes": [
           {"chave": "gokowa", "titulo": "Gokōwa-roku", "jp": "御光話録",
            "obras": [ {arquivo, titulo, data, ano, numero}, ... ]},
           ...
        ]
      },
      "palavra_escrita": {
        "titulo": "Palavra Escrita",
        "obras": [ ... ]   # livros + periódicos, por data
      }
    }
    """
    obras = _listar_todas()

    orais = [o for o in obras if o["tipo"] == "oral"]
    escritas = [o for o in obras if o["tipo"] != "oral"]

    # Agrupa orais por coleção, em ordem fixa (Gokōwa, Gosuiji, Mioshie),
    # e dentro de cada coleção ordena por data (e número como desempate).
    colecoes = []
    for chave, rotulo, jp in _COLECOES_ORAIS:
        itens = [o for o in orais if o["colecao"] == chave]
        itens.sort(key=lambda o: (o["data"] or "", o["numero"] if o["numero"] is not None else 0, o["titulo"].lower()))
        colecoes.append({
            "chave": chave,
            "titulo": rotulo,
            "jp": jp,
            "obras": itens,
        })

    return {
        "palavra_oral": {
            "titulo": "Palavra Oral",
            "colecoes": colecoes,
        },
        "palavra_escrita": {
            "titulo": "Palavra Escrita",
            "obras": escritas,  # já ordenadas por data em _listar_todas
        },
    }


def obter_texto(nome_arquivo):
    """Retorna o conteúdo de um arquivo de texto (str) ou None.

    Valida que o nome é um arquivo .txt simples (sem path traversal).
    """
    if not nome_arquivo or ".." in nome_arquivo or "/" in nome_arquivo or "\\" in nome_arquivo:
        return None
    caminho = TEXTOS_DIR / nome_arquivo
    try:
        if not caminho.is_file() or caminho.suffix.lower() != ".txt":
            return None
        return caminho.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        _logger.warning("leitura_service: erro ao ler %s (%s)", nome_arquivo, exc)
        return None


# ---------------------------------------------------------------------------
# Colaboração — observações dos leitores sobre os textos (piloto)
# ---------------------------------------------------------------------------
#
# Tabela criada idempotentemente (ver garantir_tabelas_colaboracao):
#
#   CREATE TABLE IF NOT EXISTS public.leitura_colaboracoes (
#       id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
#       arquivo text NOT NULL,               -- nome do arquivo (textos_portugues)
#       trecho text,                         -- trecho selecionado pelo leitor
#       observacao text NOT NULL,            -- comentário do colaborador
#       autor_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,  -- NULL = anônimo
#       autor_nome text,                     -- apelido (nunca e-mail)
#       status text NOT NULL DEFAULT 'pendente',  -- pendente | analisado
#       criada_em timestamptz NOT NULL DEFAULT now(),
#       analisada_em timestamptz
#   );
#   CREATE INDEX IF NOT EXISTS idx_leitura_colab_status ON public.leitura_colaboracoes (status, criada_em);

SQL_CRIAR_TABELA_COLABORACAO = """
CREATE TABLE IF NOT EXISTS public.leitura_colaboracoes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    arquivo text NOT NULL,
    trecho text,
    observacao text NOT NULL,
    autor_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    autor_nome text,
    status text NOT NULL DEFAULT 'pendente',
    criada_em timestamptz NOT NULL DEFAULT now(),
    analisada_em timestamptz
);
CREATE INDEX IF NOT EXISTS idx_leitura_colab_status ON public.leitura_colaboracoes (status, criada_em);
"""


def _conn():
    import psycopg2
    from ..config import Config

    conn_str = getattr(Config, "POSTGRES_CONNECTION_STRING", None) or ""
    if not conn_str:
        raise RuntimeError("POSTGRES_CONNECTION_STRING não configurada no .env.")
    return psycopg2.connect(conn_str, connect_timeout=15)


def garantir_tabelas_colaboracao():
    """Cria a tabela de colaborações se não existir (idempotente)."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(SQL_CRIAR_TABELA_COLABORACAO)
                conn.commit()
                return True
    except Exception as exc:
        _logger.warning("leitura_service: falha ao garantir tabela colaboração (%s)", exc)
        return False


def criar_colaboracao(arquivo, observacao, trecho=None, autor_id=None, autor_nome=None):
    """Salva uma observação de colaboração sobre um trecho do texto.

    Retorna o dict salvo ou None em caso de erro.
    """
    arquivo = (arquivo or "").strip()
    observacao = (observacao or "").strip()
    if not arquivo or not observacao:
        return None
    # Limita o tamanho para não sobrecarregar o banco
    observacao = observacao[:2000]
    trecho = (trecho or "").strip()[:1000] or None
    autor_nome = (autor_nome or "").strip()[:80] or None
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.leitura_colaboracoes
                        (arquivo, trecho, observacao, autor_id, autor_nome, status, criada_em)
                    VALUES (%s, %s, %s, %s, %s, 'pendente', now())
                    RETURNING id, arquivo, trecho, observacao, autor_nome, status, criada_em
                    """,
                    (arquivo, trecho, observacao, autor_id, autor_nome),
                )
                row = cur.fetchone()
                conn.commit()
                if not row:
                    return None
                col = [d[0] for d in cur.description]
                data = dict(zip(col, row))
                return {
                    "id": str(data["id"]),
                    "arquivo": data["arquivo"],
                    "trecho": data["trecho"],
                    "observacao": data["observacao"],
                    "autor_nome": data["autor_nome"],
                    "status": data["status"],
                    "criada_em": data["criada_em"].isoformat() if data.get("criada_em") else None,
                }
    except Exception as exc:
        _logger.warning("leitura_service: erro ao criar colaboração (%s)", exc)
        return None


def listar_colaboracoes(status="pendente", limite=200):
    """Lista as colaborações (para a equipe revisar)."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, arquivo, trecho, observacao, autor_nome, status, criada_em
                    FROM public.leitura_colaboracoes
                    WHERE status = %s
                    ORDER BY criada_em DESC
                    LIMIT %s
                    """,
                    (status, limite),
                )
                col = [d[0] for d in cur.description]
                itens = []
                for row in cur.fetchall():
                    data = dict(zip(col, row))
                    itens.append({
                        "id": str(data["id"]),
                        "arquivo": data["arquivo"],
                        "trecho": data["trecho"],
                        "observacao": data["observacao"],
                        "autor_nome": data["autor_nome"],
                        "status": data["status"],
                        "criada_em": data["criada_em"].isoformat() if data.get("criada_em") else None,
                    })
                return itens
    except Exception as exc:
        _logger.warning("leitura_service: erro ao listar colaborações (%s)", exc)
        return []
