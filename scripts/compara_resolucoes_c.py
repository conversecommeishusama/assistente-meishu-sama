"""Terceiro passe: as duas leituras resolveram o caso da MESMA forma?

Concordar no veredito ("é resolvível") não é concordar no texto. Duas leituras
independentes podem dizer «RESOLVIDO» e propor correções que se contradizem --
e aplicar uma delas por sorteio seria pior do que não aplicar nenhuma.

Este passe compara os dois textos finais. Concordância só conta quando
preservam o mesmo sentido; diferença de estilo que não muda o conteúdo passa.
Divergência real cai para a mesa do usuário, com as duas versões lado a lado.

Comparar por igualdade de string não serviria: os dois modelos escrevem
independentemente, então quase nunca produzem o mesmo caractere. O que importa
é se resolvem a disputa do mesmo jeito -- isso é leitura, não diff.

    python3 scripts/compara_resolucoes_c.py
    python3 scripts/compara_resolucoes_c.py --relatorio
"""

from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from goshinsho.services import agentic_search as ag  # noqa: E402

R = RAIZ / "reports/varredura_padronizacao"
D1 = R / "RESOLVE_C_1.json"
D2 = R / "RESOLVE_C_2.json"
DEST = R / "COMPARA_C.json"
MODELO = "deepseek-v4-flash"
PARALELISMO = 16
MAX_TOKENS = 16384

SYSTEM = """Você compara duas propostas independentes de correção para o mesmo
trecho de uma tradução do japonês para o português.

Diga se as duas resolvem a disputa da MESMA forma -- mesmo sentido, mesmo
conteúdo -- ainda que com palavras diferentes. Diferença de estilo, ordem das
palavras ou sinônimo que não muda o que o texto afirma conta como CONCORDAM.

DIVERGEM quando o conteúdo difere: uma afirma o que a outra nega, uma inclui
informação que a outra omite, uma atribui a ação a um sujeito e a outra a
outro, ou os números/nomes não batem.

Responda UMA única linha:

CONCORDAM | <qual das duas está melhor escrita em português, A ou B, e por quê em poucas palavras>
DIVERGEM | <em que exatamente diferem, em uma frase>
"""


def compara(c: dict) -> dict:
    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content":
                   f"TRECHO ATUAL NO TEXTO:\n{c['de']}\n\n"
                   f"PROPOSTA A:\n{c['t1']}\n(razão: {c['r1'][:300]})\n\n"
                   f"PROPOSTA B:\n{c['t2']}\n(razão: {c['r2'][:300]})\n\n"
                   f"As duas resolvem do mesmo jeito?"}])
    texto = (r.choices[0].message.content or "").strip()
    prim = next((l for l in texto.splitlines() if l.strip()), "")
    p = [x.strip() for x in prim.split("|")]
    concordam = bool(p) and p[0].upper().startswith("CONCORDAM")
    return {**c, "concordam": concordam, "nota": p[-1] if len(p) > 1 else prim}


def pares() -> list[dict]:
    d1 = json.loads(D1.read_text(encoding="utf-8"))
    d2 = json.loads(D2.read_text(encoding="utf-8"))
    out = []
    for k in set(d1) & set(d2):
        a, b = d1[k], d2[k]
        if not (a.get("resolvido") and b.get("resolvido")):
            continue
        out.append({"chave": k, "obra": a["obra"], "artigo": a["artigo"],
                    "grau": a.get("grau", ""), "de": a["de"],
                    "t1": a["texto_final"], "r1": a.get("razao", ""),
                    "t2": b["texto_final"], "r2": b.get("razao", "")})
    return out


def relatorio() -> None:
    d = json.loads(DEST.read_text(encoding="utf-8"))
    ok = [v for v in d.values() if "erro" not in v]
    con = [v for v in ok if v.get("concordam")]
    print(f"{len(ok)} pares comparados")
    print(f"  {len(con)} CONCORDAM  -- prontos para aplicação")
    print(f"  {len(ok) - len(con)} DIVERGEM   -- mesa do usuário")


def main() -> None:
    if "--relatorio" in sys.argv:
        relatorio()
        return
    feitos: dict[str, dict] = json.loads(DEST.read_text(encoding="utf-8")) if DEST.exists() else {}
    cs = [c for c in pares() if c["chave"] not in feitos]
    print(f"{len(cs)} pares a comparar ({len(feitos)} já feitos)\n", flush=True)
    trava, n = threading.Lock(), [0]

    def trabalho(c):
        try:
            r = compara(c)
        except Exception as exc:
            r = {**c, "erro": repr(exc)[:140]}
        with trava:
            feitos[c["chave"]] = r
            n[0] += 1
            if n[0] % 50 == 0:
                DEST.write_text(json.dumps(feitos, ensure_ascii=False, indent=1), encoding="utf-8")
                cc = sum(1 for x in feitos.values() if x.get("concordam"))
                print(f"  [{n[0]}/{len(cs)}] {cc} concordam", flush=True)

    if cs:
        with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
            list(pool.map(trabalho, cs))
    DEST.write_text(json.dumps(feitos, ensure_ascii=False, indent=1), encoding="utf-8")
    relatorio()


if __name__ == "__main__":
    main()
