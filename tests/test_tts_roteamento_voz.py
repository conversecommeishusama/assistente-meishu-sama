"""Roteamento de VOZ nos áudios da Leitura Colaborativa (tts_service).

Cobre a decisão "A" de 2026-09-10: fala de TERCEIROS nos escritos vai para o
narrador (Antônio), não para a voz clonada do Meishu-Sama.

⚠️ CONTEXTO DO BUG QUE ESTES TESTES PROTEGEM
Antes, o rótulo era genérico (`^\\s*([^:]{2,40}):`) e QUALQUER narração com
dois-pontos era tratada como fala de terceiro → 390 trechos dos ORAIS saíram com
a voz do Antônio por engano. Os casos abaixo (`Pensei:`, `Vejam:`, `Eu:`,
`Não só isso:`, `Resposta:`) são EXEMPLOS REAIS dos textos e devem continuar com
a voz do Meishu-Sama. Se alguém "simplificar" a regex para um rótulo genérico,
estes testes quebram — é intencional.
"""
import unittest

from goshinsho.services import tts_service


class FalanteMeishuTests(unittest.TestCase):
    """Rótulos que são a VOZ DO MEISHU-SAMA (Fish / voz clonada)."""

    def test_rotulos_explicitos_do_meishu(self):
        for t in ("Meishu-Sama: Pratico há cerca de vinte anos.",
                  "Grão-Mestre: Assim diz o ensinamento.",
                  "Mestre: Vejamos."):
            with self.subTest(texto=t):
                self.assertEqual(tts_service._identificar_falante(t), "meishu")

    def test_resposta_e_do_meishu(self):
        """`Resposta:` é a resposta DELE (132 trechos) — não é terceiro."""
        t = ("Resposta: Não se pode falar disso de modo geral. A verdade difere "
             "conforme o ponto de vista e a posição de cada um.")
        self.assertEqual(tts_service._identificar_falante(t), "meishu")

    def test_narracao_do_meishu_nao_e_terceiro(self):
        """Regressão do bug de 390 trechos: 1ª pessoa e conectivos são dele."""
        casos = (
            'Pensei: "Mesmo aplicando tantas injeções, ainda tenho febre."',
            'Perguntei: "Por que se apossou dela?"',
            'Pensava: "Ah, mãe, como deve estar sofrendo seu coração..."',
            "Vejam: o medo da guerra, o medo da doença e o medo da pobreza.",
            "Não só isso: as afirmações de nossa Igreja não se limitam à religião.",
            "Observem: esse método corta a carne, faz sair sangue, raspa os ossos.",
            "Recordando: no verão de 1941, há nove anos, comecei com nevralgia.",
        )
        for t in casos:
            with self.subTest(texto=t[:40]):
                self.assertEqual(tts_service._identificar_falante(t), "")

    def test_eu_e_narracao_do_meishu(self):
        """`Eu:` (35 trechos) é o próprio Meishu relatando um diálogo.

        Contexto real ("Conversas sobre a Fé"): `Eu: "Quem é o senhor?"` /
        `Ela: "Este aqui é um deus."` — o "Eu" é o Mestre.
        """
        self.assertEqual(tts_service._identificar_falante('Eu: "Quem é o senhor?"'), "")

    def test_narracao_com_dois_pontos_nao_e_terceiro(self):
        """O bug original: narração com ":" não é fala de ninguém."""
        casos = (
            "Outra coisa: minha teoria sobre mineração é bastante diferente.",
            "Naquela época aconteceu algo misterioso: havia uma estátua de Kannon.",
            "A Igreja: a preocupação com doenças desaparece.",
        )
        for t in casos:
            with self.subTest(texto=t[:38]):
                self.assertEqual(tts_service._identificar_falante(t), "")


class FalanteTerceiroTests(unittest.TestCase):
    """Rótulos de TERCEIRO → narrador/Antônio (decisão "A", 2026-09-10)."""

    def test_forma_de_tratamento_com_nome(self):
        casos = ("Sr. Mayama: Ouvi dizer que o senhor foi de automóvel até Kyoto.",
                 "Sr. Tanikawa: O vaso com cabeça de galo é uma peça excelente.",
                 "Sr. Cartier: Estou muito grato por ter vindo especialmente.",
                 "Sr. Nakamura: Os leitores americanos pediram que informássemos.",
                 "Dr. Braden: Vim ao Japão e observei diversas religiões.",
                 "Sra. Cartier: Vamos publicar com o título \"O leque que cura\".",
                 "Srta. Tazuke: Este senhor é redator-chefe da maior revista.",
                 "Sr. H: O senhor é um grande apreciador de arte.")
        for t in casos:
            with self.subTest(texto=t[:34]):
                self.assertEqual(tts_service._identificar_falante(t), "outro")

    def test_inicial_de_sobrenome(self):
        """`Sr. H`, `Sr. Kondō`: inicial e nome com acento japonês."""
        self.assertEqual(tts_service._identificar_falante("Sr. Kondō: Parece que o senhor..."),
                         "outro")

    def test_funcoes_de_midia(self):
        casos = ("Repórter: A fé pode, de fato, salvar o sofrimento humano?",
                 "Moderador: Tomizō Ishii",
                 "Jornalista: Qual é a sua opinião?",
                 "Entrevistador: Como o senhor começou?")
        for t in casos:
            with self.subTest(texto=t[:30]):
                self.assertEqual(tts_service._identificar_falante(t), "outro")

    def test_pergunta_e_coletivo_e_parentesco(self):
        casos = ("Pergunta: Sobre a verdade.",
                 "Pergunta: Por que motivo existem o mal e o sofrimento?",
                 "Todos: Muito obrigado pelo seu tempo.",
                 "Participantes: Tatsu Oda, Kansaku Kataoka, Tatsuo Uesaka.",
                 "Esposa: Não, entende-se muito bem...")
        for t in casos:
            with self.subTest(texto=t[:30]):
                self.assertEqual(tts_service._identificar_falante(t), "outro")

    def test_ocupacao_anonimizada(self):
        """Falas citadas por Meishu-Sama com o falante anonimizado."""
        casos = ('Médico: "Não posso dizer com clareza, mas se for compatível..."',
                 "Político: O que há de mais importante a fazer, hoje, no Japão?",
                 'Chefe: "Você fica sempre atrás de uma cortina de bambu."',
                 'Promotor: "Você sabe o que é \'dinheiro para suborno\'?"')
        for t in casos:
            with self.subTest(texto=t[:28]):
                self.assertEqual(tts_service._identificar_falante(t), "outro")

    def test_interlocutor_mantem_comportamento_dos_orais(self):
        t = "Interlocutor: O senhor pratica caligrafia há muito tempo?"
        self.assertEqual(tts_service._identificar_falante(t), "outro")


class CoerenciaDeVozTests(unittest.TestCase):
    """A MESMA pessoa não pode alternar duas vozes no mesmo texto."""

    def test_tanikawa_com_e_sem_tratamento(self):
        """`Sr. Tanikawa:` (40) e `Tanikawa:` (55) são a mesma pessoa.

        Sem tratar o nome sem título, a entrevista alternaria narrador e voz
        clonada para o mesmo falante.
        """
        com = "Sr. Tanikawa: Como da vez passada, o vaso é uma peça excelente."
        sem = "Tanikawa: Desta vez chegou a edição Hōeidō das Cinquenta e Três Estações."
        self.assertEqual(tts_service._identificar_falante(com), "outro")
        self.assertEqual(tts_service._identificar_falante(sem), "outro")

    def test_falsos_positivos_que_nao_podem_entrar(self):
        """Títulos de tabela e listas: NÃO são fala.

        `Título:` (73), `Autor:` (20), `Endereço:` (20), `Variedade:` (5) são
        cabeçalhos de tabela/expediente. `Dragão` era capturado pela 1ª versão
        da regra (`dr` casando dentro de "Dragão").
        """
        casos = (
            'Título: "Carteira Vazia"',
            "Autor: Okada Jikan",
            "Endereço: 1-9, Fukagawa Morishita-chō, Kōtō-ku, Tóquio",
            "Variedade: Nōrin 32-gō",
            "Arroz: Prêmio especial, 3 pontos",
            "Igreja: Igreja Média Nyoirin",
            "Nome: Kazue Sannomiya (19)",
        )
        for t in casos:
            with self.subTest(texto=t[:32]):
                self.assertEqual(tts_service._identificar_falante(t), "")

    def test_dragao_nao_e_forma_de_tratamento(self):
        """Falso positivo real: `dr` casando dentro de "Dragão" (tabela)."""
        t = "Dragão — Deus — Parar — Escuridão — Negro"
        self.assertEqual(tts_service._identificar_falante(t), "")

    def test_editorial_e_metadado_nao_rotulo_de_fala(self):
        """Expediente da revista: metadado (edge), não fala de terceiro."""
        for t in ("Editor: Koizumi Morinosuke",
                  "Editora: Igreja Miroku do Japão",
                  "Gráfica: Taiyō Insatsu Kabushiki Gaisha"):
            with self.subTest(texto=t):
                self.assertEqual(tts_service._identificar_falante(t), "")


class MetadadoTests(unittest.TestCase):
    """Metadados continuam roteando para o narrador (decisão de 09/09)."""

    def test_metadados_conhecidos(self):
        casos = ("19520825 - Gosuiji-roku nº 12",
                 "[1º de agosto]",
                 "1º de janeiro do ano 23 da Era Showa (1948)",
                 "(Relato)",
                 "──────────")
        for t in casos:
            with self.subTest(texto=t[:32]):
                self.assertTrue(tts_service._eh_metadado(t))

    def test_fala_explicita_nunca_e_metadado(self):
        for t in ("Meishu-Sama: Pratico há cerca de vinte anos.",
                  "Interlocutor: O senhor pratica caligrafia?"):
            with self.subTest(texto=t[:32]):
                self.assertFalse(tts_service._eh_metadado(t))


class SemConteudoNarravelTests(unittest.TestCase):
    """Trechos só de pontuação não têm o que narrar (edge-tts recusaria)."""

    def test_apenas_simbolos(self):
        for t in ("──────────", "| | |", "****", "—", ""):
            with self.subTest(texto=t):
                self.assertTrue(tts_service._sem_conteudo_narravel(t))

    def test_texto_real_e_narravel(self):
        for t in ("Meishu-Sama: Pratico há cerca de vinte anos.", "1º de agosto"):
            with self.subTest(texto=t):
                self.assertFalse(tts_service._sem_conteudo_narravel(t))


class TrechoSemFalaTests(unittest.TestCase):
    """`_trecho_sem_fala`: união do caso cru + o que a PREPARAÇÃO esvazia.

    Esta é a checagem que o app usa para entregar uma PAUSA em vez de HTTP 500.

    ⚠️ CONTEXTO DO BUG (2026-09-11)
    A checagem anterior (`_sem_conteudo_narravel`) olhava só o texto CRU. Então
    `観 — 世 — 音` passava (tem kanji!), seguia para o provedor, que o recusava
    (`NoAudioReceived`) → **HTTP 500** → o front chamava
    `fallbackParaSpeechSynthesis` e a leitura INTEIRA caía para a voz do
    NAVEGADOR ("voz do Google"). Um separador de seção bastava para matar a
    leitura neural: em "Conversas sobre a Fé" o 1º está no trecho 6 (são 84).
    Ao todo: 200 trechos em 18 obras.
    """

    def test_separadores_e_tabelas(self):
        for t in ("──────────────────────────────────", "---",
                  "―――――――――・――――――――――", "| | |", "|:--- |:--- |", "|", "/"):
            with self.subTest(texto=t[:20]):
                self.assertTrue(tts_service._trecho_sem_fala(t))

    def test_kanji_que_vira_travessao(self):
        """Kanji removido na preparação deixa só travessão → nada a falar."""
        for t in ("観 — 世 — 音", "立 — 正 — 安 — 国"):
            with self.subTest(texto=t):
                self.assertTrue(tts_service._trecho_sem_fala(t))

    def test_kana_residual(self):
        """O kana (hiragana/katakana) também é removido — sobrava '(をぶ)'."""
        self.assertTrue(tts_service._trecho_sem_fala("(五大州を結ぶ)"))

    def test_fala_real_nunca_e_sem_fala(self):
        casos = ("Meishu-Sama: Pratico há cerca de vinte anos.",
                 "Sr. Mayama: Ouvi dizer que o senhor foi de automóvel a Kyoto.",
                 "Resposta: A verdade difere conforme o ponto de vista.",
                 "1º de agosto",
                 "A gratidão é a base de tudo.")
        for t in casos:
            with self.subTest(texto=t[:34]):
                self.assertFalse(tts_service._trecho_sem_fala(t))

    def test_kanji_isolado_sem_travessao_ainda_narra(self):
        """Se a preparação deixa texto, o trecho NÃO é tratado como sem fala.

        `(五大州を結ぶ)` vira vazio, mas um título com kanji E palavras
        latinas continua narrável — não pode virar pausa por engano.
        """
        t = "O Sutra do Lótus (法華経) é recitado"
        self.assertFalse(tts_service._trecho_sem_fala(t))


class KanaNaPreparacaoTests(unittest.TestCase):
    """A preparação remove kana E kanji (a voz pt-BR não lê nenhum dos dois)."""

    def test_kana_removido(self):
        # antes: "(五大州を結ぶ)" → "(をぶ)"  (kana ficava órfão)
        out = tts_service._preparar_texto_edge("(五大州を結ぶ)")
        self.assertNotIn("を", out)
        self.assertNotIn("ぶ", out)

    def test_kanji_removido(self):
        out = tts_service._preparar_texto_edge("観 — 世 — 音")
        self.assertNotIn("観", out)
        self.assertNotIn("世", out)

    def test_texto_latino_preservado(self):
        out = tts_service._preparar_texto_edge("Meishu-Sama: A gratidão é a base.")
        self.assertIn("gratidão", out)
        self.assertIn("base", out)


if __name__ == "__main__":
    unittest.main()
