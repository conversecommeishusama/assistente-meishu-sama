"""Segunda passada semântica: as quatro decisões de 2026-08-08.

Mesma disciplina da primeira (`reaplica_semantico.py`), que existe porque os
scripts de substituição produziram 355 erros em 1.292 alterações:

    "TODO O TRABALHO DEVE SER FEITO LINHA A LINHA COMPARANDO JP PT DE FORMA
     SEMÂNTICA."

Nada aqui nasce de busca-e-troca. O modelo lê o artigo japonês e o português
lado a lado e devolve trecho a trecho. Cada proposta é conferida contra o
português antes de gravar, e só grava se o trecho for único no arquivo.

Só entra o artigo em que o japonês traz a chave MAIS vezes do que o português
traz a forma canônica -- assim uma obra já correta não gasta leitura.

Uso:
    python3 scripts/reaplica_semantico2.py            # lê e propõe
    python3 scripts/reaplica_semantico2.py --aplicar  # grava o já lido
"""

from __future__ import annotations

import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import reaplica_semantico as R  # noqa: E402  (reaproveita artigos/aplicar)
from goshinsho.services import agentic_search as ag  # noqa: E402

DESTINO = RAIZ / "reports/varredura_padronizacao/REAPLICACAO_SEMANTICA3.json"
MODELO = "deepseek-v4-flash"
PARALELISMO = 8

# (rótulo, regex no japonês, regex da forma canônica no português)
# Os lookbehind excluem os compostos que já têm decisão própria e diferente.
GATILHOS = [
    ("教修", r"教修", r"curso \(aula\) de prepara|curso de prepara|kyoshu"),
    ("主神", r"主神", r"Deus Supremo"),
    ("天照皇大神", r"天照皇大神", r"Amaterasu Ōmikami"),
    ("大和民族", r"大和民族", r"Raça de Yamato"),
    ("観音力", r"観音力", r"Poder Kannon"),
    ("観世音菩薩", r"観世音菩薩", r"Kanzeon-Bosatsu"),
    ("稲荷", r"稲荷", r"Inari"),
    ("浄霊", r"(?<!法)浄霊(?!法)", r"Johrei"),
    ("夜の世界", r"夜の世界", r"Mundo da Noite"),
    ("仏滅", r"仏滅", r"Extinção do Budismo"),
    ("自観", r"自観", r"Jikan"),
    ("正神", r"正神", r"divindades corretas"),
    ("弥勒三会", r"弥勒三会", r"encontro dos três Miroku"),
    ("御霊徳", r"御霊徳", r"Graças Divinas"),
]

SYSTEM = """Você é revisor de tradução japonês→português do acervo de Meishu-Sama (Igreja Messiânica Mundial).

Recebe UM artigo em japonês e o MESMO artigo em português. Leia os dois frase a frase e aplique as formas canônicas abaixo — SOMENTE onde o japonês daquele ponto trouxer a chave. Todas já foram decididas pelo usuário em sessões anteriores; o corpus as viola em pontos isolados.

教修 → "curso (aula) de preparação para receber o Ohikari (kyoshu)", em texto
    corrido. NÃO é "curso de iniciação". EXCEÇÃO: 英語教修 é a palestra em
    inglês no Museu de Hakone, e continua "palestra".
主神 → "Deus Supremo" (nunca "Deus Principal")
天照皇大神 → "Amaterasu Ōmikami" (com mácron)
大和民族 → "Raça de Yamato"     観音力 → "Poder Kannon"
観世音菩薩 → "Kanzeon-Bosatsu". CUIDADO: 観音様 é "Kannon-Sama" e 観音 sozinho
    é "Kannon" — termos distintos que NÃO mudam.
稲荷 → "Inari" (nome da divindade; não traduzir por "Raposa". CUIDADO: 狐 é
    "raposa" de verdade e não muda.)
浄霊 → "Johrei". CUIDADO GRAVE: 浄化 é "purificação" e 浄霊法 é "método do
    Johrei" — NÃO converta um no outro.
夜の世界 → "Mundo da Noite"      仏滅 → "Extinção do Budismo"
自観 → "Jikan" (pseudônimo literário do próprio Meishu-Sama; a série
    自観叢書 é "Jikan Sōsho")
正神 → "divindades corretas". CUIDADO: 邪神 é termo distinto e não muda aqui.
弥勒三会 → "O encontro dos três Miroku"
御霊徳 → "Graças Divinas". CUIDADO: 御利益 é "benefício material", termo
    DIFERENTE, e não muda aqui.

REGRAS DE OURO:
1. Só proponha troca se o japonês DAQUELE ponto trouxer a chave. Se não
   conseguir localizar a correspondência, não proponha.
2. Preserve a gramática: gênero, número, artigo, preposição contraída.
3. Nunca toque numa palavra portuguesa que apenas contenha o termo como
   pedaço.
4. O trecho que você citar precisa existir LITERALMENTE no português dado.
5. Se a forma atual já for equivalente e o japonês for ambíguo, não proponha.

FORMATO — uma linha por ocorrência, nada mais:

TROCA | <trecho português exato, 4 a 10 palavras> | <o mesmo trecho corrigido>

Se o artigo não precisar de nenhuma mudança:

NADA
"""


def alvos() -> list[dict]:
    saida = []
    for p in sorted(R.PT_FONTE.glob("*.txt")):
        obra = p.name
        ajp = R.artigos(R.JP_DIR / obra, "jp_anchor", obra)
        apt = R.artigos(p, "pt_anchor", obra)
        if not ajp or len(ajp) != len(apt):
            continue
        for i, (jp, pt) in enumerate(zip(ajp, apt)):
            falta = any(
                len(re.findall(rj, jp)) > len(re.findall(rp, pt))
                and re.search(rj, jp)
                for _, rj, rp in GATILHOS)
            if falta:
                saida.append({"obra": obra, "artigo": i,
                              "jp": jp[:14000], "pt": pt[:14000]})
    return saida


def julga(item: dict) -> dict:
    pedido = (f"ORIGEM: {item['obra']} (artigo {item['artigo']})\n\n"
              f"=== JAPONÊS ===\n{item['jp']}\n\n"
              f"=== PORTUGUÊS ===\n{item['pt']}")
    texto, tokens, tent = "", 0, 0
    while not texto.strip() and tent < 3:
        tent += 1
        extra = "\n\nIMPORTANTE: responda DIRETAMENTE no formato." if tent > 1 else ""
        r = ag._client().chat.completions.create(
            model=MODELO, max_tokens=16000,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": pedido + extra}])
        u = r.usage
        tokens += (u.prompt_tokens or 0) + (u.completion_tokens or 0)
        texto = r.choices[0].message.content or ""
    trocas = []
    for ln in texto.splitlines():
        if not ln.strip().upper().startswith("TROCA"):
            continue
        partes = [x.strip() for x in ln.split("|")]
        if (len(partes) >= 3 and partes[1] and partes[2]
                and partes[1] != partes[2] and partes[1] in item["pt"]):
            trocas.append({"de": partes[1], "para": partes[2]})
    return {"obra": item["obra"], "artigo": item["artigo"],
            "trocas": trocas, "tokens": tokens, "bruto": texto[:4000]}


def main() -> None:
    if "--aplicar" in sys.argv:
        R.DESTINO = DESTINO          # reaproveita a gravação já endurecida
        R.aplicar()
        return
    itens = alvos()
    feitos = []
    if DESTINO.exists():
        feitos = [r for r in json.loads(DESTINO.read_text(encoding="utf-8"))
                  if "erro" not in r]
        vistos = {(r["obra"], r["artigo"]) for r in feitos}
        itens = [i for i in itens if (i["obra"], i["artigo"]) not in vistos]
        print(f"retomando: {len(feitos)} lidos, {len(itens)} restantes", flush=True)
    print(f"{len(itens)} artigos a ler\n", flush=True)

    trava, n = threading.Lock(), [0]

    def trabalho(it):
        try:
            r = julga(it)
        except Exception as exc:
            r = {"obra": it["obra"], "artigo": it["artigo"],
                 "erro": repr(exc)[:140], "trocas": []}
        with trava:
            feitos.append(r)
            n[0] += 1
            if n[0] % 25 == 0:
                print(f"[{n[0]:>4}/{len(itens)}] {r['obra'][:30]:<32} "
                      f"{sum(len(x.get('trocas', [])) for x in feitos)} trocas acumuladas",
                      flush=True)
            DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                               encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, itens))
    tk = sum(r.get("tokens", 0) for r in feitos)
    tot = sum(len(r.get("trocas", [])) for r in feitos)
    err = sum(1 for r in feitos if "erro" in r)
    print(f"\n{len(feitos)} artigos lidos | {tot} trocas propostas | {err} erros | "
          f"{tk:,} tokens | ~US$ {tk / 1e6 * 0.0424:.3f}")


if __name__ == "__main__":
    main()
