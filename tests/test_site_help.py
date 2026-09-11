"""Detecção de perguntas sobre o PRÓPRIO SITE (site_info) e sua resposta.

Contexto (2026-09-11): uma usuária viu "📖 Leitura Colaborativa" no menu do app,
ao lado do Chat, e perguntou ao chat o que era. O chat — que só sabia consultar
os Escritos — buscou o termo no acervo doutrinário, não encontrou, e respondeu
que o recurso "não é um conceito do acervo" e que "nada nas instruções deste
agente fala em leitura colaborativa". O produto oferecia algo na tela e o
assistente negava a existência disso.

⚠️ O RISCO DA CORREÇÃO É O FALSO POSITIVO: se uma pergunta doutrinária for
classificada como "sobre o site", ela sai do acervo e perde a resposta real —
que é o produto. Por isso os dois blocos de teste abaixo são igualmente
importantes, e o de perguntas doutrinárias usa perguntas REAIS dos usuários.
"""
import unittest

from goshinsho.services import site_info


class DetectaPerguntaSobreOSiteTests(unittest.TestCase):
    """Perguntas que DEVEM ser desviadas para a resposta sobre o site."""

    def test_perguntas_reais_que_originaram_a_correcao(self):
        """As duas perguntas literais da usuária (painel de perguntas)."""
        casos = (
            'O que vc oferece como "leitura colaborativa" é o que significa',
            'Na apresentação do agente, vc oferece "leitura colaborativa". '
            "Depois cada segmento de obra. Como o usuario usa essa proposta "
            "aqui nesse agente?",
        )
        for q in casos:
            with self.subTest(pergunta=q[:44]):
                self.assertTrue(site_info.is_site_help_question(q))

    def test_recursos_nomeados(self):
        casos = ("o que é leitura colaborativa?",
                 "Como funciona a Leitura Colaborativa?",
                 "tem forum de estudos?",
                 "o que é o aviso de independência?",
                 "onde leio a política de privacidade?",
                 "o que dizem os termos de uso?",
                 "para que serve o meta pixel?")
        for q in casos:
            with self.subTest(pergunta=q):
                self.assertTrue(site_info.is_site_help_question(q))

    def test_rotas_de_documento(self):
        for q in ("o que tem em /privacidade?",
                  "me explique /aviso-independencia",
                  "para que serve /doacao"):
            with self.subTest(pergunta=q):
                self.assertTrue(site_info.is_site_help_question(q))

    def test_uso_do_produto(self):
        casos = ("como eu uso isso aqui no site",
                 "o que voce oferece nesse site?",
                 "quais sao as funcionalidades do goshinsho?",
                 "como me cadastro?",
                 "como faço uma doação?",
                 "quem criou o goshinsho?")
        for q in casos:
            with self.subTest(pergunta=q):
                self.assertTrue(site_info.is_site_help_question(q))

    def test_audio_dos_textos(self):
        """Inclui 'ouço' (o-u-ç-o), que um padrão ingênuo erra."""
        casos = ("como ouço o audio do texto?",
                 "como escuto o audio",
                 "onde baixo o audio",
                 "quero ouvir o texto",
                 "como ouvir os escritos")
        for q in casos:
            with self.subTest(pergunta=q):
                self.assertTrue(site_info.is_site_help_question(q))

    def test_dados_e_privacidade(self):
        casos = ("o goshinsho guarda meus dados?",
                 "voces armazenam minhas conversas?",
                 "posso excluir minha conta?",
                 "como apagar meu histórico?")
        for q in casos:
            with self.subTest(pergunta=q):
                self.assertTrue(site_info.is_site_help_question(q))

    def test_relacao_com_a_igreja_exige_produto_e_vinculo(self):
        casos = ("voces são oficiais? tem vinculo com a igreja?",
                 "esse site é oficial da igreja messiânica?",
                 "o Goshinsho é vinculado à Igreja Messiânica Mundial?")
        for q in casos:
            with self.subTest(pergunta=q):
                self.assertTrue(site_info.is_site_help_question(q))


class NaoDetectaPerguntaDoutrinariaTests(unittest.TestCase):
    """Perguntas que NÃO podem ser desviadas — são o produto do chat.

    Todas são perguntas REAIS do acervo de usuários (painel /admin/perguntas).
    """

    def test_perguntas_reais_dos_usuarios(self):
        casos = (
            "Quais são as orientações de Meishu-Sama em relação ao uso do "
            "microondas nos lares de membros messiânicos",
            "O que Meishu-Sama fala sobre os dentes",
            "Casamento entre pessoas de nacionalidades diferentes",
            "O canto da boca e a fisionomia em relação ao desejo",
            "O que Meishu-Sama fala a respeito do povo africano",
            "deus esta no comando de tudo ? frase de meishu sama",
            "detalhar como conduzir o Johrei em quem já teve um rim retirado",
            "O que significa Goshinsho, o seu nome",
            "1 - Porque o mal foi necessário, 4 tipos de mal, qual é o significado",
            "O ensinamento existe no corpus do goshinsho exatamente sob esse título",
            "Até hoje houve por parte da Igreja uma grande parcimônia na "
            "divulgação dos Escritos",
            "Traga todos os escritos sobre esse assunto na íntegra",
        )
        for q in casos:
            with self.subTest(pergunta=q[:44]):
                self.assertFalse(site_info.is_site_help_question(q))

    def test_igreja_sozinha_nao_desvia(self):
        """'Igreja' é assunto doutrinário/histórico legítimo.

        Exigir produto E vínculo evita capturar perguntas sobre a Igreja em si.
        """
        casos = ("o que Meishu-Sama diz sobre a Igreja",
                 "como era a Igreja na época de Meishu-Sama",
                 "a Igreja Messiânica foi perseguida?")
        for q in casos:
            with self.subTest(pergunta=q):
                self.assertFalse(site_info.is_site_help_question(q))

    def test_ouvir_em_contexto_doutrinario(self):
        casos = ("o que Meishu-Sama diz sobre ouvir",
                 "a importancia de ouvir os conselhos",
                 "como escutar a voz de Deus")
        for q in casos:
            with self.subTest(pergunta=q):
                self.assertFalse(site_info.is_site_help_question(q))

    def test_pergunta_longa_e_pedido_de_conteudo(self):
        """Perguntas longas são pedidos de conteúdo, não dúvidas de uso."""
        longa = ("Explique detalhadamente como funciona a causa e efeito na "
                 "vida das pessoas segundo os ensinamentos, " + "e também " * 100)
        self.assertFalse(site_info.is_site_help_question(longa))


class ContextoEFallbackTests(unittest.TestCase):
    """O contexto injetado e a resposta de segurança."""

    def test_contexto_descreve_as_duas_partes(self):
        texto = site_info.site_help_context()
        self.assertIn("Leitura Colaborativa", texto)
        self.assertIn("Chat", texto)
        # O nome não pode ser apresentado como leitura conjunta de IA.
        self.assertIn("BIBLIOTECA", texto.upper())

    def test_contexto_menciona_os_documentos(self):
        texto = site_info.site_help_context()
        for doc in ("Termos de Uso", "Política de Privacidade",
                    "Aviso de Independência"):
            self.assertIn(doc, texto)

    def test_instrucoes_proibem_negar_a_existencia(self):
        texto = site_info.site_help_instructions()
        self.assertIn("PROIBIDO", texto)
        self.assertIn("não existe", texto)

    def test_fallback_nunca_e_vazio(self):
        """Regressão: antes retornava "" para idioma != "Português".

        O nome do idioma chega com e sem acento conforme o chamador, e isso
        bastava para esvaziar a resposta — o usuário ficava sem nada.
        """
        for lang in ("Português", "Portugues", "português", "English",
                     "Español", "", "日本語", "العربية"):
            with self.subTest(lang=lang):
                self.assertGreater(len(site_info.site_help_fallback(lang)), 100)

    def test_fallback_nao_nega_o_recurso(self):
        texto = site_info.site_help_fallback("Portugues").lower()
        self.assertNotIn("não existe", texto)
        self.assertNotIn("não é um conceito", texto)
        self.assertIn("leitura colaborativa", texto)


if __name__ == "__main__":
    unittest.main()
