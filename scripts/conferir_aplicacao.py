"""Confere o arquivo INTEIRO depois de aplicar — e reverte o que não se explicar.

O usuário disse, com razão, que a preocupação dele na pilha A não é o conteúdo
das correções (três pareceres e um desafiador decidiram isso) e sim se a
APLICAÇÃO será feita de forma adequada — que é engenharia minha, e minha
engenharia falhou várias vezes neste projeto.

A verificação que já existe em `aplicar_semantico.py` confere cada parágrafo
antes de gravar. Isto aqui é outra coisa: compara o arquivo inteiro com o
backup e exige que CADA diferença corresponda a uma correção aprovada. Diferença
sem explicação -- em qualquer lugar do arquivo, mesmo longe das correções --
reverte a obra inteira.

Por que isso, e não confiar na verificação anterior: o dano de 07/08 aconteceu
porque um script alterou lugares que ninguém estava olhando. Uma guarda que só
olha onde se pretendia mexer não pega isso por construção. Esta olha o resto.

    python3 scripts/conferir_aplicacao.py <carimbo>
    python3 scripts/conferir_aplicacao.py <carimbo> --reverter
"""

from __future__ import annotations

import difflib
import re
import json
import shutil
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import auditoria as A  # noqa: E402
from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402
from aplicar_semantico import contido  # noqa: E402

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
REGISTRO = RAIZ / "reports/varredura_padronizacao/APLICADO.json"


def paragrafos(t: str) -> list[str]:
    return [x for x in re.split(r"\n\s*\n", t) if x.strip()]


def blocos_diferentes(antes: str, depois: str) -> list[tuple[str, str]]:
    """Os PARÁGRAFOS que mudaram, em pares (antes, depois).

    A primeira versão comparava caractere a caractere e produzia micro-diffs
    sem sentido -- 'qu' -> 't', 'eu' -> 'ido' --, em que nada é reconhecível.
    Pior: a comparação `v[:40] in t` com `v` vazio dá sempre verdadeiro, porque
    string vazia está contida em qualquer coisa, e toda inserção pura passava.
    O teste da própria conferência pegou isso: uma mudança distante da correção
    passou como explicada.

    Parágrafo é a granularidade certa: se um parágrafo mudou, ele tinha de
    conter um trecho autorizado.
    """
    a, b = paragrafos(antes), paragrafos(depois)
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        # Um par por PARÁGRAFO, nunca um bloco com vários. O SequenceMatcher
        # funde parágrafos vizinhos que mudaram, e aí a mudança não autorizada
        # pega carona na autorizada -- foi o que o teste pegou: um parágrafo
        # distante alterado passou junto com o corrigido, por serem adjacentes.
        velhos, novos = a[i1:i2], b[j1:j2]
        for i in range(max(len(velhos), len(novos))):
            out.append((velhos[i] if i < len(velhos) else "",
                        novos[i] if i < len(novos) else ""))
    return out


MARGEM = 60


def _mudanca_no_vao(velho: str, novo: str, achados: list[str]) -> str | None:
    """Cada trecho que mudou no parágrafo cai no vão de alguma correção?

    Um parágrafo pode ter MAIS DE UMA correção aprovada -- é comum em diálogo
    denso. A primeira versão media a distância em relação a um trecho só, e
    acusava a segunda correção legítima como mudança fora do vão: 12 dos 100
    parágrafos de uma obra real. Aqui cada diferença é comparada com TODOS os
    vãos autorizados do parágrafo.
    """
    vaos = []
    for t in achados:
        i = velho.find(t)
        while i >= 0:
            vaos.append((i - MARGEM, i + len(t) + MARGEM))
            i = velho.find(t, i + 1)
    if not vaos:
        return "nenhum trecho autorizado no parágrafo original"
    sm = difflib.SequenceMatcher(None, velho, novo, autojunk=False)
    for tag, i1, i2, _, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if not any(a <= i1 and i2 <= b for a, b in vaos):
            return (f"mudou fora dos vãos autorizados: "
                    f"{velho[i1:i2][:60]!r} -> {novo[max(0,j2-60):j2][:60]!r}")
    return None


def inexplicadas(antes: str, depois: str,
                 trechos: list[str]) -> list[tuple[str, str]]:
    """Toda diferença que não se explica por uma correção autorizada.

    Duas condições, e as duas vieram de falha em teste, não de precaução:

      1. o parágrafo alterado tem de conter um trecho autorizado -- sem isso,
         qualquer mudança em qualquer lugar do arquivo passaria;
      2. a mudança DENTRO dele tem de ficar no vão do trecho -- porque um
         parágrafo que mudou por motivo legítimo pode carregar dano junto. No
         teste sobre obra real, «proteção divina divina», a assinatura do
         estrago de 07/08, passou escondida num parágrafo com correção aprovada.
    """
    out = []
    for velho, novo in blocos_diferentes(antes, depois):
        if not velho.strip() and not novo.strip():
            continue
        achados = [t for t in trechos if t and t in velho]
        if not velho.strip() or not achados:
            out.append((velho[:110] or "(parágrafo acrescentado)",
                        novo[:110] or "(parágrafo removido)"))
            continue
        # `contido` do aplicador não serve aqui inteiro: ele também exige que
        # o trecho antigo tenha sumido, o que é regra de ANTES de gravar. Na
        # conferência interessa só a localização da mudança.
        motivo = _mudanca_no_vao(velho, novo, achados)
        if motivo:
            out.append((f"[dentro de parágrafo autorizado] {motivo}", novo[:110]))
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: conferir_aplicacao.py <carimbo> [--reverter]")
        sys.exit(1)
    carimbo = sys.argv[1]
    reverter = "--reverter" in sys.argv

    aplicadas = set(json.loads(REGISTRO.read_text(encoding="utf-8"))
                    if REGISTRO.exists() else [])
    proc = {A.chave(r): r for r in A.procedentes()}
    # o que cada obra tinha autorização para mudar
    autorizado: dict[str, list[str]] = {}
    for k in aplicadas:
        if k in proc:
            autorizado.setdefault(proc[k]["obra"], []).append(proc[k]["de"])

    total_ok = total_susp = obras_rev = 0
    for bak in sorted(PT_FONTE.glob(f"*.bak_aplic_{carimbo}")):
        obra = bak.name.replace(f".bak_aplic_{carimbo}", "")
        f = PT_FONTE / obra
        if not f.exists():
            continue
        antes, depois = bak.read_text(encoding="utf-8"), f.read_text(encoding="utf-8")
        difs = blocos_diferentes(antes, depois)
        trechos = autorizado.get(obra, [])

        suspeitas = inexplicadas(antes, depois, trechos)

        # âncoras e contagem de artigos continuam de pé?
        quebrou = ""
        sp = SPEC_DIR / f"{obra}.json"
        if sp.exists():
            anc = [x.get("pt_anchor", "") for x in
                   json.loads(sp.read_text(encoding="utf-8")).get("articles", [])]
            if len(anc) > 1 and all(anc):
                try:
                    if len(split_by_anchors(clean_body(depois), anc, label=obra)) != len(anc):
                        quebrou = "contagem de artigos mudou"
                except ValueError as exc:
                    quebrou = str(exc)[:70]

        if suspeitas or quebrou:
            total_susp += 1
            print(f"\n  *** {obra[:46]}")
            if quebrou:
                print(f"      ÂNCORA: {quebrou}")
            for v, n in suspeitas[:4]:
                print(f"      inexplicada: {v!r}\n                -> {n!r}")
            if reverter:
                shutil.copy(bak, f)
                shutil.copy(bak, PT_STAGING / obra)
                obras_rev += 1
                print(f"      REVERTIDA")
        else:
            total_ok += 1
            print(f"  {obra[:46]:<48} {len(difs):>3} diferenças, todas explicadas")

    print(f"\n{total_ok} obras conferidas e limpas, {total_susp} com diferença "
          f"inexplicada" + (f", {obras_rev} revertidas" if reverter else ""))
    if total_susp and not reverter:
        print("(rode com --reverter para desfazer as obras suspeitas)")


if __name__ == "__main__":
    main()
