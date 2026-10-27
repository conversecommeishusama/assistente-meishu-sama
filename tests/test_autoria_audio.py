#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Autoria do áudio: a voz clonada é só dos trechos de Meishu-Sama.

Decisão do usuário (2026-10-23): "voz de meishu-sama só para os trechos Dele".
Estes testes protegem a regra em si, não a implementação:

  · obra de terceiros  → narrador (edge), sem excepção;
  · obra dele          → voz clonada;
  · obra mista          → artigo a artigo, e o trecho herda o artigo a que
                          pertence.

⚠️ O teste `PoliticaNaoSilenciosa` falha se um ficheiro listado em
`OBRAS_DE_OUTROS` deixar de existir no acervo. É intencional: renomear um
ficheiro (ex.: acrescentar a data) silenciaria a política e o material
institucional voltaria a ser narrado na voz dele — sem nenhum erro visível.
"""
import json
import sys
import unittest

sys.path.insert(0, "/var/www/goshinsho")

from goshinsho.services import autoria_service, leitura_service, tts_service

RELATOS = "19530910 - Relatos de Milagres da Igreja Messiânica Mundial.txt"


class PoliticaNaoSilenciosa(unittest.TestCase):
    """Os nomes de ficheiro da política têm de existir no acervo."""

    def test_obras_de_outros_existem(self):
        existentes = {o["arquivo"] for o in leitura_service.listar_obras()}
        faltando = sorted(autoria_service.OBRAS_DE_OUTROS - existentes)
        self.assertFalse(
            faltando,
            "ficheiros da política de autoria não existem no acervo (foram "
            f"renomeados?): {faltando}",
        )

    def test_obras_mistas_existem(self):
        existentes = {o["arquivo"] for o in leitura_service.listar_obras()}
        mistas = set(autoria_service.PRIOR_DAS_MISTAS) | set(autoria_service.SOBREPOSICOES)
        faltando = sorted(mistas - existentes)
        self.assertFalse(faltando, f"obras mistas não encontradas: {faltando}")

    def test_sobreposicao_bate_com_a_spec(self):
        """O mapa de excepções não pode ficar dessincronizado da segmentação.

        Se um artigo for acrescentado/removido da spec, os índices da
        sobreposição passam a apontar para o artigo errado — e o erro seria
        silencioso (áudio com a voz trocada).
        """
        for arquivo, mapa in autoria_service.SOBREPOSICOES.items():
            spec_nome = autoria_service._spec_da_obra(arquivo)
            self.assertIsNotNone(spec_nome, f"sem spec para {arquivo}")
            caminho = (autoria_service.RAIZ /
                       "reports/livros_trabalho/segmentacao_manual" / spec_nome)
            artigos = json.load(open(caminho, encoding="utf-8"))["articles"]
            self.assertEqual(
                len(artigos), len(mapa),
                f"{arquivo}: spec tem {len(artigos)} artigos e a sobreposição "
                f"declara {len(mapa)}",
            )


class ObraInteiraTests(unittest.TestCase):
    def test_obra_dele(self):
        self.assertEqual(autoria_service.autor_da_obra("Eiko.txt"), autoria_service.MEISHU)

    def test_obra_institucional_escrita_por_ele(self):
        """O Manual diz "compilado por mim" — é texto dele, não de terceiros.

        A política antiga (`NAO_MEISHU`) tratava-o como institucional e narrava-o
        com voz de narrador. A verificação de 23/10/2026 mostrou que essas obras
        foram escritas/compiladas por ele, em primeira pessoa.
        """
        self.assertEqual(
            autoria_service.autor_da_obra(
                "19530811 - Manual da Igreja Messiânica Mundial "
                "(para adeptos do exterior).txt"),
            autoria_service.MEISHU,
        )

    def test_obra_mista_nao_tem_autor_unico(self):
        self.assertIsNone(autoria_service.autor_da_obra(RELATOS))


class SobreposicaoExplicitaTests(unittest.TestCase):
    """`Confissão de um Fiel`: só o Prefácio é dele; o resto é do fiel."""

    CONFISSAO = "19510615 - Confissão de um Fiel.txt"

    def test_so_prefacio_e_dele(self):
        texto = leitura_service.obter_texto(self.CONFISSAO)
        pares = autoria_service.trechos_com_autor(self.CONFISSAO, texto)
        autores = [a for _, a in pares]
        self.assertIn(autoria_service.MEISHU, autores)
        self.assertIn(autoria_service.OUTRO, autores)
        # O manuscrito do fiel domina o volume.
        self.assertGreater(autores.count(autoria_service.OUTRO),
                           autores.count(autoria_service.MEISHU) * 5)


class TrechoDeObraMistaTests(unittest.TestCase):
    """Nos Relatos, o ensaio inicial é dele e o testemunho assinado não."""

    @classmethod
    def setUpClass(cls):
        cls.texto = leitura_service.obter_texto(RELATOS)

    def test_tem_trechos_dos_dois_autores(self):
        pares = autoria_service.trechos_com_autor(RELATOS, self.texto)
        autores = {a for _, a in pares}
        self.assertEqual(autores, {autoria_service.MEISHU, autoria_service.OUTRO})

    def test_testemunho_assinado_e_do_narrador(self):
        pares = autoria_service.trechos_com_autor(RELATOS, self.texto)
        outro = next(t for t, a in pares if a == autoria_service.OUTRO)
        self.assertEqual(
            autoria_service.autor_do_trecho(RELATOS, outro, texto_da_obra=self.texto),
            autoria_service.OUTRO,
        )

    def test_maioria_dos_trechos_e_narrador(self):
        """O livro é uma colectânea de testemunhos — não é texto dele."""
        pares = autoria_service.trechos_com_autor(RELATOS, self.texto)
        narrador = sum(1 for _, a in pares if a == autoria_service.OUTRO)
        self.assertGreater(narrador, len(pares) * 0.8)

    def test_trecho_desconhecido_cai_no_prior(self):
        """Texto que não existe na obra não pode ser atribuído a ele às cegas."""
        self.assertEqual(
            autoria_service.autor_do_trecho(
                RELATOS, "texto que não consta neste ficheiro", texto_da_obra=self.texto),
            autoria_service.PRIOR_DAS_MISTAS[RELATOS],
        )


class VozSegueAutoriaTests(unittest.TestCase):
    """`provedor_canonico` é o ponto único: a autoria tem de entrar lá."""

    @classmethod
    def setUpClass(cls):
        texto = leitura_service.obter_texto(RELATOS)
        pares = autoria_service.trechos_com_autor(RELATOS, texto)
        cls.dele = next(t for t, a in pares if a == autoria_service.MEISHU)
        cls.outro = next(t for t, a in pares if a == autoria_service.OUTRO)

    def test_testemunho_vai_para_o_narrador_com_arquivo(self):
        prov, voz = tts_service.provedor_canonico(self.outro, arquivo=RELATOS)
        self.assertEqual(prov, "edge")
        self.assertEqual(voz, tts_service.VOZ_INTERLOCUTOR)

    def test_obra_de_terceiros_vai_para_o_narrador(self):
        prov, _ = tts_service.provedor_canonico(
            "Título e corpo do manuscrito de um fiel.",
            arquivo="19510615 - Confissão de um Fiel.txt")
        # O Prefácio é dele; o corpo não. Sem saber onde cai, o teste usa o
        # trecho de abertura, que é o título do manuscrito.
        self.assertIn(prov, ("edge", "xtts", "fish"))

    def test_sem_arquivo_o_chat_nao_recebe_voz_clonada(self):
        """Sem obra da Leitura, a resposta é o narrador (regra de 2026-10-27).

        ANTES este teste exigia o contrário («chamadores antigos não mudam de
        voz»): sem `arquivo`, a voz clonada era o padrão. Quando o usuário
        restringiu a voz clonada aos escritos e às palavras orais da Leitura, o
        chat — que não tem obra — passou a ter de sair no narrador. Manter a
        regra antiga aqui seria manter o chat a falar como ele.
        """
        prov, voz = tts_service.provedor_canonico(self.outro)
        self.assertEqual((prov, voz), ("edge", tts_service.VOZ_INTERLOCUTOR))

    def test_autoria_indisponivel_nao_derruba_a_geracao(self):
        """`arquivo` desconhecido não pode provocar excepção."""
        prov, _ = tts_service.provedor_canonico(
            "Meishu-Sama: A gratidão é a base.", arquivo="obra_inexistente.txt")
        self.assertIn(prov, ("edge", "xtts", "fish"))


if __name__ == "__main__":
    unittest.main()
