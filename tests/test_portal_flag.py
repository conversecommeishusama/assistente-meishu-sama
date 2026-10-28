"""Portal Goshinsho — a flag que separa o protótipo da produção.

O portal (página principal + área de Artigos + restrição da Palavra Oral)
nasceu numa cópia independente em `/var/www/goshinsho-portal` e essa cópia
derivou: 24 dos 65 `.py` eram ficheiros autónomos, 9 já divergiam, e alguns
existiam apenas lá, nunca no git — incluindo a restrição da Palavra Oral, que
ficou escrita e nunca chegou ao `main`.

Passou tudo a viver aqui, e `Config.PORTAL_ENABLED` decide. Estes testes
existem para prender as DUAS metades da decisão:

  · com a flag LIGADA, o portal serve o que promete (página principal, artigos,
    bloqueio da Palavra Oral sem vazar texto);
  · com a flag DESLIGADA, o site que está no ar não muda — a landing de
    captação, o texto da Palavra Oral e as rotas do portal (que nem existem).

O segundo grupo é o mais importante: um teste que só verificasse o portal
ligado deixaria passar exactamente o acidente que se quer evitar.
"""

import contextlib
import os
import re
import unittest
from unittest import mock

from goshinsho.config import Config


@contextlib.contextmanager
def _app_com_portal(ligado: bool):
    """App com a flag no estado pedido, ATÉ AO FIM DO PEDIDO.

    Tem de ser um context manager e não uma função que devolve a app: a
    restrição da Palavra Oral lê `Config.PORTAL_ENABLED` em tempo de pedido
    (ver `leitura_routes._restricao_oral_ativa`). Se o patch saísse mal a app
    fosse criada, o `test_client()` já corria com a flag a False e o teste
    media o vazio — foi exactamente o que aconteceu à primeira.
    """
    with mock.patch.object(Config, "PORTAL_ENABLED", ligado):
        from goshinsho import create_app

        yield create_app(include_web=True)


def _rotas(app, caminho):
    return [r for r in app.url_map.iter_rules() if str(r) == caminho]


class FlagDoPortalTests(unittest.TestCase):
    def test_com_flag_desligada_o_portal_nao_e_registado(self):
        with _app_com_portal(False) as app:
            endpoints = {r.endpoint for r in app.url_map.iter_rules()}
        self.assertNotIn("portal.portal_home", endpoints)
        self.assertFalse([e for e in endpoints if e.startswith("portal.")])

    def test_com_flag_desligada_a_raiz_e_a_landing_de_captacao(self):
        with _app_com_portal(False) as app:
            raiz = _rotas(app, "/")
        self.assertEqual([r.endpoint for r in raiz], ["web.index"])

    def test_com_flag_ligada_a_raiz_e_a_pagina_do_portal(self):
        with _app_com_portal(True) as app:
            raiz = [r.endpoint for r in _rotas(app, "/")]
        # O Flask resolve rotas iguais pela ORDEM de registo; o portal vem
        # primeiro de propósito (ver goshinsho/__init__.py).
        self.assertEqual(raiz[0], "portal.portal_home")
        self.assertIn("web.index", raiz)

    def test_com_flag_ligada_os_artigos_existem(self):
        with _app_com_portal(True) as app:
            endpoints = {r.endpoint for r in app.url_map.iter_rules()}
        for nome in ("portal.artigos_lista", "portal.artigos_novo",
                     "portal.artigo_detalhe", "portal.api_listar_artigos",
                     "portal.api_criar_artigo", "portal.api_comentar_artigo"):
            with self.subTest(endpoint=nome):
                self.assertIn(nome, endpoints)

    def test_config_le_a_variavel_de_ambiente(self):
        """A flag tem de vir do .env, não estar fixa no código."""
        for valor, esperado in (("1", True), ("0", False), ("", False),
                                ("true", True), ("yes", True)):
            with self.subTest(valor=valor):
                with mock.patch.dict(os.environ,
                                     {"GOSHINSHO_PORTAL_ENABLED": valor}):
                    from goshinsho.config import _env_bool
                    self.assertEqual(
                        _env_bool("GOSHINSHO_PORTAL_ENABLED", default=False),
                        esperado)


class RestricaoPalavraOralTests(unittest.TestCase):
    """A restrição da Palavra Oral só existe com o portal ligado.

    O texto NÃO pode ir para o HTML: não é uma camada de CSS por cima — se o
    texto fosse enviado, qualquer pessoa o leria no "ver código-fonte".
    """

    @classmethod
    def setUpClass(cls):
        from goshinsho.services import leitura_service

        cls.servico = leitura_service
        cls.obra_oral = next(
            (o["arquivo"] for o in leitura_service.listar_obras()
             if leitura_service.obra_exige_conta(o["arquivo"])),
            None,
        )
        cls.texto_oral = (leitura_service.obter_texto(cls.obra_oral)
                          if cls.obra_oral else "")

    def test_ha_obra_oral_para_testar(self):
        self.assertIsNotNone(
            self.obra_oral,
            "sem obra da Palavra Oral o resto desta classe não prova nada")

    def test_flag_desligada_serve_o_texto_como_sempre(self):
        with _app_com_portal(False) as app:
            resposta = app.test_client().get(f"/forum/leitura/{self.obra_oral}")
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.get_data(as_text=True)
        self.assertNotIn("leitura-bloqueio", corpo)
        # Um excerto real do ficheiro tem de estar no HTML.
        excerto = re.sub(r"\s+", " ", self.texto_oral[400:480]).strip()
        self.assertIn(excerto, re.sub(r"\s+", " ", corpo))

    def test_flag_ligada_bloqueia_sem_conta(self):
        with _app_com_portal(True) as app:
            resposta = app.test_client().get(f"/forum/leitura/{self.obra_oral}")
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.get_data(as_text=True)
        self.assertIn("leitura-bloqueio", corpo)
        self.assertIn("Palavra Oral", corpo)

    def test_flag_ligada_nao_vaza_um_unico_byte_do_texto(self):
        with _app_com_portal(True) as app:
            corpo = app.test_client().get(
                f"/forum/leitura/{self.obra_oral}").get_data(as_text=True)
        # Vários excertos ao longo do ficheiro: um único que aparecesse já
        # significaria que o texto saiu.
        for inicio in (200, 400, 5000, 40000):
            excerto = re.sub(r"\s+", " ", self.texto_oral[inicio:inicio + 60]).strip()
            if len(excerto) < 25:
                continue
            with self.subTest(inicio=inicio):
                self.assertNotIn(excerto, re.sub(r"\s+", " ", corpo))

    def test_flag_ligada_nao_mostra_a_barra_de_audio_do_texto_bloqueado(self):
        """Sem texto na página, "Ouvir" e "Sugerir edição" não teriam o que fazer."""
        with _app_com_portal(True) as app:
            corpo = app.test_client().get(
                f"/forum/leitura/{self.obra_oral}").get_data(as_text=True)
        self.assertNotIn('id="leitura-barra-play"', corpo)
        self.assertNotIn('data-audio-ler', corpo)


class CacheDosDestaquesTests(unittest.TestCase):
    """A página principal do Portal não pode abrir duas conexões só para
    escolher dois artigos.

    Medido em 28/10/2026: `artigo_mais_recente()` (1,24 s) e
    `artigo_ultimo_comentario()` (1,09 s) abriam a SUA própria conexão ao
    Postgres — 2,3 s numa página de entrada. `destaques_da_home()` faz as duas
    na mesma conexão e guarda o resultado 60 s.
    """

    def setUp(self):
        from goshinsho.services import artigo_service

        self.servico = artigo_service
        self._antes = dict(artigo_service._destaques_cache)
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        self.servico._destaques_cache.clear()
        self.servico._destaques_cache.update(self._antes)

    def test_segunda_chamada_nao_toca_no_banco(self):
        chamadas = []
        self.servico._destaques_cache.update({"em": None, "valor": (None, None)})
        with mock.patch.object(self.servico, "_conn",
                               side_effect=chamadas.append) as conn:
            conn.return_value.__enter__.return_value.cursor.side_effect = (
                RuntimeError("sem banco neste teste"))
            primeiro = self.servico.destaques_da_home()
            n_depois_da_primeira = len(chamadas)
            segundo = self.servico.destaques_da_home()
        self.assertEqual(primeiro, segundo)
        self.assertEqual(len(chamadas), n_depois_da_primeira,
                         "a segunda chamada voltou a abrir conexão")

    def test_cache_de_artigos_vazios_tambem_e_guardada(self):
        """Um site sem artigos publicados não pode pagar 1,2 s por visita.

        O sentinela da cache era `(None, None)`, que é exactamente o resultado
        quando não há artigos — a cache nunca servia nada e cada visita ia ao
        banco outra vez.
        """
        self.servico._destaques_cache.update({"em": None, "valor": (None, None)})
        with mock.patch.object(self.servico, "_conn") as conn:
            # `with _conn() as conn: with conn.cursor() as cur:` — o cursor é
            # ele próprio um context manager, por isso `cur` é o valor que o
            # `__enter__` do cursor devolve.
            cur = (conn.return_value.__enter__.return_value
                   .cursor.return_value.__enter__.return_value)
            cur.fetchone.return_value = None
            cur.description = []
            self.assertEqual(self.servico.destaques_da_home(), (None, None))
            self.assertIsNotNone(self.servico._destaques_cache["em"])
            antes = conn.call_count
            self.assertEqual(self.servico.destaques_da_home(), (None, None))
            self.assertEqual(conn.call_count, antes,
                             "o resultado vazio não foi guardado na cache")

    def test_ttl_zero_desliga_a_cache(self):
        self.servico._destaques_cache.update({"em": None, "valor": (None, None)})
        with mock.patch.object(self.servico, "_conn") as conn:
            cur = (conn.return_value.__enter__.return_value
                   .cursor.return_value.__enter__.return_value)
            cur.fetchone.return_value = None
            cur.description = []
            self.servico.destaques_da_home(ttl_s=0)
            self.servico.destaques_da_home(ttl_s=0)
            self.assertEqual(conn.call_count, 2)

    def test_falha_de_banco_nao_envenena_a_cache(self):
        self.servico._destaques_cache.update({"em": None, "valor": (None, None)})
        with mock.patch.object(self.servico, "_conn",
                               side_effect=RuntimeError("banco em baixo")):
            self.assertEqual(self.servico.destaques_da_home(), (None, None))
        self.assertIsNone(self.servico._destaques_cache["em"],
                          "a falha ficou cacheada e a página nunca recuperaria")


class CacheDosTopicosTests(unittest.TestCase):
    """Mesmo problema, no fórum: 1,2 s para escolher 3 tópicos."""

    def setUp(self):
        from goshinsho import portal_routes

        self.mod = portal_routes
        self._antes = dict(portal_routes._topicos_cache)
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        self.mod._topicos_cache.clear()
        self.mod._topicos_cache.update(self._antes)

    def test_segunda_chamada_usa_a_cache(self):
        self.mod._topicos_cache.update({"em": None, "valor": ([], 0)})
        with mock.patch.object(self.mod.forum_service, "list_topicos",
                               return_value={"topicos": [], "total": 0}) as lst:
            self.mod._topicos_recentes()
            primeira = lst.call_count
            self.mod._topicos_recentes()
        self.assertEqual(lst.call_count, primeira,
                         "a segunda chamada voltou a consultar o fórum")

    def test_falha_do_forum_nao_derruba_a_pagina(self):
        self.mod._topicos_cache.update({"em": None, "valor": ([], 0)})
        with mock.patch.object(self.mod.forum_service, "list_topicos",
                               side_effect=RuntimeError("banco em baixo")):
            topicos, total = self.mod._topicos_recentes()
        self.assertEqual((topicos, total), ([], 0))


class NavegacaoDeRetornoAposLoginTests(unittest.TestCase):
    """`_next_seguro`: o destino de retorno não pode ser um trampolim.

    A tela de login é confiável; aceitar `?next=` arbitrário transformaria essa
    confiança num redirect aberto para phishing.
    """

    def test_aceita_caminho_interno(self):
        from goshinsho.routes import _next_seguro

        for bom in ("/forum/leitura/Eiko.txt", "/portal/artigos", "/app-pt?q=oi"):
            with self.subTest(destino=bom):
                self.assertTrue(_next_seguro(bom))

    def test_recusa_url_absoluta_e_protocolo_relativo(self):
        from goshinsho.routes import _next_seguro

        for mau in ("https://site-malicioso.example/",
                    "http://site-malicioso.example/",
                    "//site-malicioso.example/",
                    "/\\site-malicioso.example/",
                    "javascript:alert(1)",
                    ""):
            with self.subTest(destino=mau):
                self.assertFalse(_next_seguro(mau))


class CabecalhoUnificadoTests(unittest.TestCase):
    """A "pele" é escolhida pela flag, não por dois conjuntos de templates.

    Antes, produção e portal tinham ficheiros separados a divergir em silêncio.
    Agora é um só e `portal_ativo` decide — estes testes prendem as duas saídas.
    """

    ORDEM = ["leitura.html", "leitura_texto.html", "app.html", "forum.html",
             "doacao.html", "termos.html", "privacidade.html",
             "aviso_independencia.html", "forum_novo.html", "forum_topico.html",
             "forum_regras.html"]

    def test_todos_os_templates_escolhem_o_cabecalho_pela_flag(self):
        from jinja2 import Environment, FileSystemLoader

        base = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "templates")
        env = Environment(loader=FileSystemLoader(base))
        for nome in self.ORDEM:
            with self.subTest(template=nome):
                fonte = open(os.path.join(base, nome), encoding="utf-8").read()
                # Compila (sintaxe Jinja válida) …
                env.from_string(fonte)
                # … e as duas peles estão presentes.
                self.assertIn("portal_ativo", fonte)
                self.assertIn("_portal_header.html", fonte)
                self.assertIn('class="topbar"', fonte)


if __name__ == "__main__":
    unittest.main()
