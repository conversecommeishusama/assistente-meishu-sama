#!/usr/bin/env python3
"""Triagem das regras do glossário: a regra está certa ou é estreita demais?

Por que isto vem ANTES da auditoria do acervo: auditar com regra errada
produz ruído. Já aconteceu duas vezes nesta sessão (327/415 e depois 243/415
com falsos positivos). A ordem correta é validar a régua e só então medir.

Para cada termo JP que o motor acusa, este script mostra:
  • quantos itens são afetados
  • sentenças JP reais contendo o termo (para ler o sentido no contexto)
  • se o PT traz a RAIZ da forma exigida, sem os modificadores
    (ex.: exigido «purificação pessoal», PT tem «purificação»)
  • se o PT traz alguma palavra da mesma família semântica já grafada

Classificação automática (indício, não veredito):
  REGRA_ESTREITA  — PT tem a raiz mas não os modificadores
  CANDIDATO_ERRO  — PT não tem nada da raiz (provável erro do texto)
  SEM_RELACAO     — o termo JP é polissêmico e a regra pode não se aplicar

Saída: reports/triagem_regras_glossario/TRIAGEM.{md,json}
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from glossario_core import auditar, _raiz, _norm, _tokens  # noqa: E402

# Palavras de ligação/modificadores que NÃO definem a raiz semântica
_VAZIAS = {"pessoal", "pessoais", "do", "da", "de", "proprio", "propria",
           "material", "materials", "espiritual", "espirituais", "mutavel"}


def _raizes_significativas(formas: list[str]) -> set[str]:
    """Raízes das palavras que realmente carregam o sentido da forma exigida."""
    out: set[str] = set()
    for f in formas:
        for t in _tokens(_norm(f)):
            if t in _VAZIAS or len(t) < 4:
                continue
            out.add(_raiz(t))
    return out


def _frases_com(jp: str, termo: str, limite: int = 3) -> list[str]:
    """Frases do JP que contêm o termo (contexto para leitura humana)."""
    frases = re.split(r"(?<=[。！？])|\n", jp)
    achadas = []
    for f in frases:
        f = f.strip()
        if termo in f and len(f) > 4:
            achadas.append(re.sub(r"\s+", " ", f)[:220])
        if len(achadas) >= limite:
            break
    return achadas


def _ocorrencias_raiz(pt: str, raizes: set[str]) -> list[str]:
    """Palavras do PT que compartilham raiz com a forma exigida."""
    if not pt or not raizes:
        return []
    achadas = []
    for p in re.findall(r"[A-Za-zÀ-ÿ]{4,}", pt):
        pr = _raiz(_norm(p))
        for r in raizes:
            if pr.startswith(r) or r.startswith(pr):
                achadas.append(p)
                break
    return sorted(set(achadas))[:12]


def classificar(jp: str, termo: str, formas: list[str], pt_raiz: list[str]) -> str:
    if not pt_raiz:
        return "CANDIDATO_ERRO"
    # PT tem a raiz-base mas não os modificadores → regra possivelmente estreita
    base = {_raiz(t) for t in _tokens(_norm(formas[0])) if len(t) >= 4}
    if any(_raiz(_norm(p)) in base for p in pt_raiz):
        return "REGRA_ESTREITA"
    return "SEM_RELACAO"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--itens", default="reports/traducao_periodicos/itens/*.json")
    ap.add_argument("--saida", default="reports/triagem_regras_glossario")
    ap.add_argument("--min-itens", type=int, default=3,
                    help="só mostra termos acusados em >= N itens")
    args = ap.parse_args()

    arquivos = sorted(glob.glob(args.itens))
    print(f"itens: {len(arquivos)}")

    # termo -> dados agregados
    agg: dict[str, dict] = defaultdict(
        lambda: {"itens": set(), "formas": [], "frases": [], "pt_raiz": set()})

    for f in arquivos:
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:                                    # noqa: BLE001
            continue
        nome = Path(f).name
        pares = (("titulo_jp", "titulo_pt"), ("texto_jp", "texto_pt"))
        for cj, cp in pares:
            jp, pt = d.get(cj) or "", d.get(cp) or ""
            if not jp or not pt:
                continue
            rel = auditar(jp, pt)
            for v in rel["forma"]:
                t = v["termo_jp"]
                a = agg[t]
                a["itens"].add(nome)
                a["formas"] = v["formas"]
                for fr in _frases_com(jp, t):
                    if fr not in a["frases"] and len(a["frases"]) < 4:
                        a["frases"].append(fr)
                a["pt_raiz"].update(
                    _ocorrencias_raiz(pt, _raizes_significativas(v["formas"])))

    linhas: list[str] = [
        "# Triagem das regras do glossário",
        "",
        "Regra do motor × realidade do texto. Decisão por termo:",
        "**REGRA_ESTREITA** (ajustar a regra) ou **CANDIDATO_ERRO** (revisar o texto).",
        "",
        f"Termos acusados: **{len(agg)}**",
        "",
    ]
    resumo = []
    for termo, a in sorted(agg.items(), key=lambda x: -len(x[1]["itens"])):
        if len(a["itens"]) < args.min_itens:
            continue
        cls = classificar(None, termo, a["formas"], sorted(a["pt_raiz"]))
        resumo.append({"termo": termo, "itens": len(a["itens"]),
                       "formas": a["formas"], "classe": cls,
                       "pt_raiz": sorted(a["pt_raiz"])[:8],
                       "frases": a["frases"]})

    # ordena por classe (REGRA_ESTREITA primeiro, é o que exige ação)
    ordem = {"REGRA_ESTREITA": 0, "SEM_RELACAO": 1, "CANDIDATO_ERRO": 2}
    resumo.sort(key=lambda r: (ordem[r["classe"]], -r["itens"]))

    for r in resumo:
        linhas += [
            f"## `{r['termo']}` — {r['itens']} itens · **{r['classe']}**",
            "",
            f"- **exigido pelo glossário:** {r['formas']}",
            f"- **raízes no PT:** {r['pt_raiz'] or '_(nenhuma)_'}",
            "",
        ]
        for fr in r["frases"]:
            linhas.append(f"  > {fr}")
        linhas.append("")

    saida = RAIZ / args.saida
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "TRIAGEM.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    (saida / "TRIAGEM.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    from collections import Counter
    c = Counter(r["classe"] for r in resumo)
    print(f"\ntermos com >= {args.min_itens} itens: {len(resumo)}")
    for k, v in c.most_common():
        print(f"   {k:16} {v}")
    print(f"\ngravado em: {saida}")
    print("\n--- REGRA_ESTREITA (ação: ajustar o glossário) ---")
    for r in resumo:
        if r["classe"] == "REGRA_ESTREITA":
            print(f"   {r['itens']:4}  {r['termo']:10} -> {r['formas']}")
            print(f"         PT usa: {r['pt_raiz'][:6]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
