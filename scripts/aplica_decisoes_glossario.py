"""Aplica as decisões de glossário tomadas pelo usuário em 2026-08-07.

Cada troca é feita SÓ dentro de artigos cujo japonês contém a chave, e só
quando a contagem bate: se o japonês tem N ocorrências da chave e o português
tem N da forma errada, troca as N. Se não bater, não toca e reporta -- é o que
evita transformar "Mestre" (先生) em "Grão-Mestre" só porque 大先生 aparece
noutro ponto do mesmo artigo.

Uso:
    python3 scripts/aplica_decisoes_glossario.py            # não grava
    python3 scripts/aplica_decisoes_glossario.py --aplicar
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

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
JP_DIR = RAIZ / "reports/livros_trabalho/jp"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"

# (chave japonesa, [formas erradas em ordem de tentativa], forma certa)
# As formas erradas vieram do julgamento do DeepSeek e foram conferidas
# contra o texto antes de entrar aqui.
DECISOES = [
    ("大光明如来", ["grande Komyo-Nyorai", "Komyo-Nyorai"], "Daikōmyō Nyorai"),
    ("中教会", ["Igreja Central"], "Igreja Média"),
    ("大教会", ["Igreja Média Kōhō"], "Igreja Grande Kōhō"),
    ("千手観音様", ["Kannon-Sama de Mil Braços"], "Kannon de Mil Braços"),
    ("日光殿", ["Salão Nikko"], "Nikkōden"),
    ("大先生", ["o Mestre"], "o Grão-Mestre"),
    ("真善美", ["Verdade, Bondade e Beleza"], "a Verdade, o Bem e o Belo"),
    ("五六七の世", ["era de Miroku"], "Mundo de Miroku"),
    ("副霊", ["espíritos auxiliares"], "Espíritos Secundários"),
    ("副霊", ["espírito guardião auxiliar", "espírito auxiliar"], "Espírito Secundário"),
    ("濁血", ["sangue impuro", "sangue sujo"], "sangue turvo"),
    ("本守護神", ["espírito guardião verdadeiro"], "espírito protetor primordial"),
    ("根底の国", ["reino fundamental"], "Reino do Fundo da Raiz"),
    ("メシヤ会館", ["Salão Messiânico"], "Templo Messiânico"),
    ("肺結核", ["doença pulmonar"], "tuberculose pulmonar"),
    # 悪霊: o usuário fixou "espíritos malignos". Note que "Divindades
    # malignas" (437 ocorrências) traduz 邪神, que tem entrada própria -- não
    # é o mesmo termo e não entra aqui.
    ("悪霊", ["Espíritos do Mal", "espíritos do mal"], "espíritos malignos"),
    ("悪霊", ["Espírito do Mal", "espírito do mal"], "espírito maligno"),
]

# Quando a forma errada é palavra COMUM em português, a contagem sozinha não
# basta: um artigo pode ter 祝詞 três vezes e "oração" três vezes por
# coincidência, com parte das "orações" traduzindo 祈り. Nesses casos só toca
# o artigo se o japonês NÃO tiver o termo concorrente.
CONFLITOS = {
    "祝詞": ["祈り", "祈願", "お祈り", "御祈願", "善言讃詞"],
    "支部": ["中心", "拠点", "本部"],
}

DECISOES += [
    ("祝詞", ["orações", "oração", "preces", "prece"], "norito"),
    ("支部", ["Centros Regionais", "centros regionais", "núcleos", "núcleo"], "filial"),
]

_cache: dict[str, tuple[list[str], list[str]]] = {}


def artigos(caminho: Path, spec: dict, campo: str) -> list[str]:
    texto = clean_body(caminho.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n"))
    arts = spec.get("articles", [])
    anc = [a.get(campo, "") for a in arts]
    if len(arts) <= 1 or not all(anc):
        return [texto]
    try:
        pedacos = split_by_anchors(texto, anc, label=caminho.name)
    except ValueError:
        return [texto]
    return pedacos if len(pedacos) == len(arts) else [texto]


def par(obra: str):
    if obra not in _cache:
        spec = json.loads((SPEC_DIR / f"{obra}.json").read_text(encoding="utf-8"))
        _cache[obra] = (artigos(JP_DIR / obra, spec, "jp_anchor"),
                        artigos(PT_FONTE / obra, spec, "pt_anchor"))
    return _cache[obra]


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    trocas: dict[str, list[tuple[str, str]]] = {}
    pulados = []

    for chave, errados, certo in DECISOES:
        feitos = 0
        for pt_path in sorted(PT_FONTE.glob("*.txt")):
            obra = pt_path.name
            if not (SPEC_DIR / f"{obra}.json").exists() or not (JP_DIR / obra).exists():
                continue
            ajp, apt = par(obra)
            if len(ajp) != len(apt):
                continue
            for jp, pt in zip(ajp, apt):
                if chave not in jp or certo in pt:
                    continue
                conflito = next((c for c in CONFLITOS.get(chave, []) if c in jp), None)
                if conflito:
                    pulados.append((chave, obra, f"convive com {conflito}", 0, 0))
                    continue
                njp = jp.count(chave)
                for errado in errados:
                    npt = pt.count(errado)
                    if not npt:
                        continue
                    if npt != njp:
                        pulados.append((chave, obra, errado, njp, npt))
                        break
                    trocas.setdefault(obra, []).append((errado, certo))
                    feitos += npt
                    break
        print(f"  {chave:<10} {feitos:>3} trocas  ({' | '.join(errados)} -> {certo})")

    if pulados:
        print(f"\n{len(pulados)} casos pulados por contagem divergente (não tocados):")
        for chave, obra, errado, njp, npt in pulados[:10]:
            print(f"  {chave:<8} {obra[:30]:<32} JP tem {njp}x, PT tem {npt}x {errado!r}")

    if not aplicar:
        print("\n(diagnóstico apenas — rode com --aplicar)")
        return

    print("\naplicando...")
    for obra, pares in trocas.items():
        for base in (PT_FONTE, PT_STAGING):
            f = base / obra
            if not f.exists():
                continue
            t = f.read_text(encoding="utf-8")
            if base is PT_FONTE:
                f.with_suffix(f".txt.bak_pre_decisoes_{carimbo}").write_text(t, encoding="utf-8")
            for errado, certo in pares:
                t = t.replace(errado, certo)
            f.write_text(t, encoding="utf-8")

    ruins = 0
    for obra in trocas:
        spec_path = SPEC_DIR / f"{obra}.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        arts = spec.get("articles", [])
        anc = [a.get("pt_anchor", "") for a in arts]
        if len(anc) <= 1 or not all(anc):
            continue
        texto = clean_body((PT_FONTE / obra).read_text(encoding="utf-8"))
        mudou = False
        for a in arts:
            alvo = a.get("pt_anchor", "")
            if not alvo or alvo in texto:
                continue
            chv = alvo[:45]
            pos = texto.find(chv)
            if pos < 0 or texto.count(chv) != 1:
                continue
            a["pt_anchor"] = texto[pos: pos + len(alvo)]
            mudou = True
        if mudou:
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
            anc = [a["pt_anchor"] for a in arts]
        for base in (PT_FONTE, PT_STAGING):
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
    print(f"  {len(trocas)} obras tocadas, {ruins} âncoras quebradas")


if __name__ == "__main__":
    main()
