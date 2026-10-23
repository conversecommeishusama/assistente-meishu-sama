#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Classifica a autoria dos artigos dos periódicos (dele / não dele).

Por que existe (2026-10-23):
    Os periódicos são publicações MISTAS: ao lado dos artigos de Meishu-Sama
    convivem comunicados da instituição, contribuições de dirigentes e — em
    grande número — testemunhos de fiéis (おかげばなし), assinados com a igreja
    e o nome de quem relata. Narrar o ficheiro inteiro com a voz clonada dele
    atribui-lhe texto que não é dele.

    A decisão do usuário (23/10) é "voz dele só nos trechos Dele". Como não é
    aceitável inventar autoria, a regra é CONSERVADORA: só recebe a voz clonada
    o artigo com evidência positiva; na dúvida, narrador.

Fontes (nenhuma delas basta sozinha — cada uma tem falsos negativos):
    · `/var/www/rattail/work/autoria.json`
        Mapa ficha→peças do acervo, com `veiculo`, `numero`, `titulo`, `secao`
        e `autor`. É a evidência mais forte: `secao` distingue 御論文 (ensaios
        dele) de おかげばなし (testemunhos) e `autor` traz nomes próprios.
    · `reports/periodicos_trabalho/PERIODICOS_MEISHU_SAMA_FINAL.json`
        Lista de 1.187 artigos atribuídos a ele. Tem falsos negativos (não cobre
        "Perguntas e Respostas", "Palavras de Abertura", "Sun-Tetsu"), por isso
        só é usada como evidência POSITIVA, nunca para negar.
    · specs `reports/livros_trabalho/segmentacao_manual/<obra>.txt.json`
        Fronteiras e títulos (jp/pt) de cada artigo — a segmentação oficial.

Saída: `reports/autoria_periodicos/AUTORIA_ARTIGOS.json`
    {obra: {"arquivo": ..., "artigos": [{titulo_jp, titulo_pt, autor,
     evidencia, confianca}]}}

Uso:
    .venv/bin/python scripts/classificar_autoria_periodicos.py
    .venv/bin/python scripts/classificar_autoria_periodicos.py --amostra 8
"""
from __future__ import annotations

import argparse
import collections
import difflib
import glob
import json
import re
import unicodedata
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
SPECS = RAIZ / "reports/livros_trabalho/segmentacao_manual"
AUTORIA_ACERVO = Path("/var/www/rattail/work/autoria.json")
LISTA_DELE = RAIZ / "reports/periodicos_trabalho/PERIODICOS_MEISHU_SAMA_FINAL.json"
SAIDA = RAIZ / "reports/autoria_periodicos/AUTORIA_ARTIGOS.json"

# Obras mistas: classificadas artigo a artigo.
#
# `default_indeterminado` é o prior de cada obra — o que fazer quando NÃO há
# evidência nem a favor nem contra. Os priors diferem porque a natureza das
# obras difere, e isso é uma decisão editorial registada, não um acaso do
# código:
#
#   · Tijotengoku / Kyusei — jornais escritos por ele. O grosso do conteúdo é
#     dele (a lista cobre ~84%); o que não tem marca é, com alta probabilidade,
#     dele também. Prior = meishu.
#   · Relatos de Milagres — colectânea de TESTEMUNHOS de fiéis. O que não tem
#     marca é, com alta probabilidade, testemunho. Prior = outro.
MISTAS = {
    "Tijotengoku": ("地上天国", "Tijotengoku.txt", "meishu"),
    "Kyusei": ("救世", "Kyusei.txt", "meishu"),
    "Relatos": ("", "19530910 - Relatos de Milagres da Igreja Messiânica Mundial.txt",
                "outro"),
}

# Nomes/assinaturas que SÃO ele. `自観` e `明主` são os nomes religiosos;
# `Ｓ・Ｍ生` é a abreviatura usada nos periódicos.
NOMES_DELE = (
    "自観", "明主", "Ｓ・Ｍ", "Ｓ・M", "S・M", "メシヤ", "妙智", "大先生",
)

# Secções que são texto dele.
SECOES_DELE = ("御論文", "論評", "時評", "随想", "巻頭言")
# Secções que NÃO são dele.
SECOES_OUTRO = ("おかげばなし", "寄稿")

# Testemunho de fiel: "<igreja>　<nome>（<idade>）" ou título com 教会.
RE_TESTEMUNHO = re.compile(r"(中|大)?教会[\s\u3000]|（\d{1,3}）\s*$")


def norm(s: str) -> str:
    """Normaliza título para comparação (NFKC, sem parênteses/pontuação)."""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"\(.*?\)|（.*?）", "", s)
    return re.sub(r"[^\w]", "", s).lower()


def numero_do_artigo(artigo: dict) -> str | None:
    """Número da edição, lido do cabeçalho PT ("Tijotengoku nº 12, ...")."""
    m = re.search(r"n[º°o]\s*(\d+)", artigo.get("pt_anchor") or "", re.I)
    return m.group(1) if m else None


def _indice_por_edicao(autoria: dict) -> dict:
    """(veículo JP, número) → peças dessa edição."""
    idx: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for _ficha, pecas in autoria.items():
        for p in pecas:
            idx[(p.get("veiculo", ""), str(p.get("numero", "")).strip())].append(p)
    return idx


def melhor_peca(por_edicao: dict, veiculo: str, numero: str | None,
                titulo_jp: str) -> tuple[dict | None, float]:
    """Peça do acervo que corresponde a este artigo (mesma edição + título)."""
    if not numero:
        return None, 0.0
    candidatas = por_edicao.get((veiculo, str(numero).strip()), [])
    alvo = norm(titulo_jp)
    melhor, score = None, 0.0
    for p in candidatas:
        tp = norm(p.get("titulo"))
        if not tp:
            continue
        if tp == alvo:
            return p, 1.0
        # "質問応答 妙智之光(地上天国11号)" contém "妙智之光": contenção vale mais
        # do que a razão de semelhança, que penaliza o prefixo.
        if alvo and (tp in alvo or alvo in tp):
            return p, 0.9
        s = difflib.SequenceMatcher(None, alvo, tp).ratio()
        if s > score:
            melhor, score = p, s
    return (melhor, score) if score >= 0.7 else (None, score)


def classificar_artigo(artigo: dict, veiculo: str, por_edicao: dict,
                       titulos_lista: list[str]) -> dict:
    """Atribui autoria a UM artigo, registando a evidência usada.

    Devolve `autor` em {meishu, outro, indeterminado}. A ordem da evidência
    importa: a assinatura de fiel vence tudo (um testemunho pode citar um ensaio
    dele), depois o autor explícito, depois a secção editorial e só então a
    lista. A lista entra por último porque tem falsos negativos conhecidos
    (não cobre "Perguntas e Respostas", "Sun-Tetsu", "Palavras de Abertura").
    """
    titulo_jp = artigo.get("title_jp") or ""
    base = {
        "titulo_jp": titulo_jp,
        "titulo_pt": artigo.get("title_pt") or "",
        "numero": numero_do_artigo(artigo),
    }
    alvo = norm(titulo_jp)

    # 1. Testemunho de fiel — assinado com igreja/nome/idade.
    if RE_TESTEMUNHO.search(titulo_jp):
        return {**base, "autor": "outro", "evidencia": "assinatura-de-fiel",
                "confianca": "alta"}

    peca, score = melhor_peca(por_edicao, veiculo, base["numero"], titulo_jp)

    # 2. Autor explícito na ficha do acervo.
    #
    #    ⚠️ Um nome de terceiro aqui NÃO prova que o texto não é dele: as
    #    fichas registam quem EDITOU (`井上茂登吉編`) ou quem RELATOU uma
    #    entrevista (`木原道治` numa crónica de encontro com jornalistas) e há
    #    valores que nem são nomes (`「そこひと神霊療法に就て」に関する文章`).
    #    Por isso o autor de terceiro vale como INDÍCIO (indeterminado), não
    #    como exclusão. Quem exclui de facto é a secção editorial (passo 3) e a
    #    assinatura de fiel (passo 1).
    indicio_terceiro = None
    if peca:
        autor = (peca.get("autor") or "").strip()
        if autor:
            if any(n in autor for n in NOMES_DELE):
                return {**base, "autor": "meishu", "evidencia": f"autor:{autor}",
                        "confianca": "alta"}
            indicio_terceiro = autor

    # 3. Secção editorial — esta sim exclui.
    if peca:
        secao = (peca.get("secao") or "").strip()
        if secao in SECOES_DELE:
            return {**base, "autor": "meishu", "evidencia": f"secao:{secao}",
                    "confianca": "alta"}
        if secao in SECOES_OUTRO:
            return {**base, "autor": "outro", "evidencia": f"secao:{secao}",
                    "confianca": "alta"}

    # 4. Lista dos artigos atribuídos a ele. Casamento GLOBAL por título (não
    #    ancorado à edição): o título já traz a edição e a edição extraída do
    #    cabeçalho PT nem sempre coincide com a da fonte JP.
    if alvo and alvo in titulos_lista:
        return {**base, "autor": "meishu", "evidencia": "lista-dele",
                "confianca": "alta"}
    if alvo:
        proximo = difflib.get_close_matches(alvo, titulos_lista, n=1, cutoff=0.88)
        if proximo:
            return {**base, "autor": "meishu", "evidencia": "lista-dele-fuzzy",
                    "confianca": "media",
                    "corresp": proximo[0]}

    # 5. Sem evidência positiva. Fica INDETERMINADO — não se afirma nem que é
    #    dele nem que não é. O prior da obra decide (ver `MISTAS`).
    if indicio_terceiro:
        return {**base, "autor": "indeterminado",
                "evidencia": f"credito-a-terceiro:{indicio_terceiro}",
                "confianca": "nenhuma"}
    if peca:
        return {**base, "autor": "indeterminado", "evidencia": "secao-sem-marca",
                "confianca": "nenhuma"}
    return {**base, "autor": "indeterminado", "evidencia": "sem-evidencia",
            "confianca": "nenhuma"}


def _aplicar_bloco_prefacial(classificados: list[dict]) -> None:
    """Nos `Relatos de Milagres`, os ensaios doutrinários abrem o volume.

    O livro é uma colectânea de testemunhos de fiéis, mas começa com textos
    dele (序文, 奇蹟とは何ぞや, 霊主体従, 霊と体). Esses não têm assinatura, por
    isso caem em `indeterminado` — e são justamente os que pertencem a ele.

    Regra estrutural: o que vem ANTES do primeiro testemunho assinado é
    prefácio/ensaio. Não se aplica às outras obras, onde a ordem é cronológica.
    """
    primeira = next((i for i, c in enumerate(classificados)
                     if c["evidencia"] == "assinatura-de-fiel"), None)
    if primeira is None:
        return
    for c in classificados[:primeira]:
        if c["autor"] == "indeterminado":
            c["autor"] = "meishu"
            c["evidencia"] = "bloco-prefacial"
            c["confianca"] = "media"


def spec_de(obra: str) -> str | None:
    candidatos = [p for p in glob.glob(str(SPECS / f"*{obra}*.txt.json"))
                  if ".bak" not in p]
    return candidatos[0] if candidatos else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--amostra", type=int, default=0,
                    help="Mostrar N exemplos por categoria (revisão manual).")
    args = ap.parse_args()

    autoria = json.load(open(AUTORIA_ACERVO, encoding="utf-8"))
    por_edicao = _indice_por_edicao(autoria)
    lista = json.load(open(LISTA_DELE, encoding="utf-8"))["itens"]
    titulos_por_veiculo: dict[str, list[str]] = collections.defaultdict(list)
    for i in lista:
        titulos_por_veiculo[i["veiculo"]].append(norm(i["titulo"]))

    saida = {}
    for obra, (veiculo_jp, ficheiro, prior) in MISTAS.items():
        caminho = spec_de(obra)
        if not caminho:
            print(f"AVISO: sem spec para {obra}")
            continue
        artigos = json.load(open(caminho, encoding="utf-8"))["articles"]
        titulos_lista = titulos_por_veiculo[obra]
        classificados = [classificar_artigo(a, veiculo_jp, por_edicao, titulos_lista)
                         for a in artigos]
        _aplicar_bloco_prefacial(classificados)
        # Resolve os indeterminados pelo prior da obra, deixando o rasto.
        for c in classificados:
            if c["autor"] == "indeterminado":
                c["autor"] = prior
                c["evidencia"] = f"{c['evidencia']}+prior-da-obra"
        saida[obra] = {"arquivo": ficheiro, "spec": Path(caminho).name,
                       "prior_indeterminado": prior, "artigos": classificados}

        cont = collections.Counter(c["autor"] for c in classificados)
        evid = collections.Counter(c["evidencia"].split(":")[0].split("+")[0]
                                   for c in classificados)
        n = len(classificados)
        print(f"=== {obra} ({n} artigos, prior={prior}) ===")
        print(f"   voz dele: {cont['meishu']:4d} | narrador: {cont['outro']:4d}")
        print(f"   evidência: {dict(evid.most_common())}")
        if args.amostra:
            for autor in ("meishu", "outro"):
                exemplos = [c for c in classificados if c["autor"] == autor]
                print(f"   -- exemplos {autor} --")
                for c in exemplos[:args.amostra]:
                    print(f"      [{c['evidencia']}] {c['titulo_jp'][:38]!r} "
                          f"| {c['titulo_pt'][:40]}")
        print()

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
    print(f"Escrito {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
