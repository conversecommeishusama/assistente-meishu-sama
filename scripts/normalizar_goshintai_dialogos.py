#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aplica as duas convenções decididas pelo usuário (20/10/2026).

**1. 御神体 = «Imagem da Luz Divina».**
A ronda R5 da auditoria dos periódicos (14/10) substituiu 御神体 por «objeto
sagrado de culto (goshintai)» em 83 lugares, contra o `glossario_traducao.json`
(御神体 → «Imagem da Luz Divina») e contra a convenção do acervo, que já tinha
462 «Imagem da Luz Divina». Revertido, com concordância de género — «Imagem» é
feminino: o/do/ao/um/no → a/da/à/uma/na, e os cinco particípios que concordavam
com «objeto» passam a concordar com «Imagem».

**2. Diálogos = «Interlocutor:» / «Meishu-Sama:».**
É a forma dominante no acervo (5336 + 6007 ocorrências) e a única das obras
orais. Os periódicos e os Cursos de Johrei usavam marcadores próprios em linha
isolada: `(Pergunta)` 396, `(Resposta Divina)` 507 e mais 10 variantes
(`(Consulta)`, `(Indagação)`, `(Revelação Divina)`, `(Instrução Divina)`,
`**Pergunta:**`, `**Ensinamento Divino:**` e as de largura inteira `（Consulta）`,
`（Indagação）`, `（Resposta Divina）`, `（Orientação）`, `（Orientação Divina）`,
`（Resposta de Meishu-Sama）`).

Só se convertem marcadores **no início de linha** — é o formato dos diálogos. As
ocorrências inline (117 + 85) ficam intactas: são anotações de citação
(«A calvície é hereditária? (Pergunta) (Mioshie-shū)»), não falas. Do mesmo
modo, `（Kyusei nº 49）` é referência de fonte, não marcador.

Quando o marcador traz a citação de fonte na mesma linha
(`(Pergunta) (Mioshie-shū)` seguido da pergunta), a citação passa para o fim da
pergunta em vez de se perder:
`Interlocutor: <pergunta> (Mioshie-shū)`.

**Âncoras.** Uma âncora pode incluir o próprio marcador
(`título\\n\\n(Pergunta)`); a conversão invalida-a e o artigo fundir-se-ia com o
anterior. `repara_ancoras()` reconstrói essas âncoras a partir do texto actual,
exigindo que a primeira linha seja única.

Aplica a `textos_portugues/`, `textos_leitura_colaborativa/` e aos itens de
`reports/traducao_periodicos/itens/` — se os itens não acompanharem, o
`sincronizar_acervo_correcoes.py` passa a acusar ~1000 divergências.
Idempotente; backup `.bak_convencoes_<ts>`; recusa gravar se a transformação
perder âncoras.

Uso:
    .venv/bin/python scripts/normalizar_goshintai_dialogos.py
    .venv/bin/python scripts/normalizar_goshintai_dialogos.py --aplicar
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ))

PT = RAIZ / "textos_portugues"
LC = RAIZ / "textos_leitura_colaborativa"
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
SPECS = RAIZ / "reports" / "livros_trabalho" / "segmentacao_manual"

VEICULOS = ["Tijotengoku", "Eiko", "Hikari", "Kyusei"]

# --- 1. 御神体 ------------------------------------------------------------
# A ordem importa: maiúsculas e contrações antes de «o objeto…», que casaria
# dentro delas («ao objeto» → «a» + «o objeto» → «aa Imagem»).
GOSHINTAI = [
    ("Ao objeto sagrado de culto (goshintai)", "À Imagem da Luz Divina"),
    ("ao objeto sagrado de culto (goshintai)", "à Imagem da Luz Divina"),
    ("Um objeto sagrado de culto (goshintai)", "Uma Imagem da Luz Divina"),
    ("um objeto sagrado de culto (goshintai)", "uma Imagem da Luz Divina"),
    ("O objeto sagrado de culto (goshintai)", "A Imagem da Luz Divina"),
    ("o objeto sagrado de culto (goshintai)", "a Imagem da Luz Divina"),
    # forma sem artigo — aparece nas transições dos backups (a R5 substituía o
    # termo isolado) e tem de ser reconhecida senão o sincronizador reaplica a
    # convenção abolida
    ("Objeto sagrado de culto (goshintai)", "Imagem da Luz Divina"),
    ("objeto sagrado de culto (goshintai)", "Imagem da Luz Divina"),
]

# Particípios que concordavam com «objeto» (masculino) e têm de concordar com
# «Imagem» (feminino). São os cinco casos que existem no acervo.
CONCORDANCIA_PRE = [
    ("foi entronizado o objeto sagrado de culto (goshintai)",
     "foi entronizada a Imagem da Luz Divina"),
]
CONCORDANCIA_POS = [
    ("a Imagem da Luz Divina foi entronizado por nós",
     "a Imagem da Luz Divina foi entronizada por nós"),
    ("A Imagem da Luz Divina foi entronizado por nós",
     "A Imagem da Luz Divina foi entronizada por nós"),
    ("a Imagem da Luz Divina está sendo solicitado",
     "a Imagem da Luz Divina está sendo solicitada"),
    ("à Imagem da Luz Divina que foi danificado",
     "à Imagem da Luz Divina que foi danificada"),
    ("a Imagem da Luz Divina [dele] foi recebido",
     "a Imagem da Luz Divina [dele] foi recebida"),
    ("A Imagem da Luz Divina [dele] foi recebido",
     "A Imagem da Luz Divina [dele] foi recebida"),
]

# --- 2. marcadores de diálogo --------------------------------------------
PERGUNTA = [
    "(Pergunta)", "(Consulta)", "(Indagação)", "**Pergunta:**",
    "（Pergunta）", "（Consulta）", "（Indagação）", "**Consulta:**",
    "PERGUNTA", "CONSULTA",
]
RESPOSTA = [
    "(Resposta Divina)", "(Revelação Divina)", "(Instrução Divina)",
    "**Ensinamento Divino:**", "（Resposta Divina）", "（Orientação）",
    "（Orientação Divina）", "（Resposta de Meishu-Sama）",
    "（Instrução Divina）", "（Revelação Divina）", "（Ensinamento Divino）",
    # variantes sem o adjectivo, encontradas depois da 1.ª passagem (Tijo 20,
    # 22, 29, 32, 43, 46): todas em posição de resposta
    "(Orientação)", "(Orientação Divina)", "(Instrução)", "(Ensinamento)",
    "INSTRUÇÃO DIVINA", "RESPOSTA DIVINA",
]
ALVO = {"Interlocutor:": PERGUNTA, "Meishu-Sama:": RESPOSTA}

SEP = r"[ \t]*\n+"
CITACAO = (r"(\((?:Mioshie-shū|Gosuiji-roku|Gokōwa-roku|Kyōshu|Hikari|Eikō)"
           r"[^)\n]*\))")


TODAS_MARCAS = PERGUNTA + RESPOSTA

# Marcadores empilhados: 48 sítios do Tijotengoku tinham quatro `(Resposta
# Divina)` seguidos (defeito herdado de uma inserção repetida, anterior a
# 20/10). Fica só o último, o que está mais perto do texto.
EMPILHADO = re.compile(
    r"^(?:" + "|".join(re.escape(m) for m in TODAS_MARCAS) +
    r")[ \t]*\n+(?=(?:" + "|".join(re.escape(m) for m in TODAS_MARCAS) +
    r")[ \t]*\n)", re.M)

# Prefixos repetidos gerados pela 1.ª passagem, antes de `converte` desempilhar
PREFIXO_REPETIDO = re.compile(r"^(Interlocutor: |Meishu-Sama: )(?:\1)+", re.M)


def converte(t: str) -> str:
    t = PREFIXO_REPETIDO.sub(lambda mo: mo.group(1), t)
    # desempilha marcadores repetidos, preservando o último de cada sequência
    anterior = None
    while anterior != t:
        anterior = t
        t = EMPILHADO.sub("", t)
    for antigo, novo in CONCORDANCIA_PRE:
        t = t.replace(antigo, novo)
    for antigo, novo in GOSHINTAI:
        t = t.replace(antigo, novo)
    for antigo, novo in CONCORDANCIA_POS:
        t = t.replace(antigo, novo)
    for alvo, marcas in ALVO.items():
        for m in marcas:
            # marcador isolado na linha + quebras → prefixo inline
            t = re.sub("^" + re.escape(m) + r"[ \t]*\n+", alvo + " ", t, flags=re.M)
            # marcador + citação na mesma linha: a citação passa para o fim da
            # pergunta seguinte
            t = re.sub("^" + re.escape(m) + r"[ \t]+" + CITACAO + SEP +
                       r"([^\n]+)",
                       lambda mo: f"{alvo} {mo.group(2)} {mo.group(1)}",
                       t, flags=re.M)
            # marcador + fala na mesma linha
            t = re.sub("^" + re.escape(m) + r"[ \t]+([^\n]+)",
                       lambda mo: f"{alvo} {mo.group(1)}", t, flags=re.M)
            # marcador isolado no fim do texto (é assim que aparece uma
            # transição em que só o marcador mudou)
            t = re.sub("^" + re.escape(m) + r"[ \t]*$", alvo, t, flags=re.M)
    return t


def conta(t: str) -> int:
    """Quantas substituições `converte` faria neste texto.

    Conta marcadores no início de linha em qualquer das formas tratadas
    (isolado, com citação, ou com a fala na mesma linha) — a versão anterior só
    contava os seguidos de quebra e reportava 0 quando não restava nenhum
    desses, escondendo o trabalho feito.
    """
    n = 0
    for marcas in ALVO.values():
        for m in marcas:
            n += len(re.findall("^" + re.escape(m) + r"(?=\s|$)", t, re.M))
    for antigo, _ in GOSHINTAI:
        n += t.count(antigo)
    return n


def ancoras_resolvidas(veic: str, texto: str) -> int:
    spec = json.loads((SPECS / f"{veic}.txt.json").read_text(encoding="utf-8"))
    return sum(1 for a in spec["articles"]
               if not a["pt_anchor"] or a["pt_anchor"] in texto)


def repara_ancoras(ts: str, aplicar: bool) -> int:
    """Reconstrói âncoras PT que a conversão invalidou.

    Uma âncora pode incluir o próprio marcador (`título\\n\\n(Pergunta)`); nesse
    caso a conversão muda o texto e a âncora deixa de resolver — e o artigo
    funde-se com o anterior. Critério restrito: só se toca em âncoras que
    (a) não resolvem, (b) contêm um marcador de diálogo e (c) cuja primeira
    linha é única no ficheiro. A nova âncora é a primeira linha mais a linha
    seguinte do texto actual (`Interlocutor: …` / `Meishu-Sama: …`).
    """
    marcas = PERGUNTA + RESPOSTA
    mudadas = 0
    for sp in sorted(SPECS.glob("*.txt.json")):
        veic = sp.name[:-len(".txt.json")]
        caminho = PT / f"{veic}.txt"
        if not caminho.exists():
            continue
        t = caminho.read_text(encoding="utf-8", errors="replace")
        d = json.loads(sp.read_text(encoding="utf-8"))
        tocou = False
        for art in d.get("articles", []):
            anc = art.get("pt_anchor") or ""
            if not anc or anc in t:
                continue
            linha1 = anc.split("\n")[0]
            if t.count(linha1) != 1:
                continue
            j = t.find(linha1)
            k = t.find("\n", j)
            m = k
            while m < len(t) and t[m] == "\n":
                m += 1
            fim = t.find("\n", m)
            nova = t[j:fim if fim > 0 else len(t)][:260].rstrip()
            # só repara o que for claramente o caso do marcador: a âncora agora
            # começa por um rótulo de diálogo
            if not (nova.split("\n")[-1].startswith("Interlocutor:")
                    or nova.split("\n")[-1].startswith("Meishu-Sama:")):
                continue
            if not nova or nova == anc:
                continue
            art["pt_anchor"] = nova
            tocou = True
            mudadas += 1
            print(f"  âncora actualizada: {veic[:42]}: {nova[:64]!r}")
        if tocou:
            d["editor_notes"] = ((d.get("editor_notes") or "") +
                                 " | âncoras PT actualizadas para a convenção "
                                 "de diálogos (Interlocutor/Meishu-Sama)").strip()
            if aplicar:
                shutil.copy2(sp, f"{sp}.bak_convencoes_{ts}")
                sp.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    return mudadas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    total = 0
    falhas = 0

    # ---- corpus ----
    for destino in (PT, LC):
        for path in sorted(destino.glob("*.txt")):
            texto = path.read_text(encoding="utf-8", errors="replace")
            novo = converte(texto)
            if novo == texto:
                continue
            veic = path.stem
            if veic in VEICULOS:
                antes = ancoras_resolvidas(veic, texto)
                depois = ancoras_resolvidas(veic, novo)
                if depois < antes:
                    print(f"  {destino.name}/{path.name}: âncoras {antes} -> "
                          f"{depois} — NÃO aplico")
                    falhas += 1
                    continue
            n = conta(texto)
            if args.aplicar:
                shutil.copy2(path, f"{path}.bak_convencoes_{ts}")
                path.write_text(novo, encoding="utf-8")
            total += n
            print(f"  {destino.name:28} {path.name[:52]:54} {n:>4}"
                  f"  ({len(texto):,} -> {len(novo):,})")

    # ---- itens ----
    n_itens = 0
    for f in sorted(glob.glob(str(ITENS / "*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        t = d.get("texto_pt") or ""
        novo = converte(t)
        if novo == t:
            continue
        n_itens += 1
        if args.aplicar:
            Path(f).with_suffix(".json.bak_convencoes_" + ts).write_text(
                json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            d["texto_pt"] = novo
            d.setdefault("reparos", []).append(
                {"tipo": "convencoes_20261020", "data": ts,
                 "o_que": "御神体=Imagem da Luz Divina; diálogos "
                          "Interlocutor/Meishu-Sama"})
            Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=1),
                               encoding="utf-8")

    # ---- âncoras de spec ----
    mudadas = repara_ancoras(ts, args.aplicar)

    # ---- glossário ----
    if args.aplicar:
        regras_path = RAIZ / "glossario_regras.json"
        r = json.loads(regras_path.read_text(encoding="utf-8"))
        if not any(p.get("proibido_pt") == ["objeto sagrado de culto"]
                   for p in r["proibicoes"]):
            r["proibicoes"].append({
                "gatilho_jp": ["御神体"],
                "gravidade": "erro",
                "motivo": "御神体 = «Imagem da Luz Divina» (glossario_traducao; "
                          "462 ocorrências no acervo). A ronda R5 da auditoria "
                          "dos periódicos impôs «objeto sagrado de culto "
                          "(goshintai)» em 83 lugares, contra o glossário; "
                          "revertido em 20/10/2026 por decisão do usuário.",
                "proibido_pt": ["objeto sagrado de culto",
                                "objetos sagrados de culto"],
            })
        r.setdefault("decisoes_usuario", {})["dialogos"] = (
            "Em diálogos, o padrão é SEMPRE «Interlocutor:» / «Meishu-Sama:» "
            "(decisão de 20/10/2026). Não usar (Pergunta)/(Resposta Divina)/"
            "(Consulta)/(Indagação)/(Revelação Divina)/(Instrução Divina)/"
            "(Orientação).")
        r["versao"] = "2026-10-20"
        shutil.copy2(regras_path, f"{regras_path}.bak_convencoes_{ts}")
        regras_path.write_text(json.dumps(r, ensure_ascii=False, indent=1),
                               encoding="utf-8")
        print(f"\nglossario_regras.json -> versão {r['versao']}")

    print(f"\nsubstituições no corpus: {total}")
    print(f"itens alterados: {n_itens}")
    print(f"âncoras reparadas: {mudadas}")
    if args.aplicar:
        print(f"gravado. backups *.bak_convencoes_{ts}")
    else:
        print("(dry-run — use --aplicar)")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
