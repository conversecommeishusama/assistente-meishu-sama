"""Etapa 3 -- julgamento das entradas do glossário, uma por vez, via DeepSeek.

Cada entrada é julgada UMA vez, com toda a evidência junta: a chave japonesa,
a forma canônica registrada, a taxa de aplicação no acervo, e os trechos reais
onde a chave aparece no japonês sem a forma canônica no português.

Julgar por TERMO e não por ocorrência é o ponto central. Permite distinguir:

  - violação pontual        -- o termo é a regra e alguém escorregou em 2 de 300
  - divergência sistemática -- o português usa outra forma de maneira
                               consistente, o que é pergunta de glossário para
                               o usuário, não erro a corrigir em 40 lugares
  - falso positivo          -- a chave japonesa ali significa outra coisa, ou
                               o casamento automático não reconheceu a forma

Pré-requisito: scripts/glossario_taxa_aplicacao.py (gera GLOSSARIO_TAXA.json).

Uso:
    python3 scripts/glossario_julga_deepseek.py --faixa E
    python3 scripts/glossario_julga_deepseek.py --faixa A --limite 40
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402
from glossario_taxa_aplicacao import fold, formas_aceitas  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

PT_DIR = RAIZ / "livros_publicacao_pt_revisado"
JP_DIR = RAIZ / "reports/livros_trabalho/jp"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
SAIDA = RAIZ / "reports/varredura_padronizacao"
MODELO = "deepseek-v4-flash"

MAX_AMOSTRAS = 4
MAX_PT_POR_AMOSTRA = 2200
# O raciocínio do deepseek-v4-flash consome a maior parte do orçamento de
# saída (medido nesta sessão: 72-77% dos tokens de saída). Com max_tokens=4000
# a primeira rodada devolveu resposta VAZIA em 3 de 3 termos, gastando 11.716
# tokens sem produzir uma linha. O orçamento precisa caber raciocínio E
# resposta.
MAX_TOKENS = 16000
PARALELISMO = 6

SYSTEM = """Você julga entradas do glossário de tradução japonês→português do acervo de Meishu-Sama (Igreja Messiânica Mundial).

Recebe UMA entrada e as passagens reais em que a chave japonesa aparece no original SEM a forma canônica registrada aparecer no português correspondente.

Sua tarefa é decidir o que essa divergência é, e a decisão tem exatamente três saídas:

1. VIOLACAO — o termo é regra fixa e o português deveria usar a forma canônica. Diga, para cada passagem, que palavra o português usou no lugar.
2. SISTEMATICO — o português usa outra forma de maneira consistente e defensável. Isto NÃO é erro a corrigir passagem por passagem: é uma pergunta de glossário. Diga qual forma o corpus prefere e por quê ela pode ser a certa.
3. FALSO_POSITIVO — não há divergência real. Ou a chave japonesa ali tem outro sentido (kanji dentro de composto, homógrafo, citação), ou o português usou uma variante legítima que o casamento automático não reconheceu (flexão, sinônimo da própria entrada, forma abreviada).

REGRAS:
- Baseie-se no japonês das passagens, não em conhecimento geral do termo.
- Se as passagens forem de tipos diferentes, escolha a saída que vale para a MAIORIA e explique a exceção.
- Não invente que o português "deveria" dizer algo que a entrada não registra.
- Se a evidência não bastar para decidir, use INCERTO e diga exatamente o que faltou. Preferimos INCERTO a um palpite.

FORMATO — responda só isto, sem preâmbulo:

VEREDITO: <VIOLACAO|SISTEMATICO|FALSO_POSITIVO|INCERTO>
FORMA_USADA: <a palavra ou expressão que o português usa no lugar, ou "-" se não se aplica>
JUSTIFICATIVA: <no máximo 3 frases, citando o japonês>
PARA_O_USUARIO: <se for SISTEMATICO ou INCERTO, a pergunta objetiva a fazer; senão "-">"""


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


_cache: dict[str, tuple[list[str], list[str]]] = {}


def par_de_artigos(obra: str) -> tuple[list[str], list[str]]:
    if obra not in _cache:
        spec = json.loads((SPEC_DIR / f"{obra}.json").read_text(encoding="utf-8"))
        _cache[obra] = (artigos(JP_DIR / obra, spec, "jp_anchor"),
                        artigos(PT_DIR / obra, spec, "pt_anchor"))
    return _cache[obra]


def coleta_amostras(chave: str, formas: list[str]) -> list[dict]:
    """Passagens reais onde a chave ocorre no JP sem forma canônica no PT."""
    amostras = []
    for pt_path in sorted(PT_DIR.glob("*.txt")):
        obra = pt_path.name
        if not (SPEC_DIR / f"{obra}.json").exists() or not (JP_DIR / obra).exists():
            continue
        ajp, apt = par_de_artigos(obra)
        if len(ajp) != len(apt):
            continue
        for i, (jp, pt) in enumerate(zip(ajp, apt)):
            if chave not in jp or not pt:
                continue
            if any(f in fold(pt) for f in formas):
                continue
            p = jp.find(chave)
            # Recorte PROPORCIONAL do português: se a chave está a 70% do
            # artigo japonês, a passagem correspondente está perto de 70% do
            # português. Mandar sempre o começo do artigo fazia o modelo
            # responder INCERTO por não enxergar o trecho -- 8 de 25 termos na
            # primeira rodada da faixa E, todos com a mesma justificativa
            # ("o excerto está truncado antes da frase que traduz...").
            if len(pt) <= MAX_PT_POR_AMOSTRA:
                janela, truncado = pt, False
            else:
                centro = int(len(pt) * (p / max(1, len(jp))))
                ini = max(0, centro - MAX_PT_POR_AMOSTRA // 2)
                janela = pt[ini: ini + MAX_PT_POR_AMOSTRA]
                truncado = True
            amostras.append({
                "obra": obra, "artigo": i,
                "jp": re.sub(r"\s+", " ", jp[max(0, p - 150): p + 220]),
                "pt": janela, "pt_truncado": truncado,
            })
            if len(amostras) >= MAX_AMOSTRAS:
                return amostras
    return amostras


def julga(chave: str, info: dict) -> dict:
    formas = formas_aceitas(info["canonico"])
    amostras = coleta_amostras(chave, formas)
    if not amostras:
        return {"chave": chave, "erro": "nenhuma amostra recuperada"}

    partes = [
        f"ENTRADA DO GLOSSÁRIO\n  chave japonesa: {chave}\n"
        f"  forma canônica registrada: {info['canonico']}\n\n"
        f"TAXA DE APLICAÇÃO NO ACERVO\n"
        f"  artigos em que a forma canônica FOI usada:  {info['hit']}\n"
        f"  artigos em que NÃO foi usada:               {info['miss']}\n"
        f"  ({info['taxa']:.0%} de aplicação)\n\n"
        f"PASSAGENS DIVERGENTES ({len(amostras)} de {info['miss']}):"
    ]
    for k, a in enumerate(amostras, 1):
        partes.append(
            f"\n--- passagem {k} — {a['obra']} (artigo {a['artigo']})\n"
            f"JAPONÊS ao redor da chave:\n{a['jp']}\n\n"
            f"PORTUGUÊS do mesmo artigo{' (janela ao redor da posição correspondente)' if a['pt_truncado'] else ''}:\n{a['pt']}")

    t0 = time.time()
    pedido = "\n".join(partes)
    texto, tokens, tentativas = "", 0, 0
    while not texto.strip() and tentativas < 3:
        tentativas += 1
        # Na retomada, pede resposta direta: sem isso o raciocínio volta a
        # consumir o orçamento inteiro e devolver vazio.
        extra = ("\n\nIMPORTANTE: escreva o veredito DIRETAMENTE no formato "
                 "pedido, sem deliberar longamente antes." if tentativas > 1 else "")
        resp = ag._client().chat.completions.create(
            model=MODELO, max_tokens=MAX_TOKENS,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": pedido + extra}],
        )
        u = resp.usage
        tokens += (u.prompt_tokens or 0) + (u.completion_tokens or 0)
        texto = resp.choices[0].message.content or ""
    ver = re.search(r"VEREDITO:\s*(\w+)", texto)
    forma = re.search(r"FORMA_USADA:\s*(.+)", texto)
    just = re.search(r"JUSTIFICATIVA:\s*(.+?)(?=\nPARA_O_USUARIO:|$)", texto, re.S)
    perg = re.search(r"PARA_O_USUARIO:\s*(.+)", texto, re.S)
    return {
        "chave": chave, "canonico": info["canonico"], "taxa": info["taxa"],
        "hit": info["hit"], "miss": info["miss"],
        "veredito": ver.group(1) if ver else "SEM_PARSE",
        "forma_usada": forma.group(1).strip() if forma else "",
        "justificativa": just.group(1).strip() if just else "",
        "para_o_usuario": perg.group(1).strip() if perg else "",
        "amostras": [{"obra": a["obra"], "artigo": a["artigo"]} for a in amostras],
        "tempo": round(time.time() - t0, 1),
        "tokens": tokens, "tentativas": tentativas,
        "resposta_bruta": texto,
    }


def faixa_de(v: dict) -> str:
    if v["natureza"] != "candidata":
        return "Z"
    t = v["taxa"]
    return "A" if t >= 0.9 else "B" if t >= 0.6 else "C" if t >= 0.25 else "D" if t > 0 else "E"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--faixa", default="E", help="A, B, C, D ou E")
    ap.add_argument("--limite", type=int, default=0)
    args = ap.parse_args()

    taxa = json.loads((SAIDA / "GLOSSARIO_TAXA.json").read_text(encoding="utf-8"))
    alvos = [(k, v) for k, v in taxa.items() if faixa_de(v) == args.faixa]
    # Termo sem nenhuma falta está 100% aplicado -- não há divergência para
    # julgar e chamar a API seria desperdício. Na primeira rodada da faixa A
    # esses 190 termos apareceram como "erro: nenhuma amostra recuperada",
    # o que é rótulo enganoso: eles são o melhor resultado possível.
    perfeitos = [k for k, v in alvos if v["miss"] == 0]
    alvos = [(k, v) for k, v in alvos if v["miss"] > 0]
    if perfeitos:
        print(f"{len(perfeitos)} termos com 100% de aplicação — nada a julgar", flush=True)
    alvos.sort(key=lambda x: -x[1]["miss"])
    if args.limite:
        alvos = alvos[: args.limite]
    print(f"faixa {args.faixa}: {len(alvos)} termos a julgar\n", flush=True)

    destino = SAIDA / f"GLOSSARIO_JULGAMENTO_{args.faixa}.json"
    feitos = []
    if destino.exists():
        feitos = json.loads(destino.read_text(encoding="utf-8"))
        ja = {r["chave"] for r in feitos}
        alvos = [(k, v) for k, v in alvos if k not in ja]
        print(f"retomando: {len(ja)} já julgados, {len(alvos)} restantes\n", flush=True)

    # Pré-carrega os artigos de todas as obras UMA vez, em série. `_cache` é
    # um dict compartilhado; deixá-lo ser preenchido por várias threads ao
    # mesmo tempo faria o mesmo arquivo ser lido e segmentado N vezes.
    print("pré-carregando artigos...", flush=True)
    for pt_path in sorted(PT_DIR.glob("*.txt")):
        obra = pt_path.name
        if (SPEC_DIR / f"{obra}.json").exists() and (JP_DIR / obra).exists():
            try:
                par_de_artigos(obra)
            except Exception:
                pass
    print(f"{len(_cache)} obras em memória\n", flush=True)

    trava = threading.Lock()
    tk = [0]
    feito_n = [0]

    def trabalho(item):
        chave, info = item
        try:
            r = julga(chave, info)
        except Exception as exc:
            r = {"chave": chave, "erro": repr(exc)[:200]}
        with trava:
            feitos.append(r)
            feito_n[0] += 1
            tk[0] += r.get("tokens", 0)
            if "erro" in r:
                print(f"[{feito_n[0]:>3}/{len(alvos)}] {chave:<12} ERRO {r['erro'][:60]}", flush=True)
            else:
                print(f"[{feito_n[0]:>3}/{len(alvos)}] {chave:<12} {r['veredito']:<15} "
                      f"{r['miss']:>4} falta | usa: {r['forma_usada'][:36]}", flush=True)
            destino.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                               encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, alvos))
    print(f"\n{len(feitos)} julgados | {tk[0]:,} tokens | ~US$ {tk[0] / 1e6 * 0.0424:.4f}")
    print(f"saída em {destino}")


if __name__ == "__main__":
    main()
