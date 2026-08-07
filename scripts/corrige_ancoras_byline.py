"""Corrige âncoras de artigo que começam na byline, deixando o cabeçalho
(título do depoimento, endereço, e às vezes metade do nome do depoente) preso
no fim do artigo anterior.

Achado pela varredura de padronização (regra H5) em 4 obras, 157 artigos, dos
quais 13 com o NOME da pessoa partido ao meio pela fronteira -- o artigo
anterior termina em 'Yamada' e o seguinte começa em 'Tomie (42)'.

Estrutura real, verificada no texto:

    ...fim do depoimento anterior.
                                          <- linha em branco
    Título do depoimento seguinte         <- fica preso no artigo anterior
                                          <- linha em branco
    Endereço                              <- idem
    Sobrenome                             <- idem (metade do nome!)
    Nome (42), Igreja Média ...           <- onde a âncora aponta hoje

A correção move a âncora para o início do cabeçalho e preenche `title_pt`
quando estiver vazio. Nada do TEXTO é alterado -- só o ponteiro da spec.

Uso:
    python3 scripts/corrige_ancoras_byline.py            # diagnóstico, não grava
    python3 scripts/corrige_ancoras_byline.py --aplicar  # grava, com backup
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

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"

FIM_DE_FRASE = (".", "!", "?", "”", '"', "…", ":", ";", ")")


def le(caminho: Path) -> str:
    return clean_body(caminho.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n"))


DIVISOR = re.compile(r"^[\s\-—–─*=_·・]{2,}$")


def eh_divisor(linha: str) -> bool:
    return bool(DIVISOR.fullmatch(linha.strip()))


def limpa_markdown(s: str) -> str:
    return re.sub(r"[*_]{1,3}", "", s).strip(" —–-―")


RE_ENDERECO = re.compile(
    r"^(Província|Cidade|Distrito|Vila|Bairro|Aldeia|Município|Rua|Avenida|Povoado)\b")
RE_IGREJA = re.compile(r"^Igreja\b")
RE_CITACAO = re.compile(r"n[ºo°]\s*\d+|—\s*\d{1,2}\s+de\s+\w+\s+de\s+(Showa|Sh[oō]wa|19\d\d)")
RE_NOME_NU = re.compile(r"^[A-ZÀ-Ú][\wÀ-ÿ'\-]{1,24}$")
RE_SO_PARENTESES = re.compile(r"^\(.*\)$")


def classifica(linha: str) -> str:
    """Uma linha do fim do artigo anterior pertence ao corpo dele ou ao
    cabeçalho do próximo? Classificar é mais robusto que parar na primeira
    pontuação: título terminado em '!' e ficha de publicação terminada em ')'
    interrompiam a busca e escondiam o cabeçalho real (verificado nos artigos
    14 e 93 de 19530910-世界救世教奇蹟集)."""
    s = linha.strip()
    if not s:
        return "vazia"
    if eh_divisor(s):
        return "divisor"
    if RE_SO_PARENTESES.fullmatch(s):
        return "corpo"        # data de fechamento do depoimento anterior
    if len(s) > 130:
        return "corpo"
    if RE_ENDERECO.match(s):
        return "endereco"
    if RE_IGREJA.match(s):
        return "igreja"
    if RE_CITACAO.search(s):
        return "citacao"
    if RE_NOME_NU.fullmatch(s):
        return "nome"
    if s.startswith("**") or not s.endswith("."):
        return "titulo"
    return "corpo"


def cabecalho_vazado(corpo_anterior: str) -> list[str]:
    """Linhas do fim do artigo anterior que na verdade abrem o próximo."""
    linhas = [ln.rstrip() for ln in corpo_anterior.splitlines()]
    vazadas: list[str] = []
    for ln in reversed(linhas):
        tipo = classifica(ln)
        if tipo == "vazia":
            if vazadas:
                continue
            break
        if tipo == "corpo":
            break
        vazadas.insert(0, ln.strip())
        if len(vazadas) > 8:  # cabeçalho longo demais: desconfiar, não mexer
            return []
    while vazadas and eh_divisor(vazadas[0]):
        vazadas.pop(0)
    return vazadas


# Linha que é só uma data de sessão. Nas séries 御教え集 / 御光話録 /
# 御垂示録 a data ficar no FIM do artigo anterior é convenção deliberada do
# acervo -- confirmada em 32 dos 33 volumes de 御教え集 -- e não bug. Já
# tratei isso como defeito uma vez neste projeto e tive de reverter; a
# guarda existe para não repetir.
# O sufixo entre parênteses faz parte do cabeçalho de data desta série --
# dia da semana ("28 de dezembro (terça-feira)") ou nota editorial
# ("5 de agosto (apenas neste dia, sem uso de taquigrafia)", exigida pelo
# §4.4-A3 do protocolo). Sem aceitá-lo, 4 datas escapavam da guarda.
RE_SO_DATA = re.compile(
    r"^\[?\s*\d{1,2}\s*(º|o)?\s+de\s+"
    r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|"
    r"outubro|novembro|dezembro)"
    r"(\s+de\s+\d{4})?\s*(\([^)]*\))?\s*\]?\s*$", re.IGNORECASE)


def eh_titulo(linha: str) -> bool:
    """Serve como início de artigo? Título de depoimento, não endereço, não
    byline, não nota de rodapé, não divisor."""
    cand = limpa_markdown(linha)
    if len(cand) < 12 or eh_divisor(linha) or RE_SO_DATA.match(linha.strip()):
        return False
    if linha.lstrip().startswith(("*", "†", "(")) and not linha.lstrip().startswith("**"):
        return False
    if re.match(r"^(Província|Distrito|Bairro|Cidade|Vila|Aldeia|Igreja|Rua|Avenida)\b", cand):
        return False
    if re.search(r"\(\s*\d{1,3}\s*(anos)?\s*\)\s*$", cand):
        return False
    return True


def titulo_do_cabecalho(vazadas: list[str]) -> str:
    if not vazadas or not eh_titulo(vazadas[0]):
        return ""
    return limpa_markdown(vazadas[0])


def analisa(nome: str) -> dict:
    spec_path = SPEC_DIR / f"{nome}.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    arts = spec.get("articles", [])
    ancoras = [a.get("pt_anchor", "") for a in arts]
    if len(arts) <= 1 or not all(ancoras):
        return {"arquivo": nome, "erro": "spec sem âncoras completas"}
    texto = le(PT_FONTE / nome)
    try:
        corpos = split_by_anchors(texto, ancoras, label=nome)
    except ValueError as exc:
        return {"arquivo": nome, "erro": f"split falhou antes de mexer: {exc}"}

    # Posição real de cada âncora, para garantir que uma âncora nova nunca
    # invada o artigo anterior. Nestes livros existem artigos que são SÓ o
    # título, separados do corpo (padrão já catalogado em 17/07 para
    # 結核の革命的療法): nesses casos o "cabeçalho vazado" é, na verdade, o
    # artigo anterior inteiro, e movê-lo o deixaria vazio.
    pos_ancora: list[int] = []
    cursor = 0
    for anc in ancoras:
        p = texto.find(anc.strip().splitlines()[0], cursor)
        pos_ancora.append(p)
        cursor = max(cursor, p + 1)

    propostas = []
    for i in range(1, len(arts)):
        anc = ancoras[i].strip()
        # Âncora que já traz a ficha de publicação é um cabeçalho estruturado
        # correto (§4.4-A4) -- não é este bug. Mas âncora multilinha SEM ficha
        # é só a byline quebrada em duas linhas, e é exatamente o caso.
        if "\n" in anc and RE_CITACAO.search(anc):
            continue
        primeira = anc.splitlines()[0].strip()
        eh_byline = (
            re.match(r"^[A-ZÀ-Ú][\wÀ-ÿ'\- ]{1,40}\s*\(\s*\d{1,3}\s*(anos)?\s*\)", primeira)
            or re.match(r"^Igreja\s+\w+.{0,60}\(\s*\d{1,3}", primeira)
            or re.match(r"^[A-ZÀ-Ú][\wÀ-ÿ'\- ]{2,40},\s*\d{1,3}\s+anos", primeira)
        )
        # Segunda assinatura do mesmo bug, achada em 2026-08-07 ao verificar um
        # achado de glossário: a âncora aponta para o RÓTULO DE DIÁLOGO em vez
        # do título do item. Efeito idêntico -- o título, com sua citação de
        # fonte, fica pendurado no fim do artigo anterior. Foi o que fez o
        # julgamento do glossário acusar "omissão da citação （御垂示録 19号
        # P.24）" em 6 artigos: a citação estava no texto, mas fora do artigo.
        eh_rotulo_dialogo = bool(
            re.match(r"^\((Pergunta|Consulta|Resposta|Ensinamento|Orientação)", primeira)
            or re.match(r"^(Interlocutor|Meishu-Sama):", primeira))
        if not (eh_byline or eh_rotulo_dialogo):
            continue
        vazadas = cabecalho_vazado(corpos[i - 1])
        if not vazadas:
            continue
        # Normalmente o cabeçalho começa na primeira linha vazada, mas há casos
        # em que a âncora do artigo ANTERIOR é ela própria um fragmento dentro
        # do bloco (âncora antiga apontando para meio de frase). Aí a primeira
        # linha utilizável é a seguinte.
        anterior = pos_ancora[i - 1]
        nova = ""
        for cand in vazadas[:-1] or vazadas:
            if not eh_titulo(cand):
                continue
            if texto.count(cand) != 1:
                continue
            if anterior < 0 or texto.find(cand) <= anterior:
                continue
            nova = cand
            break
        if not nova:
            continue
        # a âncora nova precisa ser única a partir do fim do artigo i-2,
        # senão split_by_anchors pode casar cedo demais
        propostas.append({
            "artigo": i, "ancora_atual": anc, "ancora_nova": nova,
            "cabecalho_vazado": vazadas,
            "title_pt_atual": arts[i].get("title_pt", ""),
            "title_pt_novo": titulo_do_cabecalho(vazadas),
            "nome_partido": bool(
                re.fullmatch(r"[A-ZÀ-Ú][\wÀ-ÿ'\-]{1,20}", vazadas[-1])
                and re.match(r"^[A-ZÀ-Ú][\wÀ-ÿ'\- ]{1,30}\s*\(", primeira)),
        })
    return {"arquivo": nome, "n_artigos": len(arts), "propostas": propostas}


def aplica(nome: str, propostas: list[dict]) -> dict:
    """Grava as âncoras novas e revalida com a função REAL de produção.
    Se a validação falhar, reverte tudo e não deixa o arquivo pior."""
    spec_path = SPEC_DIR / f"{nome}.json"
    original = spec_path.read_text(encoding="utf-8")
    spec = json.loads(original)
    arts = spec["articles"]

    for p in propostas:
        a = arts[p["artigo"]]
        a["pt_anchor"] = p["ancora_nova"]
        if p["title_pt_novo"] and not (a.get("title_pt") or "").strip():
            a["title_pt"] = p["title_pt_novo"]

    ancoras = [a["pt_anchor"] for a in arts]
    resultado = {"arquivo": nome, "aplicadas": len(propostas)}
    for rotulo, base in (("fonte", PT_FONTE), ("staging", PT_STAGING)):
        caminho = base / nome
        if not caminho.exists():
            resultado[rotulo] = "arquivo ausente"
            continue
        try:
            pedacos = split_by_anchors(le(caminho), ancoras, label=nome)
        except ValueError as exc:
            spec_path.write_text(original, encoding="utf-8")
            return {"arquivo": nome, "REVERTIDO": f"{rotulo}: {exc}"}
        if len(pedacos) != len(arts):
            spec_path.write_text(original, encoding="utf-8")
            return {"arquivo": nome, "REVERTIDO": f"{rotulo}: {len(pedacos)} != {len(arts)}"}
        resultado[rotulo] = f"{len(pedacos)}/{len(arts)} ok"

    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (spec_path.parent / f"{spec_path.name}.bak_pre_ancora_byline_{carimbo}").write_text(
        original, encoding="utf-8")
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    alvos = sorted({p.name for p in PT_FONTE.glob("*.txt")})
    total = partidos = 0
    for nome in alvos:
        # Corrigir uma âncora muda a fronteira do artigo seguinte e pode
        # revelar um cabeçalho vazado que antes estava escondido dentro de um
        # bloco maior. Repete até estabilizar, com teto de segurança.
        for rodada in range(1, 7):
            r = analisa(nome)
            props = r.get("propostas") or []
            if r.get("erro") or not props:
                break
            n_part = sum(1 for p in props if p["nome_partido"])
            total += len(props)
            partidos += n_part
            print(f"\n{nome}  —  rodada {rodada}: {len(props)} âncoras a mover "
                  f"({n_part} com nome partido)")
            for p in props[:3]:
                print(f"   art {p['artigo']:>4}: {p['ancora_atual'][:44]!r}")
                print(f"          -> {p['ancora_nova'][:60]!r}")
                if p["title_pt_novo"] and not p["title_pt_atual"]:
                    print(f"          title_pt vazio -> {p['title_pt_novo'][:56]!r}")
            if len(props) > 3:
                print(f"   ... mais {len(props) - 3}")
            if not aplicar:
                break
            res = aplica(nome, props)
            print("  ", res)
            if "REVERTIDO" in res:
                break
    print(f"\nTOTAL: {total} âncoras, {partidos} com nome partido ao meio")
    if not aplicar:
        print("(diagnóstico apenas — rode com --aplicar para gravar)")


if __name__ == "__main__":
    main()
