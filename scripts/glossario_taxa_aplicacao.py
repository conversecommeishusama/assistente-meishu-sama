"""Taxa de aplicação de cada entrada do glossário de tradução.

A varredura de padronização (regra A1) diz em quantos artigos a chave japonesa
ocorre SEM a forma canônica no português. Sozinho, esse número não distingue
as duas coisas que precisam ser distinguidas:

  - REGRA FIXA violada     -- o termo é aplicado quase sempre, e as exceções
                              são erro (ex.: 御守 -> Ohikari)
  - GLOSA DESCRITIVA       -- a entrada é uma tradução possível de vocabulário
                              comum, que varia legitimamente com o contexto
                              (ex.: 熱 -> febre, que às vezes é "calor")

O que distingue é a TAXA: quantas vezes a forma canônica FOI usada, contra
quantas não foi. Um termo aplicado em 95% dos artigos e ausente em 5% é regra
com violação; um aplicado em 12% é glosa descritiva.

Esse cálculo é determinístico e roda de graça -- e é o que a varredura de
2026-07-27 não fez, tendo descartado ~559 dos 564 termos sinalizados "por
amostragem". Foi dentro desse descarte que 御利益, 邪神, 微熱 e 本教 passaram.

Saída: reports/varredura_padronizacao/GLOSSARIO_TAXA.json e .md
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

PT_DIR = RAIZ / "livros_publicacao_pt_revisado"
JP_DIR = RAIZ / "reports/livros_trabalho/jp"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
SAIDA = RAIZ / "reports/varredura_padronizacao"
CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿]")


def fold(s: str) -> str:
    """Minúscula, sem acento e SEM MARCA DE PLURAL.

    O plural cai no meio de expressões de várias palavras -- "micróbio
    patogênico" contra "micróbios patogênicos" --, então a comparação por
    substring falhava mesmo com o termo aplicado corretamente. Medido: 16
    ocorrências reais de "micróbios patogênicos" no acervo eram contadas como
    ausência de `病菌`, e o mesmo padrão inflava a contagem de todos os 608
    termos. Remover o `s` final de cada palavra dos DOIS lados resolve; é
    grosseiro para o português mas simétrico, e erra para o lado permissivo,
    que é o certo para quem procura faltas.
    """
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"([a-z])s\b", r"\1", s)


def formas_aceitas(valor: str) -> list[str]:
    """Todas as formas que contam como "o termo foi aplicado".

    Muitas entradas oferecem alternativas dentro do próprio valor -- por
    "ou", por vírgula, por barra -- e algumas trazem glosa entre parênteses
    ou colchetes. Aceitar cada alternativa isoladamente só torna o casamento
    MAIS permissivo, então erra para o lado seguro: pode transformar uma
    falta em acerto, nunca o contrário. Sem isso, `一生懸命` ("com empenho ou
    com esforço") aparecia como nunca aplicado em 359 artigos.
    """
    formas = {valor}
    sem = re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", valor).strip()
    if sem:
        formas.add(sem)
    for m in re.finditer(r"[\(\[]([^)\]]+)[\)\]]", valor):
        parte = m.group(1).strip()
        if len(parte) >= 4:
            formas.add(parte)
    for pedaco in re.split(r"\s*[/;,]\s*|\s+ou\s+", sem):
        pedaco = pedaco.strip()
        if len(pedaco) >= 4:
            formas.add(pedaco)
    # Variante com hífen: o corpus escreve "Daikōmyō-Nyorai" e o glossário
    # registra "Daikōmyō Nyorai". Sem aceitar as duas, o termo aparecia como
    # violado em artigos que na verdade o aplicam corretamente.
    for f in list(formas):
        if " " in f:
            formas.add(f.replace(" ", "-"))
    return [fold(f) for f in formas if len(f.strip()) >= 3]


RE_CONTEXTUAL = re.compile(
    r"conforme (o )?contexto|ajustad|depende|variável|variavel|segundo o contexto",
    re.IGNORECASE)


def natureza_da_entrada(chave: str, valor: str) -> str:
    """Classificação determinística do TIPO de entrada, antes de qualquer
    julgamento de conteúdo. Duas categorias podem ser decididas sem modelo:

    - `contextual_declarada`: a própria entrada diz que varia (ex.: 管長 ->
      "presidente ou líder (ajustado conforme contexto)"). Não é regra fixa
      por definição do glossário; nada a cobrar.
    - `chave_curta`: chave japonesa de 1 caractere casa dentro de compostos
      (我 casa em 我々, 我慢...), então a contagem de "ausências" é ruído de
      substring, não evidência de erro.
    """
    if RE_CONTEXTUAL.search(valor):
        return "contextual_declarada"
    if len(chave) <= 1:
        return "chave_curta"
    return "candidata"


def artigos(caminho: Path, spec: dict, campo: str) -> list[str]:
    texto = clean_body(caminho.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n"))
    arts = spec.get("articles", [])
    anc = [a.get(campo, "") for a in arts]
    if len(arts) <= 1 or not all(anc):
        return [texto]
    try:
        pedacos = split_by_anchors(texto, anc, label=caminho.name)
    except ValueError:
        return [texto]
    return pedacos if len(pedacos) == len(arts) else [texto]


def main() -> None:
    gloss = json.loads((RAIZ / "glossario_traducao.json").read_text(encoding="utf-8"))
    gloss = {k: v for k, v in gloss.items()
             if isinstance(k, str) and isinstance(v, str)
             and not k.startswith("_") and CJK.search(k)}
    aceitas = {k: formas_aceitas(v) for k, v in gloss.items()}
    print(f"{len(gloss)} entradas com chave japonesa", flush=True)

    stats = {k: {"canonico": gloss[k], "hit": 0, "miss": 0,
                 "obras_hit": set(), "obras_miss": set(),
                 "ocorrencias_jp": 0, "exemplos": []} for k in gloss}

    livros = sorted(PT_DIR.glob("*.txt"))
    for n, pt_path in enumerate(livros, 1):
        nome = pt_path.name
        spec_path = SPEC_DIR / f"{nome}.json"
        jp_path = JP_DIR / nome
        if not spec_path.exists() or not jp_path.exists():
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        apt = artigos(pt_path, spec, "pt_anchor")
        ajp = artigos(jp_path, spec, "jp_anchor")
        if len(apt) != len(ajp):
            continue
        for i, (jp, pt) in enumerate(zip(ajp, apt)):
            if not jp or not pt:
                continue
            ptf = fold(pt)
            for chave, formas in aceitas.items():
                if chave not in jp:
                    continue
                s = stats[chave]
                s["ocorrencias_jp"] += jp.count(chave)
                if any(f in ptf for f in formas):
                    s["hit"] += 1
                    s["obras_hit"].add(nome)
                else:
                    s["miss"] += 1
                    s["obras_miss"].add(nome)
                    if len(s["exemplos"]) < 3:
                        p = jp.find(chave)
                        s["exemplos"].append({
                            "obra": nome, "artigo": i,
                            "jp": re.sub(r"\s+", " ", jp[max(0, p - 60): p + 90]),
                        })
        print(f"[{n:>3}/{len(livros)}] {nome[:56]}", flush=True)

    saida = {}
    for k, s in stats.items():
        tot = s["hit"] + s["miss"]
        if tot == 0:
            continue
        saida[k] = {
            "canonico": s["canonico"], "hit": s["hit"], "miss": s["miss"],
            "total": tot, "taxa": round(s["hit"] / tot, 3),
            "natureza": natureza_da_entrada(k, s["canonico"]),
            "obras_hit": len(s["obras_hit"]), "obras_miss": len(s["obras_miss"]),
            "ocorrencias_jp": s["ocorrencias_jp"], "exemplos": s["exemplos"],
        }
    (SAIDA / "GLOSSARIO_TAXA.json").write_text(
        json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")

    def faixa(v: dict) -> str:
        if v["natureza"] == "contextual_declarada":
            return "Z1. a propria entrada diz que varia -- nao e regra"
        if v["natureza"] == "chave_curta":
            return "Z2. chave de 1 caractere -- ruido de substring"
        t = v["taxa"]
        if t >= 0.90:
            return "A. regra fixa, violacao pontual  (>=90% aplicado)"
        if t >= 0.60:
            return "B. provavel regra, violacao ampla (60-89%)"
        if t >= 0.25:
            return "C. ambiguo, precisa julgamento     (25-59%)"
        if t > 0:
            return "D. provavel glosa descritiva       (1-24%)"
        return "E. nunca aplicado                  (0%)"

    from collections import Counter
    c = Counter(faixa(v) for v in saida.values())
    L = ["# Glossário — taxa de aplicação por termo", "",
         f"{len(saida)} entradas do glossário cuja chave japonesa ocorre no acervo.",
         "",
         "A taxa é a fração dos artigos em que a forma canônica **foi** usada,",
         "entre os artigos cujo japonês contém a chave. É o sinal que separa",
         "regra fixa violada de glosa descritiva — e é o que faltou na varredura",
         "de 27/07, que descartou ~559 termos por amostragem.", "",
         "| faixa | termos |", "|---|---:|"]
    for k in sorted(c):
        L.append(f"| {k} | {c[k]} |")
    L += ["", "## Termos por faixa", ""]
    for nome_faixa in sorted(c):
        itens = sorted(((k, v) for k, v in saida.items() if faixa(v) == nome_faixa),
                       key=lambda x: -x[1]["miss"])
        L += [f"### {nome_faixa}", "",
              "| termo | forma canônica | aplicado | ausente | taxa | obras |",
              "|---|---|---:|---:|---:|---:|"]
        for k, v in itens:
            can = v["canonico"].replace("|", "\\|")[:58]
            L.append(f"| `{k}` | {can} | {v['hit']} | {v['miss']} | "
                     f"{v['taxa']:.0%} | {v['obras_miss']} |")
        L.append("")
    (SAIDA / "GLOSSARIO_TAXA.md").write_text("\n".join(L), encoding="utf-8")
    print("\n" + "\n".join(f"  {k}: {v}" for k, v in sorted(c.items())))
    print(f"\nsaída em {SAIDA}")


if __name__ == "__main__":
    main()
