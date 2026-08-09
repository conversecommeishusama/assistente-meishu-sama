"""Traz de volta ao artigo o título que vazou para o bloco anterior, no japonês.

Achado ao auditar a etapa 4: um achado GRAVE dizia que «Quinta Aula» devia ser
«Sexta Aula» em 観音講座, citando 第六講座 como prova. Lendo os blocos, o
japonês do idx5 de fato termina em 第六講座 -- mas porque o cabeçalho da aula
SEGUINTE ficou preso no fim dele. O português estava certo; aplicar teria
quebrado a âncora e criado duas «Sexta Aula».

É a mesma classe do vazamento de byline corrigido em julho, agora do lado
japonês e no cabeçalho de seção.

Corrige só o caso ASSIMÉTRICO -- o japonês perdeu o título e o português
manteve. Quando os dois vazam igual (37 fronteiras, ex. 光への道), os blocos
continuam alinhados entre si e mexer só num lado é que criaria o desencontro.

As três séries orais ficam de fora: ali a linha de data fechar o bloco
anterior é convenção deliberada, confirmada em 32 dos 33 volumes de 御教え集,
e já foi tratada como defeito uma vez neste projeto, com reversão.

Uso:
    python3 scripts/repara_titulo_vazado_jp.py            # diagnóstico
    python3 scripts/repara_titulo_vazado_jp.py --aplicar
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

SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
JP_DIR = RAIZ / "reports/livros_trabalho/jp"
PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
ORAL = {"mioshie_shu", "gokowa_roku_qa", "gokowa_roku_ho", "ochishiji_roku"}
SECAO = re.compile(r"第[一二三四五六七八九十百\d]+[講話章節篇回](座)?")


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def alvos_da_obra(obra: str) -> list[tuple[int, str]]:
    """(índice do artigo, linha de título que vazou para o bloco anterior)."""
    sp = SPEC_DIR / f"{obra}.json"
    jf, pf = JP_DIR / obra, PT_FONTE / obra
    if not (sp.exists() and jf.exists() and pf.exists()):
        return []
    spec = json.loads(sp.read_text(encoding="utf-8"))
    if spec.get("profile") in ORAL:
        return []
    arts = spec.get("articles", [])
    aj = [a.get("jp_anchor", "") for a in arts]
    ap = [a.get("pt_anchor", "") for a in arts]
    if len(arts) < 2 or not all(aj) or not all(ap):
        return []
    try:
        bj = split_by_anchors(clean_body(jf.read_text(encoding="utf-8")), aj, label=obra)
        bp = split_by_anchors(clean_body(pf.read_text(encoding="utf-8")), ap, label=obra)
    except ValueError:
        return []

    saida = []
    for i in range(len(bj) - 1):
        ls = [l.strip("　 \t") for l in bj[i].rstrip().split("\n") if l.strip("　 \t")]
        if not ls:
            continue
        ult = norm(ls[-1])
        tit = norm(arts[i + 1].get("title_jp", ""))
        if not ((tit and len(tit) >= 3 and ult == tit) or SECAO.fullmatch(ult)):
            continue
        # só o assimétrico: se o português também vaza, os dois estão alinhados
        tp = (arts[i + 1].get("title_pt") or ap[i + 1].split("\n")[0]).strip()
        lp = [l for l in bp[i].rstrip().split("\n") if l.strip()]
        if lp and lp[-1].strip()[:18] == tp[:18]:
            continue
        saida.append((i + 1, ls[-1]))
    return saida


def nova_ancora(texto: str, velha: str, titulo: str) -> str | None:
    """Estende a âncora para trás até incluir a linha de título."""
    pos = texto.find(velha)
    if pos < 0:
        return None
    janela = texto[max(0, pos - 400):pos]
    achou = janela.rfind(titulo)
    if achou < 0:
        return None
    ini = max(0, pos - 400) + achou
    # a linha inteira, não o pedaço casado
    ini = texto.rfind("\n", 0, ini) + 1
    cand = texto[ini:pos + len(velha)]
    # entre o título e o corpo só pode haver espaço em branco
    meio = texto[ini + len(texto[ini:pos].rstrip()):pos]
    if meio.strip():
        return None
    return cand if texto.count(cand) == 1 else None


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tot = falhou = obras = 0

    for pj in sorted(JP_DIR.glob("*.txt")):
        obra = pj.name
        alvos = alvos_da_obra(obra)
        if not alvos:
            continue
        sp = SPEC_DIR / f"{obra}.json"
        spec = json.loads(sp.read_text(encoding="utf-8"))
        arts = spec["articles"]
        texto = clean_body(pj.read_text(encoding="utf-8"))
        antes = [a.get("jp_anchor", "") for a in arts]

        feitos = 0
        for idx, titulo in alvos:
            nova = nova_ancora(texto, arts[idx].get("jp_anchor", ""), titulo)
            if nova is None:
                falhou += 1
                continue
            arts[idx]["jp_anchor"] = nova
            feitos += 1

        depois = [a.get("jp_anchor", "") for a in arts]
        try:
            if len(split_by_anchors(texto, depois, label=obra)) != len(arts):
                raise ValueError("contagem")
        except ValueError as exc:
            print(f"  REVERTIDO {obra[:44]}: {str(exc)[:70]}")
            for a, v in zip(arts, antes):
                a["jp_anchor"] = v
            continue

        obras += 1
        tot += feitos
        print(f"  {obra[:50]:<52} {feitos:>3} títulos recuperados")
        if aplicar and feitos:
            sp.with_suffix(f".json.bak_titulo_vazado_{carimbo}").write_text(
                json.dumps({"articles": [{"jp_anchor": v} for v in antes]},
                           ensure_ascii=False, indent=1), encoding="utf-8")
            sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                          encoding="utf-8")

    print(f"\n{tot} âncoras japonesas estendidas em {obras} obras "
          f"({falhou} não resolvidas)")
    if not aplicar:
        print("(diagnóstico apenas -- rode com --aplicar)")
        return

    ruins = 0
    for pj in sorted(JP_DIR.glob("*.txt")):
        sp = SPEC_DIR / f"{pj.name}.json"
        if not sp.exists():
            continue
        arts = json.loads(sp.read_text(encoding="utf-8")).get("articles", [])
        anc = [a.get("jp_anchor", "") for a in arts]
        if len(anc) <= 1 or not all(anc):
            continue
        try:
            if len(split_by_anchors(clean_body(pj.read_text(encoding="utf-8")),
                                    anc, label=pj.name)) != len(anc):
                raise ValueError("contagem")
        except ValueError as exc:
            print(f"  QUEBRADA jp/{pj.name}: {str(exc)[:80]}")
            ruins += 1
    print(f"verificação final: {ruins} âncoras japonesas quebradas")


if __name__ == "__main__":
    main()
