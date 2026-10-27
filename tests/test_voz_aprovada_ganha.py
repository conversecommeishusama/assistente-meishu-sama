#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A voz APROVADA ganha sempre à voz local (XTTS).

Decisão do usuário (2026-09-09): a voz clonada aprovada é a do Fish Audio
(kikivoice remasterizada). O XTTS local é o substituto quando a chave não está
configurada.

⚠️ CONTEXTO DO BUG (2026-10-27)

Sem a chave Fish no `.env`, `provedor_canonico` devolve XTTS e a procura no
cache começava pela chave canónica do XTTS (`xtts:meishu:v2`). O áudio aprovado
(`fish:meishu-hybrid`) só era considerado DEPOIS — e as chaves históricas do
XTTS incluem-no, mas em último lugar. Consequência: 13.906 trechos que tinham o
áudio aprovado, já pago, passaram a ser servidos pela voz local.

O usuário ouviu o Gokowa-roku nº 14 e reconheceu a voz que já tinha descartado:
naquela obra, 113 dos 117 trechos com áudio tinham as duas versões em disco e o
app escolhia a local.

Regra fixada aqui: se o áudio aprovado existe, é ele que se serve — e o lote não
gasta CPU a gerar outro por cima.
"""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "/var/www/goshinsho")

from goshinsho.services import tts_service

TEXTO = "Meishu-Sama: A gratidão é a base de tudo."
RATE = "+0%"
# Obra real do corpus: desde 27/10 a voz clonada só existe na Leitura, e é
# `arquivo` que o prova. Sem isto, a resposta passa a ser o narrador.
OBRA = "19510520 - Luz dos Ensinamentos.txt"


class VozAprovadaGanhaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="voz_aprovada_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        p = mock.patch.object(tts_service, "_cache_dir", return_value=self.tmp)
        p.start()
        self.addCleanup(p.stop)
        # Sem chave Fish: é o estado real de produção (o `.env` não a tem).
        p2 = mock.patch.object(tts_service, "_fish_disponivel", return_value=False)
        p2.start()
        self.addCleanup(p2.stop)
        p3 = mock.patch.object(tts_service, "_autor_do_trecho", return_value="meishu")
        p3.start()
        self.addCleanup(p3.stop)

    def _criar(self, provedor: str, voz: str, bytes_=b"MP3"):
        chave = tts_service._chave_cache(f"{provedor}:{voz}", TEXTO, RATE)
        caminho = os.path.join(self.tmp, f"{chave}.mp3")
        with open(caminho, "wb") as f:
            f.write(bytes_)
        return caminho

    def test_aprovado_ganha_ao_xtts_canonico(self):
        aprovado = self._criar("fish", tts_service.FISH_MEISHU_CACHE)
        self._criar("xtts", tts_service.VOZ_MEISHU_CACHE)

        self.assertEqual(tts_service.caminho_em_cache(TEXTO, arquivo=OBRA), aprovado)

    def test_aprovado_ganha_no_sintetizar_sem_regerar(self):
        aprovado = self._criar("fish", tts_service.FISH_MEISHU_CACHE)
        self._criar("xtts", tts_service.VOZ_MEISHU_CACHE)

        with mock.patch.object(tts_service, "_sintetizar_xtts") as xtts, \
             mock.patch.object(tts_service, "_gerar_edge") as edge:
            saida = tts_service.sintetizar(TEXTO, voz="meishu", arquivo=OBRA)

        self.assertEqual(saida, aprovado)
        xtts.assert_not_called()
        edge.assert_not_called()

    def test_sem_aprovado_usa_o_xtts_existente(self):
        """Sem áudio aprovado, um mp3 local válido continua a servir."""
        local = self._criar("xtts", tts_service.VOZ_MEISHU_CACHE)
        self.assertEqual(tts_service.caminho_em_cache(TEXTO, arquivo=OBRA), local)

    def test_mp3_aprovado_de_zero_bytes_nao_conta(self):
        """Zero bytes é falha de geração, não cache (regra de 2026-10-23)."""
        self._criar("fish", tts_service.FISH_MEISHU_CACHE, b"")
        self.assertIsNone(tts_service.caminho_em_cache(TEXTO, arquivo=OBRA))

    def test_narrador_nao_recebe_voz_aprovada(self):
        """O áudio aprovado é da voz clonada; o narrador não o pode herdar."""
        self._criar("fish", tts_service.FISH_MEISHU_CACHE)
        with mock.patch.object(tts_service, "_autor_do_trecho", return_value="outro"):
            caminho = tts_service.caminho_em_cache(TEXTO, arquivo=OBRA)
        self.assertIsNone(caminho, "texto de terceiros não pode servir voz clonada")

    def test_o_lote_nao_regera_sobre_o_aprovado(self):
        """O worker pergunta ao serviço; não repete a regra por conta própria."""
        with open("/var/www/goshinsho/scripts/gerar_texto_worker_v2.py",
                  encoding="utf-8") as f:
            fonte = f.read()
        self.assertIn("caminho_em_cache(trecho, arquivo=arquivo)", fonte)


class AmostraDoDaemonTests(unittest.TestCase):
    """O daemon tem uma omissão própria, e mais antiga que a do serviço.

    ⚠️ 2026-10-27: `pre_gerar_lote_orais.py` lançava o daemon SEM `--amostra`,
    por isso o lote sintetizava com `amostra_meishu_30s_limpa.wav` (a antiga) e
    gravava sob a chave `xtts:meishu:v2` — ficheiros que o app serve, sem nada
    que os distinga dos bons. Foi assim que a voz descartada voltou ao ar.
    """

    def setUp(self):
        with open("/var/www/goshinsho/scripts/daemon_xtts.py",
                  encoding="utf-8") as f:
            self.daemon = f.read()
        with open("/var/www/goshinsho/scripts/pre_gerar_lote_orais.py",
                  encoding="utf-8") as f:
            self.lote = f.read()

    def test_a_omissao_do_daemon_e_a_amostra_antiga(self):
        """A omissão do daemon não é a do serviço — é essa a armadilha."""
        omissao = self.daemon.split("AMOSTRA_PADRAO =")[1].split("\n")[0]
        self.assertIn("amostra_meishu_30s_limpa.wav", omissao)

    def test_o_lote_passa_a_amostra_explicitamente(self):
        self.assertIn('"--amostra"', self.lote,
                      "o lote tem de dizer ao daemon qual voz usar")
        self.assertIn("_amostra_do_servico()", self.lote)

    def test_amostra_inexistente_aborta_em_vez_de_gerar(self):
        """Gerar com outra voz é pior do que não gerar: os ficheiros parecem bons."""
        self.assertIn("a abortar", self.lote)


if __name__ == "__main__":
    unittest.main()
