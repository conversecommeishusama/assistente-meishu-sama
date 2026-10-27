#!/usr/bin/env python3
"""Audita o volume contra o glossário de tradução.

Por omissão audita **o volume montado** (`docs/DOSSIE_DIFUSAO_20261020.md`), não
as fontes. A razão é de calibração, não de gosto: o `glosar()` do montador insere
a glosa automaticamente na montagem, e o que se quer medir é o defeito **visível
pelo leitor no volume** — não a ausência de glosa na fonte, que a montagem supre.
Medido nas fontes, o verificador superestima (24/10/2026: 127 achados, quase todos
falsos positivos). Medido no volume, mede o que resta.

Três verificações independentes:

  A. TERMO SEM GLOSA — primeira ocorrência de um termo do glossário, em prosa,
     sem a tradução correspondente na vizinhança. A glosa tanto vale depois do
     termo ("御神体 (Imagem da Luz Divina)") quanto antes ("**Imagem da Luz
     Divina** (御神体)") — as duas formas são usadas no volume.

  B. GLOSA DIVERGENTE — o termo vem seguido de parêntese com tradução em
     português que não é a do glossário.

  C. PROIBIÇÃO VIOLADA — forma portuguesa proibida por `glossario_regras.json`
     quando o gatilho japonês corresponde. Endereços romanizados (`Shizuoka-ken`,
     `Tosu-chō`), nomes próprios e as tabelas de romaji do próprio glossário não
     contam: ali o ken/chō/ri não é medida.

  D. CAMINHO DO ACERVO — nome de ficheiro do acervo (`bunkai04.html`,
     `search1/...`) que vazou para o corpo do volume. A regra editorial manda
     citar veículo, número e data, nunca o caminho. Os nomes aparecem entre
     crases, e é por aí que se detectam.

Uso:
    python3 scripts/auditar_glossario_volume.py
    python3 scripts/auditar_glossario_volume.py --detalhar
    python3 scripts/auditar_glossario_volume.py --fontes
    python3 scripts/auditar_glossario_volume.py --arquivo docs/volume_novo/06_grade1948.md

Saída: relatório em reports/auditoria_glossario_volume.json e resumo na tela.
"""
import json
import os
import re
import sys
import unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(BASE, "..")
DOCS = os.path.join(RAIZ, "docs")
SAIDA = os.path.join(RAIZ, "reports", "auditoria_glossario_volume.json")

FONTES = [
    os.path.join(DOCS, "LEVANTAMENTO_DIFUSAO_PARTE_I_PROSA_20261002.md"),
    os.path.join(DOCS, "DOSSIE_PARTE_II_CULTO_E_VIDA_20261002.md"),
    os.path.join(DOCS, "DOSSIE_PARTE_III_DOUTRINA_ECONOMIA_E_HIERARQUIA_20261013.md"),
]
NOVO = os.path.join(DOCS, "volume_novo")
VOLUME = os.path.join(DOCS, "DOSSIE_DIFUSAO_20261020.md")

CJK = r"\u3040-\u30ff\u4e00-\u9fff"
KANJI = r"\u4e00-\u9fff"

# Anexos cuja revisão já foi feita e encerrada (decisão do autor, 23/10/2026):
# audita-se para registro, mas os achados não entram na contagem de pendências.
REVISAO_ENCERRADA = {"47_anexo_kyoshu_yoko.md"}


def blocos_de_codigo(texto):
    """Intervalos de linhas (1-based) ocupados por blocos ``` ... ```."""
    faixas, dentro, ini = [], False, 0
    for n, l in enumerate(texto.split("\n"), 1):
        if l.lstrip().startswith("```"):
            if dentro:
                faixas.append((ini, n))
                dentro = False
            else:
                dentro, ini = True, n
    if dentro:
        faixas.append((ini, texto.count("\n") + 1))
    return faixas


def em_citacao(texto, pos):
    """O termo está dentro de 「…」 ou 『…』?

    O `glosar()` do montador protege os trechos entre 「」 e 『』: ali nenhuma
    glosa é inserida, por decisão editorial. Cobrar glosa dentro de citação é,
    portanto, falso positivo por construção. O que se mede aqui é a glosa em
    prosa corrente.
    """
    for abre, fecha in (("「", "」"), ("『", "』")):
        a = texto.rfind(abre, 0, pos)
        if a < 0:
            continue
        if texto.rfind(fecha, 0, pos) > a:
            continue
        if texto.find(fecha, pos) >= 0:
            return True
    return False


def em_composto(texto, ini, fim):
    """O termo é parte de uma palavra japonesa maior?

    御神体 em 御神体代り, 天国 em 地上天国, 神霊 em 代理神霊: a glosa que
    interessa é a do composto, não a da parte. Sem esta regra o verificador
    cobrava glosa de fragmentos.
    """
    antes = texto[ini - 1] if ini > 0 else ""
    depois = texto[fim] if fim < len(texto) else ""
    return bool(re.match("[" + KANJI + "]", antes or " ")) or \
        bool(re.match("[" + KANJI + "]", depois or " "))


def em_italico_inline(linha, rel):
    """O termo está entre crases na linha?"""
    return linha[:rel].count("`") % 2 == 1


def em_titulo_glosado(texto, pos):
    """O termo está dentro de 『…』 seguido de tradução entre parênteses?"""
    abre = texto.rfind("『", 0, pos)
    if abre < 0:
        return False
    if texto.rfind("』", 0, pos) > abre:
        return False            # o 『 anterior já foi fechado
    fecha = texto.find("』", pos)
    if fecha < 0:
        return False
    m = re.match(r"\s*[（(]([^）)\n]{2,80})[）)]", texto[fecha + 1:fecha + 90])
    return bool(m and re.search(r"[A-Za-zÀ-ÿ]{4,}", m.group(1)))


def normalizar(s):
    """Compara sem acento, sem caixa e sem pontuação — 'Kōmyō' == 'Komyo'."""
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("ō", "o").replace("ū", "u").replace("ā", "a")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def carregar_glossario():
    """(jp, pt, principal) das entradas que servem de regra de superfície.

    O 'principal' é o primeiro segmento antes do travessão, sem parênteses: é o
    que se espera encontrar no texto. Entradas cujo PT é só explicação, sem
    forma curta utilizável, ficam de fora.
    """
    bruto = json.load(open(os.path.join(RAIZ, "glossario_traducao.json"),
                           encoding="utf-8"))
    regras = []
    for jp, pt in bruto.items():
        if not isinstance(pt, str):
            continue
        principal = pt.split("—")[0].strip()
        principal = re.sub(r"\([^)]*\)", "", principal).strip(" .,;")
        if not principal or len(principal) > 70:
            continue
        regras.append((jp, pt, principal))
    return regras


def carregar_proibicoes():
    d = json.load(open(os.path.join(RAIZ, "glossario_regras.json"),
                       encoding="utf-8"))
    saida = []
    for p in d.get("proibicoes", []):
        gat = [g for g in p.get("gatilho_jp", []) if g]
        pro = [x for x in p.get("proibido_pt", []) if x]
        if pro:
            saida.append({"gatilho": gat, "proibido": pro,
                          "motivo": p.get("motivo", ""),
                          "gravidade": p.get("gravidade", "")})
    vistos, unicos = set(), []
    for p in saida:
        chave = (tuple(p["gatilho"]), tuple(p["proibido"]))
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(p)
    return unicos


def arquivos(origem="volume"):
    """Arquivos a auditar.

    ``volume`` (omissão): o volume montado — mede o que o leitor vê.
    ``fontes``: as três partes + ``docs/volume_novo/*.md`` — mede o insumo.
    """
    if origem == "fontes":
        lista = [f for f in FONTES if os.path.exists(f)]
        if os.path.isdir(NOVO):
            for nome in sorted(os.listdir(NOVO)):
                if nome.endswith(".md"):
                    lista.append(os.path.join(NOVO, nome))
        return lista
    if os.path.exists(VOLUME):
        return [VOLUME]
    print("aviso: volume não encontrado (%s); a auditar as fontes" %
          os.path.relpath(VOLUME, RAIZ))
    return [f for f in FONTES if os.path.exists(f)]


def capitulos_encerrados():
    """Números dos capítulos cuja fonte está em `REVISAO_ENCERRADA`.

    No volume contínuo não há nome de ficheiro por achado: sem este mapa, os
    achados do Anexo H — cuja revisão o autor deu por encerrada — voltariam a
    contar. A numeração segue a regra de `montar_volume_unico.PLANO`: só a
    entrada "titulo" não incrementa capítulo.
    """
    try:
        if BASE not in sys.path:
            sys.path.insert(0, BASE)
        from montar_volume_unico import PLANO
    except Exception:
        return set()
    caps, cap = set(), 0
    for item in PLANO:
        if item[0] == "titulo":
            continue
        cap += 1
        if item[0] == "novo" and os.path.basename(item[1]) in REVISAO_ENCERRADA:
            caps.add(cap)
    return caps


def faixas_encerradas(texto):
    """Intervalos de linhas (1-based, inclusivos) dos capítulos encerrados."""
    caps = capitulos_encerrados()
    if not caps:
        return []
    marcas = [(int(m.group(1)), texto.count("\n", 0, m.start()) + 1)
              for m in re.finditer(r"^## (\d+)\. ", texto, flags=re.M)]
    faixas = []
    for i, (num, ini) in enumerate(marcas):
        if num not in caps:
            continue
        fim = marcas[i + 1][1] - 1 if i + 1 < len(marcas) else \
            texto.count("\n") + 1
        faixas.append((ini, fim))
    return faixas


def eh_endereco(linha, ini_rel, fim_rel):
    """'Shizuoka-ken', 'Tosu-chō' — sufixo de endereço, não medida."""
    return (ini_rel > 0 and linha[ini_rel - 1] == "-") or \
           (fim_rel < len(linha) and linha[fim_rel] == "-")


def eh_nome_proprio(token_original, linha, ini_rel):
    """'Tsurumi Ken' — inicial maiúscula precedida de nome próprio."""
    if not token_original[:1].isupper():
        return False
    antes = linha[:ini_rel].rstrip()
    # a palavra anterior é um nome próprio capitalizado?
    return bool(re.search(r"(?:^|\s)([A-Z][a-z]+)\s*$", antes))


def linha_de(texto, pos):
    ini = texto.rfind("\n", 0, pos) + 1
    fim = texto.find("\n", pos)
    return texto[ini:fim if fim > 0 else len(texto)], ini


def auditar(caminho, regras, proibicoes, faixas=()):
    texto = open(caminho, encoding="utf-8").read()
    nome = os.path.relpath(caminho, RAIZ)
    encerrado = os.path.basename(caminho) in REVISAO_ENCERRADA
    codigo = blocos_de_codigo(texto)
    achados = []

    def encerrada_linha(n):
        return any(ini <= n <= fim for ini, fim in faixas)

    def em_codigo(n):
        return any(ini <= n <= fim for ini, fim in codigo)

    def descartar(m, linha, rel):
        """Motivos de contexto que tornam a ocorrência não-mensurável."""
        if linha.lstrip().startswith((">", "|", "#", "—", "!")):
            return True
        if linha.count("「") > linha.count("」"):
            return True
        n = texto.count("\n", 0, m.start()) + 1
        if encerrada_linha(n) or em_codigo(n):
            return True
        if em_italico_inline(linha, rel):
            return True
        if em_citacao(texto, m.start()):
            return True
        if em_composto(texto, m.start(), m.end()):
            return True
        if em_titulo_glosado(texto, m.start()):
            return True
        return False

    # --- A: primeira ocorrência em prosa precisa de glosa na vizinhança
    for jp, pt_completo, principal in regras:
        alvo = normalizar(principal)
        if not alvo or encerrado:
            continue
        primeira = None
        for m in re.finditer(re.escape(jp), texto):
            linha, ini_linha = linha_de(texto, m.start())
            if descartar(m, linha, m.start() - ini_linha):
                continue
            primeira = m
            break
        if primeira is None:
            continue
        janela = texto[max(0, primeira.start() - 140):primeira.end() + 140]
        if alvo in normalizar(janela):
            continue
        linha, _ = linha_de(texto, primeira.start())
        achados.append({
            "tipo": "A-termo-sem-glosas",
            "arquivo": nome,
            "jp": jp,
            "esperado": principal,
            "linha": texto.count("\n", 0, primeira.start()) + 1,
            "contexto": linha.strip()[:110],
        })

    # --- B: parêntese logo depois do termo com tradução divergente
    for jp, pt_completo, principal in regras:
        alvo = normalizar(principal)
        if not alvo or encerrado:
            continue
        for m in re.finditer(re.escape(jp) + r"\**[（(]([^）)\n]{2,80})[）)]",
                             texto):
            linha, ini_linha = linha_de(texto, m.start())
            if descartar(m, linha, m.start() - ini_linha):
                continue
            dentro = m.group(1)
            if not re.search(r"[A-Za-zÀ-ÿ]{4,}", dentro):
                continue            # parêntese com romaji só, ou vazio
            if alvo in normalizar(dentro) or normalizar(dentro) in alvo:
                continue
            achados.append({
                "tipo": "B-glosas-divergentes",
                "arquivo": nome,
                "jp": jp,
                "esperado": principal,
                "encontrado": dentro.strip()[:80],
                "linha": texto.count("\n", 0, m.start()) + 1,
            })
            break

    # --- C: proibições
    for p in proibicoes:
        for mau in p["proibido"]:
            for m in re.finditer(r"\b" + re.escape(mau) + r"\b", texto,
                                 flags=re.I):
                linha, ini_linha = linha_de(texto, m.start())
                rel_ini = m.start() - ini_linha
                rel_fim = m.end() - ini_linha
                if linha.lstrip().startswith("|") and \
                        re.search("[" + CJK + "]", linha):
                    continue
                if eh_endereco(linha, rel_ini, rel_fim):
                    continue
                if eh_nome_proprio(m.group(0), linha, rel_ini):
                    continue
                n = texto.count("\n", 0, m.start()) + 1
                if encerrado or encerrada_linha(n) or em_codigo(n):
                    continue
                achados.append({
                    "tipo": "C-proibicao",
                    "arquivo": nome,
                    "termo": mau,
                    "gatilho": p["gatilho"][:4],
                    "motivo": p["motivo"][:120],
                    "gravidade": p["gravidade"],
                    "linha": n,
                    "contexto": linha.strip()[:110],
                })

    # --- D: nome de ficheiro do acervo no corpo do volume
    for m in re.finditer(r"`([^`\n]{3,80})`", texto):
        dentro = m.group(1)
        if not re.search(r"(?:^|/)[\w.\-]+\.(?:html?|txt|json)$", dentro):
            continue
        n = texto.count("\n", 0, m.start()) + 1
        if encerrada_linha(n) or em_codigo(n):
            continue
        linha, _ = linha_de(texto, m.start())
        achados.append({
            "tipo": "D-caminho-do-acervo",
            "arquivo": nome,
            "caminho": dentro[:80],
            "linha": n,
            "contexto": linha.strip()[:110],
        })
    return achados


def main():
    detalhar = "--detalhar" in sys.argv
    origem = "fontes" if "--fontes" in sys.argv else "volume"
    alvo = None
    if "--arquivo" in sys.argv:
        alvo = sys.argv[sys.argv.index("--arquivo") + 1]

    regras = carregar_glossario()
    proibicoes = carregar_proibicoes()
    lista = [alvo] if alvo else arquivos(origem)

    todos = []
    for f in lista:
        faixas = ()
        if os.path.abspath(f) == os.path.abspath(VOLUME):
            faixas = faixas_encerradas(open(f, encoding="utf-8").read())
        todos.extend(auditar(f, regras, proibicoes, faixas))

    por_tipo = {}
    for a in todos:
        por_tipo.setdefault(a["tipo"], []).append(a)

    print("=" * 74)
    print("AUDITORIA DO GLOSSÁRIO — %d entradas, %d proibições" %
          (len(regras), len(proibicoes)))
    print("objeto: %s" % ("arquivo indicado" if alvo else
                          ("fontes (insumo)" if origem == "fontes" else
                           "volume montado (o que o leitor vê)")))
    print("=" * 74)
    for tipo in sorted(por_tipo):
        print("\n%s: %d" % (tipo, len(por_tipo[tipo])))
        por_arquivo = {}
        for a in por_tipo[tipo]:
            por_arquivo.setdefault(a["arquivo"], []).append(a)
        for arq in sorted(por_arquivo):
            print("   %-58s %3d" % (arq, len(por_arquivo[arq])))
        if detalhar:
            for a in por_tipo[tipo]:
                if tipo == "C-proibicao":
                    print("     %-26s L%-5s %-8s | %s" %
                          (os.path.basename(a["arquivo"])[:26], a["linha"],
                           a["termo"], a.get("contexto", "")[:64]))
                elif tipo == "D-caminho-do-acervo":
                    print("     %-26s L%-5s %-30s | %s" %
                          (os.path.basename(a["arquivo"])[:26], a["linha"],
                           a["caminho"], a.get("contexto", "")[:48]))
                elif tipo == "B-glosas-divergentes":
                    print("     %-26s L%-5s %-10s esperado=%-20s achado=%s" %
                          (os.path.basename(a["arquivo"])[:26], a["linha"],
                           a["jp"], a["esperado"][:20], a["encontrado"][:32]))
                else:
                    print("     %-26s L%-5s %-14s falta: %s" %
                          (os.path.basename(a["arquivo"])[:26], a["linha"],
                           a["jp"], a["esperado"][:40]))

    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    json.dump(todos, open(SAIDA, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\ntotal de achados: %d" % len(todos))
    print("gravado: %s" % os.path.relpath(SAIDA, RAIZ))


if __name__ == "__main__":
    main()
