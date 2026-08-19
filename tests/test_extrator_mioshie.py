#!/usr/bin/env python3
"""Teste do extrator Mioshie — verifica se as respostas do Meishu-Sama
após 〔御垂示〕 + Meishu-Sama: são capturadas (bug conhecido).

Uso:
  .venv/bin/python tests/test_extrator_mioshie.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraduzir_colecao import extrair_falas_mioshie  # noqa: E402


def test_resposta_apos_yuiji_meishu():
    """Caso Mioshie 1号: 〔御垂示〕 + Meishu-Sama: resposta.

    O bug: o while interno para na 1ª linha da resposta (que contém 'Meishu-Sama'),
    descartando a resposta. Este teste deve PASSAR após a correção.
    """
    jp_trecho = """Interlocutor: （お伺）昭和二十四年五月ごろ急に喘息となりました。
右御教示お願い申し上げます。

〔御垂示〕
Meishu-Sama: 大元愛善様というのは、別に、神様――御神体じゃないですがね。これは、やっぱり元にお帰り願ったらいいですね。

Interlocutor: （お伺）次の質問です。
"""
    falas = extrair_falas_mioshie(jp_trecho)
    meishu = [pt for quem, pt in falas if quem == "Meishu-Sama"]
    assert meishu, f"FALHOU: resposta Meishu-Sama não capturada. falas={falas}"
    assert "大元愛善様" in meishu[0], f"FALHOU: resposta sem o conteúdo esperado: {meishu[0][:60]}"
    print(f"✅ resposta capturada: {meishu[0][:50]}...")


def test_resposta_apos_yuiji_sem_rotulo():
    """Caso Mioshie 3号: 〔御垂示〕 sem rótulo Meishu-Sama: (formato 3号).

    Não deve quebrar com a correção.
    """
    jp_trecho = """Interlocutor: （お伺）本年二十歳の女、三年ほど前アブに眼の縁を刺されました。

〔御垂示〕
　これはなんでもないですよ。これはアブに刺された時内出血したのが、外に出きらないで、目の中に入って固まるんです。

Interlocutor: （お伺）次の質問です。
"""
    falas = extrair_falas_mioshie(jp_trecho)
    meishu = [pt for quem, pt in falas if quem == "Meishu-Sama"]
    assert meishu, f"FALHOU: resposta sem rótulo não capturada. falas={falas}"
    assert "アブ" in meishu[0], f"FALHOU: resposta sem conteúdo esperado: {meishu[0][:60]}"
    print(f"✅ resposta sem rótulo capturada: {meishu[0][:50]}...")


def test_perguntas_preservadas():
    """As perguntas (Interlocutor) não podem ser perdidas/alteradas pela correção."""
    jp_trecho = """Interlocutor: （お伺）第一の質問です。

〔御垂示〕
Meishu-Sama: 第一の答えです。

Interlocutor: （お伺）第二の質問です。

〔御垂示〕
Meishu-Sama: 第二の答えです。
"""
    falas = extrair_falas_mioshie(jp_trecho)
    inter = [pt for quem, pt in falas if quem == "Interlocutor"]
    meishu = [pt for quem, pt in falas if quem == "Meishu-Sama"]
    assert len(inter) == 2, f"FALHOU: esperava 2 perguntas, veio {len(inter)}: {inter}"
    assert len(meishu) == 2, f"FALHOU: esperava 2 respostas, veio {len(meishu)}: {meishu}"
    print(f"✅ perguntas preservadas ({len(inter)}), respostas capturadas ({len(meishu)})")


def test_sequencia_alternada():
    """A ordem deve ser: pergunta, resposta, pergunta, resposta..."""
    jp_trecho = """Interlocutor: （お伺）P1

〔御垂示〕
Meishu-Sama: R1

Interlocutor: （お伺）P2

〔御垂示〕
Meishu-Sama: R2
"""
    falas = extrair_falas_mioshie(jp_trecho)
    seq = [quem for quem, _ in falas]
    esperado = ["Interlocutor", "Meishu-Sama", "Interlocutor", "Meishu-Sama"]
    assert seq == esperado, f"FALHOU: sequência {seq} != esperado {esperado}"
    print(f"✅ sequência alternada correta: {seq}")


def test_formato_8gou():
    """Formato do 8号: 'Meishu-Sama: 〔御垂示〕' numa linha + resposta nas seguintes.

    Deve capturar a resposta (regressão da correção).
    """
    jp_trecho = """Interlocutor: （お伺）井上昇（二十七歳）昭和十八年中学にて体格検査の結果肋膜を発見。

Meishu-Sama: 〔御垂示〕
　樹脂――プラスチックの玉ですね。マイシン七十本――随分金がかかったですね。

Interlocutor: （お伺）牧野広生（八歳）二十六年九月、三尺くらいのカボチャ棚より落ち。

Meishu-Sama: 〔御垂示〕
　神経麻痺――病名については滑稽なんでね。
"""
    falas = extrair_falas_mioshie(jp_trecho)
    seq = [quem for quem, _ in falas]
    esperado = ["Interlocutor", "Meishu-Sama", "Interlocutor", "Meishu-Sama"]
    assert seq == esperado, f"FALHOU: sequência {seq} != {esperado}"
    meishu = [pt for quem, pt in falas if quem == "Meishu-Sama"]
    assert "樹脂" in meishu[0], f"FALHOU: 1ª resposta incompleta: {meishu[0][:40]}"
    assert "神経麻痺" in meishu[1], f"FALHOU: 2ª resposta incompleta: {meishu[1][:40]}"
    print(f"✅ formato 8号 OK: {len(meishu)} respostas capturadas")


if __name__ == "__main__":
    test_resposta_apos_yuiji_meishu()
    test_resposta_apos_yuiji_sem_rotulo()
    test_perguntas_preservadas()
    test_sequencia_alternada()
    test_formato_8gou()
    print("\n🎉 TODOS OS TESTES PASSARAM")
