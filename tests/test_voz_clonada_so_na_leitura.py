#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A voz clonada do Meishu-Sama não existe no Chat do Goshinsho.

Regra do usuário (2026-10-27): «a voz clonada é para ser opção apenas nos
escritos e nas palavras orais da Leitura Colaborativa». O chat responde na voz
do assistente — citar Meishu-Sama não é ser Meishu-Sama.

⚠️ CONTEXTO DO BUG QUE ESTES TESTES PROTEGEM

O chat e a Leitura Colaborativa usam o MESMO botão, o mesmo JS e a mesma rota
(`POST /forum/api/tts`). A preferência de voz da Leitura fica no `localStorage`
da origem (`goshinsho-leitura-voz-edge`), e o botão "Ouvir resposta" do chat
lia-a: quem escolhesse "Meishu-Sama" na Leitura passava a ouvir o chat na voz
clonada, sem nunca o ter pedido ali. O pedido saía sem `arquivo` — e o servidor
não tinha como distinguir chat de Leitura.

A correção tem duas camadas, e ambas são testadas aqui:

  1. o botão do chat força a voz do narrador (`VOZ_CHAT`);
  2. o servidor recusa "meishu" sem uma obra real da Leitura, porque a voz não
     pode depender de JS que um cliente pode contornar.

Se alguém "simplificar" a rota para `voz=dados.get("voz")`, estes testes
quebram. É intencional.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, "/var/www/goshinsho")

from goshinsho.services import tts_service

RAIZ = "/var/www/goshinsho"
OBRA = "19510520 - Luz dos Ensinamentos.txt"


class ObraDaleituraTests(unittest.TestCase):
    """`obra_da_leitura` é a prova de que o pedido veio da Leitura."""

    def test_obra_real_do_acervo(self):
        self.assertEqual(tts_service.obra_da_leitura(OBRA), OBRA)

    def test_sem_arquivo_nao_e_leitura(self):
        for valor in (None, "", "   "):
            with self.subTest(arquivo=valor):
                self.assertIsNone(tts_service.obra_da_leitura(valor))

    def test_caminho_embutido_e_recusado(self):
        """Travessia de caminho não pode passar por obra do corpus."""
        for valor in ("../.env", "sub/obra.txt", "/etc/passwd.txt",
                      "..\\obra.txt"):
            with self.subTest(arquivo=valor):
                self.assertIsNone(tts_service.obra_da_leitura(valor))

    def test_obra_inexistente_e_recusada(self):
        self.assertIsNone(tts_service.obra_da_leitura("Obra Que Nao Existe.txt"))

    def test_sem_extensao_txt_e_recusada(self):
        self.assertIsNone(tts_service.obra_da_leitura(OBRA[:-4]))

    def test_voz_clonada_so_com_obra(self):
        self.assertTrue(tts_service.voz_clonada_autorizada(OBRA))
        self.assertFalse(tts_service.voz_clonada_autorizada(None))
        self.assertFalse(tts_service.voz_clonada_autorizada(""))


class ApiTtsRecusaVozClonadaNoChatTests(unittest.TestCase):
    """A rota é a porta única de todos os clientes web — inclusive do chat."""

    def setUp(self):
        # App mínimo: só o blueprint da Leitura. Montar a app completa em teste
        # puxaria índices e base de dados que não têm nada a ver com a regra.
        from flask import Flask

        from goshinsho.leitura_routes import leitura_bp

        app = Flask(__name__)
        app.register_blueprint(leitura_bp)
        self.client = app.test_client()

    def _post(self, corpo):
        """Faz o pedido e devolve (voz pedida ao serviço, resposta HTTP)."""
        with mock.patch.object(tts_service, "sintetizar") as sint:
            sint.return_value = os.path.join(RAIZ, "static", "js", "app.js")
            resp = self.client.post("/forum/api/tts", json=corpo)
        voz = sint.call_args.kwargs.get("voz") if sint.called else None
        return voz, resp

    def test_chat_sem_arquivo_sai_no_narrador(self):
        """O caso do chat: voz=meishu, sem obra. Tem de sair em Antônio."""
        voz, resp = self._post({"texto": "Meishu-Sama: A gratidão é a base.",
                                "voz": "meishu"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(voz, "antonio",
                         "o chat não pode falar na voz clonada")

    def test_arquivo_falso_sai_no_narrador(self):
        """Um nome que não é obra do corpus não serve para autorizar a voz."""
        for falso in ("chat", "resposta.txt", "../.env"):
            with self.subTest(arquivo=falso):
                voz, resp = self._post({"texto": "A gratidão é a base.",
                                        "voz": "meishu", "arquivo": falso})
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(voz, "antonio")

    def test_leitura_com_obra_mantem_a_voz_clonada(self):
        """Na Leitura a opção continua a existir — é o que o usuário pediu."""
        voz, resp = self._post({"texto": "A gratidão é a base.",
                                "voz": "meishu", "arquivo": OBRA})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(voz, "meishu",
                         "a Leitura Colaborativa perdeu a voz clonada")

    def test_vozes_neurais_nao_sao_afetadas(self):
        for voz_pedida in ("antonio", "francisca", "thalita"):
            with self.subTest(voz=voz_pedida):
                voz, resp = self._post({"texto": "A gratidão é a base.",
                                        "voz": voz_pedida})
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(voz, voz_pedida)

    def test_sem_voz_explicita_nao_usa_clonada(self):
        voz, resp = self._post({"texto": "A gratidão é a base."})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(voz, "antonio")

    def test_a_recusa_fica_no_log_uma_unica_vez(self):
        """Um aviso que não se vê não serve de nada — mas não pode inundar.

        O nível efectivo da app é WARNING: um `info` nunca aparecia no journal.
        E o chat faz prefetch de um pedido por trecho — sem o guarda, seriam
        centenas de linhas iguais.
        """
        from goshinsho import leitura_routes

        leitura_routes._avisou_voz_clonada = False
        self.addCleanup(setattr, leitura_routes, "_avisou_voz_clonada",
                        leitura_routes._avisou_voz_clonada)

        with self.assertLogs("goshinsho.leitura_routes", level="WARNING") as logs:
            self._post({"texto": "A gratidão é a base.", "voz": "meishu"})
            self._post({"texto": "A gratidão é a base.", "voz": "meishu"})

        avisos = [l for l in logs.output if "narrador" in l]
        self.assertEqual(len(avisos), 1, logs.output)


class BotaoDoChatNaoHerdaVozDaleituraTests(unittest.TestCase):
    """O `localStorage` da Leitura não pode decidir a voz do chat."""

    def setUp(self):
        caminho = os.path.join(RAIZ, "static", "js", "leitura_tts.js")
        with open(caminho, encoding="utf-8") as f:
            self.fonte = f.read()

    def test_opts_do_chat_forcam_a_voz_do_narrador(self):
        self.assertIn("if (!isLeitura) opts.voz = VOZ_CHAT;", self.fonte)

    def test_voz_do_chat_nao_e_clonada(self):
        trecho = self.fonte.split("var VOZ_CHAT =")[1].split(";")[0]
        self.assertIn('"antonio"', trecho)
        self.assertNotIn("meishu", trecho.lower())

    def test_seletor_de_voz_nao_e_consultado_fora_da_leitura(self):
        """`verificarVozMeishu` sai antes do fetch quando não há seletor."""
        funcao = self.fonte.split("function verificarVozMeishu()")[1]
        antes_do_fetch = funcao.split("fetch(")[0]
        self.assertIn("leitura-voz-select", antes_do_fetch)
        self.assertIn("return", antes_do_fetch)


if __name__ == "__main__":
    unittest.main()
