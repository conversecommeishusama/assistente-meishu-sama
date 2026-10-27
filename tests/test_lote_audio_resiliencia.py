"""O lote de áudio não pode falhar em silêncio (scripts/pre_gerar_lote_orais.py
e scripts/gerar_texto_worker_v2.py).

⚠️ CONTEXTO DOS BUGS QUE ESTES TESTES PROTEGEM (2026-10-27)

1. O worker fazia `except Exception: pass` no ramo do edge-tts. Um trecho ficava
   sem áudio, o worker saía com rc=0 e o orquestrador escrevia "concluído". A
   falha não chegava a nenhum relatório: era indistinguível de sucesso.
2. O orquestrador dava TODA obra terminada como `feito` no checkpoint, mesmo
   com trechos em branco. Sem `--lista`, essas obras nunca eram retentadas.
3. O log dizia "concluído" tanto para uma obra que gerou 1.200 trechos agora
   como para uma que só fez cache hit — não havia forma de saber se o lote
   estava a produzir alguma coisa.
4. `_esperar_mp3` esperava 600 s fixos por uma resposta que podia nunca chegar,
   e uma falha do daemon era indistinguível de lentidão.

Se alguém voltar a "simplificar" o tratamento de erros, estes testes quebram.
É intencional.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _carregar(nome_ficheiro, nome_modulo):
    """Importa um script de `scripts/` pelo caminho (não são um pacote)."""
    caminho = os.path.join(RAIZ, "scripts", nome_ficheiro)
    spec = importlib.util.spec_from_file_location(nome_modulo, caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome_modulo] = modulo
    spec.loader.exec_module(modulo)
    return modulo


# O orquestrador importa o worker por nome (`from gerar_texto_worker_v2 import
# FALHAS_DIR`), por isso `scripts/` tem de estar no sys.path.
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
worker = _carregar("gerar_texto_worker_v2.py", "gerar_texto_worker_v2")
lote = _carregar("pre_gerar_lote_orais.py", "pre_gerar_lote_orais")


class EsperarMp3Tests(unittest.TestCase):
    """O que aconteceu a uma tarefa tem de ser dito, não adivinhado."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="esperar_mp3_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.spool = os.path.join(self.tmp, "d0")
        for sub in ("", "done", "erro"):
            os.makedirs(os.path.join(self.spool, sub), exist_ok=True)
        self.destino = os.path.join(self.tmp, "saida.mp3")
        self.tarefa = os.path.join(self.spool, "tarefa_1.json")

    def test_mp3_aparece_e_ok(self):
        open(self.tarefa, "w").close()

        def gerar():
            with open(self.destino, "wb") as f:
                f.write(b"MP3")
        import threading
        threading.Timer(0.2, gerar).start()

        estado, motivo = worker._esperar_mp3(self.destino, self.tarefa,
                                            self.spool, limite=10)
        self.assertEqual((estado, motivo), ("ok", ""))

    def test_tarefa_no_erro_falha_de_imediato(self):
        self.assertTrue(os.path.exists(self.tarefa) is False)
        open(self.tarefa, "w").close()
        os.replace(self.tarefa, os.path.join(self.spool, "erro",
                                             os.path.basename(self.tarefa)))
        inicio = time.time()
        estado, motivo = worker._esperar_mp3(self.destino, self.tarefa,
                                            self.spool, limite=30)
        self.assertEqual(estado, "erro")
        self.assertIn("erro", motivo)
        self.assertLess(time.time() - inicio, 5,
                        "devia desistir logo, não esperar o limite")

    def test_done_sem_mp3_e_falha(self):
        open(self.tarefa, "w").close()
        os.replace(self.tarefa, os.path.join(self.spool, "done",
                                             os.path.basename(self.tarefa)))
        estado, motivo = worker._esperar_mp3(self.destino, self.tarefa,
                                            self.spool, limite=30)
        self.assertEqual(estado, "erro")
        self.assertIn("mp3", motivo)

    def test_mp3_de_zero_bytes_nao_conta(self):
        open(self.tarefa, "w").close()
        open(self.destino, "wb").close()  # 0 bytes: ainda a ser escrito
        estado, _ = worker._esperar_mp3(self.destino, self.tarefa, self.spool,
                                        limite=1)
        self.assertEqual(estado, "timeout")


class _ServicoFalso:
    """Substituto de `tts_service` para exercitar o laço do worker."""

    VOZ_MEISHU_CACHE = "meishu:v2"

    def __init__(self, tmp, provedor="edge", erro_em=None):
        self.tmp = tmp
        self.provedor = provedor
        self.erro_em = erro_em or set()
        self.chamadas = []

    def provedor_canonico(self, texto, rate="+0%", *, arquivo=None):
        return self.provedor, "pt-BR-AntonioNeural"

    def _trecho_sem_fala(self, texto):
        return False

    def caminho_em_cache(self, texto, rate="+0%", *, arquivo=None):
        return None

    def sintetizar(self, texto, voz=None, rate="+0%", *, arquivo=None):
        self.chamadas.append(texto)
        if self.chamadas.index(texto) in self.erro_em:
            raise RuntimeError("edge-tts timeout após 120s")
        return os.path.join(self.tmp, "x.mp3")

    def _preparar_texto_xtts(self, texto):
        return texto

    def _chave_cache(self, prov, texto, rate):
        return f"chave{abs(hash(texto)) % 1000}"

    def _cache_dir(self):
        return self.tmp

    def _chaves_historicas(self, prov, voz):
        return ()

    def _fish_disponivel(self):
        return False


class WorkerFalhasTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="worker_falhas_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.falhas_dir = os.path.join(self.tmp, "tts_falhas")
        self.spool = os.path.join(self.tmp, "spool")
        os.makedirs(self.spool, exist_ok=True)
        self.obra = os.path.join(self.tmp, "obra.txt")
        with open(self.obra, "w") as f:
            f.write("Primeiro trecho do texto.\n\nSegundo trecho do texto.\n\n"
                    "Terceiro trecho do texto.\n")

    def test_trecho_que_falha_nao_desaparece(self):
        servico = _ServicoFalso(self.tmp, erro_em={1})
        with redirect_stderr(io.StringIO()) as err:
            rc = worker.processar_obra(self.obra, self.spool, servico,
                                       dir_falhas=self.falhas_dir)

        self.assertEqual(rc, 1, "obra com trecho sem áudio deve sair != 0")
        relatorio = json.load(open(os.path.join(self.falhas_dir,
                                               "obra.txt.json")))
        self.assertEqual(len(relatorio["falhas"]), 1, relatorio)
        falha = relatorio["falhas"][0]
        self.assertEqual(falha["provedor"], "edge")
        self.assertIn("timeout", falha["motivo"])
        self.assertIn("Segundo trecho", falha["excerto"])
        self.assertIn("FALHA", err.getvalue())

    def test_obra_sem_falhas_sai_limpa(self):
        servico = _ServicoFalso(self.tmp)
        with redirect_stderr(io.StringIO()):
            rc = worker.processar_obra(self.obra, self.spool, servico,
                                       dir_falhas=self.falhas_dir)
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(os.path.join(self.falhas_dir,
                                                    "obra.txt.json")))

    def test_relatorio_antigo_e_apagado_no_sucesso(self):
        """Uma obra que falhou e depois passou não pode continuar na lista."""
        os.makedirs(self.falhas_dir, exist_ok=True)
        caminho = os.path.join(self.falhas_dir, "obra.txt.json")
        with open(caminho, "w") as f:
            json.dump({"arquivo": "obra.txt", "falhas": [{"indice": 0}]}, f)

        with redirect_stderr(io.StringIO()):
            rc = worker.processar_obra(self.obra, self.spool,
                                       _ServicoFalso(self.tmp),
                                       dir_falhas=self.falhas_dir)
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(caminho))

    def test_resumo_distingue_gerado_de_cache(self):
        """'concluído' tem de dizer quantos trechos são novos."""
        servico = _ServicoFalso(self.tmp)
        resumos = os.path.join(self.tmp, "tts_resumos")
        with redirect_stderr(io.StringIO()) as err:
            worker.processar_obra(self.obra, self.spool, servico,
                                  dir_falhas=self.falhas_dir,
                                  dir_resumos=resumos)
        linha = [l for l in err.getvalue().splitlines() if "FIM:" in l][0]
        self.assertIn("3 novos", linha, linha)
        self.assertIn("falhas 0", linha, linha)

        dados = json.load(open(os.path.join(resumos, "obra.txt.json")))
        self.assertEqual(dados["novos"], 3)
        self.assertEqual(dados["edge_novos"], 3)
        self.assertEqual(dados["edge_cache"], 0)
        self.assertEqual(dados["falhas"], 0)
        self.assertEqual(dados["trechos"], 3)


class ResumoDaObraTests(unittest.TestCase):
    """O log do lote tem de dizer o que foi feito, não só que acabou."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="resumo_obra_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.resumos = os.path.join(self.tmp, "tts_resumos")
        os.makedirs(self.resumos, exist_ok=True)
        patcher = mock.patch.object(lote, "RESUMOS_DIR", self.resumos)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _escrever(self, nome, **campos):
        with open(os.path.join(self.resumos, f"{nome}.json"), "w") as f:
            json.dump({"arquivo": nome, **campos}, f)

    def test_diz_novos_e_cache(self):
        self._escrever("a.txt", novos=12, edge_cache=300, xtts_cache=40)
        texto = lote._resumo_da_obra("a.txt")
        self.assertIn("12 novos", texto)
        self.assertIn("340 em cache", texto)

    def test_diz_falhas_quando_existem(self):
        self._escrever("b.txt", novos=0, edge_cache=5, xtts_cache=1, falhas=3)
        self.assertIn("3 falhas", lote._resumo_da_obra("b.txt"))

    def test_obra_sem_contagens_avisa(self):
        """Worker que morreu a meio não pode parecer concluído com sucesso."""
        self.assertIn("sem contagens", lote._resumo_da_obra("nao_existe.txt"))


class ResumoDoLoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="resumo_lote_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.falhas_dir = os.path.join(self.tmp, "tts_falhas")
        os.makedirs(self.falhas_dir, exist_ok=True)
        patcher = mock.patch.object(lote, "FALHAS_DIR", self.falhas_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _escrever(self, nome, n):
        with open(os.path.join(self.falhas_dir, f"{nome}.json"), "w") as f:
            json.dump({"arquivo": nome, "falhas": [{"indice": i}
                                                   for i in range(n)]}, f)

    def test_resumo_conta_trechos_e_obras(self):
        self._escrever("a.txt", 2)
        self._escrever("b.txt", 3)
        with redirect_stdout(io.StringIO()) as out:
            lote._resumir_falhas([])
        texto = out.getvalue()
        self.assertIn("5 trecho(s) sem áudio em 2 obra(s)", texto)
        self.assertIn("a.txt", texto)
        self.assertIn("b.txt", texto)
        self.assertIn(self.falhas_dir, texto)

    def test_resumo_sem_falhas_nao_alarma(self):
        with redirect_stdout(io.StringIO()) as out:
            lote._resumir_falhas([])
        self.assertIn("nenhuma falha", out.getvalue())

    def test_worker_morto_sem_relatorio_aparece(self):
        with redirect_stdout(io.StringIO()) as out:
            lote._resumir_falhas(["morreu.txt"])
        self.assertIn("morreu.txt", out.getvalue())
        self.assertIn("não terminou", out.getvalue())


class CheckpointDoLoteTests(unittest.TestCase):
    """Uma obra com falhas não pode entrar no checkpoint como concluída."""

    def test_codigo_de_saida_do_worker_decide_o_checkpoint(self):
        with open(os.path.join(RAIZ, "scripts", "pre_gerar_lote_orais.py")) as f:
            fonte = f.read()
        trecho = fonte.split("if p.returncode == 0:")[1].split("concluidas += 1")[0]
        self.assertIn("feitos.add(arquivo)", trecho,
                      "só obra com rc=0 pode entrar no checkpoint")
        self.assertIn("com_falhas.append(arquivo)", trecho,
                      "obra com rc!=0 tem de ser registada como falha")


if __name__ == "__main__":
    unittest.main()
