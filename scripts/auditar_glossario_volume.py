#!/usr/bin/env python3
"""Audita o volume contra o glossário de tradução.

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

Uso:
    python3 scripts/auditar_glossario_volume.py
    python3 scripts/auditar_glossario_volume.py --detalhar
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

CJK = r"\u3040-\u30ff\u4e00-\u9fff"

# Anexos cuja revisão já foi feita e encerrada (decisão do autor, 23/10/2026):
# audita-se para registro, mas os achados não entram na contagem de pendências.
REVISAO_ENCERRADA = {"47_anexo_kyoshu_yoko.md"}


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


def arquivos():
    lista = [f for f in FONTES if os.path.exists(f)]
    if os.path.isdir(NOVO):
        for nome in sorted(os.listdir(NOVO)):
            if nome.endswith(".md"):
                lista.append(os.path.join(NOVO, nome))
    return lista


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


def auditar(caminho, regras, proibicoes):
    texto = open(caminho, encoding="utf-8").read()
    nome = os.path.relpath(caminho, RAIZ)
    encerrado = os.path.basename(caminho) in REVISAO_ENCERRADA
    achados = []

    # --- A: primeira ocorrência em prosa precisa de glosa na vizinhança
    for jp, pt_completo, principal in regras:
        alvo = normalizar(principal)
        if not alvo:
            continue
        primeira = None
        for m in re.finditer(re.escape(jp), texto):
            linha, _ = linha_de(texto, m.start())
            if linha.lstrip().startswith((">", "|", "#", "—")):
                continue
            if linha.count("「") > linha.count("」"):
                continue
            primeira = m
            break
        if primeira is None or encerrado:
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
                if encerrado:
                    continue
                achados.append({
                    "tipo": "C-proibicao",
                    "arquivo": nome,
                    "termo": mau,
                    "gatilho": p["gatilho"][:4],
                    "motivo": p["motivo"][:120],
                    "gravidade": p["gravidade"],
                    "linha": texto.count("\n", 0, m.start()) + 1,
                    "contexto": linha.strip()[:110],
                })
    return achados


def main():
    detalhar = "--detalhar" in sys.argv
    alvo = None
    if "--arquivo" in sys.argv:
        alvo = sys.argv[sys.argv.index("--arquivo") + 1]

    regras = carregar_glossario()
    proibicoes = carregar_proibicoes()
    lista = [alvo] if alvo else arquivos()

    todos = []
    for f in lista:
        todos.extend(auditar(f, regras, proibicoes))

    por_tipo = {}
    for a in todos:
        por_tipo.setdefault(a["tipo"], []).append(a)

    print("=" * 74)
    print("AUDITORIA DO GLOSSÁRIO — %d entradas, %d proibições" %
          (len(regras), len(proibicoes)))
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
