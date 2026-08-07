"""Padroniza 御屏風観音様 como "Byōbu Kannon", com glosa na 1ª menção.

Decisão do usuário (2026-08-08), depois de investigar o que o objeto é.
O próprio Meishu-Sama descreve:

    早速新規蒔直しに書いたのが五六七（ミロク）教会小田原本部にある千手観音の
    お姿で、仏壇へ祀る御屏風観音でもある。

    "O que pintei de novo é a imagem da Kannon de Mil Braços que está na sede
     de Odawara da Igreja Miroku, e é também a Byōbu Kannon que se entroniza
     no butsudan."

Ou seja: é a MESMA Kannon de Mil Braços (千手観音, que já tem entrada no
glossário) numa montagem diferente -- reprodução da pintura, montada em
biombo pequeno para o altar doméstico. O "biombo" não é acessório descritivo,
é o que distingue esta forma da outra. Por isso o elemento fica no nome.

Padrão adotado, o mesmo que o projeto já usa em 日光殿:

    1ª menção de cada arquivo:  Byōbu Kannon (Kannon do biombo)
    depois:                     Byōbu Kannon

Corrige também uma inconsistência de gênero que já existia: o acervo escreve
"a Kannon do biombo" 172 vezes e "o Kannon do biombo" 8. Kannon é feminino
neste corpus.

Uso:
    python3 scripts/padroniza_byobu_kannon.py            # não grava
    python3 scripts/padroniza_byobu_kannon.py --aplicar
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

BASES = [RAIZ / "livros_publicacao_pt_revisado", RAIZ / "reports/livros_trabalho/pt"]
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"

NOME = "Byōbu Kannon"
GLOSA = f"{NOME} (Kannon do biombo)"

# Todas as formas em uso, levantadas do acervo -- não imaginadas.
VARIANTES = re.compile(
    r"Imagem\s+da\s+Luz\s+Divina\s+do\s+Biombo\s+Kannon"
    r"|imagens?\s+de\s+Kannon\s+n[oa]\s+biombo"
    r"|biombos?\s+de\s+Kannon"
    r"|Kannon\s+d[oe]\s+[Bb]iombo"
    r"|Byobu\s+Kannon",
    re.IGNORECASE)

# Nome próprio dispensa artigo. Decisão do usuário (2026-08-08), depois de
# constatar que Meishu-Sama ensina que Kannon é homem E mulher ao mesmo tempo
# (観世音菩薩は... 男であり、女であり、いわば両性を具備され給うておらる) --
# o português obriga a escolher um artigo onde o japonês não obriga nada, e
# não usar artigo evita tomar partido.
#
# O acervo confirma que é o padrão dos nomes irmãos: Komyo-Nyorai aparece sem
# artigo em 60% das 724 ocorrências, Daikōmyō Nyorai em 56%, Kannon de Mil
# Braços em 71%. Só "Kannon do biombo" usava artigo em 88% -- justamente
# porque lia como descrição, e descrição pede artigo.
#
# Preposição contraída volta à forma simples: "diante DA Kannon do biombo"
# -> "diante DE Byōbu Kannon".
CONTRACAO = {
    "da": "de", "do": "de", "das": "de", "dos": "de",
    "na": "em", "no": "em", "nas": "em", "nos": "em",
    "pela": "por", "pelo": "por", "pelas": "por", "pelos": "por",
    "à": "a", "ao": "a", "às": "a", "aos": "a",
    "duma": "de uma", "dum": "de um", "numa": "em uma", "num": "em um",
}
ARTIGO_NU = {"a", "o", "as", "os", "um", "uma"}
RE_ANTES = re.compile(r"([A-Za-zÀ-ÿ]+)(\s+)$")


def concorda(prefixo: str) -> tuple[str, bool]:
    """Remove o artigo, ou reduz a preposição contraída à forma simples."""
    m = RE_ANTES.search(prefixo)
    if not m:
        return prefixo, False
    palavra = m.group(1)
    baixa = palavra.lower()
    if baixa in ARTIGO_NU:
        # Sem o artigo, o que sobra antes pode ser vazio (artigo abrindo a
        # frase) -- aí não pode restar espaço solto no começo.
        resto = prefixo[: m.start(1)].rstrip()
        return (resto + " ") if resto else "", True
    alvo = CONTRACAO.get(baixa)
    if not alvo:
        return prefixo, False
    novo = alvo.capitalize() if palavra[0].isupper() else alvo
    return prefixo[: m.start(1)] + novo + prefixo[m.end(1):], True


def transforma(texto: str, ja_glosou: bool = False) -> tuple[str, int, bool]:
    saida, cursor, n = [], 0, 0
    for m in VARIANTES.finditer(texto):
        prefixo = texto[cursor: m.start()]
        prefixo, _ = concorda(prefixo)
        alvo = NOME if ja_glosou else GLOSA
        ja_glosou = True
        if m.group()[0].isupper() or not m.group()[0].isalpha():
            pass  # o nome já começa em maiúscula
        saida.append(prefixo)
        saida.append(alvo)
        cursor = m.end()
        n += 1
    saida.append(texto[cursor:])
    return "".join(saida), n, ja_glosou


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    por_obra: dict[str, int] = {}
    exemplos: list[str] = []

    for base in BASES:
        for p in sorted(base.glob("*.txt")):
            texto = p.read_text(encoding="utf-8")
            novo, n, _ = transforma(texto)
            if not n:
                continue
            if base is BASES[0]:
                por_obra[p.name] = n
                if len(exemplos) < 6:
                    m = VARIANTES.search(texto)
                    exemplos.append(re.sub(r"\s+", " ", texto[max(0, m.start() - 50): m.end() + 40]))
            if aplicar:
                if base is BASES[0]:
                    p.with_suffix(f".txt.bak_pre_byobu_{carimbo}").write_text(texto, encoding="utf-8")
                p.write_text(novo, encoding="utf-8")

    print(f"{sum(por_obra.values())} ocorrências em {len(por_obra)} obras")
    for e in exemplos:
        print(f"   {e[:110]}")
    for obra, n in sorted(por_obra.items(), key=lambda x: -x[1])[:6]:
        print(f"  {n:>4}  {obra[:56]}")

    if not aplicar:
        print("\n(diagnóstico apenas — rode com --aplicar)")
        return

    print("\nâncoras...")
    ajust = ruins = 0
    for obra in por_obra:
        spec_path = SPEC_DIR / f"{obra}.json"
        if not spec_path.exists():
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        arts = spec.get("articles", [])
        anc = [a.get("pt_anchor", "") for a in arts]
        if len(anc) <= 1 or not all(anc):
            continue
        texto = clean_body((BASES[0] / obra).read_text(encoding="utf-8"))
        mudou = False
        for a in arts:
            alvo = a.get("pt_anchor", "")
            if not alvo or alvo in texto:
                continue
            chv = alvo[:45]
            pos = texto.find(chv)
            if pos < 0 or texto.count(chv) != 1:
                # o próprio prefixo pode conter o termo trocado
                for cand in (transforma(alvo)[0], transforma(alvo, True)[0]):
                    if cand != alvo and cand in texto:
                        a["pt_anchor"] = cand
                        mudou = True
                        ajust += 1
                        break
                continue
            a["pt_anchor"] = texto[pos: pos + len(alvo)]
            mudou = True
            ajust += 1
        if mudou:
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
            anc = [a["pt_anchor"] for a in arts]
        for base in BASES:
            f = base / obra
            if not f.exists():
                continue
            try:
                c = split_by_anchors(clean_body(f.read_text(encoding="utf-8")), anc, label=obra)
                if len(c) != len(anc):
                    raise ValueError("contagem")
            except ValueError as exc:
                print(f"  QUEBROU {base.name}/{obra}: {exc}")
                ruins += 1
    print(f"  {ajust} âncoras ajustadas, {ruins} quebradas")


if __name__ == "__main__":
    main()
