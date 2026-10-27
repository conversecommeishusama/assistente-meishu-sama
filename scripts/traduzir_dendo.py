#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Traduz 『伝導の手引』 I e II (A Chave da Difusão, vols. 1 e 2) JP → PT-BR.

Pipeline:
  1. lê a estrutura extraída dos EPUBs (`reports/traducao_dendo/estrutura_*.json`);
  2. converte as linhas de citação de fonte de forma DETERMINÍSTICA
     (`citacoes_dendo.py`), sem passar pela API;
  3. traduz o corpo bloco a bloco, em lotes JSON (`{"itens":[{id,papel,jp}]}`
     → `{"itens":[{id,pt}]}`), com o glossário relevante ao lote e memória de
     continuidade dentro da mesma unidade;
  4. valida: todos os ids devolvidos, sem CJK, sem 『』「」, rótulos de fala
     correctos, razão PT/JP plausível, violações de glossário registadas;
  5. checkpoint por unidade em `reports/traducao_dendo/itens/dendo{vol}/`.

Uso:
    .venv/bin/python scripts/traduzir_dendo.py --vol 1 --workers 6
    .venv/bin/python scripts/traduzir_dendo.py --vol 1 --so 12
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

from citacoes_dendo import analisar, montar, titulos_a_traduzir  # noqa: E402
from retraducao_completa_gokowa import MODELO  # noqa: E402
from traduzir_periodicos_meishu_sama import violacoes_glossario  # noqa: E402

OUT = RAIZ / "reports" / "traducao_dendo"
CACHE_TITULOS = OUT / "titulos_citacao.json"
MODELO_TRAD = MODELO
TEMPERATURA = 0.15
MAX_TOKENS = 16000
LIMITE_LOTE = 2600          # caracteres JP por chamada
TIMEOUT_API = 300.0

CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]")
MARCA_JP_RE = re.compile(r"[『』「」]")

# Termos que entram SEMPRE no prompt do lote (núcleo doutrinário)
CORE = [
    "明主様", "浄霊", "光明如来", "観世音菩薩", "御神体", "御守り", "経綸",
    "地上天国", "浄化", "御守護", "信者", "入信", "御教え", "大乗", "小乗",
    "智慧証覚", "霊界", "幽界", "神界", "罪穢", "曇り", "薬毒", "先祖", "祖霊",
    "祝詞", "御詣り", "御論文", "御垂示", "御講話", "教導師", "教師", "取次",
    "御奉斎", "御神前", "月次祭", "御利益", "御用", "奉仕", "浄財", "御蔭",
]

CONTEXTO = """CONTEXTO DA OBRA — 『伝導の手引』 {romano} (A Chave da Difusão — Volume {romano})

- Compilação de ensinamentos de Meishu-Sama organizada por Nakamura Ichirō,
  publicada em 1954: um manual de trabalho para dirigentes de igreja e
  auxiliares (支部長・奉仕者). Cada item reúne citações do próprio Meishu-Sama,
  classificadas por assunto.
- As linhas entre 〔 〕 são a FICHA DA FONTE (palestra/instrução + obra + data)
  e já vêm traduzidas no pedido: NÃO as repita, NÃO as altere, traduza apenas
  os blocos de corpo que receber. Se um bloco de corpo começar por 〔, devolva-o
  inalterado.
- Os trechos citados vêm dos registros orais (御講話, 御垂示, 御光話) e de
  artigos de periódico. O japonês é o da edição (1954), com ortografia antiga
  ocasional (旧字体/旧仮名: 「之」「其」「居る」「出来る」): traduza para
  português moderno.
- TOM: formal, reverente, directo — é um manual de orientação prática a quem
  difunde e atende fiéis. Não florear, não resumir, não acrescentar.
- Os títulos numerados (１, ２, 附1, 附2, 一、二、) fazem parte do título do item.

REGRA DE FALA (papel indicado em cada bloco):
- `interlocutor` → comece com `Interlocutor: ` e ponha a fala entre aspas retas.
  Se o japonês nomear o interlocutor (ex.: 「…氏」), use `Nome:` em vez de
  `Interlocutor:`.
- `mestre_inicio` → comece com `Meishu-Sama: `, sem aspas.
- `continuacao` → prossegue a fala anterior: sem rótulo.
- `discurso` → texto corrido de Meishu-Sama: sem rótulo, sem aspas externas.
- `titulo` → traduza só o título, sem numeração inventada (mantenha a
  numeração que o original traz: １, 附1, 一、, etc.).
- Aspas tipográficas “ ” apenas para citações internas dentro de um parágrafo.
"""

PROMPT = """{contexto}

GLOSSÁRIO OBRIGATÓRIO (termo japonês → forma única em português):
{glossario}

REGRAS:
1. Fidelidade absoluta: nada omitido, nada inventado, mesma ordem das ideias.
2. Use EXACTAMENTE a forma portuguesa do glossário quando o termo japonês
   aparecer no bloco (inclusive títulos).
3. Português brasileiro formal e reverente; períodos bem formados; concordância
   e regência correctas.
4. PROIBIDO na saída: kanji, hiragana, katakana, 『』「」. Nomes próprios
   japoneses são transliterados (Hepburn, com macron: Gokōwa, Eikō, Tenjō).
5. Não junte nem divida parágrafos: cada item da entrada devolve exactamente
   um item na saída, com o mesmo `id`.
6. Não repita o japonês nem comente a tradução.

ENTRADA (JSON):
{entrada}

Responda APENAS com JSON válido, sem markdown:
{{"itens":[{{"id":"...","pt":"..."}}]}}
"""


# ─────────────────────────── glossário ────────────────────────────
_GLOSSARIO: dict[str, str] | None = None


def glossario() -> dict[str, str]:
    global _GLOSSARIO
    if _GLOSSARIO is None:
        _GLOSSARIO = json.loads(
            (RAIZ / "glossario_traducao.json").read_text(encoding="utf-8"))
    return _GLOSSARIO


def glossario_relevante(texto: str) -> str:
    """Só as entradas cujo termo japonês aparece no lote (+ núcleo fixo).

    O glossário completo tem 35 mil caracteres e iria em cada uma das ~300
    chamadas; o filtro reduz a prompt sem perder nenhum termo aplicável.
    """
    g = glossario()
    selecionadas: dict[str, str] = {}
    for termo in CORE:
        if termo in g:
            selecionadas[termo] = g[termo]
    for jp, pt in g.items():
        if jp in selecionadas:
            continue
        # termos com mais de um kanji: presença literal no texto do lote
        if len(jp) > 1 and jp in texto:
            selecionadas[jp] = pt
    return "\n".join(f"- {k} → {v}" for k, v in sorted(selecionadas.items()))


# ─────────────────────────── estrutura ───────────────────────────
def carregar_unidades(vol: int) -> list[dict]:
    d = json.loads((OUT / f"estrutura_dendo{vol}.json").read_text("utf-8"))
    unidades: list[dict] = []
    atual: dict | None = None
    for b in d["blocos"]:
        if b["tipo"] in ("h1", "h2", "h3"):
            atual = {"tipo": b["tipo"], "nivel": b["nivel"],
                     "titulo": b["jp"], "blocos": [], "i_titulo": b["i"]}
            unidades.append(atual)
        elif atual is not None:
            atual["blocos"].append(b)
    for n, u in enumerate(unidades):
        u["uid"] = f"v{vol}-{n:03d}"
    return unidades


def limpar_marcas(txt: str) -> str:
    """Tira as aspas japonesas da ponta e converte as internas em “ ”."""
    t = txt.strip()
    t = re.sub(r"^[『「]\s*", "", t)
    t = re.sub(r"\s*[』」]$", "", t)
    t = t.strip()
    t = t.replace("『", "“").replace("』", "”")
    t = t.replace("「", "“").replace("」", "”")
    t = re.sub(r"“\s+", "“", t)
    t = re.sub(r"\s+”", "”", t)
    return t


def papeis(blocos: list[dict]) -> list[str]:
    """Classifica cada bloco (título interno, fala, discurso, continuação).

    A classificação é feita POR SEGMENTO (entre títulos internos h4/h5/h6),
    não pela unidade inteira: um item pode ter primeiro um discurso corrido
    (sem falas) e, num 附, um par pergunta/resposta. Sem esta separação, o
    『 do discurso inicial recebia rótulo `Meishu-Sama:` indevidamente.
    """
    ps: list[str] = ["discurso"] * len(blocos)
    for n, b in enumerate(blocos):
        if b["tipo"] != "p":
            ps[n] = "titulo"

    ini = 0
    for n in range(len(blocos) + 1):
        if n < len(blocos) and blocos[n]["tipo"] == "p":
            continue
        seg = list(range(ini, n))
        tem_interlocutor = any(
            re.match(r"^[「]|^御伺い|^お伺い", blocos[k]["jp"].strip())
            for k in seg)
        for k in seg:
            s = blocos[k]["jp"].strip()
            if re.match(r"^[「]|^御伺い|^お伺い", s):
                ps[k] = "interlocutor"
            elif s.startswith("『"):
                ps[k] = "mestre_inicio" if tem_interlocutor else "discurso"
            else:
                ps[k] = "continuacao" if tem_interlocutor else "discurso"
        ini = n + 1
    return ps


# ─────────────────────────── API ───────────────────────────
def _cliente():
    from goshinsho.services.agentic_search import _client
    return _client()


def _json_da_resposta(raw: str) -> dict | None:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    ini, fim = raw.find("{"), raw.rfind("}")
    if ini < 0 or fim <= ini:
        return None
    try:
        return json.loads(raw[ini:fim + 1])
    except Exception:  # noqa: BLE001
        return None


def pedir(itens: list[dict], vol: int, extra: str = "") -> dict[str, str]:
    """Uma chamada à API para um lote de blocos. Devolve {id: pt}."""
    texto_jp = "\n".join(i["jp"] for i in itens)
    entrada = json.dumps({"itens": itens}, ensure_ascii=False)
    prompt = PROMPT.format(
        contexto=CONTEXTO.format(romano="I" if vol == 1 else "II"),
        glossario=glossario_relevante(texto_jp + " " + entrada),
        entrada=entrada) + extra
    resp = _cliente().with_options(timeout=TIMEOUT_API).chat.completions.create(
        model=MODELO_TRAD,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURA,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or ""
    d = _json_da_resposta(raw)
    if not d or "itens" not in d:
        return {}
    out: dict[str, str] = {}
    for it in d["itens"]:
        if isinstance(it, dict) and "id" in it and "pt" in it:
            out[str(it["id"])] = str(it["pt"]).strip()
    return out


def validar(itens: list[dict], out: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Valida o lote e devolve (traduções aceites, problemas)."""
    problemas: list[str] = []
    ok: dict[str, str] = {}
    for it in itens:
        i = it["id"]
        pt = out.get(i)
        if not pt:
            problemas.append(f"{i}: ausente")
            continue
        if CJK_RE.search(pt):
            problemas.append(f"{i}: CJK residual")
            continue
        if MARCA_JP_RE.search(pt):
            problemas.append(f"{i}: marcador japonês")
            continue
        if re.match(r"^[〔]", it["jp"].strip()) and pt != it["jp"]:
            # citação já traduzida: devolver tal e qual
            pt = it["jp"]
        if it.get("papel") == "interlocutor" and not re.match(r"^[A-ZÀ-Ú][^:]{0,40}:", pt):
            problemas.append(f"{i}: falta rótulo de interlocutor")
            continue
        if it.get("papel") == "mestre_inicio" and not pt.startswith("Meishu-Sama:"):
            problemas.append(f"{i}: falta rótulo Meishu-Sama:")
            continue
        if it.get("papel") != "titulo" and len(it["jp"]) >= 60:
            razao = len(pt) / max(1, len(it["jp"]))
            if razao < 0.9 or razao > 4.4:
                problemas.append(f"{i}: razão PT/JP anómala ({razao:.2f})")
                continue
        ok[i] = pt
    return ok, problemas


# ─────────────────────────── execução ───────────────────────────
def _lotes(u: dict) -> list[list[dict]]:
    itens: list[dict] = [{"id": "titulo", "papel": "titulo",
                          "jp": u["titulo"]}]
    ps = papeis(u["blocos"])
    for n, b in enumerate(u["blocos"]):
        if b["jp"].strip().startswith("〔"):
            continue                      # ficha de fonte: determinística
        itens.append({"id": f"b{n}", "papel": ps[n], "jp": b["jp"]})
    lotes, buf, tam = [], [], 0
    for it in itens:
        if buf and tam + len(it["jp"]) > LIMITE_LOTE:
            lotes.append(buf)
            buf, tam = [], 0
        buf.append(it)
        tam += len(it["jp"])
    if buf:
        lotes.append(buf)
    return lotes


def processar(u: dict, vol: int, refazer: bool = False,
              cache_titulos: dict[str, str] | None = None) -> str:
    pasta = OUT / "itens" / f"dendo{vol}"
    destino = pasta / f"{u['uid']}.json"
    if destino.exists() and not refazer:
        try:
            d = json.loads(destino.read_text(encoding="utf-8"))
            if d.get("status") == "ok":
                return f"[pula] {u['uid']} {u['titulo'][:36]}"
        except Exception:  # noqa: BLE001
            pass

    cache_titulos = cache_titulos or {}
    # fichas de fonte: conversão determinística, sem API
    trads: dict[str, str] = {}
    problemas: list[str] = []
    for n, b in enumerate(u["blocos"]):
        if b["jp"].strip().startswith("〔"):
            trads[f"b{n}"] = montar(analisar(b["jp"]), cache_titulos)
    lotes = _lotes(u)
    anterior_jp = anterior_pt = ""
    for n, lote in enumerate(lotes):
        cont = ""
        if anterior_pt:
            cont = ("\n\nCONTINUIDADE — o bloco anterior da MESMA unidade já foi "
                    "traduzido. Mantenha os mesmos termos e o mesmo tom; NÃO o "
                    "repita.\n"
                    f"JP anterior: …{anterior_jp[-240:]}\n"
                    f"PT anterior: …{anterior_pt[-600:]}")
        for tentativa in range(4):
            try:
                out = pedir(lote, vol, cont)
            except Exception as e:  # noqa: BLE001
                problemas.append(f"lote {n + 1}: erro API {e}")
                out = {}
            bons, probs = validar(lote, out)
            if len(bons) == len(lote):
                trads.update(bons)
                break
            cont += ("\n\nCORRIGA e devolva TODOS os itens do lote, com o mesmo "
                     "`id`, completos: " + "; ".join(probs))
            if tentativa == 3:
                trads.update(bons)
                problemas += [f"lote {n + 1}: {p}" for p in probs]
            else:
                time.sleep(1 + tentativa)
        ultimo = lote[-1]
        if ultimo["id"] in trads:
            anterior_jp = ultimo["jp"]
            anterior_pt = trads[ultimo["id"]]

    blocos = []
    ps = papeis(u["blocos"])
    for n, b in enumerate(u["blocos"]):
        blocos.append({
            "i": b["i"], "tipo": b["tipo"], "jp": b["jp"],
            "pt": trads.get(f"b{n}", ""), "papel": ps[n],
        })
    titulo_pt = trads.get("titulo", "")
    completo = (not problemas) and all(b["pt"] for b in blocos) and bool(titulo_pt)

    alertas = []
    for b in blocos:
        if b["pt"]:
            for v in violacoes_glossario(b["jp"], b["pt"]):
                alertas.append({"bloco": b["i"], "termo": v.get("termo_jp"),
                                "formas": v.get("formas")})

    reg = {
        "vol": vol, "uid": u["uid"], "tipo": u["tipo"], "nivel": u["nivel"],
        "titulo_jp": u["titulo"], "titulo_pt": titulo_pt,
        "blocos": blocos, "problemas": problemas,
        "glossario_alertas": alertas,
        "status": "ok" if completo else "parcial",
    }
    pasta.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
    marca = "ok " if completo else "PARCIAL"
    return (f"[{marca}] {u['uid']} {u['titulo'][:34]:<36} "
            f"{sum(len(b['pt']) for b in blocos):>7}c")


# ─────────────────────────── títulos de citação ───────────────────────────
def traduzir_titulos_citacao(unidades: list[dict], vol: int) -> None:
    """Traduz UMA vez os títulos de artigo que aparecem nas fichas de fonte."""
    citacoes = [b["jp"] for u in unidades for b in u["blocos"]
                if b["jp"].startswith("〔")]
    cache: dict[str, str] = {}
    if CACHE_TITULOS.exists():
        cache = json.loads(CACHE_TITULOS.read_text(encoding="utf-8"))
    faltam = sorted(t for t in titulos_a_traduzir(citacoes) if t not in cache)
    if not faltam:
        return
    print(f"títulos de citação a traduzir: {len(faltam)}")
    itens = [{"id": str(n), "papel": "titulo", "jp": t}
             for n, t in enumerate(faltam)]
    out = {}
    for tentativa in range(3):
        out = pedir(itens, vol,
                    "\n\nSão TÍTULOS de artigos/séries que aparecem na ficha "
                    "de fonte de uma citação (não são o corpo do texto). "
                    "Traduza com elegância, respeitando o glossário; nomes de "
                    "obras japonesas dentro do título vão transliterados.")
        if len(out) == len(itens):
            break
        time.sleep(2)
    for n, t in enumerate(faltam):
        pt = out.get(str(n), "").strip().strip("“”\"")
        if pt and not CJK_RE.search(pt):
            cache[t] = pt
    CACHE_TITULOS.write_text(json.dumps(cache, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
    print(f"  guardados: {len(cache)} títulos em {CACHE_TITULOS.name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", type=int, choices=(1, 2), required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--so", help="processar apenas a unidade com este uid")
    ap.add_argument("--refazer", action="store_true")
    args = ap.parse_args()

    unidades = carregar_unidades(args.vol)
    traduzir_titulos_citacao(unidades, args.vol)
    cache_titulos = json.loads(CACHE_TITULOS.read_text(encoding="utf-8")) \
        if CACHE_TITULOS.exists() else {}

    alvos = [u for u in unidades if not args.so or u["uid"] == args.so]
    print(f"vol {args.vol}: unidades={len(unidades)} | a processar={len(alvos)} "
          f"| workers={args.workers}\n")

    feitos = parciais = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futuros = {pool.submit(processar, u, args.vol, args.refazer,
                               cache_titulos): u
                   for u in alvos}
        for fut in as_completed(futuros):
            try:
                msg = fut.result()
            except Exception as e:  # noqa: BLE001
                msg = f"[EXCECAO] {futuros[fut]['uid']} {e}"
            print(msg, flush=True)
            if msg.startswith("[ok"):
                feitos += 1
            elif not msg.startswith("[pula"):
                parciais += 1
    print(f"\nconcluídas: {feitos} | parciais: {parciais}")
    return 0 if not parciais else 1


if __name__ == "__main__":
    raise SystemExit(main())
