#!/usr/bin/env python3
"""Consolida o Gokōwa-roku (Suplemento) retraduzido na pasta provisória das orais.

Fonte de verdade: o JAPONÊS (textos_japones/19480101-御光話録（補）.txt) conforme o
protocolo de tradução (modelo A2). O corpo de diálogo vem do checkpoint da
retradução (laco_retraducao_checkpoint.json, 957 falas).

Estrutura de saída (modelo A2 do protocolo):
  Gokōwa-roku (Suplemento)
  [prefácio editorial — tradução das notas JP]
  **1º de janeiro do ano 23 da Era Showa (1948)**
  (Poemas do Grão-Mestre para o Ano Novo)
  [poemas + nota musical]
  **{data por extenso + Era Showa + ano ocidental}**
  Interlocutor: ...
  Meishu-Sama: ...
  ...

Destino: revisao_literaria/orais/19480101 - Gokōwa-roku (Suplemento).txt
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

JP = RAIZ / "textos_japones" / "19480101-御光話録（補）.txt"
CKPT = RAIZ / "reports" / "amostragem_semantica_gokowa" / "laco_retraducao_checkpoint.json"
DEST_DIR = RAIZ / "revisao_literaria" / "orais"
DEST = DEST_DIR / "19480101 - Gokōwa-roku (Suplemento).txt"

# Mapa de datas JP (mes, dia) -> PT completo (do protocolo A2)
# (usar o mapa salvo; se faltar, estes são os 35)
DATAS_PT = {
    (1, 1): "1º de janeiro do ano 23 da Era Showa (1948)",
    (1, 18): "18 de janeiro do ano 23 da Era Showa (1948)",
    (1, 28): "28 de janeiro do ano 23 da Era Showa (1948) (quarta-feira)",
    (2, 8): "8 de fevereiro do ano 23 da Era Showa (1948) (domingo)",
    (2, 18): "18 de fevereiro do ano 23 da Era Showa (1948) (quarta-feira)",
    (2, 28): "28 de fevereiro do ano 23 da Era Showa (1948) (sábado)",
    (3, 8): "8 de março do ano 23 da Era Showa (1948) (segunda-feira)",
    (3, 28): "28 de março do ano 23 da Era Showa (1948) (domingo)",
    (4, 8): "8 de abril do ano 23 da Era Showa (1948) (quinta-feira)",
    (4, 18): "18 de abril do ano 23 da Era Showa (1948) (domingo)",
    (4, 28): "28 de abril do ano 23 da Era Showa (1948) (quarta-feira)",
    (5, 8): "8 de maio do ano 23 da Era Showa (1948) (sábado)",
    (5, 18): "18 de maio do ano 23 da Era Showa (1948)",
    (5, 28): "28 de maio do ano 23 da Era Showa (1948) (sexta-feira)",
    (6, 8): "8 de junho do ano 23 da Era Showa (1948) (terça-feira)",
    (6, 18): "18 de junho do ano 23 da Era Showa (1948) (sexta-feira)",
    (6, 28): "28 de junho do ano 23 da Era Showa (1948)",
    (7, 8): "8 de julho do ano 23 da Era Showa (1948) (quinta-feira)",
    (7, 18): "18 de julho do ano 23 da Era Showa (1948) (domingo)",
    (7, 28): "28 de julho do ano 23 da Era Showa (1948) (quarta-feira)",
    (8, 8): "8 de agosto do ano 23 da Era Showa (1948) (domingo)",
    (8, 18): "18 de agosto do ano 23 da Era Showa (1948) (quarta-feira)",
    (8, 28): "28 de agosto do ano 23 da Era Showa (1948)",
    (9, 8): "8 de setembro do ano 23 da Era Showa (1948) (quarta-feira)",
    (9, 18): "18 de setembro do ano 23 da Era Showa (1948) (sábado)",
    (9, 28): "28 de setembro do ano 23 da Era Showa (1948) (terça-feira)",
    (10, 8): "8 de outubro do ano 23 da Era Showa (1948) (sexta-feira)",
    (10, 18): "18 de outubro do ano 23 da Era Showa (1948) (segunda-feira)",
    (10, 28): "28 de outubro do ano 23 da Era Showa (1948) (quinta-feira)",
    (11, 8): "8 de novembro do ano 23 da Era Showa (1948) (segunda-feira)",
    (11, 18): "18 de novembro do ano 23 da Era Showa (1948) (quinta-feira)",
    (11, 28): "28 de novembro do ano 23 da Era Showa (1948)",
    (12, 8): "8 de dezembro do ano 23 da Era Showa (1948) (quarta-feira)",
    (12, 18): "18 de dezembro do ano 23 da Era Showa (1948) (domingo)",
    (12, 28): "28 de dezembro do ano 23 da Era Showa (1948) (terça-feira)",
}

# Prefácio editorial (tradução das notas JP 21-24, conforme protocolo)
PREFACIO = [
    "O Gokōwa-roku é um registro de audiências com Meishu-Sama, com data de publicação desconhecida; estima-se que tenha sido publicado por volta do ano 26 da Era Showa (1951).",
    "Trata-se de um manuscrito em encadernação japonesa, cópia em carbono, de 138 páginas, registrando as audiências realizadas de 1º de janeiro a 18 de outubro do ano 23 da Era Showa (1948).",
    "Por volta do ano 30 da Era Showa (1955), foram acrescentados os números 1 e 2, já publicados, e a obra foi editada em capa dura, formato A5. Conhecida popularmente como “Gokōwa-roku (Suplemento)”, reúne os registros de audiências do ano 23 da Era Showa (1948).",
]

# Poemas do Ano Novo (tradução do publicado, já validada)
POEMAS = [
    "(Poemas do Grão-Mestre para o Ano Novo)",
    "A dor aos poucos se cura, e com alegria recebo o início do novo ano.",
    "Ao receber o ano novo, corpo e alma se purificam, pois sou um ser divino.",
    "A escuridão do caminho tenebroso se esgota, e sinto como se pisasse pela primeira vez na estrada da luz.",
    "Miroku Ōkami, que surge dotado do poder trino do Sol, Lua e Terra.",
    "(O poema acima foi cantado pelo compositor Sr. Haseo Sugiyama, acompanhado pelo Sr. Shusuke Fukui ao piano.)",
]


def extrai_data_jp(s: str) -> tuple[int, int] | None:
    """Extrai (mes, dia) de uma linha de data JP."""
    jp_mes = {'一':'1','二':'2','三':'3','四':'4','五':'5','六':'6','七':'7','八':'8','九':'9','十':'10','十一':'11','十二':'12'}
    jp_dia = {'一日':'1','八日':'8','十八日':'18','二十八日':'28'}
    m = re.match(r'^昭和[一二三四五六七八九十]+年([一二三四五六七八九十]+)月([一二三四五六七八九十]+日)', s) or re.match(r'^([一二三四五六七八九十]+)月([一二三四五六七八九十]+日)', s)
    if not m:
        return None
    mes = jp_mes.get(m.group(1))
    dia = jp_dia.get(m.group(2))
    if mes is None or dia is None:
        return None
    return (int(mes), int(dia))


def turnos_jp_por_data() -> list[tuple[tuple[int, int] | None, int, int]]:
    """Retorna [(data, inicio_turno, fim_turno)] — cada sessão datada com o
    intervalo de turnos que lhe pertence. data=None para o bloco inicial."""
    linhas = [l.rstrip() for l in JP.read_text(encoding="utf-8").splitlines()]
    sessoes: list[tuple[tuple[int, int] | None, int, int]] = []
    data_atual: tuple[int, int] | None = None
    inicio_atual = 0
    acum = 0
    for l in linhas:
        s = l.strip()
        if re.match(r'^(Meishu-Sama|Interlocutor)[:：]', s):
            acum += 1
        else:
            d = extrai_data_jp(s)
            if d:
                if data_atual is not None or inicio_atual > 0 or acum > 0:
                    sessoes.append((data_atual, inicio_atual, acum))
                data_atual = d
                inicio_atual = acum
    sessoes.append((data_atual, inicio_atual, acum))
    return sessoes


def main() -> int:
    ck = json.loads(CKPT.read_text(encoding="utf-8"))
    falas = ck["falas"]
    if len(falas) != 957:
        print(f"ERRO: checkpoint tem {len(falas)} falas, esperado 957", file=sys.stderr)
        return 1
    vazias = [k for k, f in falas.items() if not f.get("pt_contextual")]
    if vazias:
        print(f"ERRO: falas vazias no checkpoint: {vazias}", file=sys.stderr)
        return 1

    sessoes = turnos_jp_por_data()
    print(f"Sessões datadas: {len(sessoes)}")

    linhas_out: list[str] = []
    linhas_out.append("Gokōwa-roku (Suplemento)")
    linhas_out.append("")
    linhas_out.extend(PREFACIO)
    linhas_out.append("")

    n_turnos_emitidos = 0
    for data, ini, fim in sessoes:
        # cabeçalho de data (se houver)
        if data is not None:
            pt_data = DATAS_PT.get(data)
            if not pt_data:
                print(f"AVISO: data {data} sem tradução PT", file=sys.stderr)
                pt_data = f"{data[1]} do mês {data[0]}"
            linhas_out.append(f"**{pt_data}**")
            linhas_out.append("")
            # subtítulo/poemas na primeira sessão (1/1)
            if data == (1, 1):
                linhas_out.extend(POEMAS)
                linhas_out.append("")
        # turnos desta sessão
        for i in range(ini, fim):
            f = falas.get(str(i))
            if not f:
                print(f"ERRO: fala {i} ausente", file=sys.stderr)
                return 1
            quem = f["quem"]
            pt = f["pt_contextual"].strip()
            rotulo = "Interlocutor" if quem == "Interlocutor" else "Meishu-Sama"
            linhas_out.append(f"{rotulo}: {pt}")
            linhas_out.append("")
            n_turnos_emitidos += 1

    texto = "\n".join(linhas_out).strip() + "\n"
    if n_turnos_emitidos != 957:
        print(f"ERRO: emiti {n_turnos_emitidos} turnos, esperado 957", file=sys.stderr)
        return 1

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    DEST.write_text(texto, encoding="utf-8")
    print(f"Consolidado: {DEST}")
    print(f"Turnos emitidos: {n_turnos_emitidos}/957")
    print(f"Tamanho: {len(texto)} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
