"""Desempate CEGO das divergências — e medição do meu próprio viés.

O usuário levantou o problema certo: quem desempata Claude contra DeepSeek não
pode ser o Claude, porque é parte na disputa. A solução dele — dizer no prompt
para não puxar para o próprio lado — declara o conflito mas não o remove.

Aqui a origem é removida da informação, não pedida por instrução. Os dois
pareceres viram "A" e "B", em ordem embaralhada por uma semente derivada da
própria chave (reprodutível, mas sem relação com quem escreveu). Quem julga não
tem como saber qual é qual.

Isso permite medir o viés em vez de discutir sobre ele: se, ao julgar cego, eu
escolher os pareceres do Claude na mesma proporção em que os escolhia sabendo,
não há viés detectável. Se a proporção cair, havia — e o desempate tem de sair
de mim.

    python3 scripts/desempate_cego.py --caso <chave>    # dossiê cego
    python3 scripts/desempate_cego.py --escolher <chave> <A|B|nenhum> "<razão>"
    python3 scripts/desempate_cego.py --vies              # a medição
    python3 scripts/desempate_cego.py --lista [N]
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import auditoria as A  # noqa: E402
import auditor_deepseek as D  # noqa: E402

DESTINO = RAIZ / "reports/varredura_padronizacao/DESEMPATE.json"


def ordem(k: str) -> bool:
    """True = o parecer do Claude sai como A. Estável por chave, sem padrão."""
    return hashlib.sha256(k.encode()).digest()[0] % 2 == 0


def divergencias() -> list[str]:
    meu, dele = A.carrega(), D.carrega()
    return sorted(k for k in dele if k in meu
                  and dele[k].get("veredito") not in ("erro", "?")
                  and meu[k]["veredito"] != dele[k]["veredito"])


def caso(k: str) -> str:
    meu, dele = A.carrega(), D.carrega()
    c, d = meu[k], dele[k]
    a, b = (c, d) if ordem(k) else (d, c)
    return (A.dossie(k) +
            f"\n=== DOIS PARECERES INDEPENDENTES (origem omitida de propósito) ===\n"
            f"\nPARECER A — {a['veredito']}\n  {a['nota']}\n"
            f"\nPARECER B — {b['veredito']}\n  {b['nota']}\n"
            f"\nQual dos dois se sustenta contra o japonês? Responda A, B, ou "
            f"'nenhum' se os dois erram.\n")


def carrega() -> dict:
    return json.loads(DESTINO.read_text(encoding="utf-8")) if DESTINO.exists() else {}


def escolher(k: str, escolha: str, razao: str) -> None:
    if escolha not in ("A", "B", "nenhum"):
        print("escolha inválida: use A, B ou nenhum")
        sys.exit(1)
    d = carrega()
    # a origem só é revelada AQUI, depois da decisão gravada
    if escolha == "nenhum":
        vencedor = "nenhum"
    else:
        claude_e_A = ordem(k)
        vencedor = "claude" if (escolha == "A") == claude_e_A else "deepseek"
    d[k] = {"escolha": escolha, "vencedor": vencedor, "razao": razao}
    DESTINO.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"gravado: {escolha} -> venceu o parecer do {vencedor}")


def vies() -> None:
    d = carrega()
    if not d:
        print("nenhum desempate cego ainda")
        return
    c = Counter(v["vencedor"] for v in d.values())
    n = sum(c[x] for x in ("claude", "deepseek"))
    print(f"{len(d)} desempates cegos")
    for k, v in c.most_common():
        print(f"  {k:<10} {v:>4}" + (f"  ({v/n:.0%} dos decididos)" if k != "nenhum" and n else ""))
    if n >= 20:
        p = c["claude"] / n
        print(f"\nreferência: no julgamento NÃO cego de 2026-08-09, eu me dei "
              f"razão em 9 de 14 decididos = 64%")
        print(f"cego: {p:.0%}")
        if abs(p - 0.64) >= 0.15:
            print("-> diferença relevante: havia viés, e o desempate não deve ser meu")
        else:
            print("-> sem diferença relevante nesta amostra")
    else:
        print(f"\n(amostra pequena — {n} decididos; a medição pede ao menos 20)")


def main() -> None:
    if "--caso" in sys.argv:
        print(caso(sys.argv[sys.argv.index("--caso") + 1]))
    elif "--escolher" in sys.argv:
        i = sys.argv.index("--escolher")
        escolher(sys.argv[i + 1], sys.argv[i + 2], sys.argv[i + 3])
    elif "--vies" in sys.argv:
        vies()
    else:
        n = int(sys.argv[sys.argv.index("--lista") + 1]) if "--lista" in sys.argv else 30
        feitos = set(carrega())
        pend = [k for k in divergencias() if k not in feitos]
        print(f"{len(pend)} divergências à espera de desempate (de "
              f"{len(divergencias())} no total)\n")
        for k in pend[:n]:
            print(f"  {k}")


if __name__ == "__main__":
    main()
