#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Traduz os artigos de Meishu-Sama dos periódicos ausentes do acervo.

Executor DeepSeek (`deepseek-v4-flash`) + trava de glossário, com checkpoint
POR ARTIGO (retomável) e N workers paralelos.

Reutiliza o PROMPT / glossário do pipeline do projeto
(`scripts/retraducao_completa_gokowa.py`), com CONTEXTO e EXEMPLO próprios dos
artigos de periódico (prosa editorial de jornal/revista, não diálogo).

Saída: `reports/traducao_periodicos/itens/<slug>.json`, um por artigo, com:
    titulo_pt, fonte_pt, texto_pt, glossario_alertas, status

Uso:
    .venv/bin/python scripts/traduzir_periodicos_meishu_sama.py --workers 16
    .venv/bin/python scripts/traduzir_periodicos_meishu_sama.py --fase P1
"""
from __future__ import annotations

import argparse
import html
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
from trava_glossario import relatorio_glossario, TERMOS_FIXOS  # noqa: E402

FILA = RAIZ / "reports" / "periodicos_trabalho" / "FILA_TRADUCAO_PERIODICOS.json"
OUT = RAIZ / "reports" / "traducao_periodicos"
ITENS = OUT / "itens"
RATTAIL = Path("/var/www/rattail")

LIMITE_CHUNK = 4000          # chars JP por chamada
# 2026-10-09: era 16000. O modelo é de RACIOCÍNIO e os tokens de reasoning
# consomem o mesmo orçamento da resposta — itens longos estouravam o teto e o
# PT saía truncado no meio da frase (Eiko 194/250/256, Tijotengoku 46).
MAX_TOKENS = 32000
TIMEOUT_API = 240.0          # s — modelo de raciocínio precisa de mais tempo

VEIC_PT = {"Eiko": "Eikō", "Hikari": "Hikari",
           "Kyusei": "Kyusei", "Tijotengoku": "Tijotengoku"}
VEIC_JP = {"Eiko": "栄光", "Hikari": "光",
           "Kyusei": "救世", "Tijotengoku": "地上天国"}

MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

CONTEXTO_ARTIGO = """CONTEXTO (artigos de Meishu-Sama nos periódicos da Igreja):
- São ARTIGOS DE JORNAL/REVISTA escritos por Meishu-Sama (岡田茂吉 / 明主様),
  publicados nos periódicos 栄光 (Eikō), 光 (Hikari), 救世 (Kyusei) e
  地上天国 (Tijotengoku), entre 1948 e 1955.
- São PROSA EDITORIAL: o mestre escreve diretamente ao leitor (ensaio, editorial,
  crítica social, coluna curta, resposta a perguntas, prefácio).
- Temas: a doutrina e a Igreja, medicina (a medicina cria doenças; o Johrei cura),
  agricultura natural, crítica social e política, arte, o Plano Divino, o mundo
  espiritual (espíritos, possessão, salvação dos espíritos), etc.
- O tom é o de um mestre/pensador: assertivo, às vezes irônico ou satírico
  (colunas 寸鉄 e 寸鉄活人 são críticas mordazes à sociedade), às vezes didático.
- Termos recorrentes: 地上天国 (Paraíso Terrestre), 光明如来 (Komyo-Nyorai),
  浄霊 (Johrei), 御守 (Ohikari), 信者 (fiel), 経綸 (Plano Divino), 自然農法
  (agricultura natural), 罪穢 (pecados e impurezas), 霊 (espírito), メシヤ教
  (Igreja Messiânica), 明主様 (Meishu-Sama).
- Referências internas a outros artigos: （御論文「...」）【栄光 一XX号】 —
  traduzir o título e PRESERVAR a fonte entre colchetes.
"""

EXEMPLO_ARTIGO = """EXEMPLO DE TRADUÇÃO IDEAL (artigo de periódico de Meishu-Sama):

JP: 迷信の定義
PT: A Definição de Superstição
(Explicação: título curto, editorial — traduzir direto, sem rodeio.)

JP: などとは、今日まであまり言われない言葉だが、実は迷信にも定義があるのだから面白い。
PT: É uma expressão que, até hoje, tem sido pouco mencionada — mas é curioso que
até a superstição tenha uma definição.
(Explicação: prosa editorial fluida. "などとは" retoma o título da seção. Sem
inventar fato novo; só se reconstrói a frase para soar natural em português.)

JP: 効かない薬を効くと思って服むのも、それを人に勧めるのも同じく迷信であり、
    肥料をやるよりやらない方が、沢山穫れるにかかわらず、肥料を施すのも迷信だからである。
PT: Tomar um remédio que não faz efeito crendo que faz, e ainda recomendá-lo a
outras pessoas, é igualmente superstição; e, embora a colheita seja maior sem
adubo do que com ele, aplicar adubo também é superstição.
(Explicação: preserva a estrutura argumentativa e o paralelismo; mantém
"igualmente" e a relação causal. Nenhuma informação acrescentada.)

O que o exemplo ensina:
- É PROSA EDITORIAL: frases completas, conectivos naturais do português,
  cadência de texto de revista — não deixar telegráfico nem truncado.
- FIDELIDADE: manter TODO o sentido, os fatos, números, nomes e datas; nunca
  acrescentar conteúdo; nunca inverter quem faz o quê.
- [Colchetes] só para desambiguar referência que o texto JÁ estabelece — nunca
  para acrescentar fato novo.
- Preservar o estilo do autor (inclusive a ironia das colunas de crítica).
"""


# --------------------------------------------------------------------------
# Extração do original (rattail)
# --------------------------------------------------------------------------
RE_NAV = re.compile(r"(御教え検索|資料検索|岡田自観師の論文集)")
RE_FIM = re.compile(r"(発行|執筆|掲載|発表)")
RE_FONTE = re.compile(
    r"『([^』]{1,30})』\s*(?:第)?([0-9〇一二三四五六七八九十百]+)\s*号、"
    r"昭和\s*([0-9一二三四五六七八九十元]{1,3})\s*[（(]\s*([0-9]{4})\s*[)）]"
    r"年\s*([0-9]{1,2})\s*月\s*([0-9]{1,2})\s*日発行")


def extrai_corpo(arq: str) -> str:
    """Corpo do artigo com parágrafos preservados (a partir do HTML cru)."""
    raw = (RATTAIL / arq).read_text(encoding="utf-8", errors="replace")
    # isola o corpo: remove <head>, converte blocos em quebras
    body = re.sub(r"(?is)<head.*?</head>", " ", raw)
    body = re.sub(r"(?is)<script.*?</script>", " ", body)
    body = re.sub(r"(?is)<style.*?</style>", " ", body)
    body = re.sub(r"(?i)<br\s*/?>", "\n", body)
    body = re.sub(r"(?i)</(p|div|blockquote|table|tr)>", "\n\n", body)
    txt = html.unescape(re.sub(r"<[^>]+>", " ", body))
    txt = txt.replace("\u3000", " ")
    # remove o cabeçalho de navegação
    m = RE_NAV.search(txt[:1500])
    if m:
        k = txt.find("資料検索", m.start())
        k = k if k >= 0 else m.end()
        mm = RE_FIM.search(txt[k:k + 200])
        txt = txt[k + (mm.end() if mm else 60):]
    # normaliza linhas
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    return txt


def extrai_fonte(arq: str) -> dict:
    raw = (RATTAIL / arq).read_text(encoding="utf-8", errors="replace")
    flat = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    m = RE_FONTE.search(flat[:1500])
    if not m:
        return {}
    veic_jp, num, era, ano, mes, dia = m.groups()
    return {"veic_jp": veic_jp, "numero": num, "ano": int(ano),
            "mes": int(mes), "dia": int(dia), "era": era}


def fonte_pt(veiculo: str, meta: dict) -> str:
    """Linha de fonte no padrão do acervo:
    `Eikō nº 74, publicado em 18 de outubro do ano 25 da Era Showa (1950)`."""
    if not meta:
        return ""
    era_ano = meta["ano"] - 1925
    return (f"{VEIC_PT[veiculo]} nº {meta['numero']}, publicado em "
            f"{meta['dia']} de {MESES[meta['mes']]} do ano {era_ano} da Era "
            f"Showa ({meta['ano']})")


# --------------------------------------------------------------------------
# Tradução
# --------------------------------------------------------------------------
def _client():
    from goshinsho.services.agentic_search import _client as c
    return c()


def _chamar(jp: str, quem: str, extra: str = "") -> str:
    # timeout maior: `deepseek-v4-flash` é modelo de RACIOCÍNIO — itens maiores
    # gastam muitos tokens em reasoning e estouram o timeout global de 30s do
    # cliente padrão (causava APITimeoutError nos itens grandes).
    resp = _client().with_options(timeout=TIMEOUT_API).chat.completions.create(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": PROMPT.format(
            contexto=CONTEXTO_ARTIGO, exemplo=EXEMPLO_ARTIGO,
            glossario_completo=carregar_glossario_completo(),
            jp=jp, quem=quem) + extra}],
        temperature=0.2,
    )
    fr = resp.choices[0].finish_reason
    if fr == "length":
        print(f"  [AVISO] finish_reason=length (possível truncamento) "
              f"| jp={len(jp)} chars", flush=True)
    return (resp.choices[0].message.content or "").strip().strip('"')


# --------------------------------------------------------------------------
# GLOSSÁRIO — aplicação DEDICADA E RIGOROSA
# --------------------------------------------------------------------------
KANJI = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf々〆ヶ]")
GLOSSARIO_JP = None


def _glossario_keys() -> set[str]:
    global GLOSSARIO_JP
    if GLOSSARIO_JP is None:
        try:
            GLOSSARIO_JP = set(json.loads(
                (RAIZ / "glossario_traducao.json").read_text(encoding="utf-8")))
        except Exception:
            GLOSSARIO_JP = set()
    return GLOSSARIO_JP


def _so_em_composto(jp: str, termo: str) -> bool:
    """True se TODAS as ocorrências do termo estão dentro de um composto maior.

    Ex.: 社会 ocorre só em 社会主義 / 社会正義 / 社会党 → é COMPONENTE de
    composto, não o termo isolado; forçar «sociedade» seria erro. Já 幽霊
    isolado (…の幽霊を…) é o termo → deve seguir o glossário.

    Regra: uma ocorrência é "composta" se o caractere imediatamente antes OU
    depois for kanji. Se todas forem compostas → True (pular).
    """
    ocorrencias = [m.start() for m in re.finditer(re.escape(termo), jp)]
    if not ocorrencias:
        return True
    for i in ocorrencias:
        antes = jp[i - 1] if i > 0 else ""
        depois = jp[i + len(termo)] if i + len(termo) < len(jp) else ""
        if not (KANJI.match(antes) or KANJI.match(depois)):
            return False     # existe ao menos 1 ocorrência isolada → vale exigir
    return True


def violacoes_glossario(jp: str, pt: str) -> list[dict]:
    """Violações REAIS: lista completa, já filtrada por falsos positivos.

    Termos críticos (TERMOS_FIXOS) são SEMPRE exigidos. Os demais só contam
    quando o termo aparece ISOLADO no japonês (não como componente de composto)
    e a forma canônica é inequívoca.

    Falsos positivos filtrados (2026-10-08):
      - termos de **1 kanji** (熱, 念, 我, 血, 道, 魂…): o kanji tem sentidos
        contextuais (ex.: 熱 = "febre" no glossário, mas "quente" em
        「冷たい戦争が熱の戦争になった」). Forçar seria ERRADO → não exigir.
      - formas com **alternativas** ("alma/consciência", "vontade/pensamento"):
        a trava buscava a string literal com "/" e nunca casava → agora aceita
        qualquer das alternativas.
    """
    limpas = []
    for v in relatorio_glossario(jp, pt):
        termo = v["termo_jp"]
        if termo in TERMOS_FIXOS:
            limpas.append(v)          # crítico: sempre bloqueia
            continue
        # 1 kanji: sentido contextual — não exigir a forma do glossário
        if len(termo) == 1 and KANJI.match(termo):
            continue
        # componente de composto: não exigir
        if _so_em_composto(jp, termo):
            continue
        # concordância por ALTERNATIVAS (formas com "/" ou " ou ")
        if _forma_presente(pt, v["formas"]):
            continue
        limpas.append(v)
    return limpas


def _alternativas(formas: list[str]) -> list[str]:
    """Expande formas com '/' ou ' ou ' em alternativas independentes."""
    out = []
    for f in formas:
        for parte in re.split(r"\s*/\s*|\s+ou\s+", f):
            parte = parte.strip()
            if parte:
                out.append(parte)
    return out or list(formas)


def _forma_presente(pt: str, formas: list[str]) -> bool:
    pt_norm = re.sub(r"[ōōŌŌ]", "o", pt or "")
    for f in _alternativas(formas):
        if re.search(re.escape(re.sub(r"[ōōŌŌ]", "o", f)), pt_norm,
                     re.IGNORECASE):
            return True
    return False


def _bloco_correcao(violacoes: list[dict]) -> str:
    """Instrução de correção dirigida: lista TODOS os termos faltantes."""
    linhas = [
        "",
        "",
        "CORREÇÃO OBRIGATÓRIA DE GLOSSÁRIO — a tradução NÃO respeitou a "
        "terminologia oficial do projeto. Reescreva a tradução inteira "
        "corrigindo TODOS os itens abaixo, usando EXATAMENTE a forma "
        "aprovada (sem sinônimos, sem variações):",
    ]
    for v in violacoes:
        alts = _alternativas(v["formas"])
        forma = alts[0] if alts else "(sem forma)"
        extra = (f" (ou, equivalentemente: {', '.join(alts[1:])})"
                 if len(alts) > 1 else "")
        linhas.append(
            f"  • o japonês 「{v['termo_jp']}」 (aparece {v['ocorrencias']}×) "
            f"DEVE ser traduzido como: «{forma}»{extra}")
    linhas.append(
        "\nMantenha todo o restante do sentido idêntico — só corrija os termos "
        "acima. Responda APENAS com a tradução corrigida, sem comentários.")
    return "\n".join(linhas)


def aplicar_glossario(jp: str, pt: str, quem: str,
                      max_iter: int = 3) -> tuple[str, list[dict]]:
    """Aplicação DEDICADA do glossário (Papel 2), rigorosa:

    1. Mede TODAS as violações (não para na primeira), já com proteção de
       compostos (社会 em 社会主義 não conta como violação).
    2. Se houver, faz UMA chamada de correção dirigida listando cada termo e a
       forma aprovada; re-mede.
    3. Repete até `max_iter`.
    4. Retorna (PT, violações remanescentes) — as remanescentes ficam
       registradas no item para a auditoria (nunca silenciadas).
    """
    if not jp or not pt:
        return pt, []
    for _ in range(max_iter):
        violacoes = violacoes_glossario(jp, pt)
        if not violacoes:
            return pt, []
        try:
            corrigido = _chamar(jp, quem, _bloco_correcao(violacoes))
        except Exception:  # noqa: BLE001
            break
        if not corrigido or len(re.sub(r"\s", "", corrigido)) < 2:
            break
        pt = corrigido
    return pt, violacoes_glossario(jp, pt)


def traduzir(jp: str, quem: str, max_retries: int = 8) -> str:
    """Traduz com retry de vazio + glossário dedicado e rigoroso."""
    reforcos = ["", "\n\nResponda APENAS a tradução, sem comentários.",
                "\n\nSaída: só o texto traduzido.",
                "\n\nTraduza agora, por favor:",
                "\n\nSua resposta veio vazia. Escreva a tradução completa:"]
    raw = ""
    for t in range(max_retries):
        try:
            raw = _chamar(jp, quem, reforcos[t] if t < len(reforcos) else "")
            if raw and len(re.sub(r"\s", "", raw)) >= 2:
                break
        except Exception as e:  # noqa: BLE001
            print(f"    [erro] {e}", flush=True)
        time.sleep(1 + t)
    if not raw:
        return ""
    # aplicação DEDICADA e rigorosa do glossário
    raw, alertas = aplicar_glossario(jp, raw, quem)
    if alertas:
        print(f"    [glossário] {len(alertas)} termo(s) sem forma aprovada "
              f"após 3 iterações: "
              f"{', '.join(a['termo_jp'] for a in alertas[:5])}", flush=True)
    return raw


def traduzir_com_alertas(jp: str, quem: str) -> tuple[str, list[dict]]:
    """Como `traduzir`, mas devolve as violações remanescentes de glossário."""
    reforcos = ["", "\n\nResponda APENAS a tradução, sem comentários.",
                "\n\nSaída: só o texto traduzido.",
                "\n\nTraduza agora, por favor:",
                "\n\nSua resposta veio vazia. Escreva a tradução completa:"]
    raw = ""
    for t in range(8):
        try:
            raw = _chamar(jp, quem, reforcos[t] if t < len(reforcos) else "")
            if raw and len(re.sub(r"\s", "", raw)) >= 2:
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1 + t)
    if not raw:
        return "", []
    return aplicar_glossario(jp, raw, quem)


def divide_chunks(corpo: str, limite: int = LIMITE_CHUNK) -> list[str]:
    paras = [p.strip() for p in corpo.split("\n") if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if buf and len(buf) + len(p) + 1 > limite:
            chunks.append(buf)
            buf = p
        else:
            buf = (buf + "\n" + p) if buf else p
    if buf:
        chunks.append(buf)
    # fallback: parágrafo gigante
    final = []
    for c in chunks:
        if len(c) > limite * 1.8:
            for i in range(0, len(c), limite):
                final.append(c[i:i + limite])
        else:
            final.append(c)
    return final


def slug(item: dict) -> str:
    return re.sub(r"[^0-9A-Za-z_-]", "_",
                  f"{item['fase']}_{item['veiculo']}_{item['numero']}_{item['ordem']}")


def processar(item: dict) -> str:
    destino = ITENS / f"{slug(item)}.json"
    if destino.exists():
        try:
            d = json.loads(destino.read_text(encoding="utf-8"))
            if d.get("status") == "ok" and d.get("texto_pt"):
                return f"[pula] {item['veiculo']} n{item['numero']} {item['titulo_jp'][:24]}"
        except Exception:
            pass

    corpo = extrai_corpo(item["arquivo_fonte"])
    meta = extrai_fonte(item["arquivo_fonte"])
    quem = "Meishu-Sama (autor do artigo)"
    alertas: list[dict] = []

    titulo_pt, al = traduzir_com_alertas(item["titulo_jp"], "título do artigo")
    alertas += [dict(a, onde="titulo") for a in al]

    partes = []
    for ch in divide_chunks(corpo):
        pt, al = traduzir_com_alertas(ch, quem)
        partes.append(pt)
        alertas += [dict(a, onde="corpo") for a in al]
    texto_pt = "\n\n".join(p for p in partes if p)

    # verificação FINAL do artigo inteiro (pega termos que aparecem em
    # qualquer parte e confirma que a forma aprovada está no PT final)
    finais = violacoes_glossario(item["titulo_jp"] + "\n" + corpo, texto_pt)
    criticos = [f for f in finais if f["termo_jp"] not in
                {a["termo_jp"] for a in alertas}]

    reg = {
        "arquivo": item["arquivo_fonte"], "veiculo": item["veiculo"],
        "numero": item["numero"], "ano": item["ano"],
        "fase": item["fase"], "ordem": item["ordem"],
        "titulo_jp": item["titulo_jp"], "titulo_pt": titulo_pt,
        "fonte_pt": fonte_pt(item["veiculo"], meta),
        "texto_jp": corpo, "texto_pt": texto_pt,
        "glossario_alertas": alertas + [dict(a, onde="final") for a in criticos],
        "glossario_ok": not (alertas or criticos),
        "status": "ok" if (titulo_pt and texto_pt) else "erro",
    }
    ITENS.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(reg, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    tag = "ok" if reg["status"] == "ok" else "ERRO"
    gl = "" if reg["glossario_ok"] else f" [{len(reg['glossario_alertas'])} gl.]"
    return f"[{tag}] {item['veiculo']} n{item['numero']} {item['titulo_jp'][:24]}{gl}"


def reprocessar_glossario(reg: dict) -> dict:
    """Reaplica SÓ a passagem de glossário a um item já traduzido."""
    alertas = []
    tp, al = aplicar_glossario(reg["titulo_jp"], reg.get("titulo_pt", "") or "",
                               "título do artigo")
    reg["titulo_pt"] = tp
    alertas += [dict(a, onde="titulo") for a in al]
    partes = []
    for ch_jp, ch_pt in zip(divide_chunks(reg["texto_jp"]),
                            reg.get("texto_pt", "").split("\n\n")):
        novo, al = aplicar_glossario(ch_jp, ch_pt, "Meishu-Sama (autor do artigo)")
        partes.append(novo)
        alertas += [dict(a, onde="corpo") for a in al]
    if partes:
        reg["texto_pt"] = "\n\n".join(partes)
    finais = violacoes_glossario(reg["titulo_jp"] + "\n" + reg["texto_jp"],
                                 reg["texto_pt"])
    reg["glossario_alertas"] = alertas + [dict(a, onde="final") for a in finais]
    reg["glossario_ok"] = not reg["glossario_alertas"]
    return reg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--fase", default=None)
    ap.add_argument("--limite", type=int, default=0, help="máx. de itens (teste)")
    ap.add_argument("--somente-glossario", action="store_true",
                    help="reaplica só a passagem de glossário a itens já feitos")
    args = ap.parse_args()

    if args.somente_glossario:
        arquivos = sorted(ITENS.glob("*.json"))
        print(f"[glossário] reaplicando em {len(arquivos)} itens", flush=True)
        t0 = time.time()
        pend = 0
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {}
            for a in arquivos:
                reg = json.loads(a.read_text(encoding="utf-8"))
                futs[ex.submit(reprocessar_glossario, reg)] = a
            for n, fut in enumerate(as_completed(futs), 1):
                a = futs[fut]
                try:
                    reg = fut.result()
                    a.write_text(json.dumps(reg, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
                    if not reg["glossario_ok"]:
                        pend += 1
                except Exception as e:  # noqa: BLE001
                    print(f"  [erro] {a.name}: {e}", flush=True)
                if n % 20 == 0 or n == len(arquivos):
                    print(f"  {n}/{len(arquivos)} | com alerta={pend} | "
                          f"{time.time()-t0:.0f}s", flush=True)
        print(f"FIM glossário: {pend} itens com alerta remanescente", flush=True)
        return 0

    fila = json.loads(FILA.read_text(encoding="utf-8"))["itens"]
    if args.fase:
        fila = [i for i in fila if i["fase"] == args.fase]
    if args.limite:
        fila = fila[:args.limite]
    print(f"[tradução periódicos] {len(fila)} artigos · workers={args.workers}",
          flush=True)

    t0 = time.time()
    ok = erro = pula = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(processar, it): it for it in fila}
        for n, fut in enumerate(as_completed(futs), 1):
            try:
                r = fut.result()
            except Exception as e:  # noqa: BLE001
                r = f"[ERRO] {e}"
            if r.startswith("[ok]"):
                ok += 1
            elif r.startswith("[pula]"):
                pula += 1
            else:
                erro += 1
            if n % 10 == 0 or n == len(fila):
                print(f"  {n}/{len(fila)} | ok={ok} pula={pula} erro={erro} | "
                      f"{time.time()-t0:.0f}s", flush=True)
    print(f"\nFIM: ok={ok} | pula={pula} | erro={erro} | "
          f"{(time.time()-t0)/60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
