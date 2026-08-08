#!/usr/bin/env python3
"""Rotula turnos de fala no japonês (Interlocutor:/Meishu-Sama:) usando a
sequência já validada do português como referência, aplicada por posição aos
parágrafos do corpo do JP.

Critério de segurança (revisado 2026-07-13 -- o que importa é nunca
confundir Interlocutor com Meishu-Sama, não bater contagem exata):
1. Zero ocorrências do padrão de risco conhecido: item de lista numerada
   (一、/二、/三、.../（一）/（二）/.../1./(1)/...) indentado aparecendo logo
   depois de uma pergunta do interlocutor, sem um parágrafo de abertura de
   resposta antes -- esse padrão engana a classificação por indentação (o
   item pertence à PERGUNTA, não à resposta). Achado real em
   `19511125-御教え集3号.txt` (formato "一、") e depois, mais grave, em 8 dos
   livros já rotulados numa rodada anterior (formato "（一）", que o regex
   original não cobria -- vazamento real confirmado, corrigido).
2. Alinhamento por difflib entre a sequência PT e a sequência JP não tem
   nenhum "replace" nem "insert" -- só "delete" (PT com mais turnos
   distintos que o JP encontrou) é aceito, porque isso nunca é troca de tipo
   na mesma posição alinhada. Contagem total diferente NÃO bloqueia mais a
   rotulagem por si só (critério antigo, substituído -- bater contagem exata
   é caro demais e não é o que protege contra o risco real).

Livros que não passam os dois critérios NÃO são rotulados -- ficam
registrados em PENDENCIAS_REVISAO.json para decisão humana, nunca rotulados
por adivinhação.

Uso:
  python3 scripts/rotular_turnos_jp.py                # dry-run, mostra relatorio
  python3 scripts/rotular_turnos_jp.py --apply         # aplica nos arquivos seguros
"""
from __future__ import annotations

import argparse
import difflib
import glob
import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PT_DIR = PROJECT_ROOT / "reports/livros_trabalho/pt"
JP_DIR = PROJECT_ROOT / "reports/livros_trabalho/jp"
PENDENCIAS_PATH = PROJECT_ROOT / "reports/livros_trabalho/segmentacao_manual/PENDENCIAS_REVISAO.json"

INTERLOCUTOR_PREFIXES = ("――", "「", "（お伺", "（御伺")
LABEL_ONLY_LINES = ("〔御垂示〕", "（御垂示）", "御垂示")
# Titulos de secao de prefacio/aviso editorial antes do diologo real comecar
# -- "「お断り」" usa aspas「」 (o mesmo prefixo de Interlocutor), mas nao e
# pergunta nenhuma, e por isso precisa de exclusao propria (achado real em
# 19520125-御垂示録6号.txt, 2026-07-13: prefacio inteiro sendo classificado
# como fala de Meishu-Sama/Interlocutor por engano).
FRONT_MATTER_TITLES = ("序文", "「お断り」", "お断り")
NUMBERED_ITEM_RE = re.compile(
    r"^　+(?:"
    r"[一二三四五六七八九十]+[、.．]"
    r"|[0-9]+[、.．]"
    r"|（(?:[一二三四五六七八九十]+|[0-9]+|[イロハニホヘトチリヌルヲワカヨタレソツネナラムウヰノオクヤマケフコエテアサキユメミシヱヒモセス])）"
    r")"
)
# Parágrafo que é SÓ uma legenda/nota editorial entre parênteses (nada mais)
# nunca é um turno de fala real -- confirmado em vários livros (achado real
# em 19480101-御光話録（補）.txt, 2026-07-13: "（新年の大先生御歌）" era uma
# legenda introduzindo um poema, não uma fala, e ficava classificada como
# Meishu-Sama por engano, desalinhando os 962 turnos seguintes por 1 posição).
CAPTION_ONLY_RE = re.compile(r"^　*（[^）]*）$")
# Titulo de poema sem parenteses (so as palavras "御歌", com espacamento
# interno variavel) -- mesmo efeito de CAPTION_ONLY_RE mas sem os parenteses.
BARE_POEM_TITLE_RE = re.compile(r"^御\s*歌$")
# Marcador de data real (com ou sem colchetes, com ou sem era/ano na frente)
# -- usado para saber quando o prefacio/aviso editorial terminou e o
# dialogo de verdade comeca.
DATE_HEADER_RE = re.compile(r"[０-９0-9一二三四五六七八九十]+月[０-９0-9一二三四五六七八九十]+日")
# Paragrafo cujo conteudo INTEIRO (apos strip) e uma citacao entre aspas,
# sem nada antes ou depois -- ver nota em classify_jp.
FULL_QUOTE_REPLY_RE = re.compile(r"^「.*」$")


def collapse(seq: list[str]) -> list[str]:
    out: list[str] = []
    for s in seq:
        if out and out[-1] == s:
            continue
        out.append(s)
    return out


def pt_label_sequence(text: str) -> list[str]:
    labels = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("Interlocutor:"):
            labels.append("Interlocutor")
        elif s.startswith("Meishu-Sama:"):
            labels.append("Meishu-Sama")
    return labels


def find_body_start(lines: list[str]) -> int:
    for i, l in enumerate(lines):
        if l.startswith("Collection ID"):
            return i + 1
    return 0


def classify_jp(text: str):
    """Retorna (lista de (indice_da_linha, tipo), risk_hits) para o corpo do JP.

    indice_da_linha é a posição em `lines` (texto completo, não só corpo) da
    linha que inicia aquele parágrafo -- usado depois para inserir o rótulo
    na posição certa sem reconstruir o arquivo do zero.
    """
    lines = text.split("\n")
    body_start = find_body_start(lines)
    entries = []  # (line_idx, "Interlocutor"|"Meishu-Sama")
    last_was_question = False
    risk_hits = 0
    in_poem_block = False
    in_front_matter = False
    # Se o livro usa marcador explicito de resposta (〔御垂示〕 etc, ver
    # LABEL_ONLY_LINES), uma pergunta pode continuar em paragrafo indentado
    # (sem numeracao nenhuma) ANTES do marcador aparecer -- esse paragrafo
    # pertence a pergunta, nao a resposta, mesmo indentado como Meishu-Sama
    # (achado real em 19511125-御教え集3号.txt, 2026-07-13: pergunta longa
    # continuando em paragrafo indentado antes do 〔御垂示〕 da resposta real).
    # So ativa essa suspensao em livros que de fato usam o marcador -- em
    # livros sem ele, o paragrafo indentado logo apos a pergunta JA é a
    # resposta real, sem marcador nenhum.
    usa_marcador_resposta = any(l.strip() in LABEL_ONLY_LINES for l in lines[body_start:])
    aguardando_marcador_resposta = False
    for i in range(body_start, len(lines)):
        p = lines[i]
        if not p.strip():
            continue
        s = p.strip()
        if DATE_HEADER_RE.search(s) and len(s) <= 30:
            # marcador de data real -- encerra qualquer prefacio/aviso ainda
            # em aberto (nao classifica o proprio marcador como turno).
            in_front_matter = False
            continue
        if s in FRONT_MATTER_TITLES:
            in_front_matter = True
            continue
        if in_front_matter:
            continue
        if s in LABEL_ONLY_LINES:
            aguardando_marcador_resposta = False
            continue
        if usa_marcador_resposta and aguardando_marcador_resposta and p.startswith("　"):
            continue
        if CAPTION_ONLY_RE.match(p):
            # legenda de poema (ex.: "（...御歌）") introduz um bloco de versos
            # que nao e turno de fala -- os versos em si (indentados como
            # Meishu-Sama) ficam suprimidos até a próxima legenda/turno real
            # (achado real em 19480101-御光話録（補）.txt, 2026-07-13).
            in_poem_block = s.endswith("御歌）")
            continue
        if BARE_POEM_TITLE_RE.match(s):
            # titulo de poema sem parenteses (ex.: "　　　　御　歌"), mesmo
            # efeito da legenda entre parenteses -- achado real em
            # 19490522-御光話録7号.txt, 2026-07-13.
            in_poem_block = True
            continue
        if in_poem_block and p.startswith("　"):
            # versos (waka) sao sempre curtos; uma linha indentada longa
            # (prosa real) encerra o bloco de poemas mesmo sem outra legenda
            # depois (achado real: 19480101-御光話録（補）.txt tem 2 blocos de
            # poema, um seguido de legenda de credito, outro direto por fala
            # real -- nao dá pra confiar só em "próxima legenda reseta").
            if len(s) <= 35:
                continue
            in_poem_block = False
        if NUMBERED_ITEM_RE.match(p) and last_was_question:
            risk_hits += 1
            continue
        if FULL_QUOTE_REPLY_RE.match(s):
            # Paragrafo INTEIRO entre aspas (nada antes nem depois do 「...」)
            # e sempre resposta curta do interlocutor num dialogo rapido
            # medico-paciente (Meishu-Sama pergunta, interlocutor responde em
            # 1a pessoa) -- achado real e confirmado por varredura em todas
            # as 248 ocorrencias deste padrao nos 58 livros de dialogo
            # (2026-07-13): quando Meishu-Sama cita algo (ex.: titulo de
            # obra), a citacao e um FRAGMENTO dentro de uma frase maior dele
            # mesmo (ex.: "　「笑の泉」は..."), nunca o paragrafo inteiro.
            entries.append((i, "Interlocutor"))
            last_was_question = True
            aguardando_marcador_resposta = True
            continue
        # Indentação (texto NÃO stripado) é o sinal primário e decide primeiro
        # -- um parágrafo de Meishu-Sama pode citar algo entre 「」 logo após
        # o espaço de indentação (ex.: "　「笑の泉」は..."), e checar o prefixo
        # de Interlocutor no texto stripado erraria esse caso (bug real
        # encontrado e corrigido em 2026-07-13, ver reports de rotulagem).
        if p.startswith("　"):
            entries.append((i, "Meishu-Sama"))
            last_was_question = False
            continue
        if s.startswith(INTERLOCUTOR_PREFIXES):
            entries.append((i, "Interlocutor"))
            last_was_question = True
            aguardando_marcador_resposta = True
    return entries, risk_hits


def collapse_entries(entries: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Colapsa entradas consecutivas do mesmo falante, mantendo a linha do
    PRIMEIRO parágrafo de cada grupo (é ali que o rótulo deve ser inserido)."""
    out: list[tuple[int, str]] = []
    for idx, spk in entries:
        if out and out[-1][1] == spk:
            continue
        out.append((idx, spk))
    return out


def analyze_book(name: str) -> dict:
    pt_path = PT_DIR / name
    jp_path = JP_DIR / name
    pt_text = pt_path.read_text(encoding="utf-8")
    pt_seq = collapse(pt_label_sequence(pt_text))
    if len(pt_seq) <= 5:
        return {"name": name, "dialogo": False}
    if not jp_path.exists():
        return {"name": name, "dialogo": True, "seguro": False, "motivo": "sem JP"}
    jp_text = jp_path.read_text(encoding="utf-8")
    if "Interlocutor:" in jp_text or "Meishu-Sama:" in jp_text:
        # ja rotulado numa rodada anterior -- nao reanalisar com a heuristica
        # (ela pressupoe texto SEM rotulo; reaplicar aqui so produziria lixo).
        jp_seq_ja = collapse(pt_label_sequence(jp_text))
        return {
            "name": name, "dialogo": True, "seguro": False,
            "motivo": "ja_rotulado", "ja_rotulado": True,
            "bate_com_pt": jp_seq_ja == pt_seq,
        }
    entries, risk_hits = classify_jp(jp_text)
    collapsed = collapse_entries(entries)
    jp_seq = [spk for _, spk in collapsed]
    diff = len(pt_seq) - len(jp_seq)
    # Critério de segurança (2026-07-13, revisado): o que importa de verdade
    # não é bater a contagem exata -- é NUNCA confundir Interlocutor com
    # Meishu-Sama (o risco real: uma pergunta do interlocutor virando base de
    # resposta no aplicativo). Usamos difflib para alinhar as duas sequências
    # de verdade: "delete" (PT tem mais turnos distintos que o JP encontrou,
    # ex.: falas longas com granularidade diferente) nunca é troca de tipo na
    # mesma posição -- é seguro. "replace" (uma posição alinhada com tipos
    # diferentes) ou "insert" (JP tem turno que o PT não tem correspondência)
    # são os casos perigosos de verdade -- aí sim não aplicamos.
    opcodes = difflib.SequenceMatcher(a=pt_seq, b=jp_seq, autojunk=False).get_opcodes()
    ops_presentes = {op for op, *_ in opcodes if op != "equal"}
    # risk_hits alto não bloqueia mais por si só -- o mecanismo de exclusão
    # (NUMBERED_ITEM_RE) já foi validado lendo o conteúdo real (2026-07-13):
    # quando ele exclui um item, o alinhamento resultante contra o PT bate
    # (delete/vazio, nunca replace/insert), confirmando que a exclusão estava
    # correta. risk_hits fica só como informação para revisão futura.
    seguro = not ({"replace", "insert"} & ops_presentes)
    return {
        "name": name,
        "dialogo": True,
        "seguro": seguro,
        "pt_turnos": len(pt_seq),
        "jp_turnos": len(jp_seq),
        "diff": diff,
        "risk_hits": risk_hits,
        "ops": sorted(ops_presentes),
        "pt_seq": pt_seq,
        "jp_entries": collapsed,
        "opcodes": opcodes,
    }


def apply_labels(name: str, analysis: dict) -> None:
    """Aplica rótulos usando o alinhamento REAL do difflib (opcodes), não
    zip posicional ingênuo -- um "delete" (PT com turnos extras que o JP não
    tem) desalinharia tudo que vem depois se aplicado por posição direta
    (bug real encontrado e corrigido em 2026-07-13). Só os blocos "equal" do
    alinhamento recebem rótulo; qualquer coisa fora disso (não deveria
    existir, dado o critério de segurança em analyze_book) fica sem rótulo,
    nunca com rótulo adivinhado."""
    jp_path = JP_DIR / name
    lines = jp_path.read_text(encoding="utf-8").split("\n")
    pt_seq = analysis["pt_seq"]
    jp_entries = analysis["jp_entries"]
    opcodes = analysis["opcodes"]

    inserts = []
    for op, i1, i2, j1, j2 in opcodes:
        if op != "equal":
            continue
        for offset in range(i2 - i1):
            speaker = pt_seq[i1 + offset]
            line_idx, _ = jp_entries[j1 + offset]
            label = "Interlocutor: " if speaker == "Interlocutor" else "Meishu-Sama: "
            inserts.append((line_idx, label))

    # inserir na ordem inversa (por indice de linha decrescente) para nao
    # invalidar os indices das entradas anteriores ao inserir uma nova linha
    inserts.sort(key=lambda x: -x[0])
    for line_idx, label in inserts:
        original = lines[line_idx]
        lines[line_idx] = label + original.lstrip("　")
    jp_path.write_text("\n".join(lines), encoding="utf-8")


def register_pending(review_items: list[dict]) -> None:
    data = json.loads(PENDENCIAS_PATH.read_text(encoding="utf-8"))
    data["items"].append({
        "arquivo": "ROTULAGEM_JP_LIVROS_PENDENTES_REVISAO",
        "estado": "pendente_decisao_usuario_rotulagem_turnos_jp_fase5",
        "nota": (
            "Rotulagem automatica de turnos JP (scripts/rotular_turnos_jp.py, 2026-07-13) "
            "processou os livros de dialogo do corpus. Os seguintes NAO foram rotulados "
            "automaticamente por nao passarem o criterio de seguranca duplo "
            "(sequencia compactada PT/JP com diff <= 2 E zero ocorrencias do padrao de "
            "risco 'lista numerada logo apos pergunta, mal-classificada por indentacao'): "
            + json.dumps(review_items, ensure_ascii=False)
        ),
    })
    PENDENCIAS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    names = sorted(os.path.basename(p) for p in glob.glob(str(PT_DIR / "*.txt")))
    safe, review = [], []
    for name in names:
        a = analyze_book(name)
        if not a.get("dialogo"):
            continue
        if a.get("seguro"):
            safe.append(a)
        else:
            review.append({k: v for k, v in a.items() if k not in ("pt_seq", "jp_entries")})

    print(json.dumps({"seguros": len(safe), "revisao": len(review)}, ensure_ascii=False, indent=2))
    for a in review:
        print("REVISAO:", a.get("name"), a.get("diff"), a.get("risk_hits"), a.get("motivo", ""))

    if args.apply:
        for a in safe:
            apply_labels(a["name"], a)
        register_pending(review)
        print(f"Aplicado em {len(safe)} livros. {len(review)} registrados em PENDENCIAS_REVISAO.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
