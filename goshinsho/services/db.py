"""Ligação ao Postgres (Supabase) — uma só fonte de verdade, com pool.

## Porque existe este módulo

Cinco serviços (`forum_service`, `artigo_service`, `leitura_service`,
`leitura_uso_service`, `leitura_progresso_service`) tinham cada um a SUA
cópia de `_conn()`, idêntica byte a byte:

    conn_str = Config.POSTGRES_CONNECTION_STRING
    return psycopg2.connect(conn_str, connect_timeout=15)

Cinco cópias da mesma regra é a mesma armadilha que já deixou três
implementações do roteamento de voz a divergir neste projecto (2026-10-22).
Aqui a regra é uma só.

## Porque tem pool

Medido em 28/10/2026 contra o Supabase (host directo, porta 5432, sem pooler):

    connect 1: 783 ms
    connect 2: 778 ms
    connect 3: 756 ms
    connect 4: 761 ms

São ~770 ms **só para abrir a ligação**. Como cada função de serviço abria a
sua, uma página que consulta três coisas pagava três vezes esse preço —
`/portal` levava 3,98 s e `/portal/forum` 2,9 s, dos quais ~1,2 s eram pura
abertura de ligação.

Com o pool, a ligação abre uma vez por processo e é reaproveitada: a página
passa a pagar só as consultas (dezenas de ms).

## Como usar

    from .db import conexao

    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute(...)

`conexao()` é um context manager que **devolve sempre** a ligação ao pool:
faz commit em caso de sucesso, rollback em caso de exceção, e devolve-a no
`finally`. Isto também corrige um detalhe que passava despercebido:
`with psycopg2.connect(...) as conn` NÃO fecha a ligação — só faz
commit/rollback. O `with _conn() as conn:` dos cinco serviços deixava a
ligação aberta até o CPython a recolher.

## Interruptor

`GOSHINSHO_DB_POOL=0` desliga o pool e volta ao comportamento anterior
(ligação nova por chamada). Existe para poder isolar um problema em produção
sem editar código, e é o que os testes usam para não depender de estado
partilhado entre processos.
"""

import logging
import os
import threading

_logger = logging.getLogger(__name__)

# Limites do pool. Cada worker gunicorn tem o SEU pool (o processo não é
# partilhado), por isso o limite efectivo é `maxconn × nº de workers`.
#
# `maxconn` tem de ser >= ao nº de threads do worker, senão threads ficam à
# espera de uma ligação livre. Os workers usam `--threads 4` (produção e
# portal), por isso 8 dá folga sem abrir 16 ligações ao Supabase por worker.
_MINCONN = 1
_MAXCONN = int(os.environ.get("GOSHINSHO_DB_POOL_MAX", "8"))
_TIMEOUT_MS = int(os.environ.get("GOSHINSHO_DB_TIMEOUT_MS", "15000"))

_pool = None
_pool_lock = threading.Lock()
_pool_desativado = False


def _pool_ativo() -> bool:
    """O pool está ligado neste processo? (`GOSHINSHO_DB_POOL=0` desliga.)"""
    valor = (os.environ.get("GOSHINSHO_DB_POOL") or "").strip().lower()
    return valor not in ("0", "false", "no", "off")


def _conn_str() -> str:
    from ..config import Config

    conn_str = getattr(Config, "POSTGRES_CONNECTION_STRING", None) or ""
    if not conn_str:
        raise RuntimeError(
            "POSTGRES_CONNECTION_STRING não configurada no .env.")
    return conn_str


def _obter_pool():
    """O pool do processo, criado na primeira utilização (lazy)."""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:  # outra thread criou entretanto
            return _pool
        from psycopg2 import pool as pg_pool

        _pool = pg_pool.ThreadedConnectionPool(
            _MINCONN, _MAXCONN, _conn_str(), connect_timeout=_TIMEOUT_MS // 1000,
        )
        _logger.warning(
            "db: pool de ligações criado (min=%s, max=%s)", _MINCONN, _MAXCONN)
        return _pool


def _ligacao_nova():
    import psycopg2

    return psycopg2.connect(_conn_str(), connect_timeout=_TIMEOUT_MS // 1000)


class _Conexao:
    """Context manager: entrega uma ligação e devolve-a SEMPRE ao pool."""

    def __init__(self):
        self._conn = None
        self._do_pool = False

    def __enter__(self):
        global _pool_desativado
        if _pool_ativo() and not _pool_desativado:
            try:
                self._conn = _obter_pool().getconn()
                self._do_pool = True
                # Uma ligação que ficou parada pode ter sido cortada do outro
                # lado (o Supabase fecha sessões inactivas). Descartar antes de
                # a entregar ao chamador; sem isto, o primeiro pedido depois de
                # um período de silêncio apanhava um 500.
                if not _ligacao_viva(self._conn):
                    self._devolver(quebrada=True)
                    self._conn = _obter_pool().getconn()
                self._conn.autocommit = False
            except Exception as exc:
                # Pool indisponível (limite atingido, rede, credenciais): não é
                # motivo para derrubar o pedido — segue com ligação directa,
                # como antes, e o pool fica desligado neste processo para não
                # pagar o erro em cada chamada.
                _logger.warning(
                    "db: pool indisponível (%s) — a usar ligação directa. "
                    "O pool fica desligado neste processo.", exc)
                _pool_desativado = True
                self._conn = None
                self._do_pool = False
        if self._conn is None:
            self._conn = _ligacao_nova()
        return self._conn

    def _devolver(self, *, quebrada: bool = False):
        if self._conn is None or not self._do_pool:
            return
        try:
            _obter_pool().putconn(self._conn, close=quebrada)
        except Exception:  # pragma: no cover - defensivo
            pass
        finally:
            self._conn = None

    def __exit__(self, exc_type, exc, tb):
        conn = self._conn
        if conn is None:
            return False
        quebrada = self._ligacao_morreu(conn, exc)
        try:
            if exc_type is None:
                conn.commit()
            else:
                conn.rollback()
        except Exception as commit_exc:
            quebrada = True
            _logger.warning("db: falha ao fechar transacção (%s)", commit_exc)
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            if self._do_pool:
                self._devolver(quebrada=quebrada)
            else:
                try:
                    conn.close()
                except Exception:
                    pass
                self._conn = None
        return False  # a excepção continua a subir

    @staticmethod
    def _ligacao_morreu(conn, exc) -> bool:
        """A ligação está inutilizável? (para NÃO voltar ao pool)

        Dois casos, e o segundo é o perigoso:

        1. `conn.closed` != 0 — o psycopg2 já sabe que fechou.
        2. `closed` continua 0 mas a ligação morreu (rede caiu, o Supabase
           cortou a sessão por inactividade). Aqui o psycopg2 marca-se só
           depois da primeira tentativa falhada, e é a excepção que o diz:
           `OperationalError`/`InterfaceError` são erros de LIGAÇÃO; os
           restantes (por exemplo `IntegrityError`, `ProgrammingError`) são
           erros de CONSULTA e a ligação está boa.

        Sem o caso 2, uma ligação morta voltava ao pool como reutilizável e
        envenenava o worker: como `minconn=1`, o mesmo socket partido servia
        todos os pedidos seguintes daquele processo. Uma falha de rede
        momentânea deixava o site em baixo até reiniciar.
        """
        if getattr(conn, "closed", 1):
            return True
        if exc is None:
            return False
        try:
            import psycopg2

            if isinstance(exc, (psycopg2.OperationalError,
                                psycopg2.InterfaceError)):
                return True
        except Exception:  # pragma: no cover - defensivo
            # Sem psycopg2 importável não há como distinguir: na dúvida,
            # descartar (perde-se uma ligação, não o serviço).
            return True
        return False


def _ligacao_viva(conn) -> bool:
    """A ligação ainda serve? Verificação LOCAL, sem ir à rede.

    `conn.closed` só diz que o *psycopg2* a fechou; não diz nada quando é o
    SERVIDOR que cortou a sessão (o Supabase fecha sessões inactivas). Nesse
    caso `closed` continua 0 e a primeira consulta seguinte rebenta com
    `OperationalError: SSL connection has been closed unexpectedly` — o
    utilizador vê um 500.

    Um `SELECT 1` resolveria, mas custa um ida-e-volta (~190 ms neste link) em
    CADA entrega de ligação. Em vez disso olha-se para o socket: se a outra
    ponta fechou, o socket fica legível com 0 bytes (EOF). `select` é local e
    custa microssegundos.

    Só devolve False quando tem a certeza. Na dúvida (socket sem `fileno`,
    plataforma estranha) devolve True e a ligação é usada — uma verificação
    que descarta ligações boas seria pior do que o problema que resolve.
    """
    if getattr(conn, "closed", 1):
        return False
    try:
        import select

        fileno = conn.fileno()
    except Exception:
        return True
    if fileno is None or fileno < 0:
        return True
    try:
        pronto, _, _ = select.select([fileno], [], [], 0)
    except Exception:
        return True
    if not pronto:
        return True  # nada a ler: ligação sã
    # Legível quando devia estar parada = a outra ponta escreveu (erro) ou
    # fechou. Não há `LISTEN/NOTIFY` neste projecto, por isso não há tráfego
    # legítimo inesperado.
    return False


def conexao() -> _Conexao:
    """Ligação ao Postgres (do pool, se estiver ligado).

    Usar sempre como context manager:

        with conexao() as conn:
            ...
    """
    return _Conexao()


def conn() -> _Conexao:
    """Alias de `conexao()` — alguns serviços chamam-lhe `_conn()`."""
    return _Conexao()


def fechar_pool() -> None:
    """Fecha todas as ligações do pool deste processo.

    Chamado no encerramento do worker gunicorn e pelos testes. Não falha se o
    pool nunca tiver sido criado, nem se já estiver fechado.
    """
    global _pool
    with _pool_lock:
        if _pool is None:
            return
        try:
            _pool.closeall()
        except Exception as exc:  # pragma: no cover - defensivo
            _logger.warning("db: falha ao fechar o pool (%s)", exc)
        finally:
            _pool = None


def estado_do_pool() -> dict:
    """Diagnóstico (usado pelos testes e por `/health`, se for preciso)."""
    return {
        "ativo": _pool_ativo() and not _pool_desativado,
        "criado": _pool is not None,
        "minconn": _MINCONN,
        "maxconn": _MAXCONN,
        "desativado_por_erro": _pool_desativado,
    }
