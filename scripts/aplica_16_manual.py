"""Aplica manualmente os 16 casos recusados pelo guarda automático de
aplica_mesa_c.py -- de/para já verificados por leitura direta (count==1,
sem risco de duplicação), sem passar pelo passo de reescrita do DeepSeek.

Mesma segurança da automação: backup por obra, grava as duas cópias,
revalida âncora, reverte a obra inteira se a contagem de artigos mudar.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"

ITENS = [
    ("19480701-御讃歌集.txt",
     "tenha nascido e desvende os vários mistérios",
     "tenha nascido e de que se desvendem os vários mistérios"),
    ("19490625-自観叢書第1篇『結核と神霊療法』.txt",
     "Pensei que minha casa talvez tivesse reunido todas as infelicidades do mundo...\nDe fato, era uma casa miserável, que sufocava sob o sofrimento da doença e da pobreza.",
     "Minha casa era tão miserável, sufocando sob o sofrimento da doença e da pobreza, que chegava a parecer que reunia todas as infelicidades do mundo em uma só família."),
    ("19491005-自観叢書第4篇『奇蹟物語』.txt",
     "à medida que a religião se divulgava amplamente pela sociedade",
     "como nossa Igreja passou a ser subitamente divulgada para a sociedade"),
    ("19500420-自観叢書第10篇『神示の健康法』.txt",
     "o fato de eu ter feito essa descoberta significa que, chegada a hora, Deus a revelou através de mim para a salvação da humanidade. Isso significa que",
     "o fato de eu ter feito essa descoberta — chegada a hora, Deus a revelou através de mim para a salvação da humanidade — significa que"),
    ("19510615-一信者の告白.txt",
     "tanto maior quanto maior for a quantidade de elementos objetivos que o compõem",
     "tanto maior quanto maior for a quantidade de elementos objetivos que o compõem e quanto maior for a veracidade deles"),
    ("19510815-結核の革命的療法.txt",
     "Minha única insatisfação com a medicina moderna foi ter que me limitar",
     "Minha única insatisfação com a medicina moderna foi ter que me limitar, por ser de meu próprio bolso,"),
    ("19511215-御教え集4号.txt",
     "o Kanrin Shin Sen Bō do Mestre Daikoku é algo extraordinário",
     "o Kankinpō do Mestre Daitō é algo extraordinário"),
    ("19511215-御教え集4号.txt",
     "Matsui, Suzuki, Azabu Shin, Kashima Shūgetsu e outros quatro foram",
     "Matsui, Suzuki, Azabu Shin e Kashima Shūgetsu — quatro pessoas — foram"),
    ("19520115-御教え集5号.txt",
     "Em geral, a arte oriental e a arte ocidental são fundamentalmente opostas.",
     "Em geral, as belas-artes orientais e ocidentais — não as belas-artes, mas a arte — são fundamentalmente opostas."),
    ("19520320-御教え集7号.txt",
     "que não faça as pessoas pensarem",
     "que não deixe as pessoas perplexas"),
    ("19520815-御教え集12号.txt",
     "No entanto, esses males são relativamente pequenos para mim",
     "No entanto, passei por relativamente poucos desses males"),
    ("19521115-御教え集15号.txt",
     "e foi nessa ocasião que falei sobre o amanhecer",
     "e afirmo que, nessa ocasião, o amanhecer raiou pela primeira vez"),
    ("19530505-革命的増産の自然農法解説.txt",
     "Nós, que recebemos a alegria de ter a vida concedida, e que, agraciados com a saúde, passamos dias felizes, que pessoas afortunadas somos!",
     "Nós, que, ainda mais do que a alegria de termos recebido a vida, somos agraciados com a saúde e passamos dias felizes, que pessoas afortunadas somos!"),
    ("19530505-革命的増産の自然農法解説.txt",
     "ainda que seja uma fração mínima, a obra divina",
     "ainda que seja um décimo-milésimo, a obra divina"),
    ("19530910-世界救世教奇蹟集.txt",
     "o Mestre Yamamoto, uma conhecida de longa data",
     "a Mestra Yamamoto, uma conhecida de longa data"),
    ("19530910-世界救世教奇蹟集.txt",
     "conecta firmemente o elo espiritual",
     "por meio do elo espiritual, firmemente"),
]

CHAVE_POR_ITEM = [
    "19480701-御讃歌集.txt|117|0|0",
    "19490625-自観叢書第1篇『結核と神霊療法』.txt|31|0|1",
    "19491005-自観叢書第4篇『奇蹟物語』.txt|3|1|1",
    "19500420-自観叢書第10篇『神示の健康法』.txt|6|1|3",
    "19510615-一信者の告白.txt|3|3|2",
    "19510815-結核の革命的療法.txt|158|0|0",
    "19511215-御教え集4号.txt|1|6|7",
    "19511215-御教え集4号.txt|4|6|5",
    "19520115-御教え集5号.txt|5|4|6",
    "19520320-御教え集7号.txt|4|1|3",
    "19520815-御教え集12号.txt|9|3|0",
    "19521115-御教え集15号.txt|6|0|0",
    "19530505-革命的増産の自然農法解説.txt|30|1|1",
    "19530505-革命的増産の自然農法解説.txt|50|0|8",
    "19530910-世界救世教奇蹟集.txt|24|0|0",
    "19530910-世界救世教奇蹟集.txt|61|0|3",
]


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    por_obra: dict[str, list[tuple[str, str]]] = {}
    for obra, de, para in ITENS:
        por_obra.setdefault(obra, []).append((de, para))

    aplicadas, recusadas = [], []
    idx = 0
    for obra, pares in por_obra.items():
        f = PT_FONTE / obra
        if not f.exists():
            for de, para in pares:
                recusadas.append((CHAVE_POR_ITEM[idx], "obra inexistente")); idx += 1
            continue
        antes = f.read_text(encoding="utf-8")
        texto = antes
        ok_n = 0
        for de, para in pares:
            chave = CHAVE_POR_ITEM[idx]; idx += 1
            n = texto.count(de)
            if n != 1:
                recusadas.append((chave, f"{n} ocorrências de 'de' no estado atual"))
                continue
            texto = texto.replace(de, para)
            aplicadas.append(chave)
            ok_n += 1
        if not ok_n:
            continue
        if not aplicar:
            print(f"  {obra[:44]:<46} {ok_n:>3} emendadas (ensaio)")
            continue
        shutil.copy(f, f.with_suffix(f".txt.bak_manual16_{carimbo}"))
        f.write_text(texto, encoding="utf-8")
        (PT_STAGING / obra).write_text(texto, encoding="utf-8")
        sp = SPEC_DIR / f"{obra}.json"
        if sp.exists():
            anc = [x.get("pt_anchor", "") for x in
                   json.loads(sp.read_text(encoding="utf-8")).get("articles", [])]
            if len(anc) > 1 and all(anc):
                try:
                    if len(split_by_anchors(clean_body(texto), anc, label=obra)) != len(anc):
                        raise ValueError("contagem")
                except ValueError:
                    print(f"  *** ÂNCORA QUEBRADA — REVERTENDO {obra}")
                    f.write_text(antes, encoding="utf-8")
                    (PT_STAGING / obra).write_text(antes, encoding="utf-8")
                    aplicadas = [c for c in aplicadas
                                 if not c.startswith(obra + "|")]
                    continue
        print(f"  {obra[:44]:<46} {ok_n:>3} aplicadas")

    print(f"\n{len(aplicadas)} aplicadas, {len(recusadas)} recusadas")
    for k, m in recusadas:
        print(f"  {k}: {m}")
    if not aplicar:
        print("(ensaio — nada gravado; rode com --aplicar)")


if __name__ == "__main__":
    main()
