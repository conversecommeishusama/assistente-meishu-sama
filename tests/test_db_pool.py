"""Ligação ao Postgres — o pool e a fonte única de verdade.

## Porque estes testes existem

Cinco serviços tinham a SUA cópia de `_conn()` (idêntica byte a byte), e cada
chamada abria uma ligação nova ao Supabase. Medido em 28/10/2026: **~770 ms
só para abrir**, porque o host é directo (porta 5432, sem pooler).

Isso não é um detalhe: `/portal` levava 3,98 s e `/portal/forum` 3,0 s, com
~1,2 s por função de serviço só em abertura de ligação.

O que se prende aqui:

  · o pool entrega e **devolve sempre** a ligação (uma fuga esgota o pool em
    produção e o site pára de responder — é a falha mais cara desta mudança);
  · em excepção faz rollback, e a ligação volta ao pool em vez de ficar com
    uma transacção aberta;
  · ligação quebrada é DESCARTADA, não devolvida (senão o erro seguinte é de
    outra pessoa);
  · se o pool falhar, cai para ligação directa e desliga-se — não se paga o
    erro a cada pedido;
  · os cinco serviços delegam no mesmo módulo (uma só fonte de verdade).

Nota: estes testes não tocam no banco. Usam duplos, para poderem correr sem
rede e sem depender de estado partilhado.
"""

import os
import unittest
from unittest import mock

from goshinsho.services import db


class _LigacaoFalsa:
    """O mínimo de uma ligação psycopg2 para o `conexao()` a tratar."""

    def __init__(self):
        self.closed = 0
        self.autocommit = True
        self.commits = 0
        self.rollbacks = 0
        self.fechada = 0
        self.falhar_commit = False

    def commit(self):
        if self.falhar_commit:
            raise RuntimeError("commit falhou")
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.fechada += 1
        self.closed = 1


class _PoolFalso:
    def __init__(self, ligacao=None):
        self.ligacao = ligacao or _LigacaoFalsa()
        self.entregues = 0
        self.devolvidas = []
        self.getconn_erro = None

    def getconn(self):
        if self.getconn_erro:
            raise self.getconn_erro
        self.entregues += 1
        return self.ligacao

    def putconn(self, conn, close=False):
        self.devolvidas.append(("fechada" if close else "reutilizada", conn))


class _BaseDb(unittest.TestCase):
    """Isola o estado global do módulo entre testes."""

    def setUp(self):
        self._antes_pool = db._pool
        self._antes_desativado = db._pool_desativado
        db._pool = None
        db._pool_desativado = False
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        db._pool = self._antes_pool
        db._pool_desativado = self._antes_desativado


class LigacaoVivaTests(unittest.TestCase):
    """`_ligacao_viva`: detetar ligação cortada pelo SERVIDOR, sem ir à rede.

    `conn.closed` só sabe o que o psycopg2 fechou. Quando é o Supabase que
    corta uma sessão inactiva, `closed` continua 0 e a consulta seguinte
    rebenta com `OperationalError: SSL connection has been closed
    unexpectedly` — o utilizador vê um 500 logo no primeiro pedido depois de um
    período parado.

    Provado à séria em 28/10/2026: `pg_terminate_backend()` na ligação do pool,
    a partir de uma ligação externa. Antes desta verificação, a tentativa
    seguinte falhava; agora são 4×OK, 0 falhas, e o pool entrega outra ligação.
    """

    class _Lig:
        def __init__(self, closed=0, fileno=10, erro_fileno=False):
            self.closed = closed
            self._fileno = fileno
            self._erro_fileno = erro_fileno

        def fileno(self):
            if self._erro_fileno:
                raise OSError("sem socket")
            return self._fileno

    def test_fechada_pelo_psycopg2(self):
        self.assertFalse(db._ligacao_viva(self._Lig(closed=2)))

    def test_sem_socket_e_dada_como_boa(self):
        """Na dúvida, usar — descartar ligações boas seria pior."""
        self.assertTrue(db._ligacao_viva(self._Lig(erro_fileno=True)))
        self.assertTrue(db._ligacao_viva(self._Lig(fileno=None)))

    def test_socket_legivel_significa_morta(self):
        """A outra ponta fechou: o socket fica legível com 0 bytes (EOF)."""
        with mock.patch("select.select", return_value=([10], [], [])):
            self.assertFalse(db._ligacao_viva(self._Lig()))

    def test_socket_parado_significa_viva(self):
        with mock.patch("select.select", return_value=([], [], [])):
            self.assertTrue(db._ligacao_viva(self._Lig()))

    def test_select_a_falhar_nao_descarta(self):
        with mock.patch("select.select", side_effect=OSError("select partiu")):
            self.assertTrue(db._ligacao_viva(self._Lig()))


class PoolTests(_BaseDb):
    def test_entrega_e_devolve_a_ligacao(self):
        lig = _LigacaoFalsa()
        pool = _PoolFalso(lig)
        with mock.patch.object(db, "_obter_pool", return_value=pool):
            with db.conexao() as conn:
                self.assertIs(conn, lig)
        self.assertEqual(lig.commits, 1)
        self.assertEqual(pool.devolvidas, [("reutilizada", lig)])

    def test_excecao_faz_rollback_e_devolve_ao_pool(self):
        lig = _LigacaoFalsa()
        pool = _PoolFalso(lig)
        with mock.patch.object(db, "_obter_pool", return_value=pool):
            with self.assertRaises(ValueError):
                with db.conexao():
                    raise ValueError("erro qualquer")
        self.assertEqual(lig.commits, 0)
        self.assertGreaterEqual(lig.rollbacks, 1)
        self.assertEqual(len(pool.devolvidas), 1,
                         "a ligação não voltou ao pool — fuga")
        self.assertEqual(pool.devolvidas[0][0], "reutilizada")

    def test_ligacao_quebrada_e_descartada_nao_devolvida(self):
        """Uma ligação que o Supabase fechou não pode voltar para o pool."""
        lig = _LigacaoFalsa()
        lig.closed = 1
        pool = _PoolFalso(lig)
        with mock.patch.object(db, "_obter_pool", return_value=pool):
            with db.conexao():
                pass
        fechadas = [d for d in pool.devolvidas if d[0] == "fechada"]
        self.assertTrue(fechadas,
                        "devolveu ao pool uma ligação já fechada")

    def test_falha_no_commit_nao_devolve_ligacao_boa(self):
        lig = _LigacaoFalsa()
        lig.falhar_commit = True
        pool = _PoolFalso(lig)
        with mock.patch.object(db, "_obter_pool", return_value=pool):
            with db.conexao():
                pass
        self.assertEqual(pool.devolvidas[0][0], "fechada",
                         "ligação com transacção partida foi reutilizada")

    def test_ligacao_morta_por_rede_e_descartada(self):
        """O caso perigoso: `closed == 0` mas a ligação morreu.

        Se voltar ao pool, envenena o worker — como `minconn=1`, o mesmo
        socket partido serve todos os pedidos seguintes daquele processo, e
        uma falha de rede momentânea deixava o site em baixo até reiniciar.
        """
        import psycopg2

        lig = _LigacaoFalsa()
        lig.closed = 0  # psycopg2 ainda não sabe
        pool = _PoolFalso(lig)
        with mock.patch.object(db, "_obter_pool", return_value=pool):
            with self.assertRaises(psycopg2.OperationalError):
                with db.conexao():
                    raise psycopg2.OperationalError("server closed the connection")
        self.assertEqual(pool.devolvidas[0][0], "fechada",
                         "ligação morta voltou ao pool como reutilizável")

    def test_erro_de_consulta_mantem_a_ligacao(self):
        """Erro de CONSULTA (SQL inválido, constraint) não estraga a ligação."""
        import psycopg2

        lig = _LigacaoFalsa()
        pool = _PoolFalso(lig)
        with mock.patch.object(db, "_obter_pool", return_value=pool):
            with self.assertRaises(psycopg2.IntegrityError):
                with db.conexao():
                    raise psycopg2.IntegrityError("violates foreign key")
        self.assertEqual(pool.devolvidas[0][0], "reutilizada",
                         "descartou uma ligação boa por causa de um erro de SQL")

    def test_pool_em_falha_cai_para_ligacao_directa(self):
        """Pool esgotado/erro não pode derrubar o pedido do utilizador."""
        directa = _LigacaoFalsa()
        pool = _PoolFalso()
        pool.getconn_erro = RuntimeError("pool exhausted")
        with mock.patch.object(db, "_obter_pool", return_value=pool), \
                mock.patch.object(db, "_ligacao_nova", return_value=directa):
            with db.conexao() as conn:
                self.assertIs(conn, directa)
        self.assertEqual(directa.commits, 1)
        self.assertTrue(db._pool_desativado,
                        "o pool devia ficar desligado após falhar")
        self.assertEqual(directa.fechada, 1,
                         "ligação directa tem de ser fechada no fim")


class InterruptorTests(_BaseDb):
    def test_variavel_de_ambiente_desliga_o_pool(self):
        for valor, esperado in (("0", False), ("false", False), ("no", False),
                                ("off", False), ("1", True), ("", True)):
            with self.subTest(valor=valor):
                with mock.patch.dict(os.environ, {"GOSHINSHO_DB_POOL": valor}):
                    self.assertEqual(db._pool_ativo(), esperado)

    def test_com_pool_desligado_usa_ligacao_directa_e_fecha(self):
        directa = _LigacaoFalsa()
        with mock.patch.dict(os.environ, {"GOSHINSHO_DB_POOL": "0"}), \
                mock.patch.object(db, "_ligacao_nova", return_value=directa), \
                mock.patch.object(db, "_obter_pool") as obter:
            with db.conexao() as conn:
                self.assertIs(conn, directa)
        obter.assert_not_called()
        self.assertEqual(directa.commits, 1)
        self.assertEqual(directa.fechada, 1)

    def test_sem_connection_string_erra_alto(self):
        from goshinsho.config import Config

        with mock.patch.object(Config, "POSTGRES_CONNECTION_STRING", ""):
            with self.assertRaises(RuntimeError):
                db._conn_str()


class FonteUnicaTests(unittest.TestCase):
    """Os cinco serviços delegam no MESMO módulo.

    Não é preciosismo: este projecto já teve três implementações do roteamento
    de voz a divergir (22/10) e duas da sanitização XTTS. Cinco cópias de
    `_conn()` é a mesma armadilha.
    """

    SERVICOS = ("forum_service", "artigo_service", "leitura_service",
                "leitura_uso_service", "leitura_progresso_service")

    def test_todos_delegam_no_modulo_db(self):
        import importlib

        for nome in self.SERVICOS:
            with self.subTest(servico=nome):
                mod = importlib.import_module(f"goshinsho.services.{nome}")
                from goshinsho.services.db import _Conexao

                self.assertTrue(
                    callable(getattr(mod, "_conn", None)),
                    f"{nome} já não tem `_conn`")
                self.assertTrue(
                    callable(getattr(mod, "_conexao", None)),
                    f"{nome} não importa `conexao` de services.db")
                conn = mod._conn()
                self.assertIsInstance(conn, _Conexao)

    def test_nao_ha_psycopg2_connect_espalhado(self):
        """Só `services/db.py` abre ligações.

        Se alguém voltar a escrever `psycopg2.connect(...)` num serviço, o pool
        deixa de valer nesse caminho — e o custo de ~770 ms volta sem ninguém
        notar.
        """
        import pathlib
        import re

        raiz = pathlib.Path(__file__).resolve().parent.parent / "goshinsho"
        permitido = {"services/db.py"}
        ofensores = []
        for caminho in raiz.rglob("*.py"):
            rel = str(caminho.relative_to(raiz))
            if rel in permitido:
                continue
            fonte = caminho.read_text(encoding="utf-8")
            if re.search(r"psycopg2\.connect\s*\(", fonte):
                ofensores.append(rel)
        self.assertEqual(ofensores, [], "ligações abertas fora de services/db.py")


class SemNH1Tests(unittest.TestCase):
    """A listagem do fórum faz um número FIXO de consultas.

    ⚠️ BUG CORRIGIDO (2026-10-28)
    `list_topicos` chamava `_ultimas_postagens_resumo(cur, id)` dentro de um
    `for topico in topicos` — uma consulta por tópico. Com cada consulta ao
    Supabase a ~190 ms, a página do fórum com 20 tópicos pagava ~3,8 s **só** a
    montar as caixas. Medido antes/depois: 1762 ms → 537 ms (5 tópicos).

    Este teste não olha ao tempo (que varia com a rede): conta as consultas.
    Se alguém voltar a pôr a consulta dentro do ciclo, o número cresce com os
    tópicos e o teste falha.
    """

    def _contar_consultas(self, n_topicos):
        from goshinsho.services import forum_service

        consultas = []

        class _Cursor:
            description = [("id",), ("titulo",), ("descricao",), ("autor_id",),
                           ("autor_nome",), ("created_at",), ("status",),
                           ("updated_at",), ("qtd_mensagens",),
                           ("ultima_atividade",)]

            def execute(self, sql, params=None):
                consultas.append(" ".join(sql.split())[:40])

            def fetchone(self):
                return (0,)

            def fetchall(self):
                # A 1ª consulta é o COUNT; a 2ª devolve os tópicos.
                if consultas and "COUNT(*)" in consultas[-1]:
                    return ()
                return [
                    (f"id{i}", f"Título {i}", "", "autor", "Nome", None,
                     "aberto", None, 1, None)
                    for i in range(n_topicos)
                ]

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class _Conn:
            def cursor(self):
                return _Cursor()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with mock.patch.object(forum_service, "_conn", return_value=_Conn()):
            forum_service.list_topicos(page=1, per_page=max(n_topicos, 1))
        return len(consultas)

    def test_numero_de_consultas_nao_cresce_com_os_topicos(self):
        poucos = self._contar_consultas(3)
        muitos = self._contar_consultas(20)
        self.assertEqual(
            poucos, muitos,
            f"consultas crescem com o nº de tópicos ({poucos} → {muitos}): "
            f"o N+1 voltou")

    def test_uma_so_chamada_ao_lote_por_listagem(self):
        """`_postagens_em_lote` é chamada UMA vez, não uma vez por tópico.

        O teste anterior conta `cur.execute`; este prende o contrato do lado do
        chamador, que é onde o N+1 vivia (`for topico in topicos: ...`).
        """
        from goshinsho.services import forum_service

        class _Cursor:
            description = [("id",), ("titulo",), ("descricao",), ("autor_id",),
                           ("autor_nome",), ("created_at",), ("status",),
                           ("updated_at",), ("qtd_mensagens",),
                           ("ultima_atividade",)]

            def execute(self, sql, params=None):
                self._sql = " ".join(sql.split())

            def fetchone(self):
                return (0,)

            def fetchall(self):
                if "COUNT(*)" in getattr(self, "_sql", ""):
                    return ()
                return [
                    (f"id{i}", f"T{i}", "", "a", "N", None, "aberto", None, 1, None)
                    for i in range(6)
                ]

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class _Conn:
            def cursor(self):
                return _Cursor()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with mock.patch.object(forum_service, "_conn", return_value=_Conn()), \
                mock.patch.object(forum_service, "_postagens_em_lote",
                                  return_value={}) as lote:
            forum_service.list_topicos(page=1, per_page=6)
        self.assertEqual(lote.call_count, 1,
                         "o resumo das postagens voltou a ser pedido por tópico")
        ids = lote.call_args[0][1]
        self.assertEqual(len(ids), 6, "o lote não recebeu todos os tópicos")


if __name__ == "__main__":
    unittest.main()
