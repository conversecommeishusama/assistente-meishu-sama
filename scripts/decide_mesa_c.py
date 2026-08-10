"""Registro das MINHAS decisões (Claude) sobre os 143 casos que sobraram.

O usuário determinou: ler cada um semanticamente, resolver o que eu estiver apto
a resolver, e levar a ele o resto -- com relatório de todos os 143.

Cada decisão é uma de três:

  A          -- a redação A resolve; aplicar
  B          -- a redação B resolve; aplicar
  MANTER     -- nenhuma das duas procede; o texto atual está certo
  OUTRO      -- as duas erram, mas o japonês sustenta uma terceira forma (dada)
  USUARIO    -- disputa real de convenção ou ambiguidade; não decido sozinho

Gravar em disco a cada lote, porque a leitura de 143 casos não cabe num
contexto só e a sessão pode compactar no meio.

    python3 scripts/decide_mesa_c.py --grava '<json>'
    python3 scripts/decide_mesa_c.py --resumo
    python3 scripts/decide_mesa_c.py --faltam
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import dossies_mesa_c as D  # noqa: E402

DEST = RAIZ / "reports/varredura_padronizacao/DECIDIDO_MESA_C.json"
VALIDOS = {"A", "B", "MANTER", "OUTRO", "USUARIO"}


def carrega() -> dict:
    return json.loads(DEST.read_text(encoding="utf-8")) if DEST.exists() else {}


def grava(novas: dict) -> None:
    d = carrega()
    cs = {c["chave"]: c for c in D.casos()}
    for k, v in novas.items():
        if k not in cs:
            raise SystemExit(f"chave desconhecida: {k}")
        if v["decisao"] not in VALIDOS:
            raise SystemExit(f"decisão inválida em {k}: {v['decisao']}")
        if v["decisao"] == "OUTRO" and not v.get("texto", "").strip():
            raise SystemExit(f"OUTRO exige texto em {k}")
        # `de` opcional: amplia o span a substituir. Existe porque em vários
        # casos o erro é real mas a correção não cabe no trecho original -- a
        # frase precisa ser refeita inteira. Sem isto eu marcaria «usuário» por
        # limitação do meu mecanismo, não por dúvida, o que seria enganoso.
        if v.get("de"):
            obra = k.split("|")[0]
            txt = (RAIZ / "livros_publicacao_pt_revisado" / obra).read_text(encoding="utf-8")
            n = txt.count(v["de"])
            if n != 1:
                raise SystemExit(f"span de {k} ocorre {n}x no arquivo (precisa 1)")
        d[k] = v
    DEST.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(novas)} gravadas ({len(d)}/{len(cs)} no total)")


def resumo() -> None:
    d, cs = carrega(), D.casos()
    c = Counter(v["decisao"] for v in d.values())
    print(f"{len(d)}/{len(cs)} decididos")
    for k, n in c.most_common():
        print(f"  {k:<9} {n}")


def faltam() -> None:
    d = carrega()
    cs = D.casos()
    idx = [i for i, c in enumerate(cs) if c["chave"] not in d]
    print(f"{len(idx)} sem decisão; próximos índices: {idx[:40]}")


def main() -> None:
    if "--grava" in sys.argv:
        grava(json.loads(sys.argv[sys.argv.index("--grava") + 1]))
    elif "--resumo" in sys.argv:
        resumo()
    elif "--faltam" in sys.argv:
        faltam()


if __name__ == "__main__":
    main()
