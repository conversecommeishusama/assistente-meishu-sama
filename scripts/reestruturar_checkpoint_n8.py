#!/usr/bin/env python3
"""Reestrutura o checkpoint do Mioshie-shū nº 8 (19520420-御教え集8号.json).

Problema: as sessões 23-27 de março são prosa contínua de Meishu-Sama SEM rótulo
`Meishu-Sama:`/`〔御垂示〕` no JP. O extractor não as captura como falas
separadas; por isso elas ficaram FUNDIDAS dentro de falas vizinhas:

  - chave 192: JP termina com "…【栄光 一五一号】 春季大祭御教え 三月二十三日 …"
    (a sessão 23 está embutida no FIM da fala anterior)
  - chave 216: idem com "三月二十四日"
  - chave 247: JP COMEÇA com "三月二十五日" (início de sessão — ok)
  - chave 279: idem com "三月二十六日"
  - chave 312: idem com "三月二十七日"

Este script DIVIDE cada fala fundida em duas no ponto exato da data:
  [parte antes da data] + [nova fala = data + texto da sessão]
e renumerA todas as falas de 0..N-1 mantendo a ordem, para que o consolidador
consiga inserir os marcadores [data] das sessões 23-27.

Uso:
  .venv/bin/python scripts/reestruturar_checkpoint_n8.py [--dry-run]
"""
import json
import re
import sys
from pathlib import Path

CKPT = Path("reports/retraducao_colecoes/19520420-御教え集8号.json")

# datas de sessão que devem virar marcadores (início de nova fala Meishu-Sama)
DATAS = ["三月二十三日", "三月二十四日", "三月二十五日", "三月二十六日", "三月二十七日"]

# chaves que contêm a data embutida (a dividir)
CHAVES_COM_DATA_EMBUTIDA = {
    "192": "三月二十三日",
    "216": "三月二十四日",
    # "247" começa com a data — NÃO dividir, é início de sessão natural
    "279": "三月二十六日",
    "312": "三月二十七日",
}


def dividir_no_marcador(jp: str, pt: str, marcador: str) -> tuple[str, str, str, str]:
    """Divide JP e PT no ponto do marcador de data.

    Retorna (jp_antes, pt_antes, jp_depois, pt_depois).
    O jp_depois começa com o marcador; o pt_depois começa com o trecho traduzido
    que corresponde à nova sessão (primeira frase após a data no PT).
    """
    idx = jp.find(marcador)
    if idx < 0:
        raise ValueError(f"marcador {marcador} não encontrado no JP")
    jp_antes = jp[:idx].strip()
    jp_depois = jp[idx:].strip()
    # No PT, o marcador de data pode aparecer como "24 de março." etc.
    # Encontramos o ponto de corte do PT alinhando com o JP da sessão nova:
    # procuramos no PT o trecho que corresponde ao início da sessão.
    # Estratégia: o PT da sessão nova é a parte que traduz o jp_depois.
    # Como não temos alinhamento palavra-a-palavra, usamos uma heurística:
    # a data em PT ("23 de março", "24 de março", etc.).
    pt_idx = _achar_inicio_sessao_pt(pt, marcador)
    pt_antes = pt[:pt_idx].strip()
    pt_depois = pt[pt_idx:].strip()
    return jp_antes, pt_antes, jp_depois, pt_depois


def _achar_inicio_sessao_pt(pt: str, marcador_jp: str) -> int:
    """Acha o índice no PT onde começa a nova sessão.

    Heurísticas, em ordem:
    1. "N de março" literal no PT (ex: "23 de março", "24 de março", …).
    2. Primeira frase do PT que aparece também como início do JP da sessão
       (fallback: procurar por palavras-chave do início da sessão).
    """
    dia = {"三月二十三日": "23", "三月二十四日": "24", "三月二十五日": "25",
           "三月二十六日": "26", "三月二十七日": "27"}[marcador_jp]
    # datas por extenso em português (ex: "Vinte e seis de março", "Vinte e três")
    dias_ext = {
        "23": "(?:Vinte|vinte) e três",
        "24": "(?:Vinte|vinte) e quatro",
        "25": "(?:Vinte|vinte) e cinco",
        "26": "(?:Vinte|vinte) e seis",
        "27": "(?:Vinte|vinte) e sete",
    }
    exts = dias_ext[dia]
    # 1. Padrões numéricos: "23 de março", "dia 23 de março", "23º de março"
    padrões_num = [
        rf"{dia}\s*de\s*março",
        rf"dia\s+{dia}\s+de\s+março",
        rf"{dia}º\s*de\s*março",
        rf"{dia}\s*de\s*Março",
    ]
    # 2. Padrões por extenso: "Vinte e seis de março", "Hoje, 27 de março"
    padrões_ext = [
        rf"{exts}\s+de\s+março",
        rf"Hoje,\s*{dia}\s+de\s+março",
        rf"Hoje,\s*{exts}\s+de\s+março",
        rf"No\s+dia\s+{dia}\s+de\s+março",
    ]
    for p in padrões_num + padrões_ext:
        m = re.search(p, pt, flags=re.IGNORECASE)
        if m:
            # volta para o início da frase (após '. ' ou início)
            inicio = pt.rfind(".", 0, m.start()) + 1
            # pula espaços
            while inicio < len(pt) and pt[inicio] in " \n":
                inicio += 1
            return inicio
    # 3. fallback: se não achar a data literal, não dividimos o PT
    #    (mantém tudo junto — pior caso, mas não corrompe).
    return len(pt)


def main() -> int:
    dry = "--dry-run" in sys.argv
    ck = json.loads(CKPT.read_text(encoding="utf-8"))
    falas = ck.get("falas", {})
    if not falas:
        print("checkpoint sem falas")
        return 1

    # 1. Ordenar chaves numericamente
    def key_num(k):
        try:
            return int(k)
        except ValueError:
            return -1

    chaves = sorted(falas.keys(), key=key_num)

    # 2. Nova lista ordenada de falas
    novas = []
    for k in chaves:
        f = falas[k]
        jp = f.get("jp", "")
        pt = f.get("pt_contextual", "")

        # Caso 1: fala com data embutida no JP → dividir
        if k in CHAVES_COM_DATA_EMBUTIDA:
            marcador = CHAVES_COM_DATA_EMBUTIDA[k]
            if marcador in jp:
                jp_antes, pt_antes, jp_depois, pt_depois = dividir_no_marcador(jp, pt, marcador)
                f_antes = dict(f)
                f_antes["jp"] = jp_antes
                f_antes["pt_contextual"] = pt_antes
                novas.append(f_antes)
                if jp_depois and pt_depois:
                    f_nova = dict(f)
                    f_nova["jp"] = jp_depois
                    f_nova["pt_contextual"] = pt_depois
                    novas.append(f_nova)
                else:
                    # se não conseguiu dividir o PT, mantém a fala inteira
                    # (a parte depois fica na fala original; registra aviso)
                    print(f"  ! aviso: chave {k}: pt_depois vazio, mantendo fala inteira")
                continue

        # Caso 2: fala que JÁ começa com data (247) → normal
        # Caso 3: fala normal
        novas.append(f)

    # 3. Renumerar 0..N-1
    novas_falas = {}
    for i, f in enumerate(novas):
        f2 = dict(f)
        f2["indice"] = i
        novas_falas[str(i)] = f2

    # 4. Salvar
    if dry:
        print(f"[dry-run] falas: {len(falas)} → {len(novas)}")
        for i, f in enumerate(novas):
            jp = f.get("jp", "")
            datas = re.findall(r"三月[一二三四五六七八九十]+日", jp)
            if datas:
                print(f"  nova chave {i}: datas no JP: {datas} | PT[:50]: {f.get('pt_contextual','')[:50]!r}")
        return 0

    ck["falas"] = novas_falas
    CKPT.write_text(json.dumps(ck, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {CKPT.name}: falas {len(falas)} → {len(novas)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
