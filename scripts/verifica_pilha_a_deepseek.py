"""Segunda leitura independente (DeepSeek) dos 4.495 trechos da pilha A --
as correções unânimes (DS1=DS2=desafiador "aprovado") já aplicadas ao corpus
por aplicar_pilha_a.py. Mesmo método de verifica_trechos_alterados_deepseek.py
(que cobre os 523 da pilha C), fonte e destino separados para não competir
pelo mesmo arquivo enquanto os dois rodam ao mesmo tempo.

    python3 scripts/verifica_pilha_a_deepseek.py
    python3 scripts/verifica_pilha_a_deepseek.py --relatorio
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

import verifica_fidelidade as V  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

R = RAIZ / "reports/varredura_padronizacao"
FONTE = Path("/tmp/claude-0/-var-www-goshinsho/9b3b11e7-4883-4ae9-9b3b-2fbf84182cdd/scratchpad/trechos_pilha_a.json")
DEST = R / "VERIFICACAO_DEEPSEEK_PILHA_A.json"
MODELO = "deepseek-v4-flash"
PARALELISMO = 20
MAX_TOKENS = 8192
MAX_JP = 40000

SYSTEM = """Você confere se uma correção aplicada a uma tradução do
japonês para o português está certa -- lendo o japonês do zero, sem
saber por que a correção foi feita.

Você recebe o japonês do artigo inteiro, o texto ANTES da correção
("de") e o texto DEPOIS ("final"). O "final" é o que está publicado
agora. Diga se "final" é uma tradução fiel e correta do trecho japonês
correspondente -- não se é "melhor estilisticamente" que "de", mas se
afirma o que o japonês afirma, sem inverter sujeito, sentido, número,
nome próprio, ou trocar termo doutrinário fixo.

Se você não conseguir localizar com segurança a que trecho do japonês
"final" corresponde, diga isso explicitamente em vez de adivinhar.

Responda UMA única linha:

OK | <por que "final" está certo, citando o japonês, em uma frase>
PROBLEMA | <o que exatamente está errado em "final", citando o japonês>
NAO_LOCALIZADO | <por que não deu para confirmar contra o japonês>
"""


def dossie(c: dict) -> str:
    jp, pt = V.textos(c["obra"], c["artigo"])
    if not jp:
        jp = "(japonês não localizado para este artigo)"
    return (f"=== JAPONÊS DO ARTIGO (obra: {c['obra_curta']}, artigo {c['artigo']}) ===\n"
            f"{jp[:MAX_JP]}\n\n"
            f"=== TEXTO ANTES (\"de\") ===\n{c['de']}\n\n"
            f"=== TEXTO DEPOIS (\"final\", publicado agora) ===\n{c['final']}\n\n"
            f"\"final\" está correto?")


def verifica(c: dict) -> dict:
    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": dossie(c)}])
    texto = (r.choices[0].message.content or "").strip()
    primeira = next((l for l in texto.splitlines() if l.strip()), "")
    p = [x.strip() for x in primeira.split("|")]
    veredito = p[0].upper() if p else "?"
    if not veredito.startswith(("OK", "PROBLEMA", "NAO_LOCALIZADO")):
        veredito = "?"
    else:
        veredito = veredito.split()[0]
    return {**c, "veredito": veredito, "razao": p[-1] if len(p) > 1 else primeira}


def main() -> None:
    if "--relatorio" in sys.argv:
        relatorio()
        return
    itens = json.loads(FONTE.read_text(encoding="utf-8"))
    feitos: dict[str, dict] = json.loads(DEST.read_text(encoding="utf-8")) if DEST.exists() else {}
    cs = [c for c in itens if c["chave"] not in feitos]
    print(f"{len(cs)} a fazer ({len(feitos)} já feitos)", flush=True)
    trava, n = threading.Lock(), [0]

    def trabalho(c):
        try:
            r = verifica(c)
        except Exception as exc:
            r = {**c, "veredito": "ERRO", "razao": repr(exc)[:140]}
        with trava:
            feitos[c["chave"]] = r
            n[0] += 1
            if n[0] % 40 == 0:
                DEST.write_text(json.dumps(feitos, ensure_ascii=False, indent=1), encoding="utf-8")
                from collections import Counter
                c2 = Counter(x.get("veredito") for x in feitos.values())
                print(f"  [{n[0]}/{len(cs)}] {dict(c2)}", flush=True)

    if cs:
        with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
            list(pool.map(trabalho, cs))
    DEST.write_text(json.dumps(feitos, ensure_ascii=False, indent=1), encoding="utf-8")
    relatorio()


def relatorio() -> None:
    if not DEST.exists():
        print("nada feito ainda")
        return
    d = json.loads(DEST.read_text(encoding="utf-8"))
    from collections import Counter
    c = Counter(v.get("veredito") for v in d.values())
    print(f"{len(d)} verificados")
    for k, v in c.most_common():
        print(f"  {v:>4}  {k}")


if __name__ == "__main__":
    main()
