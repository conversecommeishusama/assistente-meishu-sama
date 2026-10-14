#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Traduz 『天国の福音』 (5/2/1947) — O Evangelho do Paraíso.

Reutiliza o executor e a trava de glossário do pipeline do projeto
(`retraducao_completa_gokowa.PROMPT`, `traduzir_periodicos_meishu_sama.
aplicar_glossario`), mas com CONTEXTO e EXEMPLO próprios de um LIVRO de
doutrina médica de 1947 (ortografia antiga, tabelas estatísticas, relatos de
casos, e um anexo de 霊科学 / 霊界叢談 com diálogos).

Checkpoint POR SECÇÃO (retomável) em
`reports/traducao_tengoku1947/itens/<nn>_<slug>.json`.

Uso:
    .venv/bin/python scripts/traduzir_tengoku1947.py --workers 8
    .venv/bin/python scripts/traduzir_tengoku1947.py --so 12   # uma secção
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

from retraducao_completa_gokowa import (  # noqa: E402
    PROMPT, MODELO, carregar_glossario_completo,
)
from traduzir_periodicos_meishu_sama import aplicar_glossario  # noqa: E402

ESTRUTURA = RAIZ / "reports" / "livros_trabalho" / "estrutura_tengoku1947.json"
OUT = RAIZ / "reports" / "traducao_tengoku1947"
ITENS = OUT / "itens"

LIMITE_CHUNK = 3000          # chars JP por chamada (prosa antiga, densa)
MAX_TOKENS = 32000
TIMEOUT_API = 300.0

CONTEXTO_LIVRO = """CONTEXTO (livro 『天国の福音』, O Evangelho do Paraíso, 1947):

- É um LIVRO de 岡田茂吉 (明主様 / Meishu-Sama), publicado em 5 de fevereiro de
  1947, escrito em japonês PRÉ-REFORMA (旧字体/旧仮名): 「之」「其」「然し乍ら」
  「曩に」「従而」「罹る」 「ゐる」「ゑ」. Traduza para português brasileiro
  MODERNO e claro; a ortografia antiga é da edição, não do estilo pretendido.
- SEMELHANÇA FORMAL COM: `神示の健康法` (Método de Saúde por Revelação Divina),
  `結核と神霊療法` (Tuberculose e Terapia Espiritual), `霊界叢談` (Conversas
  sobre o Mundo Espiritual) — são as REEDIÇÕES POSTERIORES deste mesmo material.
  NÃO são o mesmo texto; não copie a redação daquelas obras, mas use a mesma
  terminologia consagrada do acervo.
- ESTRUTURA DO LIVRO: (I) demografia e a tese de que a medicina não prolonga a
  vida; (II) a verdadeira causa da doença; (III) tuberculose; (IV) toxinas
  medicamentosas; (V) vacinação; (VI) crítica à medicina como ciência; (VII)
  nutrição; (VIII) sintomas desmontados um a um; (IX) doenças e os erros da
  terapêutica vigente; (X) princípios do método; (XI) ANEXO 霊科学 (ciência
  espiritual) e 霊界叢談 (relatos do mundo espiritual, com diálogos com
  espíritos).
- TOM: tratado assertivo e polémico. Meishu-Sama ataca a medicina moderna com
  veemência e ironia. Manter a força da argumentação, sem amenizar nem exagerar.
- TERMOS RECORRENTES: 浄霊 (Johrei), 光明如来 (Komyo-Nyorai), 観世音菩薩
  (Kanzeon-Bosatsu), 御守 (Ohikari), 神示 (Revelação Divina), 自然農法
  (Agricultura Natural), 罪穢 (pecados e impurezas), 霊 (espírito), 霊界 (mundo
  dos espíritos), 幽界 (mundo espiritual), 神界 (mundo divino), 曇り (nuvem
  espiritual), 薬毒 (toxina medicamentosa), 浄化作用 (processo de purificação),
  顕幽不離 (o mundo visível e o invisível são inseparáveis), 本医術/本療法
  (esta terapia), 既存医術/既存療法 (a medicina/terapêutica vigente), 三毒
  (os três males), 龍神 (Ryūjin), 天狗 (Tengu), 祖霊 (espíritos ancestrais),
  憑霊 (possessão), 邪神/邪霊 (deus/espírito maligno).
- NOMES DE DOENÇAS: usar a designação médica portuguesa corrente quando existe
  (結核 tuberculose, 肋膜炎 pleurisia, 腹膜炎 peritonite, 喘息 asma, 脚気
  beribéri, バセドー氏病 doença de Basedow, 花柳病 doenças venéreas, 癲癇
  epilepsia, カリエス cárie óssea, 痔 hemorroidas, 歯槽膿漏 piorreia
  alveolar, リョウマチス reumatismo, ジフテリア difteria).
- TABELAS ESTATÍSTICAS: há tabelas de natalidade por país e por período, com
  números em kanji (一六七 = 167 etc.). Converta os números para algarismos
  arábicos e preserve o alinhamento em linhas; NUNCA invente nem altere valores.
- COERÊNCIA TERMINOLÓGICA: dentro da MESMA secção, o mesmo termo japonês tem de
  receber SEMPRE a mesma tradução portuguesa — inclusive do título para o corpo.
  Verifique no texto já traduzido que forma está em uso e mantenha-a.
- SIGLAS DO AUTOR: quando o original diz X（以下略して Y と称す）, reproduza a
  abreviatura portuguesa e use-a depois: p.ex. 天然痘毒素（以下略して然毒）->
  "toxina da varíola (doravante abreviada como 'toxina varíolica')".
- CUIDADO COM FALSOS COGNATOS MÉDICOS: 化膿 é PURULENTO (não "caseoso", que é
  乾酪性); 水泡音/ラッセル são ESTERTORES DE RUSSELL (ruído de bolhas na
  auscultação, não "corpúsculos de Russell"); 精神作用 é AÇÃO MENTAL.
- 光明 isolado é substantivo comum ("luz", "brilho", "esplendor"); só
  光明如来 é que é o nome Komyo-Nyorai.
- NÃO usar a palavra "Zenshū" nem qualquer referência a coletânea ou volume:
  quando o texto citar a própria obra, escreva 『天国の福音』/O Evangelho do
  Paraíso.
"""

EXEMPLO_LIVRO = """EXEMPLO DE TRADUÇÃO IDEAL (tratado de Meishu-Sama, 1947):

JP: 抑々全人類が要望する最大にして最後の目標は何であるか、それは一言にしていえば幸福そのものであろう。
PT: Afinal, qual é o maior e último objetivo que toda a humanidade almeja?
Numa palavra, é a própria felicidade.
(Explicação: 抑々 ("afinal, em primeiro lugar") é conectivo de abertura de
tratado. Frase dividida em duas para caber no ritmo do português.)

JP: ナザレの聖者基督は曰った。「爾、世界を得るとも生命を失わば何の益あらん」と、宜なる哉である。
PT: O santo Cristo de Nazaré disse: "De que serviria ao homem ganhar o mundo
inteiro e perder a sua vida?" — e não há como negar que tem razão.
(Explicação: citação bíblica em português consagrado; 宜なる哉 é aplauso retórico.)

JP: 此事の為に人類は数千年来医学なるものを創成し進歩し発展させつつ今日に到った。
PT: Por causa disso, ao longo de milhares de anos, a humanidade criou,
aperfeiçoou e desenvolveu essa coisa chamada medicina, até chegar ao dia de hoje.
(Explicação: 医学なるもの tem desdém embutido — "essa coisa chamada medicina".

O que o exemplo ensina:
- É TRATADO ARGUMENTATIVO: frases completas, conectivos fortes, cadência de
  ensaio. Nada telegráfico.
- FIDELIDADE: todos os fatos, números, nomes, datas e citações; nunca acrescentar
  nem inverter quem faz o quê.
- Preservar a veemência e a ironia do autor (ele ataca a medicina de frente).
- [Colchetes] só para desambiguar o que o próprio texto já estabelece.
"""


def _chamar(jp: str, quem: str, extra: str = "") -> str:
    from goshinsho.services.agentic_search import _client
    resp = _client().with_options(timeout=TIMEOUT_API).chat.completions.create(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": PROMPT.format(
            contexto=CONTEXTO_LIVRO, exemplo=EXEMPLO_LIVRO,
            glossario_completo=carregar_glossario_completo(),
            jp=jp, quem=quem) + extra}],
        temperature=0.2,
    )
    if resp.choices[0].finish_reason == "length":
        print(f"  [AVISO] finish_reason=length | jp={len(jp)} chars", flush=True)
    return (resp.choices[0].message.content or "").strip().strip('"')


def traduzir(jp: str, quem: str, continuidade: str = "") -> tuple[str, list[dict]]:
    reforcos = ["", "\n\nResponda APENAS a tradução, sem comentários.",
                "\n\nSaída: só o texto traduzido.",
                "\n\nTraduza agora, por favor:",
                "\n\nSua resposta veio vazia. Escreva a tradução completa:"]
    raw = ""
    for t in range(8):
        try:
            raw = _chamar(jp, quem,
                          continuidade + (reforcos[t] if t < len(reforcos) else ""))
            if raw and len(re.sub(r"\s", "", raw)) >= 2:
                break
        except Exception as e:  # noqa: BLE001
            print(f"    [erro] {e}", flush=True)
        time.sleep(1 + t)
    if not raw:
        return "", []
    return aplicar_glossario(jp, raw, quem)


def memoria_de_continuidade(jp_ant: str, pt_ant: str) -> str:
    """Trecho imediatamente anterior da MESMA secção.

    A secção é traduzida em blocos enviados em chamadas independentes; sem esta
    memória o mesmo termo japonês recebia traduções diferentes em blocos
    diferentes (foi a causa dominante dos 75 achados `glossario` da ronda 1).
    """
    if not pt_ant:
        return ""
    return ("\n\nCONTINUIDADE — esta secção já está traduzida até aqui. "
            "Mantenha rigorosamente os MESMOS termos e o mesmo tom do trecho "
            "abaixo; NÃO o repita na resposta.\n"
            f"JAPONÊS (fim do bloco anterior): …{jp_ant[-300:]}\n"
            f"PORTUGUÊS JÁ FEITO (fim do bloco anterior): …{pt_ant[-900:]}")


def chunks(texto: str, limite: int = LIMITE_CHUNK) -> list[str]:
    paras = [p for p in texto.split("\n") if p.strip()]
    out, buf = [], ""
    for p in paras:
        if buf and len(buf) + len(p) + 1 > limite:
            out.append(buf)
            buf = p
        else:
            buf = (buf + "\n" + p) if buf else p
    if buf:
        out.append(buf)
    final = []
    for c in out:
        if len(c) > limite * 2:
            final.extend(c[i:i + limite] for i in range(0, len(c), limite))
        else:
            final.append(c)
    return final


def slug(s: str) -> str:
    s = re.sub(r"[^\w]+", "-", s, flags=re.UNICODE).strip("-")
    return s[:48] or "sec"


def processar(i: int, sec: dict) -> str:
    destino = ITENS / f"{i:03d}_{slug(sec['titulo'])}.json"
    if destino.exists():
        try:
            d = json.loads(destino.read_text(encoding="utf-8"))
            if d.get("status") == "ok" and d.get("texto_pt"):
                return f"[pula] {i:03d} {sec['titulo']}"
        except Exception:  # noqa: BLE001
            pass

    titulo_pt, alertas = "", []
    corpo = "\n".join(sec["paras"])
    partes: list[str] = []
    falhas: list[int] = []
    listas = chunks(corpo)
    for k, ch in enumerate(listas):
        cont = memoria_de_continuidade(listas[k - 1], partes[k - 1]) \
            if k and partes[k - 1] else ""
        pt, al = traduzir(ch, "Meishu-Sama (autor do livro)", cont)
        if not pt:
            falhas.append(k + 1)
        partes.append(pt)
        alertas += [dict(a, onde="corpo") for a in al]
    texto_pt = "\n\n".join(p for p in partes if p)

    # O título é traduzido DEPOIS do corpo, para que a formulação do corpo
    # governe o título (era o defeito dos achados «título usa forma que o corpo
    # não usa», p.ex. 精神作用 = "efeito psíquico" no título e "ação mental" no
    # corpo).
    cont_tit = ("\n\nCONTINUIDADE — este é o TÍTULO da secção cujo corpo você "
                "acabou de traduzir. Use no título exatamente os mesmos termos "
                "empregados no corpo (abaixo). Responda APENAS com o título.\n"
                f"PORTUGUÊS DO CORPO: {texto_pt[:1400]}") if texto_pt else ""
    titulo_pt, alertas_t = traduzir(sec["titulo"], "título da secção", cont_tit)
    alertas = [dict(a, onde="titulo") for a in alertas_t] + alertas

    reg = {
        "ordem": i,
        "obra": "O Evangelho do Paraíso",
        "referencia": "『天国の福音』, 5 de fevereiro de 1947",
        "titulo_jp": sec["titulo"],
        "titulo_pt": titulo_pt,
        "texto_jp": corpo,
        "texto_pt": texto_pt,
        "n_paras_jp": len(sec["paras"]),
        "n_chunks": len(listas),
        "chunks_falhos": falhas,
        "glossario_alertas": alertas,
        "glossario_ok": not alertas,
        "status": "ok" if (titulo_pt and texto_pt and not falhas) else "erro",
    }
    ITENS.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
    marca = "ok " if reg["status"] == "ok" else "ERRO"
    extra = f" | chunks falhos={falhas}" if falhas else ""
    return f"[{marca}] {i:03d} {sec['titulo'][:34]:<36} {len(texto_pt):>7}c{extra}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--so", type=int, help="processar apenas a secção N (ordem)")
    args = ap.parse_args()

    secoes = json.loads(ESTRUTURA.read_text(encoding="utf-8"))
    alvos = [(i, s) for i, s in enumerate(secoes, 1)
             if args.so is None or i == args.so]
    print(f"secções: {len(secoes)} | a processar: {len(alvos)} | "
          f"workers: {args.workers}\n")

    feitos = erros = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futuros = {pool.submit(processar, i, s): i for i, s in alvos}
        for fut in as_completed(futuros):
            try:
                msg = fut.result()
            except Exception as e:  # noqa: BLE001
                msg = f"[EXCECAO] {futuros[fut]:03d} {e}"
            print(msg, flush=True)
            if msg.startswith("[ok"):
                feitos += 1
            elif not msg.startswith("[pula"):
                erros += 1

    print(f"\nconcluídas: {feitos} | com erro: {erros}")
    return 0 if not erros else 1


if __name__ == "__main__":
    raise SystemExit(main())
