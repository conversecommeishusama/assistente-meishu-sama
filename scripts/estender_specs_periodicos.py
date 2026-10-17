#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estende as specs dos 4 periódicos com os artigos anexados em 09–15/Out.

**O problema.** Os 415 artigos traduzidos e os 416 em japonês entraram nos
ficheiros de trabalho, mas as specs continuaram com N artigos. O rebuild exige
que as âncoras resolvam em ordem; o excedente cai dentro do último chunk. Com
`periodico_publicacao` (nunca corta por tamanho) e o e5-large a truncar a 512
tokens, ~2,14 M caracteres ficariam invisíveis na busca.

**Método (uniforme para PT e JP).**

1. Localiza cada artigo — antigo (pela âncora) e novo (pelo título).
2. Corta o ficheiro **inteiro** nos pontos encontrados; cada bloco é um recorte
   literal. Os blocos antigos mantêm a ordem; os novos vão para o fim, na ordem
   canónica `(ano, numero inteiro, ordem)` do registo de tradução.
3. Os dois artigos órfãos (`a_revisar`, nunca traduzidos) entram a partir de
   `reports/traducao_periodicos/orfas/`.
4. Acrescenta os artigos novos ao fim de `articles` da spec.

**Garantias** — o script recusa-se a gravar se algo disto falhar:

* round-trip: juntar os blocos na ordem original reproduz o ficheiro;
* o texto antigo, reconstruído, continua a segmentar em `len(articles)` chunks
  com as âncoras antigas (nenhum artigo antigo partido ou perdido);
* o texto novo segmenta em `len(novos)` chunks com as âncoras novas.

Backup de tudo antes de escrever.

Uso:
    .venv/bin/python scripts/estender_specs_periodicos.py            # dry-run
    .venv/bin/python scripts/estender_specs_periodicos.py --aplicar
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

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402
from completar_jp_periodicos import extrai as extrai_jp, flui as flui_jp  # noqa: E402

PT = RAIZ / "textos_portugues"
JP = RAIZ / "textos_japones"
SPECS = RAIZ / "reports" / "livros_trabalho" / "segmentacao_manual"
ITENS = RAIZ / "reports" / "traducao_periodicos" / "itens"
ORFAS = RAIZ / "reports" / "traducao_periodicos" / "orfas"

VEICULOS = ["Tijotengoku", "Eiko", "Hikari", "Kyusei"]

# Os dois órfãos: `a_revisar` no registo, ficaram fora dos 415 traduzidos.
# A `ordem` põe cada um imediatamente depois do vizinho anterior.
ORFAOS = [
    {"veiculo": "Kyusei", "numero": "62", "ano": 1950, "ordem": 322.5,
     "titulo_jp": "盲目は治る",
     "titulo_pt": "A Cegueira Pode Ser Curada",
     "arquivo": "textos_rattail/estruturado/search1/mo/momoku2.html",
     "pt": ORFAS / "kyusei62_盲目は治る.txt"},
    {"veiculo": "Tijotengoku", "numero": "15", "ano": 1950, "ordem": 31.5,
     "titulo_jp": "質問応答 妙智之光(地上天国15号)",
     "titulo_pt": "Perguntas e Respostas — A Luz da Sabedoria Maravilhosa "
                 "[Paraíso Terrestre nº 15]",
     "arquivo": "textos_rattail/estruturado/search1/situmon/situmo19.html",
     "pt": ORFAS / "tijotengoku15_妙智之光.txt"},
]

# Artigo cujo bloco JP não existe no ficheiro: a página de origem do acervo traz
# um `<title>` errado (`巻頭言(地上天国27号)`), o título colidiu com o do nº 27 e
# o `completar_jp_periodicos.py` pulou-o como duplicado — o texto nunca entrou no
# corpus JP, embora o PT tenha sido traduzido. O bloco é gerado da fonte, com o
# título corrigido pela linha de referência do próprio documento
# (「巻頭言 (地上天国28号)」 / 『地上天国』28号).
JP_GERAR = {
    "textos_rattail/estruturado/search1/ka/kantou28.html": {
        "titulo_jp": "巻頭言(地上天国28号)",
    },
}

# Títulos PT que ficaram no ficheiro diferentes do `titulo_pt` do registo. São 4,
# todos verificados: 3 porque a tradução que ficou no corpus tinha o título
# antigo/errado (ex.: nº 55 da Kyusei está como «Eikō nº 55»), 1 pelo mesmo
# motivo sem troca de veículo. A busca pelo título do registo falha nesses casos.
PT_TITULO_REAL = {
    "textos_rattail/estruturado/search1/me/meisyu3.html":
        'Meishu-Sama fala sobre "A Importância do Havaí"',
    "textos_rattail/estruturado/search1/yo/yomiuri1.html":
        'Requerendo Reflexão do "Yomiuri"',
    "textos_rattail/estruturado/search1/o/okage09.html":
        'Crítica de "Okágebana" (Eikō nº 55)',
    "textos_rattail/estruturado/search1/jo/jorei23.html":
        'A Veracidade do Johrei e a Crítica à "Graça"',
}

# Defeito de escrita herdado: 3 títulos ficaram com a aspa final repetida 8×.
# Só existe nestes 3 sítios (verificado em todo o corpus PT), sempre em fim de
# linha de título, portanto a normalização é segura e verificada.
ASPAS_REPETIDAS = re.compile(r'"{4,}')


def num_int(v) -> int:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return 0


def titulo_limpo(t: str) -> str:
    return re.split(r"\n+", (t or "").strip(), maxsplit=1)[0].strip()


def ancora_de(bloco: str) -> str:
    """Âncora = título + linha de referência (convenção do acervo).

    O separador é o que existe mesmo no bloco: os artigos do acervo têm
    `título\nreferência\n\ncorpo`, mas há blocos sem linha de referência, em que
    a linha seguinte é já corpo e vem depois de uma linha em branco. Inventar o
    separador parte a âncora.
    """
    b = bloco.strip("\n")
    if not b:
        return ""
    m = re.match(r"([^\n]+)(\n+)([^\n]+)", b)
    if not m:
        return b.split("\n")[0].strip()
    titulo = m.group(1).strip()
    cand = titulo + m.group(2) + m.group(3).strip()
    return cand if len(cand) <= 260 else titulo


def carrega_itens() -> list[dict]:
    out = []
    for f in sorted(glob.glob(str(ITENS / "*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        d["_origem"] = "traducao"
        out.append(d)
    return out


def inicios_de_bloco(texto: str, titulo: str) -> list[int]:
    """Posições onde `titulo` começa um bloco (após '\\n\\n', ou na posição 0)."""
    if not titulo:
        return []
    out = []
    alvo = "\n\n" + titulo
    p = texto.find(alvo)
    while p >= 0:
        fim = p + 2 + len(titulo)
        # o título tem de ser a linha inteira: sem isto «結核新薬» casaria
        # também «結核新薬をわらう»
        if fim >= len(texto) or texto[fim] == "\n":
            out.append(p + 2)
        p = texto.find(alvo, p + 1)
    if texto.startswith(titulo):
        fim = len(titulo)
        if fim >= len(texto) or texto[fim] == "\n":
            out.insert(0, 0)
    return out


def resolve_pt(texto: str, item: dict) -> int:
    t = titulo_limpo(item.get("titulo_pt"))
    fonte = (item.get("fonte_pt") or "").strip()
    cands = [f"{t}\n\n{fonte}", t]
    real = PT_TITULO_REAL.get(item["arquivo"])
    if real:
        cands += [f"{real}\n\n{fonte}", real]
    for cand in cands:
        if cand:
            p = inicios_de_bloco(texto, cand)
            if p:
                return p[0]
    return -1


def resolve_jp(texto: str, item: dict) -> int:
    p = inicios_de_bloco(texto, item["titulo_jp"])
    return p[0] if p else -1


def corta(texto: str, pontos: list[int]) -> dict[int, str]:
    """Blocos do texto nos `pontos` (ordenados, a começar em 0)."""
    if not pontos or pontos[0] != 0:
        raise SystemExit("partição inválida: o 1º ponto não é 0")
    if pontos != sorted(set(pontos)):
        raise SystemExit("partição inválida: pontos repetidos ou fora de ordem")
    fins = pontos[1:] + [len(texto)]
    return {p: texto[p:f] for p, f in zip(pontos, fins)}


def separa(bloco: str) -> str:
    return bloco.rstrip("\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    itens = carrega_itens()
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    for veic in VEICULOS:
        pt = clean_body((PT / f"{veic}.txt").read_text(encoding="utf-8", errors="replace"))
        jp = clean_body((JP / f"{veic}.txt").read_text(encoding="utf-8", errors="replace"))
        # aspa final repetida 8× em 3 títulos (defeito herdado, ver constante)
        if ASPAS_REPETIDAS.search(pt):
            print(f"{veic:13} ! normaliza {len(ASPAS_REPETIDAS.findall(pt))} "
                  "título(s) com aspas repetidas")
            pt = ASPAS_REPETIDAS.sub('"', pt)
        spec_path = SPECS / f"{veic}.txt.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        antigos = spec["articles"]
        n_old = len(antigos)

        # --- registo canónico ------------------------------------------------
        reg = [i for i in itens if i["veiculo"] == veic]
        reg += [dict(o, _origem="orfa") for o in ORFAOS if o["veiculo"] == veic]
        for i in reg:
            g = JP_GERAR.get(i["arquivo"])
            if g:
                i["titulo_jp_original"] = i["titulo_jp"]
                i["titulo_jp"] = g["titulo_jp"]
        reg.sort(key=lambda i: (i.get("ano") or 0, num_int(i.get("numero")),
                                float(i.get("ordem") or 0)))

        # --- âncoras antigas têm de resolver e estar em ordem ----------------
        pos_old_pt = [pt.find(a["pt_anchor"]) for a in antigos]
        pos_old_jp = [jp.find(a["jp_anchor"]) for a in antigos]
        for rot, pos in (("PT", pos_old_pt), ("JP", pos_old_jp)):
            if any(p < 0 for p in pos):
                maus = [antigos[k]["title_jp"] for k, p in enumerate(pos) if p < 0]
                raise SystemExit(f"{veic}/{rot}: âncoras antigas não resolvem: {maus[:3]}")
            if pos != sorted(pos):
                raise SystemExit(f"{veic}/{rot}: âncoras antigas fora de ordem")
            if pos[0] != 0:
                raise SystemExit(f"{veic}/{rot}: o 1º artigo antigo não está na posição 0")

        # --- artigos novos; descarta os que já são artigos antigos -----------
        dup, pos_new_pt, pos_new_jp, descartados = [], {}, {}, set()
        for i in reg:
            pp, pj = resolve_pt(pt, i), resolve_jp(jp, i)
            if pp in pos_old_pt and pj in pos_old_jp:
                # o mesmo artigo já está na lista como artigo antigo
                dup.append(i["titulo_jp"])
                descartados.add(i["arquivo"])
                pos_new_pt[i["arquivo"]] = pos_new_jp[i["arquivo"]] = -1
                continue
            pos_new_pt[i["arquivo"]] = pp
            pos_new_jp[i["arquivo"]] = pj

        # duas entradas no mesmo bloco destroem a partição (bloco repetido)
        for rot, pos in (("PT", pos_new_pt), ("JP", pos_new_jp)):
            vistos = {}
            for i in reg:
                p = pos[i["arquivo"]]
                if p < 0:
                    continue
                if p in vistos:
                    raise SystemExit(f"{veic}/{rot}: {i['titulo_jp']} e "
                                     f"{vistos[p]} caem no mesmo bloco ({p})")
                vistos[p] = i["titulo_jp"]

        reg = [i for i in reg if i["arquivo"] not in descartados]
        faltam = [i["titulo_jp"] for i in reg
                  if (pos_new_pt[i["arquivo"]] < 0 and i.get("pt") is None)
                  or (pos_new_jp[i["arquivo"]] < 0
                      and i["arquivo"] not in JP_GERAR)]

        # --- blocos ----------------------------------------------------------
        blc_pt = corta(pt, sorted(set(pos_old_pt) |
                                  {p for p in pos_new_pt.values() if p >= 0}))
        blc_jp = corta(jp, sorted(set(pos_old_jp) |
                                  {p for p in pos_new_jp.values() if p >= 0}))

        # integridade da partição: nenhum byte do ficheiro fica de fora
        for rot, texto, blc in (("PT", pt, blc_pt), ("JP", jp, blc_jp)):
            if "".join(blc[p] for p in sorted(blc)) != texto:
                raise SystemExit(f"{veic}/{rot}: partição inválida — não gravo")

        # --- artigos novos dentro da região antiga (deslocados) --------------
        # Ex.: Eiko nº 252. O bloco existe no meio dos antigos, mas é um artigo
        # novo: sai da parte antiga e vai para a região anexada.
        movidos = [i["titulo_jp"] for i in reg
                   if (0 <= pos_new_pt[i["arquivo"]] < pos_old_pt[-1])
                   or (0 <= pos_new_jp[i["arquivo"]] < pos_old_jp[-1])]

        # --- blocos novos: (item, bloco_pt, bloco_jp) ------------------------
        blocos_novos = []
        for i in reg:
            bp = blc_pt.get(pos_new_pt[i["arquivo"]], "")
            bj = blc_jp.get(pos_new_jp[i["arquivo"]], "")
            # órfãos: o bloco PT não está no ficheiro — vem da tradução nova
            if not bp and i.get("pt") is not None:
                bp = clean_body(Path(i["pt"]).read_text(encoding="utf-8"))
                print(f"{veic:13} + bloco PT novo (órfão): {i['titulo_jp']} "
                      f"({len(bp):,} chars)")
            if not bj:
                ref, paras = extrai_jp(i["arquivo"])
                bj = (f"{i['titulo_jp']}\n{ref}\n\n"
                      + "\n\n".join(flui_jp(p) for p in paras))
                print(f"{veic:13} + bloco JP gerado da fonte: {i['titulo_jp']}")
            if not bp:
                raise SystemExit(f"{veic}: bloco PT ausente para {i['titulo_jp']}")
            blocos_novos.append((i, bp, bj))

        # --- reconstrução ----------------------------------------------------
        velhos_pt = "\n\n".join(separa(blc_pt[p]) for p in pos_old_pt)
        velhos_jp = "\n\n".join(separa(blc_jp[p]) for p in pos_old_jp)
        novos_pt = "\n\n".join(separa(bp) for _, bp, _ in blocos_novos)
        novos_jp = "\n\n".join(separa(bj) for _, _, bj in blocos_novos)

        # cobertura: os textos velho+novo têm de conter todo o original, a menos
        # do branco normalizado e do artigo descartado por já ser artigo antigo
        for rot, texto, velhos, novos in (("PT", pt, velhos_pt, novos_pt),
                                         ("JP", jp, velhos_jp, novos_jp)):
            delta = len(texto) - len(velhos) - len(novos)
            print(f"{veic:13}   {rot}: original={len(texto):,} "
                  f"antigos={len(velhos):,} novos={len(novos):,} delta={delta:,}")
            if delta > 5000:
                raise SystemExit(f"{veic}/{rot}: delta {delta:,} — conteúdo "
                                 "em falta, não gravo")

        # --- validação dura --------------------------------------------------
        for rot, velhos, anc in (("PT", velhos_pt, [a["pt_anchor"] for a in antigos]),
                                 ("JP", velhos_jp, [a["jp_anchor"] for a in antigos])):
            try:
                c = split_by_anchors(velhos, anc, label=f"{veic}/{rot}-antigos")
            except ValueError as exc:
                raise SystemExit(f"{veic}/{rot}: antigos não segmentam: {exc}")
            if len(c) != n_old:
                raise SystemExit(f"{veic}/{rot}: {len(c)} chunks != {n_old} antigos")

        # blocos novos: (item, bloco_pt, bloco_jp)
        if blocos_novos:
            for rot, txt, anc in (
                    ("PT", novos_pt, [ancora_de(bp) for _, bp, _ in blocos_novos]),
                    ("JP", novos_jp, [ancora_de(bj) for _, _, bj in blocos_novos])):
                try:
                    c = split_by_anchors(txt, anc, label=f"{veic}/{rot}-novos")
                except ValueError as exc:
                    raise SystemExit(f"{veic}/{rot}: novos não segmentam: {exc}")
                if len(c) != len(blocos_novos):
                    raise SystemExit(f"{veic}/{rot}: {len(c)} chunks != "
                                     f"{len(blocos_novos)} novos")

        print(f"{veic:13} antigos={n_old:3} novos={len(blocos_novos):3} "
              f"total={n_old + len(blocos_novos):3}"
              + (f" | duplicados descartados={len(dup)}" if dup else "")
              + (f" | deslocados={len(movidos)}" if movidos else "")
              + (f" | EM FALTA={len(faltam)} {faltam[:2]}" if faltam else ""))

        if not args.aplicar:
            continue

        # --- grava ------------------------------------------------------------
        texto_pt = velhos_pt + ("\n\n" + novos_pt if novos_pt else "")
        texto_jp = velhos_jp + ("\n\n" + novos_jp if novos_jp else "")
        for p, txt in ((PT / f"{veic}.txt", texto_pt + "\n"),
                       (JP / f"{veic}.txt", texto_jp + "\n")):
            shutil.copy2(p, f"{p}.bak_extensao_spec_{ts}")
            p.write_text(txt, encoding="utf-8")

        novos = []
        for i, bp, bj in blocos_novos:
            novos.append({
                "kind": "article",
                "title_jp": i["titulo_jp"],
                "title_pt": titulo_limpo(i.get("titulo_pt") or i["titulo_jp"]),
                "jp_anchor": ancora_de(bj),
                "pt_anchor": ancora_de(bp),
                "notes": f"sort_date={i.get('ano')}-{i.get('numero')} "
                         f"origem={i['_origem']}",
            })
        spec["articles"] = antigos + novos
        spec["previous_article_count"] = n_old
        spec["editor_notes"] = ((spec.get("editor_notes") or "")
                                + f" | {ts}: +{len(novos)} artigos (região anexada "
                                  "reordenada para (ano,numero,ordem); inclui os "
                                  "órfãos 盲目は治る e 妙智之光 nº15 e o bloco JP de "
                                  "巻頭言28号 gerado da fonte)").strip()
        shutil.copy2(spec_path, f"{spec_path}.bak_extensao_{ts}")
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=1),
                             encoding="utf-8")

    if not args.aplicar:
        print("\n(dry-run — use --aplicar para gravar)")
    else:
        print(f"\ngravado. backups: *.bak_extensao_spec_{ts} (textos), "
              f"*.bak_extensao_{ts} (specs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
