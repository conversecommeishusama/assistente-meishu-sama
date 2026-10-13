#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Localiza, nos fac-símiles do acervo, a página de onde cada citação saiu.

Os fac-símiles de `/var/www/rattail/pdf_rattail/` **não têm camada de texto** —
são digitalizações puras. Mas o acervo já mantém um OCR corrido em
`/var/www/rattail/indice/ocr_txt/`, com marcadores `=== p.N ===` de página. O
OCR é ruidoso (kanji trocados, kana perdido) e por isso **não serve para citar**
— mas serve para *localizar a página*, que é o que aqui se quer.

O método: comparar a frase citada com cada página por **subsequência** — isto é,
verificar se os caracteres da frase aparecem na página na mesma ordem, ainda que
com ruído no meio. É robusto aos erros de OCR, que inserem e trocam caracteres.
Vence a página de menor janela relativa; um limite de tolerância evita aceitar
página aleatória, e um score alto é reportado como dúvida em vez de silenciado.

Uso:
    .venv/bin/python scripts/extrair_facsimiles.py             # todos os alvos
    .venv/bin/python scripts/extrair_facsimiles.py eiko191     # um alvo
    .venv/bin/python scripts/extrair_facsimiles.py --listar    # só relatório
"""
import difflib
import os
import re
import subprocess
import sys

ACERVO = "/var/www/rattail/pdf_rattail"
OCRDIR = "/var/www/rattail/indice/ocr_txt"
SAIDA = "/var/www/goshinsho/docs/facsimiles"
TOLERANCIA = 1.9      # janela máxima = len(frase) * este fator
LIMITE_BOM = 1.35     # acima disto, a localização por subsequência é duvidosa
LIMITE_JANELA = 0.48  # similaridade mínima aceitável no método de janela

ALVOS = [
    dict(
        slug="eiko191_aviso_valores",
        pdf="eiko191.pdf",
        frase="御守はじめその他の私のかいたものの値は一定している",
        alt=["盗みの罪を犯す事になる", "少しでも多い金を得る"],
        legenda="『栄光』191号, 14 de janeiro de 1953 — o aviso 「注意」, que fixa o "
                "valor das peças escritas por Meishu-Sama e qualifica como furto a "
                "cobrança acima dele.",
    ),
    dict(
        slug="eiko195_ata_kyoshu",
        pdf="eiko195.pdf",
        frase="どうしても来れないという人は二時間でも結構",
        alt=["教修をさせていただく先生が字を読めない", "二日目から坐った人は"],
        legenda="『栄光』195号, 11 de fevereiro de 1953 — ata da terceira reunião "
                "periódica de difusão, com as regras de duração e de conduta do "
                "Kyoshu.",
    ),
    dict(
        slug="eiko289_suishinden",
        pdf="eiko289_PNG.pdf",
        frase="いよいよ御神業の本スジに入って来た",
        alt=["まごつかないように", "水晶殿御遷座"],
        legenda="『栄光』289号, 1º de janeiro de 1955 — as palavras de Meishu-Sama na "
                "entronização no Palácio de Cristal (水晶殿御遷座), de 11/12/1954.",
    ),
    dict(
        slug="eiko256_norinsyo",
        pdf="eiko256_PNG.pdf",
        frase="自然農法研究会",
        alt=["農林省"],
        legenda="『栄光』256号, 14 de abril de 1954 — notícia da criação do grupo de "
                "estudo de Agricultura Natural no Ministério da Agricultura.",
    ),
    dict(
        slug="suiji29_limite_trinta",
        pdf="suiji_29.pdf",
        frase="三〇ヵ所以上になってはいけない理屈",
        alt=["支部は支部長が主催すべき", "原則としては中教会を"],
        legenda="『御垂示録』29号, 15 de março de 1954 — a resposta de que se deduz o "
                "limite prático de trinta filiais por Igreja Média.",
    ),
    dict(
        slug="suiji15_johrei",
        pdf="suiji_15.pdf",
        frase="急所を先にし従の場所に移って",
        alt=["非常に苦しんでいるとか痛い", "両方必要なのです"],
        legenda="『御垂示録』15号, 1º de novembro de 1952 — a resposta técnica sobre "
                "como ministrar Johrei, com a doutrina dos pontos vitais.",
    ),
    dict(
        slug="honan_shuki_hattan",
        pdf="honan_shuki.pdf",
        frase="昭和二十五年五月八日未明",
        alt=["家宅捜索", "無慮八十名", "青天の霹靂"],
        legenda="『法難手記』, 30 de outubro de 1950 — o capítulo 「発端」, com o relato "
                "da busca domiciliar de 8 de maio de 1950.",
    ),
    dict(
        slug="kyoshu_yoko",
        pdf="kyoshu_yoko.pdf",
        frase="教修要綱",
        alt=["非売品", "世界救世教"],
        pagina_fixa=1,
        legenda="教修要綱, 3ª edição, outubro de 1954 — capa do único manual "
                "curricular do período (fac-símile; o acervo não o tem em texto).",
    ),
    dict(
        slug="jikan02_rotina",
        pdf="jikan_02.pdf",
        frase="自観大先生の御日常",
        alt=["毎七時半御起床", "ラジオのスイッチ"],
        legenda="「自観大先生の御日常」 — o relato de Inoue Motokichi sobre a rotina "
                "diária de Meishu-Sama.",
    ),
]


def norm(s):
    """Remove espaços e normaliza o que o OCR costuma confundir."""
    s = re.sub(r"[\s|｜]+", "", s)
    for a, b in (("．", "。"), (",", "、"), ("・", ""), ("ー", "-"), ("−", "-"),
                 ("ヽ", ""), ("々", "")):
        s = s.replace(a, b)
    return s


def paginas_do_ocr(nome_pdf):
    """Lê o OCR corrido e devolve [(n, texto_normalizado)] por página."""
    arq = os.path.join(OCRDIR, os.path.splitext(nome_pdf)[0] + ".txt")
    if not os.path.exists(arq):
        return []
    txt = open(arq, encoding="utf-8", errors="replace").read()
    partes = re.split(r"===\s*p\.(\d+)\s*===", txt)
    paginas = []
    for k in range(1, len(partes) - 1, 2):
        paginas.append((int(partes[k]), norm(partes[k + 1])))
    return paginas


def janela_subsequencia(frase, texto):
    """Tamanho do menor trecho de `texto` que contém `frase` como subsequência."""
    pos = 0
    ini = None
    for ch in frase:
        j = texto.find(ch, pos)
        if j < 0:
            return None
        if ini is None:
            ini = j
        pos = j + 1
    return pos - ini


def melhor_pagina(paginas, frase, alt):
    """Escolhe a página de menor janela relativa entre a frase e as alternativas."""
    candidatos = [(frase, 1.0)] + [(a, 1.25) for a in alt]
    melhor = None
    for fr, peso in candidatos:
        n = norm(fr)
        if len(n) < 5:
            continue
        for num, txt in paginas:
            jan = janela_subsequencia(n, txt)
            if jan is None or jan > len(n) * TOLERANCIA:
                continue
            score = jan / len(n) * peso
            if melhor is None or score < melhor[0]:
                melhor = (score, num, fr, jan, len(n))
    return melhor


def melhor_pagina_janela(paginas, frase, alt):
    """Segundo critério: maior similaridade entre a frase e uma janela da página.

    Necessário porque as revistas de várias colunas foram OCR'das como se fossem
    de uma só, intercalando linhas de colunas diferentes. Nesse caso a
    subsequência se estica e falha, mas os caracteres da frase ainda se
    concentram numa vizinhança.
    """
    melhor = (0.0, None)
    for fr in [frase] + list(alt):
        n = norm(fr)
        if len(n) < 6:
            continue
        largura = int(len(n) * 2.4)
        passo = max(1, largura // 4)
        for num, txt in paginas:
            if len(txt) < 10:
                continue
            for i in range(0, max(1, len(txt) - largura), passo):
                r = difflib.SequenceMatcher(None, n, txt[i:i + largura]).ratio()
                if r > melhor[0]:
                    melhor = (r, num)
    return melhor if melhor[1] else None


def localizar(paginas, frase, alt):
    """Devolve (pagina, modo, confianca). modo: 'frase', 'janela' ou 'capa'."""
    r = melhor_pagina(paginas, frase, alt)
    if r and r[0] < LIMITE_BOM:
        return r[1], "frase", r[0], r[2]
    r2 = melhor_pagina_janela(paginas, frase, alt)
    if r2 and r2[0] >= LIMITE_JANELA:
        return r2[1], "janela", r2[0], ""
    return 1, "capa", (r[0] if r else 0), ""


def render(pdf, pagina, destino, dpi=150, largura_max=1500):
    """Renderiza a página e reduz para JPEG — o PNG cru de um scan A4 dá ~30 MB."""
    subprocess.run(
        ["pdftoppm", "-r", str(dpi), "-png", "-f", str(pagina), "-l", str(pagina),
         os.path.join(ACERVO, pdf), os.path.join(SAIDA, "_tmp")],
        check=True, capture_output=True)
    gerados = sorted(x for x in os.listdir(SAIDA) if x.startswith("_tmp"))
    if not gerados:
        return None
    bruto = os.path.join(SAIDA, gerados[0])
    try:
        from PIL import Image as _PIL
        with _PIL.open(bruto) as im:
            im = im.convert("L")
            if im.width > largura_max:
                alt = int(im.height * largura_max / im.width)
                im = im.resize((largura_max, alt), _PIL.LANCZOS)
            im.save(destino, "JPEG", quality=82, optimize=True)
        os.remove(bruto)
    except Exception as e:                      # sem PIL, mantém o PNG
        os.replace(bruto, destino)
        print("     (aviso: PIL indisponível, %s)" % e)
    return destino


def ocr_arquivo(caminho):
    """OCR de uma imagem, normalizado — usado para conferir a página extraída."""
    r = subprocess.run(["tesseract", caminho, "-", "-l", "jpn_vert"],
                       capture_output=True, text=True)
    return norm(r.stdout)


def confere(caminho, frase, alt):
    """A página extraída contém de fato o trecho? Confere por OCR próprio.

    Não se confia no palpite que escolheu a página: a própria imagem gerada é
    relida. O teste procura **fragmentos contíguos** da frase (6 caracteres),
    e não a frase inteira como subsequência — o OCR japonês vertical perde e
    troca caracteres, e exigir a frase completa reprovaria páginas corretas.
    Um fragmento de seis kanji não ocorre por acaso.
    """
    txt = ocr_arquivo(caminho)
    for fr in [frase] + list(alt):
        n = norm(fr)
        if len(n) < 6:
            continue
        for i in range(0, len(n) - 6 + 1, 2):
            if n[i:i + 6] in txt:
                return True, n[i:i + 6]
    return False, ""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    so_listar = "--listar" in sys.argv
    filtro = args[0] if args else None
    os.makedirs(SAIDA, exist_ok=True)
    ok = falha = 0
    for a in ALVOS:
        if filtro and filtro not in a["slug"] and filtro not in a["pdf"]:
            continue
        if not os.path.exists(os.path.join(ACERVO, a["pdf"])):
            print(f"[--] {a['slug']:26s} fac-símile ausente: {a['pdf']}")
            falha += 1
            continue
        paginas = paginas_do_ocr(a["pdf"])
        if not paginas:
            print(f"[--] {a['slug']:26s} sem OCR em indice/ocr_txt/")
            falha += 1
            continue
        if a.get("pagina_fixa"):
            num, modo, conf = a["pagina_fixa"], "capa", 0.0
        else:
            num, modo, conf, trecho = localizar(paginas, a["frase"], a.get("alt", []))
        destino = os.path.join(SAIDA, a["slug"] + ".jpg")
        confirmado = None
        if not so_listar:
            render(a["pdf"], num, destino)
            confirmado, achado = confere(destino, a["frase"], a.get("alt", []))
            if not confirmado and modo != "capa":
                # o palpite não se sustentou: volta à capa do caderno
                render(a["pdf"], 1, destino)
                modo, num = "capa", 1
                confirmado, achado = confere(destino, a["frase"], a.get("alt", []))
        if modo == "capa" and confirmado:
            legenda = a["legenda"] + " [Fac-símile: primeira página do número — o " \
                "trecho foi localizado nela por OCR.]"
        elif modo == "capa":
            legenda = a["legenda"] + " [Fac-símile: capa do número. A página do " \
                "artigo não pôde ser localizada com segurança no OCR do acervo.]"
        else:
            legenda = a["legenda"] + " [Página confirmada por OCR do fac-símile.]"
        marca = {"frase": "OK", "janela": "~ ", "capa": "capa"}[modo]
        print(f"[{marca}] {a['slug']:26s} {a['pdf']:17s} p.{num:<4d} "
              f"modo={modo:6s} conf={conf:4.2f} verificada={bool(confirmado)}")
        if not so_listar:
            print(f"     -> docs/facsimiles/{a['slug']}.jpg "
                  f"({os.path.getsize(destino)//1024} KB)")
        ok += 1
    print(f"\n{ok} extraídos/localizados, {falha} falhas")
    for f in list(os.listdir(SAIDA)):
        if f.startswith("_tmp"):
            os.remove(os.path.join(SAIDA, f))


if __name__ == "__main__":
    main()
