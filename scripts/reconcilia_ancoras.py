#!/usr/bin/env python3
"""Reconcilia as âncoras (pt_anchor) dos specs com o texto PT atual.

Cenário real: a Fase 2 (revisão linha a linha) alterou a 1ª linha de cada
obra (título/cabeçalho), que é a âncora do artigo 0 do spec. O spec ainda
aponta para o texto ANTIGO. Este script:

1. Para cada obra, verifica se valida_ancoras passa. Se falha:
2. Tenta reconstruir as âncoras do spec para bater com o texto atual:
   - A âncora do artigo 0 (título da obra) -> usa a 1ª linha atual do texto.
   - Para os demais artigos, verifica se a âncora atual ainda resolve a
     partir do cursor correto; se não, marca pendente (não inventa).
3. Backup do spec antes de alterar.
4. Revalida com valida_ancoras (a MESMA função de produção).

Segurança: nunca busca no arquivo inteiro (evita trocar por título igual em
outro lugar). Nunca inventa âncora. Se um artigo não resolver, fica pendente
e a obra é reportada (não esconde o problema).

Uso:
    python3 scripts/reconcilia_ancoras.py [obra1 obra2 ...]     # ensaio
    python3 scripts/reconcilia_ancoras.py [obra1 obra2 ...] --aplicar
    (sem obras = todas as que falham valida_ancoras)
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import mescla_e_aplica as me
from build_clean_large_indexes import clean_body

PT = RAIZ / "reports/livros_trabalho/pt"
SPEC = RAIZ / "reports/livros_trabalho/segmentacao_manual"
JANELA = 3000


def obras_afetadas() -> list[str]:
    out = []
    for f in sorted(PT.glob("*.txt")):
        try:
            ok, _ = me.valida_ancoras(f.name, f.read_text(encoding="utf-8"))
            if not ok:
                out.append(f.name)
        except Exception:
            out.append(f.name)
    return out


def primeira_linha(t: str) -> str:
    for l in t.split("\n"):
        if l.strip():
            return l.strip()
    return ""


def processar(obra: str, aplicar: bool, backup: Path) -> dict:
    t = (PT / obra).read_text(encoding="utf-8")
    sp = SPEC / f"{obra}.json"
    if not sp.exists():
        return {"obra": obra, "status": "sem_spec"}
    spec = json.loads(sp.read_text(encoding="utf-8"))
    arts = spec.get("articles", [])
    if not arts:
        return {"obra": obra, "status": "sem_artigos"}

    if aplicar:
        shutil.copy(sp, backup / f"{obra}.json")

    cabecalho_atual = primeira_linha(t)
    alteradas = 0
    pendentes = []
    tc = clean_body(t)
    cursor = 0

    novas_ancoras = []
    for i, a in enumerate(arts):
        anc_velha = a.get("pt_anchor", "")
        if i == 0 and cabecalho_atual:
            nova = cabecalho_atual
            if nova != anc_velha:
                alteradas += 1
            novas_ancoras.append(nova)
            pos = tc.find(nova, cursor)
            if pos >= 0:
                cursor = pos + max(1, len(nova.strip().splitlines()[0]))
            else:
                pendentes.append({"artigo": i, "motivo": "título não encontrado no texto"})
            continue
        if not anc_velha:
            novas_ancoras.append(anc_velha)
            continue
        pos = tc.find(anc_velha, cursor)
        if pos >= 0:
            cursor = pos + max(1, len(anc_velha.strip().splitlines()[0]))
            novas_ancoras.append(anc_velha)
        else:
            janela = tc[cursor:cursor + JANELA]
            prim = anc_velha.strip().splitlines()[0]
            if len(prim) >= 6:
                pos2 = janela.find(prim)
                if pos2 >= 0:
                    abs_pos = cursor + pos2
                    cursor = abs_pos + max(1, len(prim))
                    novas_ancoras.append(anc_velha)
                    continue
            novas_ancoras.append(anc_velha)
            pendentes.append({"artigo": i, "motivo": "âncora não resolve", "anc": anc_velha[:60]})

    if aplicar and (alteradas > 0 or pendentes):
        for i, nova in enumerate(novas_ancoras):
            if i < len(arts):
                arts[i]["pt_anchor"] = nova
        sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")

    try:
        ok, motivo = me.valida_ancoras(obra, t)
        status = "OK" if ok else f"FALHA: {motivo[:70]}"
    except Exception as e:
        status = f"ERRO: {str(e)[:70]}"

    return {"obra": obra, "status": status, "alteradas": alteradas,
            "pendentes": pendentes, "cabecalho": cabecalho_atual[:60]}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aplicar = "--aplicar" in sys.argv
    obras = args if args else obras_afetadas()
    print(f"Obras: {len(obras)} | aplicar: {aplicar}")

    carimbo = time.strftime('%Y%m%dT%H%M%SZ')
    backup = RAIZ / "backups" / f"pre_reconcilia_ancoras_{carimbo}"
    if aplicar:
        backup.mkdir(parents=True, exist_ok=True)

    resumo = {"OK": 0, "FALHA": 0}
    for obra in obras:
        r = processar(obra, aplicar, backup)
        tag = "OK" if r["status"] == "OK" else "FALHA"
        resumo[tag] = resumo.get(tag, 0) + 1
        print(f"  [{tag}] {obra}: {r['status']} (alteradas={r['alteradas']}, pendentes={len(r['pendentes'])})")
        for p in r["pendentes"][:5]:
            print(f"      art{p['artigo']}: {p['motivo']}")

    print(f"\nResumo: {resumo}")
    if not aplicar:
        print("(ensaio — use --aplicar para gravar)")


if __name__ == "__main__":
    main()
