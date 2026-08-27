#!/usr/bin/env python3
"""Pipeline genérico de retradução para as coleções de palavras orais truncadas.

Coleções suportadas:
  1. 御光話録 (Gokōwa-roku 1-19): formato Meishu-Sama:/Interlocutor: (igual Suplemento)
  2. 御垂示録 (Gosuiji-roku 1-30): formato Meishu-Sama:/Interlocutor: com aspas
  3. 御教え集 (Mioshie-shū 1-33): formato Interlocutor: + 〔御垂示〕 (resposta do Mestre)

Fluxo (por arquivo):
  1. Extrai falas (JP + quem fala) conforme o formato da coleção
  2. Retraduz cada fala com o executor (janela 5 falas + trava + anti-invenção + pessoa)
  3. Grava checkpoint incremental
  4. (opcional) Audita com DeepSeek e gera pontos para correção

Uso:
  .venv/bin/python scripts/retraduzir_colecao.py <colecao> <arquivo_jp> [--saida NOME] [--inicio N] [--fim N]
  colecao: gokowa | gosuiji | mioshie
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraducao_completa_gokowa import retraduzir  # noqa: E402

OUT = RAIZ / "reports" / "retraducao_colecoes"
JANELA = 5


def extrair_falas_gokowa(texto: str) -> list[tuple[str, str]]:
    """Formato Meishu-Sama:/Interlocutor: (igual ao Suplemento)."""
    falas = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        m = re.match(r"^(Meishu-Sama|Interlocutor)[:：]\s*(.*)", linha)
        if m:
            falas.append((m.group(1), m.group(2)))
    return falas


def extrair_falas_gosuiji(texto: str) -> list[tuple[str, str]]:
    """Formato Meishu-Sama:/Interlocutor: com aspas no Interlocutor."""
    return extrair_falas_gokowa(texto)


def extrair_falas_mioshie(texto: str) -> list[tuple[str, str]]:
    """Formato MISTO do Mioshie-shū (御教え集).

    O Mioshie tem natureza mista:
    1. Q&A estruturado: Interlocutor: (pergunta) + 〔御垂示〕 (resposta do Mestre).
    2. Ensinamentos contínuos: blocos 【御教え】 e seções datadas (九月一日 etc.).

    Estratégia:
    - Divide o texto em SESSÕES por data (padrão MêsX日) — cada sessão é uma unidade.
    - Dentro de cada sessão, separa falas (Interlocutor/御垂示), mas QUEBRA respostas
      longas do Meishu-Sama em blocos de ~LONGO_MAX chars (evita falas de 27K).
    - As interjeições do interlocutor （...） dentro da resposta são removidas.
    """
    falas = []
    LONGO_MAX = 400  # quebra respostas do Mestre maiores que isso
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]

    def quebrar_em_blocos(texto_bruto: str) -> list[str]:
        """Quebra um texto longo em blocos por quebras de frase (。！？)."""
        texto_bruto = re.sub(r"（[^）]{1,80}）", " ", texto_bruto)  # remove interjeições
        texto_bruto = re.sub(r"\s+", " ", texto_bruto).strip()
        if len(texto_bruto) <= LONGO_MAX:
            return [texto_bruto] if texto_bruto else []
        # quebra por pontuação de fim
        partes = re.split(r"(?<=[。！？])", texto_bruto)
        blocos = []
        buf = ""
        for p in partes:
            buf += p
            if len(buf) >= LONGO_MAX * 0.6:
                blocos.append(buf.strip())
                buf = ""
        if buf.strip():
            blocos.append(buf.strip())
        return [b for b in blocos if b]

    i = 0
    while i < len(linhas):
        linha = linhas[i]
        # Interlocutor: inicia uma pergunta
        m = re.match(r"^Interlocutor[:：]\s*(.*)", linha)
        if m:
            pergunta = m.group(1)
            i += 1
            # acumula até 〔御垂示〕 OU novo （お伺） (novo caso relatado pelo
            # Interlocutor — linha 246 do 6号 mostrava fusão: o （お伺） da Sra.
            # Sayoshi era engolido na pergunta anterior)
            while i < len(linhas) and "御垂示" not in linhas[i] and not linhas[i].startswith("（お伺）") and not re.match(r"^Interlocutor[:：]", linhas[i]):
                pergunta += " " + linhas[i].strip()
                i += 1
            # quebra TAMBÉM perguntas longas do Interlocutor (eram falas gigantes:
            # os お伺 com detalhes de casos médicos passavam de 1000+ chars e não
            # eram quebrados — causando alta taxa de erro e lentidão)
            blocos = quebrar_em_blocos(pergunta)
            for b in blocos:
                falas.append(("Interlocutor", b))
            continue
        # （お伺） = novo caso relatado pelo Interlocutor (turno próprio)
        if linha.startswith("（お伺）") or linha.startswith("(お伺)"):
            pergunta = linha
            i += 1
            # acumula até 〔御垂示〕 OU outro （お伺）/Interlocutor
            while i < len(linhas) and "御垂示" not in linhas[i] and not linhas[i].startswith("（お伺）") and not re.match(r"^Interlocutor[:：]", linhas[i]):
                pergunta += " " + linhas[i].strip()
                i += 1
            blocos = quebrar_em_blocos(pergunta)
            for b in blocos:
                falas.append(("Interlocutor", b))
            continue
        # 〔御垂示〕 marca a resposta do Mestre (Meishu-Sama).
        # Só dispara no marcador 〔御垂示〕 (sozinho ou após Meishu-Sama:),
        # NUNCA em "御垂示" no meio de frase (ex: "御垂示のほどお願い申し上げます"
        # é parte de pergunta do Interlocutor).
        if "〔御垂示〕" in linha or "Meishu-Sama" in linha:
            resposta = ""
            # Se a linha já é "Meishu-Sama: ..." (a própria resposta), usa-a
            # como primeira linha (remove o rótulo). Não avança i.
            m_direta = re.match(r"^Meishu-Sama[:：]\s*(.+)$", linha)
            if m_direta and "御垂示" not in m_direta.group(1):
                resposta += " " + m_direta.group(1)
                i += 1
            else:
                # linha é 〔御垂示〕 (ou Meishu-Sama: 〔御垂示〕): avança para a
                # resposta na(s) linha(s) seguinte(s).
                i += 1
                if i < len(linhas):
                    primeira = re.sub(r"^Meishu-Sama[:：]\s*", "", linhas[i].strip())
                    if primeira:
                        resposta += " " + primeira
                        i += 1
            # Acumula as continuações até o próximo turno/marcador.
            while i < len(linhas) and not re.match(r"^(Interlocutor|Meishu-Sama)[:：]", linhas[i]) and "御垂示" not in linhas[i] and "（お伺）" not in linhas[i] and not linhas[i].startswith("【御教え】") and not linhas[i].startswith("〔御教え〕"):
                resposta += " " + linhas[i].strip()
                i += 1
            # quebra respostas longas em blocos (evita fala gigante)
            blocos = quebrar_em_blocos(resposta)
            for b in blocos:
                falas.append(("Meishu-Sama", b))
            continue
        # 【御教え】 = bloco de ensino contínuo do Mestre (Meishu-Sama)
        if linha.startswith("【御教え】") or linha.startswith("〔御教え〕"):
            i += 1
            resposta = ""
            while i < len(linhas) and not re.match(r"^Interlocutor[:：]", linhas[i]) and "御垂示" not in linhas[i] and "Meishu-Sama" not in linhas[i] and "（お伺）" not in linhas[i] and "【御教え】" not in linhas[i]:
                linha_atual = linhas[i].strip()
                linha_atual = re.sub(r"^Meishu-Sama[:：]\s*", "", linha_atual)
                resposta += " " + linha_atual
                i += 1
            blocos = quebrar_em_blocos(resposta)
            for b in blocos:
                falas.append(("Meishu-Sama", b))
            continue
        i += 1
    return falas


# ---------------------------------------------------------------------------
# Extrator de PROSA CONTÍNUA para Mioshie 9-33 (御教え集 9号-33号)
#
# Os Mioshie 9-33 NÃO são diálogo: são prosa contínua de Meishu-Sama, com
# sessões datadas (ex: 昭和二十七年四月五日) e parágrafos contínuos. Não há
# rótulos Interlocutor:/Meishu-Sama: nem 〔御垂示〕.
#
# Estratégia (fiel ao documento e simples):
#   1. Remove o cabeçalho de metadados (# Ficheiro... / === ARTIGO === / entry_id...).
#   2. Detecta sessões por DATA (padrão 昭和XX年X月X日 no início de linha).
#   3. Cada sessão vira uma sequência de "falas" (quem="Meishu-Sama", pois é a
#      prosa do Mestre) quebradas em blocos de até LONGO_MAX chars por quebra de
#      frase (。！？), preservando a data da sessão no primeiro bloco.
#   4. O restante do arquivo (antes da 1ª data, se houver prosa) também é
#      capturado como um bloco de abertura.
# ---------------------------------------------------------------------------
def extrair_prosa_mioshie(texto: str) -> list[tuple[str, str]]:
    """Divide a prosa contínua dos Mioshie 9-33 em blocos por sessão datada."""
    LONGO_MAX = 400
    linhas = [l.rstrip("\n") for l in texto.splitlines()]

    # 1. Remove cabeçalho de metadados até a linha em branco após 'Collection ID'
    inicio_conteudo = 0
    for i, l in enumerate(linhas):
        if l.startswith("Collection ID"):
            inicio_conteudo = i + 1
            break
    # pula linhas em branco iniciais e o título/ficha da edição que seguem o
    # cabeçalho (linhas não-japonesas até a primeira sessão datada ou 1º parágrafo)
    while inicio_conteudo < len(linhas) and not linhas[inicio_conteudo].strip():
        inicio_conteudo += 1
    # se as primeiras linhas são só o título da edição (ex: 御教え集第九号) e a
    # ficha (『御教え集』9号...発行), pula-as (são metadados, não prosa da sessão)
    if inicio_conteudo < len(linhas):
        s = linhas[inicio_conteudo].strip()
        # título simples da edição (sem pontuação de frase)
        if re.fullmatch(r"御教え集第[一二三四五六七八九十百]+号", s):
            inicio_conteudo += 1
            while inicio_conteudo < len(linhas) and not linhas[inicio_conteudo].strip():
                inicio_conteudo += 1
        # ficha da edição 『御教え集』N号、昭和...発行
        if inicio_conteudo < len(linhas) and re.match(r"^『御教え集』", linhas[inicio_conteudo].strip()):
            inicio_conteudo += 1
            while inicio_conteudo < len(linhas) and not linhas[inicio_conteudo].strip():
                inicio_conteudo += 1

    # data de sessão: 昭和XX年X月X日 (no início da linha, possivelmente com
    # espaços de formatação antes)
    DATA_SESSAO = re.compile(r"^\s*(昭和[一二三四五六七八九十]+年[一二三四五六七八九十]+月[一二三四五六七八九十]+日)")

    def quebrar_prosa(texto_bruto: str) -> list[str]:
        """Quebra um trecho de prosa em blocos por quebras de frase (。！？)."""
        texto_bruto = re.sub(r"\s+", " ", texto_bruto).strip()
        if not texto_bruto:
            return []
        if len(texto_bruto) <= LONGO_MAX:
            return [texto_bruto]
        partes = re.split(r"(?<=[。！？])", texto_bruto)
        blocos, buf = [], ""
        for p in partes:
            buf += p
            if len(buf) >= LONGO_MAX * 0.6:
                blocos.append(buf.strip())
                buf = ""
        if buf.strip():
            blocos.append(buf.strip())
        return [b for b in blocos if b]

    falas: list[tuple[str, str]] = []
    bloco_atual: list[str] = []
    sessao_atual = ""

    def flush_bloco():
        nonlocal bloco_atual
        if bloco_atual:
            prosa = "".join(bloco_atual).strip()
            # junta a data da sessão ao primeiro bloco (marcador)
            blocos = quebrar_prosa(prosa)
            if blocos and sessao_atual:
                blocos[0] = f"{sessao_atual} {blocos[0]}"
                sessao_atual_ = sessao_atual
            for b in blocos:
                falas.append(("Meishu-Sama", b))
            bloco_atual = []

    for l in linhas[inicio_conteudo:]:
        s = l.strip()
        if not s:
            continue
        # linha de data = início de nova sessão
        m = DATA_SESSAO.match(l)
        if m:
            flush_bloco()
            sessao_atual = m.group(1)
            continue
        # ignora marcadores puramente tipográficos de separação
        if re.fullmatch(r"[―\-＝=·・\s]+", s):
            continue
        bloco_atual.append(s)

    flush_bloco()
    return falas


EXTRATORES = {
    "gokowa": extrair_falas_gokowa,
    "gosuiji": extrair_falas_gosuiji,
    "mioshie": extrair_falas_mioshie,
    "mioshie_prosa": extrair_prosa_mioshie,
}


def main() -> None:
    if len(sys.argv) < 3:
        print("uso: .venv/bin/python scripts/retraduzir_colecao.py <gokowa|gosuiji|mioshie> <arquivo_jp> [--saida NOME] [--inicio N] [--fim N]")
        sys.exit(1)
    colecao = sys.argv[1]
    arquivo = sys.argv[2]
    saida_nome = None
    inicio, fim = 0, 10**9
    args = sys.argv[3:]
    for a in args:
        if a.startswith("--saida"):
            saida_nome = a.split("=")[1]
        elif a.startswith("--inicio"):
            inicio = int(a.split("=")[1])
        elif a.startswith("--fim"):
            fim = int(a.split("=")[1])

    if colecao not in EXTRATORES:
        print(f"coleção inválida: {colecao}")
        sys.exit(1)
    extrator = EXTRATORES[colecao]

    texto = Path(arquivo).read_text(encoding="utf-8")
    falas = extrator(texto)
    if not saida_nome:
        saida_nome = Path(arquivo).stem

    # Checkpoint
    ckpt = OUT / f"{saida_nome}.json"
    dados = {}
    if ckpt.exists():
        try:
            dados = json.loads(ckpt.read_text(encoding="utf-8"))
        except Exception:
            dados = {}
    if "falas" not in dados:
        dados["falas"] = {}

    fim = min(fim, len(falas))
    print(f"[{colecao}] {Path(arquivo).name}: {len(falas)} falas | processando {inicio}-{fim-1} | janela={JANELA}")
    print("=" * 60)

    for i in range(inicio, fim):
        if str(i) in dados["falas"] and dados["falas"][str(i)].get("pt_contextual"):
            continue
        quem, jp = falas[i]

        # Janela de contexto (5 anteriores)
        ctx = []
        for j in range(max(inicio, i - JANELA), i):
            f = dados["falas"].get(str(j))
            if f and f.get("pt_contextual"):
                ctx.append(f"[fala {j}] {f['quem']}: JP: {f['jp']} | PT: {f['pt_contextual']}")
        contexto_anterior = "\n".join(ctx).strip() or None

        print(f"\n[{i}] {quem} (ctx: {len(ctx)})", flush=True)
        pt_ctx = retraduzir(jp, quem, max_retries=15, contexto_anterior=contexto_anterior)
        dados["falas"][str(i)] = {
            "indice": i, "quem": quem, "jp": jp, "pt_contextual": pt_ctx,
            "contexto_anterior": contexto_anterior, "status": "retraduzido",
        }
        if (i - inicio + 1) % 5 == 0:
            OUT.mkdir(parents=True, exist_ok=True)
            ckpt.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ckpt salvo ({i-inicio+1}/{fim-inicio})", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    ckpt.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    n_falhas = sum(1 for f in dados["falas"].values() if not f.get("pt_contextual"))
    print(f"\nConcluído: {len(dados['falas'])} falas | falhas: {n_falhas}")


if __name__ == "__main__":
    main()
