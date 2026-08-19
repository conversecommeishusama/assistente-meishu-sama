#!/usr/bin/env python3
"""Consolida as coleções de palavras orais na pasta provisória.

Modelos do protocolo (protocolo_traducao.txt §4.4-A):
  - A1: Gokōwa-roku / Gosuiji-roku — edições numeradas
  - A3: Mioshie-shū — casos + instruções

Usa o CHECKPOINT REORDENADO (reports/retraducao_colecoes/<stem>.json) — cujas
falas já estão na ordem do diálogo real (pergunta → resposta). As datas de
sessão são detectadas no JP original como marcadores.

Destino: revisao_literaria/orais/<nome produção>.txt (um arquivo por edição).

Uso:
  .venv/bin/python scripts/consolidar_colecoes_orais.py [--colecao X] [--arquivo stem]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

JP_DIR = RAIZ / "textos_japones"
CKPT_DIR = RAIZ / "reports" / "retraducao_colecoes"
DEST_DIR = RAIZ / "revisao_literaria" / "orais"

COLECOES = {
    "gokowa":  {"prefixo": "御光話録", "obra": "Gokōwa-roku",  "modelo": "A1"},
    "gosuiji": {"prefixo": "御垂示録", "obra": "Gosuiji-roku", "modelo": "A1"},
    "mioshie": {"prefixo": "御教え集", "obra": "Mioshie-shū", "modelo": "A3"},
}

JP_MES = {'一':'1','二':'2','三':'3','四':'4','五':'5','六':'6','七':'7','八':'8','九':'9','十':'10','十一':'11','十二':'12'}
JP_DIA = {
 '一日':'1','二日':'2','三日':'3','四日':'4','五日':'5','六日':'6','七日':'7','八日':'8','九日':'9','十日':'10',
 '十一日':'11','十二日':'12','十三日':'13','十四日':'14','十五日':'15','十六日':'16','十七日':'17','十八日':'18','十九日':'19','二十日':'20',
 '二十一日':'21','二十二日':'22','二十三日':'23','二十四日':'24','二十五日':'25','二十六日':'26','二十七日':'27','二十八日':'28','二十九日':'29','三十日':'30','三十一日':'31',
}
JP_DIA_SEMANA = {'日':'domingo','月':'segunda-feira','火':'terça-feira','水':'quarta-feira','木':'quinta-feira','金':'sexta-feira','土':'sábado'}
MESES_PT = ['', 'janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro']

DATA_RE = re.compile(r'^([一二三四五六七八九十]+)月([一二三四五六七八九十]+日)(?:[（(]([日月火水木金土])[）)])?$')


def ordinal(d: int) -> str:
    if d in (1, 2, 3):
        return f"{d}º"
    if d == 20:
        return "20"
    if d % 10 == 1 and d != 11:
        return f"{d}º"
    if d % 10 == 2 and d != 12:
        return f"{d}º"
    if d % 10 == 3 and d != 13:
        return f"{d}º"
    return str(d)


def data_jp_para_pt(s: str) -> str | None:
    m = DATA_RE.match(s)
    if not m:
        return None
    mes = JP_MES.get(m.group(1))
    dia = JP_DIA.get(m.group(2))
    ds = JP_DIA_SEMANA.get(m.group(3), '')
    if not mes or not dia:
        return None
    base = f"{ordinal(int(dia))} de {MESES_PT[int(mes)]}"
    if ds:
        base += f" ({ds})"
    return base


def ficha_jp_para_pt(ficha_jp: str, obra_pt: str, n_edicao: str) -> str:
    m = re.search(r'昭和(\d+)[(（]?(\d{4})[)）]?年(\d{1,2})月(\d{1,2})日', ficha_jp)
    if m:
        era_num, ano_oc, mes, dia = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        return (f"{obra_pt} nº {n_edicao}, publicado em {ordinal(dia)} de "
                f"{MESES_PT[mes]} do ano {era_num} da Era Showa ({ano_oc})")
    return f"{obra_pt} nº {n_edicao}, publicado em Shōwa {n_edicao} (data não indicada)"


def n_edicao_de_stem(stem: str) -> str | None:
    m = re.search(r'([0-9０-９]+)号$', stem)
    if not m:
        return None
    return m.group(1).translate(str.maketrans('０１２３４５６７８９', '0123456789'))


def datas_do_jp(stem: str) -> list[tuple[str, int]]:
    jp_path = JP_DIR / f"{stem}.txt"
    if not jp_path.exists():
        return []
    datas = []
    n_fala = 0
    in_art = False
    for l in jp_path.read_text(encoding="utf-8").splitlines():
        s = l.strip()
        if s == '=== ARTIGO ===':
            in_art = True
            continue
        if not in_art:
            continue
        if re.match(r'^(entry_id|paired_id|source_file|sort_date|title_jp|title_pt|Title:|Publication|Original|Date:|Language|Collection)', s):
            continue
        if s == '---':
            continue
        if DATA_RE.match(s):
            datas.append((s, n_fala))
            continue
        if re.match(r'^(Interlocutor|Meishu-Sama)[:：]', s):
            n_fala += 1
    return datas


def montar_arquivo(stem: str, colecao: str, dry_run: bool = False) -> str | None:
    meta = COLECOES[colecao]
    obra_pt = meta["obra"]
    modelo = meta["modelo"]

    ckpt_path = CKPT_DIR / f"{stem}.json"
    if not ckpt_path.exists():
        print(f"  ! sem checkpoint: {stem}")
        return None
    ckpt = json.loads(ckpt_path.read_text(encoding="utf-8"))
    falas = ckpt.get("falas", {})
    ordenadas = [falas[k] for k in sorted(falas.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
                 if isinstance(falas[k], dict) and falas[k].get("pt_contextual")]
    if not ordenadas:
        print(f"  ! {stem}: checkpoint sem falas com PT")
        return None

    datas = datas_do_jp(stem)

    jp_path = JP_DIR / f"{stem}.txt"
    ficha_jp = ""
    if jp_path.exists():
        for l in jp_path.read_text(encoding="utf-8").splitlines():
            s = l.strip()
            if '発行' in s and ('『' in s or '号' in s):
                ficha_jp = s
                break
    n_ed = n_edicao_de_stem(stem)
    ficha_pt = ficha_jp_para_pt(ficha_jp, obra_pt, n_ed or "")

    linhas_out = [ficha_pt, ""]

    # Fundir blocos consecutivos do MESMO falante (são continuações da mesma
    # fala — o extrator quebrou perguntas/respostas longas em blocos).
    agrupados = []
    for f in ordenadas:
        quem = f.get("quem")
        pt = f.get("pt_contextual", "").strip()
        if agrupados and agrupados[-1]["quem"] == quem:
            agrupados[-1]["pt"] += " " + pt
        else:
            agrupados.append({"quem": quem, "pt": pt})

    idx_data = 0
    for i, g in enumerate(agrupados):
        while idx_data < len(datas) and i >= datas[idx_data][1]:
            data_pt = data_jp_para_pt(datas[idx_data][0])
            if data_pt:
                linhas_out.append(f"[{data_pt}]")
                linhas_out.append("")
            idx_data += 1
        rotulo = "Interlocutor" if g["quem"] == "Interlocutor" else "Meishu-Sama"
        linhas_out.append(f"{rotulo}: {g['pt']}")
        linhas_out.append("")

    texto = "\n".join(linhas_out).strip() + "\n"

    nome_saida = f"{stem.split('-')[0]} - {obra_pt} nº {n_ed}.txt"
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    dest = DEST_DIR / nome_saida
    if not dry_run:
        dest.write_text(texto, encoding="utf-8")
    print(f"  ✓ {nome_saida}: {len(ordenadas)} falas | {len(texto)} chars")
    return str(dest)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--colecao", choices=list(COLECOES.keys()))
    ap.add_argument("--arquivo", help="stem JP (ex: 19510920-御教え集1号)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    stems = []
    if args.arquivo:
        stems = [args.arquivo]
    else:
        colecoes = [args.colecao] if args.colecao else list(COLECOES.keys())
        for colecao in colecoes:
            prefixo = COLECOES[colecao]["prefixo"]
            for p in sorted(JP_DIR.glob(f"*{prefixo}*号.txt")):
                stem = p.stem
                if (CKPT_DIR / f"{stem}.json").exists():
                    stems.append(stem)
    stems = list(dict.fromkeys(stems))

    ok = 0
    for stem in stems:
        colecao = None
        for nome, meta in COLECOES.items():
            if meta["prefixo"] in stem:
                colecao = nome
                break
        if not colecao:
            print(f"  ! coleção desconhecida: {stem}")
            continue
        dest = montar_arquivo(stem, colecao, dry_run=args.dry_run)
        if dest:
            ok += 1
    print(f"\nConcluído: {ok}/{len(stems)} arquivos ({'dry-run' if args.dry_run else 'gravados'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
