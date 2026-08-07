"""Padroniza 浄化作用 como "processo de purificação" no acervo.

Decisão do usuário (2026-08-07): o padrão da Igreja é "Processo de
Purificação". Onde a repetição próxima ficar redundante, pode intercalar com
"ação purificadora".

Estado antes: 358 ocorrências, três formas concorrentes, e `浄化作用` -- um dos
conceitos centrais do ensinamento -- SEM entrada no glossário.

    ação de purificação      195
    ação purificadora         99
    processo de purificação   64

Verificado antes de aplicar: 347 das 358 ocorrências estão em artigos cujo
japonês contém 浄化作用 (97%); as outras 11 usam 浄化 no mesmo sentido.

A troca não é substituição literal: "ação" é feminino e "processo" é
masculino, então o determinante e os adjetivos que a acompanham precisam
concordar. "é uma ação de purificação" -> "é um processo de purificação".
Sem isso o texto sai com "a processo de purificação" em dezenas de lugares.

Uso:
    python3 scripts/padroniza_purificacao.py             # mostra, não grava
    python3 scripts/padroniza_purificacao.py --aplicar
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

FONTE = RAIZ / "livros_publicacao_pt_revisado"
STAGING = RAIZ / "reports/livros_trabalho/pt"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"

PADRAO = "processo de purificação"
ALTERNATIVA = "ação purificadora"
JANELA_REPETICAO = 400  # caracteres; dentro disso, intercala para não repetir

FORMAS = re.compile(
    r"ação\s+de\s+purificação|ações\s+de\s+purificação|"
    r"ação\s+purificadora|ações\s+purificadoras|"
    r"processo\s+de\s+purificação|processos\s+de\s+purificação",
    re.IGNORECASE)

# Determinantes e adjetivos que precedem o termo e precisam concordar.
# Levantados do corpus real, não imaginados: "é uma", "é a", "que a",
# "uma grande", "ocorre uma", "de uma", "uma violenta", "são a"...
FEM_PARA_MASC = {
    "a": "o", "as": "os", "uma": "um", "umas": "uns",
    "essa": "esse", "esta": "este", "aquela": "aquele",
    "essas": "esses", "estas": "estes", "aquelas": "aqueles",
    "da": "do", "das": "dos", "na": "no", "nas": "nos",
    "pela": "pelo", "pelas": "pelos", "à": "ao", "às": "aos",
    "sua": "seu", "suas": "seus", "minha": "meu", "minhas": "meus",
    "nossa": "nosso", "nossas": "nossos",
    "toda": "todo", "todas": "todos", "mesma": "mesmo", "mesmas": "mesmos",
    "própria": "próprio", "próprias": "próprios",
    "outra": "outro", "outras": "outros", "única": "único",
    "violenta": "violento", "violentas": "violentos",
    "intensa": "intenso", "intensas": "intensos",
    "forte": "forte", "grande": "grande", "natural": "natural",
    "verdadeira": "verdadeiro", "necessária": "necessário",
    "poderosa": "poderoso", "leve": "leve", "pequena": "pequeno",
    "nova": "novo", "primeira": "primeiro", "segunda": "segundo",
    "fraca": "fraco", "lenta": "lento", "magnífica": "magnífico",
    "rápida": "rápido", "contínua": "contínuo", "tremenda": "tremendo",
    "constante": "constante", "terrível": "terrível", "última": "último",
    "certa": "certo", "simples": "simples", "grave": "grave",
}
RE_PALAVRA = re.compile(r"([A-Za-zÀ-ÿ]+)(\s+)$")

# Adjetivos e particípios que aparecem DEPOIS do termo e concordam com ele.
# Lista restrita, levantada do corpus (10 ocorrências reais) -- restrita de
# propósito: uma regra genérica de "feminino -> masculino" logo após o termo
# atingiria substantivos vizinhos ("das nuvens espirituais", "das toxinas").
POS_FEM_PARA_MASC = {
    "intensa": "intenso", "realizada": "realizado", "violenta": "violento",
    "necessária": "necessário", "feita": "feito", "iniciada": "iniciado",
    "interrompida": "interrompido", "provocada": "provocado",
    "causada": "causado", "considerada": "considerado",
    "manifestada": "manifestado", "acelerada": "acelerado",
    "impedida": "impedido", "completa": "completo", "severa": "severo",
    "branda": "brando", "reprimida": "reprimido", "suprimida": "suprimido",
}
RE_TOKEN = re.compile(r"[A-Za-zÀ-ÿ]+")
JANELA_POS_PALAVRAS = 5  # "é tanto mais intensa" -> o adjetivo é a 4ª


def concorda_depois(sufixo: str) -> tuple[str, list[str]]:
    """Passa para o masculino o primeiro adjetivo/particípio feminino da lista
    que apareça nas próximas palavras. Percorre palavra a palavra: um regex
    com `{0,4}` guloso pulava direto para além do alvo (medido -- "ser
    realizada" e "tão violenta" passavam intactos)."""
    for n, m in enumerate(RE_TOKEN.finditer(sufixo)):
        if n >= JANELA_POS_PALAVRAS:
            break
        # para numa fronteira de frase: não concorda através de ponto final
        if "." in sufixo[: m.start()]:
            break
        alvo = POS_FEM_PARA_MASC.get(m.group().lower())
        if not alvo:
            continue
        novo = alvo.capitalize() if m.group()[0].isupper() else alvo
        return (sufixo[: m.start()] + novo + sufixo[m.end():],
                [f"{m.group()}->{novo}"])
    return sufixo, []


ARTIGOS = {"a", "as", "o", "os", "uma", "um", "umas", "uns", "da", "do",
           "das", "dos", "na", "no", "nas", "nos", "pela", "pelo",
           "pelas", "pelos", "à", "ao", "às", "aos"}


def concorda_antes(prefixo: str) -> tuple[str, list[str]]:
    """Passa para o masculino as palavras anteriores que concordam com o termo:
    o adjetivo, se houver, e o determinante que o precede.

    BUG REAL, pego só depois de aplicar: a versão anterior reexaminava a
    palavra que acabara de trocar, em vez de andar para trás. Resultado --
    "uma violenta ação" virava "uma violento processo", com o artigo intacto.
    Deixou 7 discordâncias no acervo ("uma magnífica processo", "uma fraca
    processo", "uma violento processo"). Agora percorre por posição.
    """
    trocas: list[str] = []
    fim = len(prefixo)
    for _ in range(3):  # adjetivo composto + adjetivo + artigo
        m = RE_PALAVRA.search(prefixo[:fim])
        if not m:
            break
        palavra = m.group(1)
        alvo = FEM_PARA_MASC.get(palavra.lower())
        if alvo is None:
            break
        if alvo != palavra.lower():
            novo = alvo.capitalize() if palavra[0].isupper() else alvo
            prefixo = prefixo[: m.start(1)] + novo + prefixo[m.end(1):]
            trocas.append(f"{palavra}->{novo}")
        fim = m.start(1)          # continua ANTES da palavra já tratada
        if palavra.lower() in ARTIGOS:
            break                 # chegou ao determinante: acabou
    return prefixo, trocas


def plural_de(forma: str) -> bool:
    return forma.lower().startswith(("ações", "processos"))


MINUSCULAS_DE_TITULO = {"de", "da", "do", "e", "em", "a", "o"}


def aplica_caixa(original: str, alvo: str) -> str:
    """Preserva o padrão de caixa do original.

    Em título o corpus escreve "O Processo de Purificação", com as palavras
    de conteúdo em maiúscula. Copiar só a inicial rebaixava a segunda palavra
    -- medido: "O Processo de Purificação" virou "O Processo de purificação"
    em dois títulos de artigo, um deles âncora de segmentação.
    """
    palavras = original.split()
    if len(palavras) >= 2 and all(
            p[0].isupper() for p in palavras if p.lower() not in MINUSCULAS_DE_TITULO):
        return " ".join(
            p if p.lower() in MINUSCULAS_DE_TITULO else p[0].upper() + p[1:]
            for p in alvo.split())
    if original[0].isupper():
        return alvo[0].upper() + alvo[1:]
    return alvo


def eh_titulo(texto: str, pos: int) -> bool:
    """A ocorrência está numa linha de título? Título é estrutura -- é onde a
    spec de segmentação ancora e é o que o leitor vê como cabeçalho -- então
    recebe sempre a forma canônica, nunca a alternativa estilística.

    Achado ao aplicar a primeira versão: a regra de intercalar reescreveu
    'A Doença é um Processo de Purificação' e 'O Processo de Purificação'
    (títulos de artigo do 世界メシヤ教手引 e do Eikō nº 93) como 'ação
    purificadora', quebrando as âncoras dos dois livros.
    """
    ini = texto.rfind("\n", 0, pos) + 1
    fim = texto.find("\n", pos)
    linha = texto[ini: fim if fim >= 0 else len(texto)].strip()
    if len(linha) > 90:
        return False
    # linha curta que não termina em pontuação de frase = cabeçalho
    return not linha.endswith((".", "!", "?", ";", ":", ","))


def transforma(texto: str) -> tuple[str, list[dict]]:
    saida, mudancas, cursor, ultima_pos, ultima_forma = [], [], 0, -10**9, ""
    ocorrencias = list(FORMAS.finditer(texto))
    for indice, m in enumerate(ocorrencias):
        # Limite da janela de concordância posterior: nunca pode invadir a
        # ocorrência seguinte.
        #
        # BUG REAL, pego na verificação: sem esse limite o cursor avançava 90
        # caracteres e engolia a próxima ocorrência, que era então emitida de
        # novo -- duplicando texto. Saída corrompida no Medicina_do_Amanha:
        # "...uma ação de purificação fraca é localizada e radAÇÃO
        # PURIFICADORA FRACA É LOCALIZADA E RADial...". Só apareceu porque a
        # contagem final de formas não fechou.
        limite_pos = (ocorrencias[indice + 1].start()
                      if indice + 1 < len(ocorrencias) else len(texto))
        original = m.group()
        prefixo = texto[cursor: m.start()]
        perto = (m.start() - ultima_pos) <= JANELA_REPETICAO
        # não intercala através de quebra de parágrafo nem em título
        mesmo_paragrafo = "\n\n" not in texto[max(0, ultima_pos): m.start()]
        usar_alternativa = (perto and mesmo_paragrafo
                            and ultima_forma == PADRAO
                            and not eh_titulo(texto, m.start()))
        alvo = ALTERNATIVA if usar_alternativa else PADRAO
        if plural_de(original):
            alvo = ("ações purificadoras" if usar_alternativa
                    else "processos de purificação")
        alvo = aplica_caixa(original, alvo)

        trocas, pos_troca = [], []
        proximo_cursor = m.end()
        if not usar_alternativa:  # feminino -> masculino, antes e depois
            prefixo, trocas = concorda_antes(prefixo)
            fim_janela = min(len(texto), m.end() + 90, limite_pos)
            sufixo, pos_troca = concorda_depois(texto[m.end(): fim_janela])
            if pos_troca:
                # reescreve a janela seguinte já concordada e avança o cursor
                saida.append(prefixo)
                saida.append(alvo)
                saida.append(sufixo)
                cursor = fim_janela
                ultima_pos, ultima_forma = m.start(), alvo.lower()
                mudancas.append({
                    "de": re.sub(r"\s+", " ", original), "para": alvo,
                    "concordancia": trocas + pos_troca,
                    "contexto": re.sub(r"\s+", " ",
                                       texto[max(0, m.start() - 60): fim_janela]),
                })
                continue
        if original.lower().replace("\n", " ") != alvo.lower() or trocas:
            mudancas.append({
                "de": re.sub(r"\s+", " ", original), "para": alvo,
                "concordancia": trocas,
                "contexto": re.sub(r"\s+", " ",
                                   texto[max(0, m.start() - 60): m.end() + 40]),
            })
        saida.append(prefixo)
        saida.append(alvo)
        cursor = proximo_cursor
        ultima_pos, ultima_forma = m.start(), alvo.lower()
    saida.append(texto[cursor:])
    novo = "".join(saida)

    # Invariante: a transformação troca formas, nunca cria nem apaga
    # ocorrências. Se a contagem não fechar, houve texto duplicado ou perdido
    # -- foi assim que a duplicação do Medicina_do_Amanha apareceu. Falhar
    # aqui é melhor do que gravar corpus corrompido.
    antes, depois = len(ocorrencias), len(FORMAS.findall(novo))
    if antes != depois:
        raise AssertionError(
            f"transformação alterou a contagem de ocorrências: {antes} -> {depois}")
    return novo, mudancas


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    total, por_obra = 0, {}
    exemplos = []

    for pt_path in sorted(FONTE.glob("*.txt")):
        obra = pt_path.name
        texto = pt_path.read_text(encoding="utf-8")
        novo, mud = transforma(texto)
        if not mud:
            continue
        por_obra[obra] = len(mud)
        total += len(mud)
        if len(exemplos) < 12:
            exemplos.extend(mud[:2])
        if not aplicar:
            continue
        pt_path.with_suffix(f".txt.bak_pre_purificacao_{carimbo}").write_text(
            texto, encoding="utf-8")
        pt_path.write_text(novo, encoding="utf-8")
        alvo_staging = STAGING / obra
        if alvo_staging.exists():
            t2 = alvo_staging.read_text(encoding="utf-8")
            n2, _ = transforma(t2)
            alvo_staging.write_text(n2, encoding="utf-8")

    print(f"{total} ocorrências em {len(por_obra)} obras\n")
    for e in exemplos[:12]:
        conc = f"  [{', '.join(e['concordancia'])}]" if e["concordancia"] else ""
        print(f"  {e['de']} -> {e['para']}{conc}")
        print(f"     {e['contexto'][:130]}")
    print()
    for obra, n in sorted(por_obra.items(), key=lambda x: -x[1])[:8]:
        print(f"  {n:>4}  {obra[:56]}")

    if not aplicar:
        print("\n(diagnóstico apenas — rode com --aplicar para gravar)")
        return

    print("\nrevalidando âncoras...")
    ruins, ancoras_ajustadas = 0, 0
    for obra in por_obra:
        spec_path = SPEC_DIR / f"{obra}.json"
        if not spec_path.exists():
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        arts = spec.get("articles", [])
        anc = [a.get("pt_anchor", "") for a in arts]
        if len(anc) <= 1 or not all(anc):
            continue
        texto_fonte = clean_body((FONTE / obra).read_text(encoding="utf-8"))

        # Âncora que continha o termo mudou junto com o texto: aplica a MESMA
        # troca na âncora, sempre na forma canônica (âncora é ponteiro, nunca
        # recebe a variação estilística).
        mudou_spec = False
        for a in arts:
            alvo = a.get("pt_anchor", "")
            if not FORMAS.search(alvo) or alvo in texto_fonte:
                continue
            # A âncora precisa da MESMA transformação do texto, concordância
            # inclusive: o texto virou "um processo de purificação" (com
            # "uma"->"um"), então trocar só o termo na âncora produziria
            # "uma processo de purificação", que não casa com nada.
            novo_anc = transforma(alvo)[0]
            if novo_anc in texto_fonte:
                a["pt_anchor"] = novo_anc
                if a.get("title_pt"):
                    a["title_pt"] = transforma(a["title_pt"])[0]
                mudou_spec = True
                ancoras_ajustadas += 1
        if mudou_spec:
            spec_path.with_suffix(
                f".json.bak_pre_purificacao_{carimbo}").write_text(
                json.dumps(json.loads(spec_path.read_text(encoding="utf-8")),
                           ensure_ascii=False, indent=2), encoding="utf-8")
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
            anc = [a["pt_anchor"] for a in arts]

        for base in (FONTE, STAGING):
            f = base / obra
            if not f.exists():
                continue
            try:
                c = split_by_anchors(clean_body(f.read_text(encoding="utf-8")), anc, label=obra)
                if len(c) != len(anc):
                    raise ValueError(f"{len(c)} != {len(anc)}")
            except ValueError as exc:
                print(f"  QUEBROU {base.name}/{obra}: {exc}")
                ruins += 1
    print(f"  {len(por_obra) - ruins} obras com âncoras íntegras, {ruins} quebradas"
          f" | {ancoras_ajustadas} âncoras atualizadas junto com o texto")


if __name__ == "__main__":
    main()
