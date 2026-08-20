#!/usr/bin/env python3
"""Reestrutura os checkpoints dos Mioshie-shū (1-8) para separar sessões de
prosa contínua de Meishu-Sama que ficaram EMBUTIDAS em falas vizinhas.

Problema sistêmico: o extractor `extrair_falas_mioshie` não captura sessões de
prosa contínua datada (sem rótulo `Meishu-Sama:`/`〔御垂示〕`) como falas
separadas. Elas ficam EMBUTIDAS no fim do JP da fala anterior.

Para cada data de sessão EMPILHADA (mesmo n_fala no JP — sinal de prosa
contínua), divide a fala que a contém em duas:
  [parte antes da data] + [nova fala = data + texto da sessão]

Depois renumerA as falas 0..N-1 mantendo a ordem.

Uso:
  .venv/bin/python scripts/reestruturar_checkpoints_mioshie.py [--dry-run]
"""
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("cons", str(ROOT / "scripts" / "consolidar_colecoes_orais.py"))
cons = importlib.util.module_from_spec(spec)
sys.modules["cons"] = cons
spec.loader.exec_module(cons)

CKPT_DIR = ROOT / "reports" / "retraducao_colecoes"
MAPA = {1: "19510920-御教え集1号", 2: "19511025-御教え集2号", 3: "19511125-御教え集3号",
        4: "19511215-御教え集4号", 5: "19520115-御教え集5号", 6: "19510225-御教え集6号",
        7: "19520320-御教え集7号", 8: "19520420-御教え集8号"}

# datas por extenso em português (para cortar o PT no ponto da sessão)
DIAS_EXT = {
    "1": "primeiro", "2": "dois", "3": "três", "4": "quatro", "5": "cinco",
    "6": "seis", "7": "sete", "8": "oito", "9": "nove", "10": "dez",
    "11": "onze", "12": "doze", "13": "treze", "14": "catorze", "15": "quinze",
    "16": "dezesseis", "17": "dezessete", "18": "dezoito", "19": "dezenove",
    "20": "vinte", "21": "vinte e um", "22": "vinte e dois", "23": "vinte e três",
    "24": "vinte e quatro", "25": "vinte e cinco", "26": "vinte e seis",
    "27": "vinte e sete", "28": "vinte e oito",
}

MESES_PT_EXT = {"janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5,
                "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
                "novembro": 11, "dezembro": 12}


def achar_inicio_sessao_pt(pt: str, data_pt: str) -> int:
    """Acha o índice no PT onde começa a nova sessão (data_pt = "23 de setembro")."""
    # data_pt pode ser "23º de setembro" ou "23 de setembro"
    dia_num, mes = data_pt.replace("º", "").split(" de ")
    dia_num = dia_num.strip()
    # padrões: "23 de setembro", "23º de setembro", "vinte e três de setembro"
    ext = DIAS_EXT.get(dia_num, "")
    padrões = [
        rf"{dia_num}\s*º?\s*de\s+{mes}",
        rf"(?:dia|Dia)\s+{dia_num}\s*º?\s*de\s+{mes}",
        rf"(?:No|no)\s+dia\s+{dia_num}\s*º?\s*de\s+{mes}",
        rf"(?:Hoje|hoje),?\s*{dia_num}\s*º?\s*de\s+{mes}",
    ]
    if ext:
        padrões += [
            rf"{ext}\s+de\s+{mes}",
            rf"(?:Hoje|hoje),?\s+{ext}\s+de\s+{mes}",
        ]
    for p in padrões:
        m = re.search(p, pt, flags=re.IGNORECASE)
        if m:
            # volta ao início da frase
            inicio = pt.rfind(".", 0, m.start()) + 1
            while inicio < len(pt) and pt[inicio] in " \n":
                inicio += 1
            return inicio
    return len(pt)  # não achou — não divide o PT


def dividir_no_marcador(jp: str, pt: str, marcador: str, data_pt: str) -> tuple[str, str, str, str]:
    idx = jp.find(marcador)
    if idx < 0:
        raise ValueError(f"marcador {marcador} não encontrado no JP")
    jp_antes = jp[:idx].strip()
    jp_depois = jp[idx:].strip()
    pt_idx = achar_inicio_sessao_pt(pt, data_pt)
    pt_antes = pt[:pt_idx].strip()
    pt_depois = pt[pt_idx:].strip()
    return jp_antes, pt_antes, jp_depois, pt_depois


def processar_arquivo(stem: str, dry: bool) -> tuple[int, int]:
    ck = json.loads((CKPT_DIR / f"{stem}.json").read_text(encoding="utf-8"))
    falas = ck["falas"]
    datas = cons.datas_do_jp(stem)

    # datas empilhadas (mesmo n_fala — prosa contínua)
    por_nfala = defaultdict(list)
    for d, nf in datas:
        por_nfala[nf].append(d)
    empilhadas = [d for ds in por_nfala.values() if len(ds) > 1 for d in ds]
    if not empilhadas:
        return 0, len(falas)

    # ordenar falas
    chaves = sorted(falas.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
    novas = []
    n_divisoes = 0
    for k in chaves:
        f = falas[k]
        jp = f.get("jp", "").strip()
        pt = f.get("pt_contextual", "").strip()
        # achar a primeira data empilhada no JP (se embutida)
        dividiu = False
        for d in empilhadas:
            if d in jp and not cons.DATA_PREFIX_RE.match(jp):
                data_pt = cons.data_jp_para_pt(d) or ""
                if not data_pt:
                    continue
                try:
                    ja, pa, jd, pd = dividir_no_marcador(jp, pt, d, data_pt)
                except ValueError:
                    continue
                f_antes = dict(f)
                f_antes["jp"] = ja
                f_antes["pt_contextual"] = pa
                novas.append(f_antes)
                if jd and pd:
                    f_nova = dict(f)
                    f_nova["jp"] = jd
                    f_nova["pt_contextual"] = pd
                    novas.append(f_nova)
                else:
                    # não conseguiu dividir PT — mantém a fala inteira
                    novas.append(f)
                n_divisoes += 1
                dividiu = True
                break
        if not dividiu:
            novas.append(f)

    # renumerar
    novas_falas = {}
    for i, f in enumerate(novas):
        f2 = dict(f)
        f2["indice"] = i
        novas_falas[str(i)] = f2

    if dry:
        print(f"  [dry-run] {stem}: {len(falas)} → {len(novas)} ({n_divisoes} divisões)")
        return 0, len(novas)

    ck["falas"] = novas_falas
    (CKPT_DIR / f"{stem}.json").write_text(json.dumps(ck, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ✓ {stem}: {len(falas)} → {len(novas)} ({n_divisoes} divisões)")
    return n_divisoes, len(novas)


def main() -> int:
    dry = "--dry-run" in sys.argv
    apenas = None
    for a in sys.argv:
        if a.startswith("--arquivo"):
            apenas = int(a.split("=")[1])
    total_div = 0
    for n in range(1, 9):
        if apenas and n != apenas:
            continue
        div, _ = processar_arquivo(MAPA[n], dry)
        total_div += div
    print(f"\nTotal divisões: {total_div}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
