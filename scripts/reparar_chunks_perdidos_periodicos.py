#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repara chunks de tradução PERDIDOS nos artigos de periódico.

CAUSA RAIZ (2026-10-13): `traduzir_periodicos_meishu_sama.py` divide o corpo
em blocos de `LIMITE_CHUNK` (4000) chars e traduz CADA bloco numa chamada
separada. Quando uma chamada retornava vazia (após os 8 retries), o resultado
era descartado silenciosamente por `"\n\n".join(p for p in partes if p)` e o
artigo era gravado com `status: "ok"`. Resultado: artigos que COMEÇAM no meio,
sem nenhum aviso.

Este script:
  1. reproduz o MESMO chunking (`divide_chunks`, limite 4000);
  2. mede a cobertura de cada chunk no PT (termos do glossário como sondas);
  3. retraduz APENAS o prefixo contíguo de chunks sem cobertura;
  4. faz prepend das traduções novas, preservando o PT existente;
  5. registra o reparo em `reparos` (auditável) e faz backup antes de gravar.

Uso:
    python scripts/reparar_chunks_perdidos_periodicos.py            # dry-run
    python scripts/reparar_chunks_perdidos_periodicos.py --aplicar
    python scripts/reparar_chunks_perdidos_periodicos.py --item P1_Tijotengoku_50_80 --aplicar
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from glossario_core import _forma_presente, variantes  # noqa: E402
from traduzir_periodicos_meishu_sama import (  # noqa: E402
    divide_chunks, traduzir_com_alertas,
)

ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
BACKUPS = RAIZ / "reports" / "traducao_periodicos" / "backups_chunks"
RELATORIO = RAIZ / "reports" / "chunks_perdidos_periodicos.json"

# Limiares: um chunk é considerado PERDIDO se >=60% dos termos do glossário
# presentes nele não aparecerem em lugar nenhum do PT. Em artigos com rácio
# PT/JP anormal (<1.8; o normal é ~2.96), o limiar cai para 40% — porque termos
# genéricos repetidos em vários chunks mascaram a ausência.
LIMIAR_PERDIDO = 0.60
LIMIAR_PERDIDO_RATIO_RUIM = 0.40
RATIO_MINIMO_OK = 1.80
MIN_TERMOS = 8          # chunks com menos sondas que isto não são julgados
MIN_RATIO_AVALIADO = 300   # só avalia artigos com corpo relevante
# Fronteira MANUAL para lacunas no MEIO do artigo: a tradução dos chunks
# perdidos é inserida IMEDIATAMENTE ANTES deste trecho do PT. Usa-se porque a
# heurística de sondas não distingue com segurança a fronteira (termos genéricos
# reaparecem depois); cada entrada foi conferida lendo o JP.
#   P1_Tijotengoku_11_4: chunk 1 termina em 「…作曲にい」(bit.ly musical) e o
#   chunk 4 começa em 「又宗教には国境があるべきだと主張された事どもが…」.
ANCORAS_MEIO: dict[str, str] = {
    # chunk 1 termina em「…作曲にい」(vida musical) e o chunk 4 começa em
    # 「又宗教には国境があるべきだと主張された事どもが…」.
    "P1_Tijotengoku_11_4": (
        "afirmações de que a religião deve ter fronteiras nacionais"
    ),
    # chunk 1 termina em「無着は一生懸命云った。」(fala de Muchaku) e o chunk 3
    # começa em「抵抗と抵抗の連続は、人間の闘争から闘争に追いやるもので…」.
    "P2_Eiko_134_151": "A sucessão de resistência após resistência",
}

SUBLIMITE = 1400        # chars JP por chamada de reparo
# MAX_TOKENS=32000 do pipeline principal é consumido em grande parte pelo
# raciocínio do modelo; com 4000 chars JP a resposta saía TRUNCADA
# (finish_reason=length). Pedaços de 1400 chars cabem com folga.

_GLOSSARIO = json.loads((RAIZ / "glossario_traducao.json").read_text(encoding="utf-8"))
_SONDAS = {
    k: variantes(v)
    for k, v in _GLOSSARIO.items()
    if isinstance(v, str) and len(k) >= 2
}
_SONDAS = {k: v for k, v in _SONDAS.items() if v}


def cobertura(fragmento_jp: str, pt: str) -> tuple[int, int]:
    """(total de sondas presentes no fragmento, quantas faltam no PT)."""
    total = ausentes = 0
    for termo, formas in _SONDAS.items():
        if termo not in fragmento_jp:
            continue
        total += 1
        if not _forma_presente(pt, formas):
            ausentes += 1
    return total, ausentes


def posicao_perdidos(perdidos: list[bool]) -> str:
    """'prefixo', 'sufixo', 'tudo' ou '' (nada reparável automaticamente)."""
    idx = [i for i, p in enumerate(perdidos) if p]
    if not idx:
        return ""
    if idx == list(range(len(idx))):
        return "prefixo"
    if idx == list(range(len(perdidos) - len(idx), len(perdidos))):
        return "sufixo"
    if len(idx) == len(perdidos):
        return "tudo"
    return "meio"


def _sondas_de(jp_fragmento: str) -> set[str]:
    """Termos do glossário (sondas) presentes no fragmento JP."""
    return {t for t in _SONDAS if t in jp_fragmento}


def _sondas_no_pt(pt: str, sondas: set[str]) -> set[str]:
    """Subconjunto das sondas cuja forma aprovada aparece no PT."""
    return {t for t in sondas if _forma_presente(pt, _SONDAS[t])}


def ponto_insercao(pt: str, chunks: list[str], perdidos: list[int]) -> int | None:
    """Índice de caractere no PT onde inserir a tradução dos chunks perdidos.

    Para uma lacuna no MEIO do artigo: os chunks mantidos ANTES da lacuna
    traduzem o começo do PT e os mantidos DEPOIS traduzem o fim. A fronteira é
    encontrada com as sondas EXCLUSIVAS de cada lado (termos do glossário que
    só existem antes, e só existem depois): o corte fica entre o último
    parágrafo que usa uma sonda "de antes" e o primeiro que usa uma "de depois".
    """
    antes = [i for i in range(len(chunks)) if i < min(perdidos) and i not in perdidos]
    depois = [i for i in range(len(chunks)) if i > max(perdidos) and i not in perdidos]
    if not antes or not depois:
        return None
    jp_antes = "".join(chunks[i] for i in antes)
    jp_depois = "".join(chunks[i] for i in depois)

    paras = [p for p in re.split(r"\n{2,}", pt) if p.strip()]
    if len(paras) < 2:
        return None
    offs, acc = [], 0
    for p in paras:
        acc += len(p)
        offs.append(acc)
        acc += 2  # "\n\n"

    sa, sd = _sondas_de(jp_antes), _sondas_de(jp_depois)
    so_antes = sa - sd          # exclusivas do trecho anterior à lacuna
    so_depois = sd - sa         # exclusivas do trecho posterior

    ultimo_antes = -1
    primeiro_depois = len(paras)
    for k, p in enumerate(paras):
        if so_antes and _sondas_no_pt(p, so_antes):
            ultimo_antes = k
        if so_depois and _sondas_no_pt(p, so_depois) and primeiro_depois == len(paras):
            primeiro_depois = k

    if ultimo_antes >= 0 and ultimo_antes < primeiro_depois:
        # corte imediatamente antes do 1º parágrafo do trecho posterior
        return offs[primeiro_depois - 1] if primeiro_depois > 0 else 0

    # reserva: maximiza cobertura dos dois lados (prefere o corte mais à esquerda)
    melhor_k, melhor_score = None, -1
    for k in range(1, len(paras)):
        cabeca = "\n\n".join(paras[:k])
        cauda = "\n\n".join(paras[k:])
        n1, a1 = cobertura(jp_antes, cabeca)
        n2, a2 = cobertura(jp_depois, cauda)
        score = (n1 - a1) + (n2 - a2)
        if score > melhor_score:
            melhor_k, melhor_score = k, score
    return offs[melhor_k - 1] if melhor_k else None


def classificar(chunks: list[str], pt: str) -> list[bool]:
    """Para cada chunk, True se a tradução parece PERDIDA."""
    ratio_ruim = len(pt) / max(len("".join(chunks)), 1) < RATIO_MINIMO_OK
    limiar = LIMIAR_PERDIDO_RATIO_RUIM if ratio_ruim else LIMIAR_PERDIDO
    perdidos: list[bool] = []
    for ch in chunks:
        total, ausentes = cobertura(ch, pt)
        if total < MIN_TERMOS:
            perdidos.append(False)
            continue
        perdidos.append(ausentes / total >= limiar)
    return perdidos


def reparar(arquivo: Path, aplicar: bool) -> dict | None:
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    jp = dados.get("texto_jp") or ""
    pt = dados.get("texto_pt") or ""
    if not jp or not pt or len(jp) < MIN_RATIO_AVALIADO:
        return None

    chunks = divide_chunks(jp)
    flags = classificar(chunks, pt)
    perdidos = [i for i, f in enumerate(flags) if f]
    if not perdidos:
        return None
    onde = posicao_perdidos(flags)

    registro = {
        "item": arquivo.name,
        "n_chunks": len(chunks),
        "chunks_perdidos": [i + 1 for i in perdidos],
        "onde": onde or "buraco_no_meio",
        "chars_jp_perdidos": sum(len(chunks[i]) for i in perdidos),
        "ratio_pt_jp": round(len(pt) / len(jp), 2),
        "pt_antes": len(pt),
    }
    if not onde:
        registro["erro"] = "perda no meio do artigo; requer revisão manual"
        return registro
    corte = None
    if onde == "meio":
        ancora = ANCORAS_MEIO.get(arquivo.stem)
        if ancora:
            pos = pt.find(ancora)
            if pos > 0:
                corte = pos
        if corte is None:
            registro["erro"] = (
                "lacuna no meio do artigo sem âncora conferida; requer revisão "
                "manual"
            )
            return registro
        registro["corte_char"] = corte
        registro["ancora"] = ANCORAS_MEIO[arquivo.stem][:60]
    if not aplicar:
        return registro          # dry-run: não gasta API

    partes_novas: list[str] = []
    for i in perdidos:
        # subdivide para não estourar MAX_TOKENS (resposta truncada)
        for sub in divide_chunks(chunks[i], SUBLIMITE):
            nova, alertas = traduzir_com_alertas(sub, "Meishu-Sama (autor do artigo)")
            if not nova:
                registro["erro"] = f"chunk {i + 1} voltou vazio; reparo abortado"
                return registro
            partes_novas.append(nova)
            registro.setdefault("alertas", []).extend(
                [dict(a, chunk=i + 1) for a in alertas]
            )

    bloco = "\n\n".join(partes_novas)
    if onde == "prefixo":
        novo_pt = bloco + "\n\n" + pt
    elif onde == "sufixo" or onde == "tudo":
        novo_pt = pt + "\n\n" + bloco
    else:  # meio: inserir no ponto calculado
        novo_pt = pt[:corte].rstrip() + "\n\n" + bloco + "\n\n" + pt[corte:].lstrip()
    registro["pt_depois"] = len(novo_pt)
    registro["ganho_chars"] = len(novo_pt) - len(pt)

    backup = BACKUPS / (
        f"{arquivo.stem}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    )
    BACKUPS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(arquivo, backup)
    dados["texto_pt"] = novo_pt
    dados.setdefault("reparos", []).append(
        {
            "tipo": "chunks_perdidos",
            "data": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "chunks": [i + 1 for i in perdidos],
            "onde": onde,
        }
    )
    arquivo.write_text(
        json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    registro["backup"] = backup.name
    return registro


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--item", help="reparar apenas este item (stem do JSON)")
    ap.add_argument("--workers", type=int, default=1,
                    help="itens em paralelo (só com --aplicar)")
    args = ap.parse_args()

    if args.item:
        arquivos = [ITENS / f"{args.item}.json"]
    else:
        # `Path.glob("*.json")` casa também ficheiros ocultos (.bak_chunk_*.json)
        # — foi o que fez o 1.º lote reprocessar backups. Excluir explicitamente.
        arquivos = sorted(p for p in ITENS.glob("*.json") if not p.name.startswith("."))

    registros = []

    def _um(arq: Path) -> dict | None:
        try:
            return reparar(arq, args.aplicar)
        except Exception as e:  # noqa: BLE001
            return {"item": arq.name, "erro": f"exceção: {e}"}

    if args.workers > 1 and args.aplicar:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futuros = {ex.submit(_um, a): a for a in arquivos}
            for f in as_completed(futuros):
                r = f.result()
                if r:
                    registros.append(r)
                    _log(r)
    else:
        for arq in arquivos:
            r = _um(arq)
            if r:
                registros.append(r)
                _log(r)

    RELATORIO.write_text(
        json.dumps(
            {"aplicado": args.aplicar, "total": len(registros), "itens": registros},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\n{'APLICADO' if args.aplicar else 'DRY-RUN'}: {len(registros)} item(ns)")
    return 0


def _log(r: dict) -> None:
    tag = "ERRO" if r.get("erro") else "reparar"
    extra = f" | {r['erro']}" if r.get("erro") else ""
    print(
        f"  [{tag}] {r['item']:32s} chunks {r.get('chunks_perdidos')} "
        f"de {r.get('n_chunks')} | +{r.get('ganho_chars', 0)} chars{extra}",
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
