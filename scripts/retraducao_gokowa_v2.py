#!/usr/bin/env python3
"""Retradução JP→PT do Gokōwa-roku (Suplemento) — versão 2.

Reescrita do zero (não é patch do pipeline anterior — ver
project_gokowa_suplemento_frankenstein_e_comparacao_deepseek na memória do
projeto: o arquivo já tem 38 backups de 15+ campanhas diferentes, mais um
patch em cima do pipeline antigo só pioraria isso).

Duas correções centrais em relação ao pipeline anterior
(scripts/retraducao_completa_gokowa.py + auditar_retraducao_gokowa.py),
diagnosticadas por auditoria (2026-08-15):

1. O prompt antigo citava `glossario_traducao.json` de nome mas nunca lia o
   arquivo — tinha uma sublista de termos copiada à mão no código Python,
   incompleta (faltavam 御守り→Ohikari, 五六七→Miroku, entre outros que
   causaram erro real). Aqui o glossário é carregado do arquivo de verdade
   e o trecho relevante é montado dinamicamente por turno, só com os termos
   que realmente aparecem naquela fala.
2. Não havia nenhuma validação determinística pós-tradução — nem contra
   violação de glossário, nem contra a IA devolver uma mensagem de erro do
   próprio pipeline ("o texto japonês não foi fornecido...") em vez de
   tradução, o que vazou para o resultado final em pelo menos 5 falas sem
   o auditor interno (também um LLM) perceber. Aqui as duas checagens são
   determinísticas (regex/substring), não dependem de outro LLM julgar.

Além disso, a pedido do usuário (2026-08-15): a fonte é um registro
manuscrito truncado — a tradução pode suavizar/completar levemente a frase
para soar natural em português, contanto que não mude nem acrescente fato
ou sentido. Literalidade não é a régua; fidelidade de sentido é.

Uso:
    python3 scripts/retraducao_gokowa_v2.py --lote LOTE.json --saida SAIDA.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

GLOSSARIO_PATH = RAIZ / "glossario_traducao.json"
MODELO = "deepseek-v4-flash"
MAX_RETRIES = 6

# Mensagens de recusa/erro do próprio pipeline que já vazaram como "tradução"
# no lote anterior — nunca aceitar uma resposta que contenha isto.
PADROES_RECUSA = [
    r"texto japon[êe]s n[ãa]o foi fornecido",
    r"n[ãa]o recebi o texto japon[êe]s",
    r"envie o trecho",
    r"envie a fala original",
    r"por favor,? forne[çc]a",
    r"por favor,? envie",
    r"aguardo o texto",
    r"n[ãa]o h[áa] texto japon[êe]s",
]
RE_RECUSA = re.compile("|".join(PADROES_RECUSA), re.IGNORECASE)


# glossario_traducao.json tem 718 termos, mas a maioria (454) são glosas de
# vocabulário comum (ex.: ぜんそく→"asma") cuja forma exata não precisa ser
# rígida — exigir a string literal geraria falso-positivo em toda variação
# de conjugação/sinônimo natural. Só entram na checagem OBRIGATÓRIA:
# (a) termos cujo valor começa com maiúscula (nome próprio/termo fixo, ex.
#     Ohikari, Miroku, "Grande Acerto de Contas") — 260 dos 718;
# (b) uma lista curada de termos minúsculos com erro real já confirmado em
#     auditoria (2026-08-15) apesar de não serem "nome próprio".
TERMOS_MINUSCULOS_CRITICOS = {
    "信者", "土人", "ニグロ", "ニグロ的", "黒人", "野蛮人", "野蛮人的趣味",
    "新しみ", "薬毒", "然毒", "昔のほうが新しい",
}


def carregar_glossario() -> dict[str, str]:
    return json.loads(GLOSSARIO_PATH.read_text(encoding="utf-8"))


def termo_core(valor: str) -> list[str]:
    """Extrai a(s) forma(s) aceitável(is) de uma entrada de glossário,
    descartando explicação entre parênteses OU depois de travessão/hífen
    (nota de uso, não faz parte do termo — ex. "Kannon-Sama — manter o
    honorífico..."), e alternativas separadas por barra/vírgula viram
    candidatos independentes (aceita qualquer um)."""
    sem_parenteses = re.sub(r"\([^)]*\)", "", valor)
    sem_nota = re.split(r"\s+[—–]\s+| - ", sem_parenteses)[0]
    candidatos = re.split(r"[/,;]", sem_nota)
    return [c.strip() for c in candidatos if len(c.strip()) >= 2]


def eh_termo_duro(jp_termo: str, candidatos: list[str]) -> bool:
    if jp_termo in TERMOS_MINUSCULOS_CRITICOS:
        return True
    return bool(candidatos and candidatos[0][:1].isupper())


def termos_aplicaveis(jp: str, glossario: dict[str, str]) -> list[tuple[str, list[str]]]:
    """Termos DUROS do glossário cuja forma japonesa aparece literalmente
    no texto-fonte desta fala (ver TERMOS_MINUSCULOS_CRITICOS acima para o
    critério de "duro").

    Termos de 1 caractere ficam de fora: japonês não tem espaço entre
    palavras, então um kanji isolado (ex. 道) colide por substring com
    qualquer palavra maior que o contenha e não tenha nada a ver (人道的
    "humanitário", 道教 "Taoísmo") — falso-positivo confirmado em teste
    (2026-08-15, turnos 14 e 40 do lote 1)."""
    aplicaveis = []
    for jp_termo, pt_valor in glossario.items():
        if jp_termo and len(jp_termo) >= 2 and jp_termo in jp:
            candidatos = termo_core(pt_valor)
            if candidatos and eh_termo_duro(jp_termo, candidatos):
                aplicaveis.append((jp_termo, candidatos))
    # remove duplicata quando um termo é substring de outro já capturado
    # com a mesma resposta esperada (ex.: 御守 dentro de 御守り, ambos "Ohikari")
    aplicaveis.sort(key=lambda t: -len(t[0]))
    final = []
    for jp_termo, candidatos in aplicaveis:
        if any(jp_termo in outro and candidatos == c2 for outro, c2 in final):
            continue
        final.append((jp_termo, candidatos))
    return final


def checar_glossario(pt: str, termos: list[tuple[str, list[str]]]) -> list[str]:
    """Retorna lista de violações: termo japonês cuja(s) forma(s) esperada(s)
    não aparece(m) em nenhuma variação simples no texto traduzido."""
    violacoes = []
    pt_lower = pt.lower()
    for jp_termo, candidatos in termos:
        if not any(c.lower() in pt_lower for c in candidatos):
            violacoes.append(f"{jp_termo} → deveria conter \"{candidatos[0]}\"")
    return violacoes


PROMPT_BASE = """Você é um tradutor japonês→português especializado nesta obra religiosa
(Gokōwa-roku — registros manuscritos de sessões de perguntas e respostas
com Meishu-Sama, década de 1940).

## Natureza da fonte e o que fazer com o truncamento

O japonês-fonte é um registro manuscrito de fala, frequentemente truncado,
telegráfico ou elíptico — não é prosa literária, e ele SOA truncado mesmo
para um leitor japonês. Sua tarefa NÃO é copiar essa truncagem para o
português (isso produz uma tradução de aparência automática, tipo Google
Tradutor) — é RECONSTRUIR a frase como algo que soa natural, completo e
fluido em português, preservando exatamente o mesmo sentido, sem inventar
nem perder nada. Literalidade de estrutura NÃO é o objetivo; fidelidade de
sentido é.

### Exemplos (a mesma sessão desta obra — estude a diferença)

EXEMPLO A — resolução de referência elíptica:
Contexto: a fala anterior acabou de estabelecer que se está falando do
compositor Shinpei Nakayama.
JP: あれはこのごろあまり作りませんね。
RUIM (decalque, evite): "Aquilo ultimamente não se compõe muito, não é?"
  — trata あれ como uma COISA; fica vago e soa traduzido ao pé da letra.
BOM (reconstruído): "Ele não tem composto muito, ultimamente, não é?"
  — あれ aqui retoma a PESSOA mencionada na fala anterior (Nakayama), não
  uma coisa; mesmo sentido, mas natural e sem ambiguidade.

EXEMPLO B — sujeito implícito precisa virar explícito:
JP: ――残したのは中山晋平です。
RUIM (decalque, evite): "Quem deixou foi Shinpei Nakayama."
  — o japonês omite o objeto (deixou O QUÊ?); copiar a omissão em
  português soa cortado.
BOM (reconstruído): "Quem deixou obra foi Shinpei Nakayama."
  — o objeto implícito no japonês (uma obra/legado musical) é tornado
  explícito; nenhuma informação nova foi inventada, só o que a elipse
  japonesa já indicava pelo contexto.

EXEMPLO C — nome de obra/título nunca fica em japonês:
JP: ――『越後獅子』や『カッポレ』はなかなか名曲です。
RUIM (proibido): deixar 『越後獅子』 e 『カッポレ』 sem tradução, copiados
  do japonês para dentro da resposta em português.
BOM (correto): "'Echigo-jishi' e 'Kappore' são verdadeiras obras-primas."
  — títulos de peças musicais clássicas japonesas romanizados; nunca
  caracteres japoneses soltos numa resposta que deveria ser 100% português.

EXEMPLO D — negação dupla truncada precisa virar frase completa:
JP: なにか祟っているか、罪が深いと取れないんですよ。
RUIM (decalque, evite): "Alguma coisa amaldiçoando ou pecado profundo não
  se pode tomar." — segue a ordem japonesa ao pé da letra; incompreensível
  em português.
BOM (reconstruído): "Não dá para dizer se é uma maldição ou um pecado
  profundo." — reconstrói a negação dupla do japonês truncado numa frase
  natural e completa, sem inventar nem perder sentido.

Antes de responder, pergunte-se: esta frase soa como algo que uma pessoa
diria naturalmente em português, ou soa como tradução automática/decalque?
Se soar como tradução automática, reescreva antes de responder.

## Regras obrigatórias (nunca violar)

1. NUNCA inverta sujeito/objeto — quem faz a ação no japonês continua
   fazendo a ação na tradução.
2. Identifique os papéis dos falantes pelo contexto da conversa; se uma
   referência ficar ambígua, esclareça com [colchetes] SEM inventar
   conteúdo novo — só torne explícito o que o contexto já indica.
3. Preserve todo nome próprio, data, número e citação entre aspas
   exatamente como no original (nem aproximar, nem arredondar).
4. Termos como Johrei, Ohikari, Kannon, Meishu-Sama nunca são traduzidos.
5. Glossário de termos fixos desta obra — USE EXATAMENTE a forma indicada
   sempre que o termo japonês aparecer no trecho:
{glossario_bloco}
6. NUNCA deixe nenhum trecho em japonês (hiragana/katakana/kanji) na
   resposta — mesmo nomes de obra, música ou livro entre 『』/「」 precisam
   virar romanização ou tradução (ex.: 『越後獅子』 → "Echigo-jishi", nunca
   deixar os caracteres japoneses originais).

{turno_anterior}
{contexto_extra}

Traduza esta fala do personagem "{quem}":

### JAPONÊS:
{jp}

### TRADUÇÃO (responda SÓ com o texto traduzido, sem aspas externas, sem comentário):
"""


RE_JAPONES = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")


def montar_prompt(jp: str, quem: str, termos: list[tuple[str, list[str]]], contexto_extra: str, turno_anterior: str = "") -> str:
    if termos:
        linhas = [f"   - {jp_t} → \"{cands[0]}\"" for jp_t, cands in termos]
        bloco = "\n".join(linhas)
    else:
        bloco = "   (nenhum termo do glossário fixo aparece nesta fala)"
    ta = ""
    if turno_anterior:
        ta = f"## Turno anterior da conversa (só contexto — não traduzir de novo)\n{turno_anterior}\n"
    return PROMPT_BASE.format(glossario_bloco=bloco, contexto_extra=contexto_extra, turno_anterior=ta, quem=quem, jp=jp)


def segmentar_fala(jp: str, limite: int = 200) -> list[str]:
    """Divide uma fala longa em segmentos menores por quebra de frase.

    Falas curtas retornam como um único segmento. Turnos acima do limite
    tendem a fazer o modelo devolver resposta vazia (confirmado em teste,
    2026-08-15: das 18 falhas por "resposta vazia" no lote 1, todas eram os
    turnos mais longos — média dos aprovados foi 66 chars, máximo 383;
    falhas começaram em 334 chars)."""
    if len(jp) <= limite:
        return [jp]
    partes = re.split(r"(?<=[。！？.!?…])", jp)
    minimo = 40
    segmentos = []
    buf = ""
    for p in partes:
        buf += p
        if len(buf) >= minimo and (buf.endswith(("。", "！", "？", ".", "!", "?", "…")) or len(buf) >= limite * 1.2):
            segmentos.append(buf.strip())
            buf = ""
    if buf.strip():
        segmentos.append(buf.strip())
    if len(segmentos) <= 1 and len(jp) > limite * 1.5:
        segmentos = [jp[i:i + limite] for i in range(0, len(jp), limite)]
    return [s for s in segmentos if s.strip()]


def traduzir_turno(jp: str, quem: str, glossario: dict[str, str], contexto_extra: str = "") -> dict:
    segmentos = segmentar_fala(jp)
    if len(segmentos) == 1:
        return _traduzir_segmento(segmentos[0], quem, glossario, contexto_extra)

    partes_pt = []
    historico_geral = []
    status_geral = "aprovado"
    tentativas_total = 0
    termos_geral = []
    for i, seg in enumerate(segmentos):
        r = _traduzir_segmento(seg, quem, glossario, contexto_extra, rotulo_segmento=f"{i+1}/{len(segmentos)}")
        partes_pt.append(r["pt"])
        historico_geral.extend(r["historico"])
        tentativas_total += r["tentativas"]
        termos_geral.extend(r["termos_glossario_aplicaveis"])
        if r["status"] != "aprovado":
            status_geral = "max_tentativas"

    return {
        "pt": " ".join(p for p in partes_pt if p),
        "status": status_geral,
        "tentativas": tentativas_total,
        "historico": historico_geral,
        "termos_glossario_aplicaveis": termos_geral,
        "segmentado_em": len(segmentos),
    }


def _traduzir_segmento(jp: str, quem: str, glossario: dict[str, str], contexto_extra: str = "", rotulo_segmento: str = "") -> dict:
    from goshinsho.services.agentic_search import _client

    termos = termos_aplicaveis(jp, glossario)
    prompt = montar_prompt(jp, quem, termos, contexto_extra)

    historico = []
    reforco = ""
    for tentativa in range(MAX_RETRIES):
        try:
            resp = _client().chat.completions.create(
                model=MODELO,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt + reforco}],
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip().strip('"').strip()
            raw = re.sub(r"^(Meishu-Sama|Interlocutor):\s*", "", raw)
        except Exception as e:
            historico.append({"tentativa": tentativa, "erro_api": str(e)})
            time.sleep(1 + tentativa)
            continue

        problemas = []

        if not raw or len(re.sub(r"\s", "", raw)) < 3:
            problemas.append("resposta vazia ou trivial")

        if RE_RECUSA.search(raw):
            problemas.append("resposta contém padrão de recusa/erro do próprio pipeline")

        jp_termina = re.search(r"[。！？.!?]\s*$", jp.strip())
        pt_termina = re.search(r"[.!?]\s*$", raw.rstrip())
        if jp_termina and not pt_termina and raw:
            problemas.append("tradução parece cortada (japonês termina em pontuação, português não)")

        violacoes = checar_glossario(raw, termos) if raw and not problemas else []
        if violacoes:
            problemas.append("violação de glossário: " + "; ".join(violacoes))

        historico.append({"tentativa": tentativa, "segmento": rotulo_segmento, "pt": raw, "problemas": problemas})

        if not problemas:
            return {"pt": raw, "status": "aprovado", "tentativas": tentativa + 1, "historico": historico, "termos_glossario_aplicaveis": [t for t, _ in termos]}

        if "resposta vazia ou trivial" in problemas:
            # reforço curto e direto funciona melhor que descrição técnica
            # do problema para o caso de resposta vazia (lição do pipeline
            # anterior, scripts/retraducao_completa_gokowa.py).
            reforco = "\n\nNão deixe a resposta em branco. Escreva a tradução completa agora, só o texto traduzido:"
        else:
            reforco = "\n\nSUA RESPOSTA ANTERIOR TEVE PROBLEMA(S), corrija e responda de novo:\n- " + "\n- ".join(problemas)

    return {"pt": raw if 'raw' in dir() else "", "status": "max_tentativas", "tentativas": MAX_RETRIES, "historico": historico, "termos_glossario_aplicaveis": [t for t, _ in termos]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lote", required=True, help="JSON com lista de turnos [{idx, quem, texto}, ...]")
    ap.add_argument("--saida", required=True)
    ap.add_argument("--contexto", default="", help="Contexto extra opcional para este lote (ex.: cena/sessão)")
    args = ap.parse_args()

    glossario = carregar_glossario()
    turnos = json.loads(Path(args.lote).read_text(encoding="utf-8"))
    print(f"Glossário: {len(glossario)} termos. Lote: {len(turnos)} turnos.")

    saida_path = Path(args.saida)
    resultados = {}
    if saida_path.exists():
        try:
            resultados = json.loads(saida_path.read_text(encoding="utf-8")).get("resultados", {})
        except Exception:
            pass

    for i, turno in enumerate(turnos):
        idx = turno["idx"]
        if str(idx) in resultados and resultados[str(idx)].get("status") == "aprovado":
            continue
        quem, jp = turno["quem"], turno["texto"]
        print(f"[{i+1}/{len(turnos)}] turno {idx} ({quem}, {len(jp)} chars)...", flush=True)
        r = traduzir_turno(jp, quem, glossario, args.contexto)
        resultados[str(idx)] = {"idx": idx, "quem": quem, "jp": jp, **r}
        print(f"    -> {r['status']} em {r['tentativas']} tentativa(s)", flush=True)
        if (i + 1) % 10 == 0:
            saida_path.write_text(json.dumps({"resultados": resultados}, ensure_ascii=False, indent=2), encoding="utf-8")

    saida_path.write_text(json.dumps({"resultados": resultados}, ensure_ascii=False, indent=2), encoding="utf-8")

    aprovados = sum(1 for v in resultados.values() if v.get("status") == "aprovado")
    max_tent = sum(1 for v in resultados.values() if v.get("status") == "max_tentativas")
    tentativas_media = sum(v.get("tentativas", 1) for v in resultados.values()) / max(len(resultados), 1)
    print(f"\nConcluído: {len(resultados)} turnos | aprovados: {aprovados} | max_tentativas (precisa revisão manual): {max_tent} | média de tentativas: {tentativas_media:.2f}")


if __name__ == "__main__":
    main()
