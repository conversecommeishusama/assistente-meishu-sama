"""Separa, entre os vereditos que mudaram, quais mudaram POR CAUSA do OCR.

Depois de emendar 7.137 caracteres do japonês, 935 achados foram rejulgados e
cerca de 10% mudaram de veredito. Contar isso não responde nada: as mudanças
vieram simétricas -- 33 de aprovado para recusado e 30 no sentido inverso --,
e mudança simétrica é assinatura de variação do modelo, não de fonte corrigida.

A pergunta certa é uma a uma: ESTA mudança decorre do japonês restaurado, ou o
agente teria mudado de qualquer forma? O desafiador julga cego ao próprio
parecer anterior -- desenho deliberado, para o julgamento ser independente --,
e por isso a saída dele não diz por quê. Nas 16 derrubadas que caíram eu tive
de reconstruir isso lendo, e só 3 citavam um kanji restaurado. Se eu tivesse
parado na contagem, teria creditado 16 à emenda e errado em 13.

O QUE ESTE SCRIPT É, E O QUE NÃO É. Ele não decide. Ele monta a fila de
leitura: põe o japonês de antes e o de agora lado a lado com os dois vereditos,
pergunta ao agente se a mudança decorre da correção, e ordena o resultado por
essa alegação. Quem decide é a leitura -- a minha, depois. Perguntar a um
modelo por que ele mudou de ideia produz racionalização, não causa; o que torna
a resposta conferível é o japonês estar ali dos dois lados, para eu ver se o
kanji que ele invoca existe mesmo na passagem em disputa.

O código só reduz quanto eu preciso ler. Não confirma.

    python3 scripts/atribui_ocr.py            # roda sobre tudo que mudou
    python3 scripts/atribui_ocr.py --relatorio
"""

from __future__ import annotations

import json
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import auditoria as A  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

R = RAIZ / "reports/varredura_padronizacao"
DESTINO = R / "ATRIBUICAO_OCR.json"
MODELO = "deepseek-v4-flash"
TETO = 8192
PARALELISMO = 8

SYSTEM = """Você recebe um achado de revisão de tradução japonês->português que
foi julgado DUAS vezes: antes e depois de o japonês ter sido corrigido.

O japonês dos periódicos vinha de leitura óptica com caracteres trocados por
outros de forma parecida -- 实 por 実, 吉 por 同, 后 por 向, 名 por 吐, 喛 por
喜, 抭 por 抱. Quem julgou da primeira vez leu o texto adulterado.

Sua única tarefa é dizer se a mudança de veredito DECORRE dessa correção.

Decorre quando o caractere restaurado está na passagem em disputa e muda o que
ela diz -- por exemplo, o primeiro parecer alegou 本来 onde o texto agora traz
未来, ou leu 惹かれ onde havia 抱かれ.

NÃO decorre quando o japonês da passagem é o mesmo nos dois lados, ou quando o
caractere mudou num ponto que não tem relação com o que se discute. Nesse caso
o agente simplesmente mudou de opinião, e é isso que você deve responder --
sem inventar uma ligação para justificar a mudança.

Responda UMA linha:

SIM | <o caractere restaurado e como ele muda a passagem>
NAO | <por que a mudança não tem relação com a correção>
"""


def mudancas() -> list[dict]:
    """Achados cujo veredito difere entre o backup mais antigo e o estado atual."""
    proc = {A.chave(r): r for r in A.procedentes()}
    # japonês citado ANTES da emenda
    vb = json.loads(sorted(R.glob("VERIFICACAO_FIDELIDADE.json.bak_ocr_*"))[0]
                    .read_text(encoding="utf-8"))
    jp_antes = {A.chave(r): r.get("jp_apoio", "") for r in vb
                if "erro" not in r and r.get("procede")}

    out = []
    for nome in ("AUDITORIA_DEEPSEEK", "AUDITORIA_DEEPSEEK2", "DESAFIADOR"):
        baks = sorted(R.glob(f"{nome}.json.bak_ocr_*"))
        if not baks:
            continue
        velho = json.loads(baks[0].read_text(encoding="utf-8"))
        novo = json.loads((R / f"{nome}.json").read_text(encoding="utf-8"))
        for k in novo:
            if k not in velho or k not in proc:
                continue
            a, b = velho[k], novo[k]
            if "erro" in a or "erro" in b:
                continue
            # o desafiador guarda `derruba`; os auditores guardam `veredito`
            va = a.get("veredito", a.get("derruba"))
            vb_ = b.get("veredito", b.get("derruba"))
            if va == vb_:
                continue
            out.append({
                "chave": k, "agente": nome, "obra": proc[k]["obra"],
                "artigo": proc[k]["artigo"],
                "de": proc[k]["de"], "para": proc[k]["para"],
                "jp_antes": jp_antes.get(k, ""),
                "jp_agora": proc[k].get("jp_apoio", ""),
                "antes": f"{va} — {a.get('nota', a.get('razao', ''))}",
                "agora": f"{vb_} — {b.get('nota', b.get('razao', ''))}",
            })
    return out


def pergunta(m: dict) -> dict:
    dif = "DIFEREM" if m["jp_antes"] != m["jp_agora"] else "são idênticos"
    corpo = (
        f"OBRA: {m['obra']} artigo {m['artigo']}\n\n"
        f"=== JAPONÊS DA PASSAGEM, ANTES da emenda ===\n{m['jp_antes'][:900]}\n\n"
        f"=== JAPONÊS DA PASSAGEM, DEPOIS ===\n{m['jp_agora'][:900]}\n"
        f"(os dois {dif})\n\n"
        f"=== PORTUGUÊS ===\ntrecho atual: {m['de'][:400]}\n"
        f"correção proposta: {m['para'][:400]}\n\n"
        f"=== PARECER ANTES ===\n{m['antes'][:700]}\n\n"
        f"=== PARECER AGORA ===\n{m['agora'][:700]}\n\n"
        f"A mudança de parecer decorre do japonês corrigido?")
    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=TETO,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": corpo}])
    prim = next((l for l in (r.choices[0].message.content or "").splitlines()
                 if l.strip()), "")
    p = [x.strip() for x in prim.split("|")]
    return {"ocr": p[0].upper().startswith("SIM"),
            "razao": p[-1] if len(p) > 1 else prim,
            "jp_mudou": m["jp_antes"] != m["jp_agora"]}


def relatorio() -> None:
    d = json.loads(DESTINO.read_text(encoding="utf-8"))
    ms = {m["chave"] + "|" + m["agente"]: m for m in mudancas()}
    c = Counter((v["ocr"], v["jp_mudou"]) for v in d.values())
    print(f"{len(d)} mudanças de veredito examinadas\n")
    print(f"  atribuídas à emenda do OCR ....... {sum(1 for v in d.values() if v['ocr'])}")
    print(f"  o agente mudou de opinião ........ {sum(1 for v in d.values() if not v['ocr'])}\n")
    print("  cruzando com o japonês da passagem ter mudado de fato:")
    for (o, j), n in c.most_common():
        print(f"    alega OCR={'sim' if o else 'não'}  japonês mudou={'sim' if j else 'não'}  {n}")
    print("\n--- FILA DE LEITURA: as que alegam OCR, para eu conferir uma a uma ---")
    for k, v in d.items():
        if not v["ocr"]:
            continue
        m = ms.get(k)
        if not m:
            continue
        print(f"\n  {m['obra'][:30]} art{m['artigo']}  [{m['agente'].replace('AUDITORIA_','')}]")
        print(f"    JP antes : {m['jp_antes'][:100]}")
        print(f"    JP agora : {m['jp_agora'][:100]}")
        print(f"    alegação : {v['razao'][:170]}")


def main() -> None:
    if "--relatorio" in sys.argv:
        relatorio()
        return
    ms = mudancas()
    feitos = json.loads(DESTINO.read_text(encoding="utf-8")) if DESTINO.exists() else {}
    fila = [m for m in ms if m["chave"] + "|" + m["agente"] not in feitos]
    print(f"{len(ms)} mudanças de veredito; {len(fila)} a examinar\n", flush=True)
    if not fila:
        relatorio()
        return

    trava, n = threading.Lock(), [0]

    def trabalho(m):
        try:
            r = pergunta(m)
        except Exception as exc:
            r = {"ocr": False, "razao": f"erro: {exc!r}"[:90], "jp_mudou": None}
        with trava:
            feitos[m["chave"] + "|" + m["agente"]] = r
            n[0] += 1
            if n[0] % 20 == 0:
                print(f"  [{n[0]}/{len(fila)}]", flush=True)
                DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                                   encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, fila))
    DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    relatorio()


if __name__ == "__main__":
    main()
