#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificação mecânica de 『伝導の手引』 I/II (PT).

Não substitui a revisão linha a linha (`revisar_dendo.py`): é a rede de
segurança determinística antes da montagem. Verifica:

  1. todas as unidades com `status: ok`;
  2. paridade de blocos com o original japonês (um PT por bloco JP);
  3. nenhum CJK nem 『』「」 no PT;
  4. linhas de citação: contagem JP = PT e formato 〔…〕 com ano ocidental;
  5. rótulos de fala (Interlocutor:/Meishu-Sama:) coerentes com o papel;
  6. violações de glossário (trava) — contadas e listadas;
  7. razão PT/JP por unidade (fora de 0,60–2,80 = suspeita);
  8. blocos repetidos em excesso (possível cópia entre parágrafos).

Uso:  .venv/bin/python scripts/verificar_dendo_mecanico.py --vol 1
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from glossario_dendo import violacoes as violacoes_glossario  # noqa: E402
from trava_glossario import TERMOS_FIXOS  # noqa: E402

OUT = RAIZ / "reports" / "traducao_dendo"
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]")
MARCA_RE = re.compile(r"[『』「」]")
CIT_RE = re.compile(r"^〔.*〕$")


def _variantes_palavra(p: str) -> list[str]:
    """Formas singular/plural de uma palavra."""
    v = {p}
    if p.endswith("ão"):
        v.add(p[:-2] + "ões")
    elif p.endswith("l"):
        v.add(p[:-1] + "is")
    elif p.endswith("m"):
        v.add(p[:-1] + "ns")
    elif p.endswith(("r", "s", "z")):
        v.add(p + "es")
    elif p.endswith(("a", "e", "o", "u")):
        v.add(p + "s")
    return sorted(v)


def _formas_com_flexao(formas: list[str]) -> list[str]:
    """Combinações de singular/plural de cada palavra da forma aprovada.

    A trava oficial compara a forma literal; no texto corrido a mesma entrada
    aparece no plural ou no feminino («jornal» → «jornais», «filial» →
    «filiais», «injeção» → «injeções», «espírito ancestral» → «espíritos
    ancestrais», «Ministro Responsável» → «Ministros Responsáveis»). Sem isto,
    a verificação acusava dezenas de falsos positivos.
    """
    out: set[str] = set()
    for f in formas:
        partes = [p for p in f.split() if p]
        if not partes:
            continue
        combinacoes = [""]
        for p in partes:
            combinacoes = [f"{c} {v}".strip() for c in combinacoes
                           for v in _variantes_palavra(p)]
        out.update(combinacoes)
    return sorted(out)


def _presente(pt: str, formas: list[str]) -> bool:
    """A forma (ou uma flexão dela) aparece no PT, como palavra inteira."""
    for f in _formas_com_flexao(formas):
        padrao = r"\b" + re.escape(f).replace(r"\ ", r"\s+") + r"\b"
        if re.search(padrao, pt, re.IGNORECASE):
            return True
    return False


def _em_composto(jp: str, termo: str) -> bool:
    """O termo só aparece colado a outro kanji (全体的 em vez de 体的)."""
    if not termo:
        return False
    kanji = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
    ocorrencias = [m.start() for m in re.finditer(re.escape(termo), jp)]
    if not ocorrencias:
        return False
    for i in ocorrencias:
        antes = jp[i - 1] if i > 0 else ""
        depois = jp[i + len(termo)] if i + len(termo) < len(jp) else ""
        if not kanji.match(antes or " ") and not kanji.match(depois or " "):
            return False          # há ocorrência isolada
    return True


def violacoes_reais(jp: str, pt: str) -> list[dict]:
    """Violações de glossário que contam como defeito.

    Regras (as mesmas que o projecto já fixou no HANDOFF_LIVRO_1947_EVANGELHO
    §6 e no `violacoes_glossario`):
      * TERMOS_FIXOS (trava crítica) contam sempre;
      * entrada genérica só conta se o termo japonês aparecer ISOLADO no JP e
        a forma aprovada NÃO estiver no PT, com flexões reconhecidas.
    """
    out = []
    for v in violacoes_glossario(jp, pt):
        termo = v.get("termo_jp") or ""
        formas = v.get("formas") or []
        # 1) a forma aprovada, com flexões, está no PT → não é violação
        if _presente(pt, formas):
            continue
        # 2) termo crítico da trava → conta sempre
        if termo in TERMOS_FIXOS:
            out.append(dict(v, critico=True))
            continue
        # 3) termo genérico que só aparece como componente de composto japonês
        if _em_composto(jp, termo):
            continue
        out.append(dict(v, critico=False))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", type=int, choices=(1, 2), required=True)
    args = ap.parse_args()

    estrutura = json.loads(
        (OUT / f"estrutura_dendo{args.vol}.json").read_text(encoding="utf-8"))
    jp_por_i = {b["i"]: b for b in estrutura["blocos"]}
    jp_cits = [b["jp"] for b in estrutura["blocos"]
               if b["jp"].strip().startswith("〔")]

    pasta = OUT / "itens" / f"dendo{args.vol}"
    regs = [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(pasta.glob("*.json")) if ".bak" not in p.name]
    regs.sort(key=lambda d: d["uid"])

    achados: list[dict] = []
    pt_cits: list[str] = []
    repetidos: Counter[str] = Counter()
    vistos: set[int] = set()

    for d in regs:
        if d.get("status") != "ok":
            achados.append({"uid": d["uid"], "tipo": "status",
                            "detalhe": d.get("problemas")})
        if not (d.get("titulo_pt") or "").strip():
            achados.append({"uid": d["uid"], "tipo": "titulo_vazio"})
        jp_len = pt_len = 0
        for b in d["blocos"]:
            i = b["i"]
            if i in vistos:
                achados.append({"uid": d["uid"], "tipo": "bloco_duplicado", "i": i})
            vistos.add(i)
            original = jp_por_i.get(i)
            if not original or original["jp"] != b["jp"]:
                achados.append({"uid": d["uid"], "tipo": "jp_desalinhado", "i": i})
            pt = (b.get("pt") or "").strip()
            if not pt:
                achados.append({"uid": d["uid"], "tipo": "pt_vazio", "i": i})
                continue
            jp_len += len(b["jp"])
            pt_len += len(pt)
            if CJK_RE.search(pt):
                achados.append({"uid": d["uid"], "tipo": "cjk", "i": i,
                                "trecho": CJK_RE.search(pt).group(0)})
            if MARCA_RE.search(pt):
                achados.append({"uid": d["uid"], "tipo": "marca_jp", "i": i})
            if b["jp"].strip().startswith("〔"):
                pt_cits.append(pt)
                if not CIT_RE.match(pt):
                    achados.append({"uid": d["uid"], "tipo": "citacao_formato", "i": i})
                # só se exige ano ocidental quando o original traz a data de
                # publicação — hå citações que são só 〔御垂示〕
                if re.search(r"昭和[^〕]*発行|発行年月日不明", b["jp"]):
                    if not re.search(r"\(\d{4}\)", pt) and "desconhecida" not in pt:
                        achados.append({"uid": d["uid"],
                                        "tipo": "citacao_sem_ano_ocidental", "i": i,
                                        "citacao": pt})
            else:
                for v in violacoes_reais(b["jp"], pt):
                    achados.append({"uid": d["uid"], "tipo": "glossario", "i": i,
                                    "termo": v.get("termo_jp"),
                                    "formas": v.get("formas"),
                                    "critico": v.get("critico", True)})
                if len(re.sub(r"\s", "", pt)) > 30:
                    repetidos[pt] += 1
            papel = b.get("papel")
            if papel == "interlocutor" and not re.match(r"^[A-ZÀ-Ú][^:]{0,40}:", pt):
                achados.append({"uid": d["uid"], "tipo": "rotulo_interlocutor", "i": i})
            if papel == "mestre_inicio" and not pt.startswith("Meishu-Sama:"):
                achados.append({"uid": d["uid"], "tipo": "rotulo_mestre", "i": i})
        if jp_len:
            razao = pt_len / jp_len
            # faixa medida no acervo publicado (JP→PT de prosa): 2,29–3,32;
            # o intervalo aqui é deliberadamente largo (só apanha anomalia)
            if razao < 1.9 or razao > 3.9:
                achados.append({"uid": d["uid"], "tipo": "razao", "razao": round(razao, 2)})

    for texto, n in repetidos.items():
        if n > 2:
            achados.append({"tipo": "bloco_repetido", "vezes": n,
                            "trecho": texto[:120]})

    if len(pt_cits) != len(jp_cits):
        achados.append({"tipo": "citacoes_contagem",
                        "jp": len(jp_cits), "pt": len(pt_cits)})

    por_tipo = Counter(a["tipo"] for a in achados)
    destino = OUT / f"verificacao_vol{args.vol}.json"
    destino.write_text(json.dumps({
        "vol": args.vol, "unidades": len(regs), "achados": len(achados),
        "por_tipo": dict(por_tipo), "detalhe": achados,
        "citacoes_jp": len(jp_cits), "citacoes_pt": len(pt_cits),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"vol {args.vol}: unidades={len(regs)} | achados={len(achados)}")
    for t, n in por_tipo.most_common():
        print(f"   {t:<26} {n}")
    print(f"   citações: JP={len(jp_cits)} PT={len(pt_cits)}")
    print(f"   relatório -> {destino}")
    return 0 if not achados else 1


if __name__ == "__main__":
    raise SystemExit(main())
