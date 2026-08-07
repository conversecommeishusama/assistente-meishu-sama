"""Repara o excesso de "norito" LENDO cada passagem contra o japonês.

Instrução permanente do usuário, registrada em CLAUDE.md: *"a ÚNICA forma que
funciona é linha a linha de forma semântica e comparativa com o jp... o padrão
é 100%, não importa o custo e o tempo."* Contrariei isso ao aplicar
`祝詞 -> norito` por script, e o script trocou ~400 ocorrências onde eu tinha
aprovado 28 (contava por artigo, aplicava no arquivo inteiro).

O reparo por contexto recuperou 306. Sobram 63 ocorrências em 36 artigos onde
o português diz "norito" mais vezes do que o japonês diz 祝詞. Este script não
adivinha: manda cada artigo para leitura, com o japonês ao lado, e o modelo
diz qual palavra portuguesa cada "norito" indevido deveria ser -- 祈り e 祈願
viram "oração"/"prece", conforme o texto.

Uso:
    python3 scripts/repara_norito_semantico.py            # julga
    python3 scripts/repara_norito_semantico.py --aplicar
"""

from __future__ import annotations

import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402
import aplica_decisoes_glossario as A  # noqa: E402

DESTINO = RAIZ / "reports/varredura_padronizacao/NORITO_REPARO.json"
MODELO = "deepseek-v4-flash"
PARALELISMO = 6

SYSTEM = """Você revisa a tradução japonês→português do acervo de Meishu-Sama.

Um script trocou por engano várias palavras portuguesas por "norito". "Norito" só é correto quando o japonês traz 祝詞 (a oração ritual). Onde o japonês traz 祈り, 祈願, お祈り ou nada equivalente, a palavra portuguesa original era outra — em geral "oração", "orações", "prece" ou "preces".

Você recebe o japonês do artigo e o português correspondente. Para CADA ocorrência de "norito" no português, decida:

- se o japonês naquele ponto traz 祝詞, está correto e não se mexe;
- se traz 祈り/祈願/お祈り ou nenhum termo de oração ritual, diga por qual palavra trocar.

FORMATO — uma linha por ocorrência a corrigir, nada mais:

TROCA | <trecho português exato, 4 a 9 palavras, contendo o "norito" a mudar> | <o mesmo trecho corrigido>

Se todas as ocorrências estiverem corretas, escreva apenas:

MANTEM | todas justificadas por 祝詞

Regras: nunca invente trecho que não esteja no português fornecido; preserve a gramática (artigo, número, concordância) ao trocar; se não conseguir decidir uma ocorrência com segurança, deixe-a de fora."""


def alvos() -> list[dict]:
    dados = json.loads(Path("/tmp/claude-0/-var-www-goshinsho/"
                            "93cc2acd-f9e6-4ff2-b942-0e3ca3edf006/scratchpad/"
                            "norito_alvo.json").read_text(encoding="utf-8"))
    saida = []
    for d in dados:
        ajp, apt = A.par(d["obra"])
        jp, pt = ajp[d["artigo"]], apt[d["artigo"]]
        trechos = [re.sub(r"\s+", " ", jp[max(0, m.start() - 90): m.start() + 90])
                   for m in re.finditer(r"祝詞|祈り|祈願|お祈り", jp)]
        saida.append({"obra": d["obra"], "artigo": d["artigo"],
                      "jp_trechos": trechos[:12], "jp_conta": d["jp"],
                      "pt_conta": d["pt"], "pt": pt[:14000]})
    return saida


def julga(item: dict) -> dict:
    pedido = (
        f"ORIGEM: {item['obra']} (artigo {item['artigo']})\n"
        f"O japonês tem 祝詞 {item['jp_conta']}x; o português tem \"norito\" "
        f"{item['pt_conta']}x — logo {item['pt_conta'] - item['jp_conta']} "
        f"estão errados.\n\n"
        "TRECHOS JAPONESES COM TERMO DE ORAÇÃO:\n"
        + "\n".join(f"  {k}. {t}" for k, t in enumerate(item["jp_trechos"], 1))
        + f"\n\nPORTUGUÊS DO ARTIGO:\n{item['pt']}")
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
        if (len(partes) >= 3 and partes[1] and partes[2] and partes[1] != partes[2]
                and "norito" in partes[1].lower()):
            trocas.append({"de": partes[1], "para": partes[2]})
    return {"obra": item["obra"], "artigo": item["artigo"],
            "trocas": trocas, "tokens": tokens, "bruto": texto}


def aplicar() -> None:
    dados = json.loads(DESTINO.read_text(encoding="utf-8"))
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    por_obra: dict[str, list[dict]] = {}
    for d in dados:
        for t in d.get("trocas", []):
            por_obra.setdefault(d["obra"], []).append(t)
    apl = ign = 0
    for obra, ts in por_obra.items():
        for base in (A.PT_FONTE, A.PT_STAGING):
            f = base / obra
            if not f.exists():
                continue
            texto = f.read_text(encoding="utf-8")
            if base is A.PT_FONTE:
                f.with_suffix(f".txt.bak_pre_norito_{carimbo}").write_text(texto, encoding="utf-8")
            for t in ts:
                if texto.count(t["de"]) != 1:
                    if base is A.PT_FONTE:
                        ign += 1
                    continue
                texto = texto.replace(t["de"], t["para"])
                if base is A.PT_FONTE:
                    apl += 1
            f.write_text(texto, encoding="utf-8")
    print(f"{apl} trocas aplicadas, {ign} ignoradas (trecho não único)")

    ruins = 0
    for obra in por_obra:
        sp = A.SPEC_DIR / f"{obra}.json"
        spec = json.loads(sp.read_text(encoding="utf-8"))
        anc = [a.get("pt_anchor", "") for a in spec.get("articles", [])]
        if len(anc) <= 1 or not all(anc):
            continue
        for base in (A.PT_FONTE, A.PT_STAGING):
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
    print(f"  {len(por_obra)} obras, {ruins} âncoras quebradas")


def main() -> None:
    if "--aplicar" in sys.argv:
        aplicar()
        return
    itens = alvos()
    print(f"{len(itens)} artigos a ler\n", flush=True)
    feitos, trava, n = [], threading.Lock(), [0]

    def trabalho(it):
        try:
            r = julga(it)
        except Exception as exc:
            r = {"obra": it["obra"], "artigo": it["artigo"],
                 "erro": repr(exc)[:140], "trocas": []}
        with trava:
            feitos.append(r)
            n[0] += 1
            print(f"[{n[0]:>3}/{len(itens)}] {it['obra'][:30]:<32} art{it['artigo']:<4} "
                  f"{len(r.get('trocas', []))} trocas", flush=True)
            DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                               encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, itens))
    tk = sum(r.get("tokens", 0) for r in feitos)
    print(f"\n{sum(len(r.get('trocas', [])) for r in feitos)} trocas propostas | "
          f"{tk:,} tokens | ~US$ {tk / 1e6 * 0.0424:.4f}")


if __name__ == "__main__":
    main()
