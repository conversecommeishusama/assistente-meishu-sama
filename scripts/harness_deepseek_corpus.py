#!/usr/bin/env python3
"""Harness DeepSeek para correção manual/semântica do corpus, com SEGURANÇA.

Substitui o `claude -p` (Claude Code) por chamadas à API DeepSeek, dando ao
modelo ferramentas de EDIÇÃO CONTROLADA (não só leitura). O modelo decide qual
trecho corrigir, mas TODA edição passa por travas de segurança:

1. O trecho-alvo (`de`) DEVE existir literalmente no arquivo (senão a edição é
   recusada).
2. Backup automático da obra ANTES da primeira gravação.
3. `valida_ancoras(obra, novo_texto)` DEVE passar (senão a edição é revertida e
   o caso marcado como DUVIDA).
4. Fonte + staging gravados idênticos.
5. Log completo de cada edição (para auditoria).

Uso:
    python3 scripts/harness_deepseek_corpus.py <lote.json> <resultado.json> <n_lote>
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "goshinsho"))

import mescla_e_aplica as me  # valida_ancoras
from goshinsho.services import agentic_search as ag  # _client() DeepSeek

PT = RAIZ / "livros_publicacao_pt_revisado"
ST = RAIZ / "reports/livros_trabalho/pt"

MODELO = "deepseek-v4-flash"
MAX_TOKENS = 6000

# Ferramentas que o modelo pode usar (edições controladas)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ler_trecho",
            "description": "Lê um trecho do arquivo PT de uma obra, na posição aproximada (offset) com tamanho. Use para ver o contexto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "obra": {"type": "string", "description": "Nome do arquivo .txt"},
                    "offset": {"type": "integer", "description": "Posição de início"},
                    "tamanho": {"type": "integer", "description": "Qtd de caracteres (padrão 2000)"},
                },
                "required": ["obra", "offset"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_no_arquivo",
            "description": "Busca um trecho literal no arquivo PT da obra e retorna a posição da 1ª ocorrência (ou -1).",
            "parameters": {
                "type": "object",
                "properties": {
                    "obra": {"type": "string"},
                    "trecho": {"type": "string"},
                },
                "required": ["obra", "trecho"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "substituir_trecho",
            "description": "Substitui UM trecho literal exato (de) por outro (para) no arquivo PT da obra. O trecho DEVE existir exatamente (a ferramenta recusa se não existir). Faz backup automático e valida âncora antes de gravar. Se a âncora quebrar, NÃO grava e retorna erro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "obra": {"type": "string"},
                    "de": {"type": "string", "description": "Trecho exato atual a substituir"},
                    "para": {"type": "string", "description": "Novo texto"},
                },
                "required": ["obra", "de", "para"],
            },
        }
    },
]


def _client():
    return ag._client()


def _texto_obra(obra: str) -> str | None:
    p = PT / obra
    if p.exists():
        return p.read_text(encoding="utf-8")
    return None


def _buscar(obra: str, trecho: str) -> int:
    t = _texto_obra(obra)
    if t is None:
        return -1
    return t.find(trecho)


def _substituir(obra: str, de: str, para: str, ja_backup: set[str]) -> dict:
    """Substitui de->para com segurança. Retorna dict com status."""
    t = _texto_obra(obra)
    if t is None:
        return {"ok": False, "erro": f"obra não encontrada: {obra}"}
    if not de:
        return {"ok": False, "erro": "trecho 'de' vazio"}
    # o trecho deve existir
    if de not in t:
        return {"ok": False, "erro": f"trecho 'de' NÃO encontrado literalmente: '{de[:60]}...'"}
    # deve ser único ou o modelo escolheu a ocorrência — para segurança, exigir 1 ocorrência
    n = t.count(de)
    if n != 1:
        return {"ok": False, "erro": f"trecho 'de' aparece {n}x (exigido 1x para segurança): '{de[:50]}...'"}
    novo = t.replace(de, para)
    # backup (uma vez por obra)
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if obra not in ja_backup:
        shutil.copy(PT / obra, PT / f"{obra}.bak_deepseek_{carimbo}")
        ja_backup.add(obra)
    # validar âncora ANTES de gravar
    try:
        ok, motivo = me.valida_ancoras(obra, novo)
        if not ok:
            return {"ok": False, "erro": f"valida_ancoras FALHOU (não gravado): {str(motivo)[:80]}"}
    except Exception as e:
        return {"ok": False, "erro": f"erro valida_ancoras: {str(e)[:80]}"}
    # gravar fonte + staging
    (PT / obra).write_text(novo, encoding="utf-8")
    (ST / obra).write_text(novo, encoding="utf-8")
    return {"ok": True, "novo_tamanho": len(novo), "antigo_tamanho": len(t)}


def _aplicar_decisao(obra: str, de: str, texto_correto: str, ja_backup: set[str]) -> dict:
    """Aplica o texto_correto decidido pelo modelo ao trecho real da obra.

    Segurança: o trecho-alvo (de, ou o trecho atual se `de` não existir mais)
    deve ser encontrado de forma ÚNICA; backup automático; valida_ancoras antes
    de gravar; fonte + staging idênticos.
    """
    t = (PT / obra).read_text(encoding="utf-8") if (PT / obra).exists() else None
    if t is None:
        return {"ok": False, "erro": f"obra não encontrada: {obra}"}
    if not texto_correto or not de:
        return {"ok": False, "erro": "texto_correto ou 'de' vazio"}

    # o trecho-alvo: prefere o `de` (texto antigo sugerido); se não existir,
    # não consegue localizar com segurança -> DUVIDA
    if de not in t:
        return {"ok": False, "erro": f"trecho 'de' não encontrado literalmente no texto atual: '{de[:60]}...' (pode já ter sido corrigido ou reformulado)"}
    n = t.count(de)
    if n != 1:
        return {"ok": False, "erro": f"trecho 'de' aparece {n}x (exigido 1x): '{de[:50]}...'"}

    novo = t.replace(de, texto_correto)
    # backup (uma vez por obra)
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if obra not in ja_backup:
        shutil.copy(PT / obra, PT / f"{obra}.bak_deepseek_{carimbo}")
        ja_backup.add(obra)
    # validar âncora ANTES de gravar
    try:
        ok, motivo = me.valida_ancoras(obra, novo)
        if not ok:
            return {"ok": False, "erro": f"valida_ancoras FALHOU (não gravado): {str(motivo)[:80]}"}
    except Exception as e:
        return {"ok": False, "erro": f"erro valida_ancoras: {str(e)[:80]}"}
    # gravar fonte + staging
    (PT / obra).write_text(novo, encoding="utf-8")
    (ST / obra).write_text(novo, encoding="utf-8")
    return {"ok": True, "motivo": f"substituiu '{de[:40]}...' -> '{texto_correto[:40]}...'"}


def _executar_ferramenta(nome: str, args: dict, ja_backup: set[str]) -> str:
    try:
        if nome == "ler_trecho":
            obra = args["obra"]
            off = int(args.get("offset", 0))
            tam = int(args.get("tamanho", 2000))
            t = _texto_obra(obra)
            if t is None:
                return f"ERRO: obra {obra} não encontrada"
            return t[max(0, off):off + tam]
        elif nome == "buscar_no_arquivo":
            obra = args["obra"]
            trecho = args["trecho"]
            pos = _buscar(obra, trecho)
            return json.dumps({"posicao": pos, "obra": obra, "trecho": trecho[:80]}, ensure_ascii=False)
        elif nome == "substituir_trecho":
            r = _substituir(args["obra"], args["de"], args["para"], ja_backup)
            return json.dumps(r, ensure_ascii=False)
        else:
            return f"ERRO: ferramenta desconhecida {nome}"
    except Exception as e:
        return f"ERRO execução: {str(e)[:120]}"


def _glossario_resumo() -> str:
    """Glossário canônico, formatado como linhas 'termo -> forma (nota?)'."""
    try:
        g = json.loads((RAIZ / "glossario_traducao.json").read_text(encoding="utf-8"))
    except Exception:
        return "(glossário indisponível)"
    linhas = []
    if isinstance(g, dict):
        for termo, v in g.items():
            if isinstance(v, dict):
                forma = v.get("pt") or v.get("traducao") or v.get("forma") or ""
                linhas.append(f"{termo} -> {forma}")
            else:
                linhas.append(f"{termo} -> {v}")
    elif isinstance(g, list):
        for item in g:
            if isinstance(item, dict):
                termo = item.get("jp") or item.get("termo") or ""
                forma = item.get("pt") or item.get("traducao") or ""
                linhas.append(f"{termo} -> {forma}")
    return "\n".join(linhas[:800])  # limite de segurança


SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"


def _jp_janelas(obra: str) -> list[tuple[int, int, str]]:
    """(ini, fim, titulo) de cada artigo no JP, pelas jp_anchor do spec
    (mesma lógica de ajuste_lote_helper.py — alinhamento PRECISO, não proporção)."""
    try:
        texto = (RAIZ / "reports/livros_trabalho/jp" / obra).read_text(encoding="utf-8")
        sp = json.loads((SPEC_DIR / f"{obra}.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    arts = sp.get("articles", [])
    if not arts:
        return [(0, len(texto), "")]
    ini = []
    cur = 0
    for a in arts:
        anc = a.get("jp_anchor", "")
        p = texto.find(anc, cur) if anc else -1
        if p < 0:
            p = texto.find(anc) if anc else -1
        ini.append(p)
        if p >= 0:
            cur = p + len(anc)
    out = []
    for i, a in enumerate(arts):
        s = ini[i]
        e = next((ini[j] for j in range(i + 1, len(arts)) if ini[j] >= 0), len(texto))
        out.append((s, e, a.get("title_jp") or a.get("title_pt") or ""))
    return out


def _artigo_da_chave(chave: str) -> int | None:
    """Extrai o índice de artigo da chave ('obra|artigo|...|...'),
    ignorando prefixos de pilha (REFORMAR:, C:, MESA:, etc.)."""
    import re as _re
    k = _re.sub(r"^(REFORMAR:|C:|A:|B:|MESA:)", "", chave)
    partes = k.split("|")
    if len(partes) >= 2 and partes[1].isdigit():
        return int(partes[1])
    return None


def _extrair_json(texto: str) -> str | None:
    """Extrai UM objeto JSON balanceado do texto (robusto a texto ao redor,
    múltiplos JSONs e markdown). Retorna o primeiro JSON válido ou None."""
    if not texto:
        return None
    i = texto.find("{")
    while i != -1:
        # percorrer balanceando chaves, respeitando strings
        prof = 0
        em_string = False
        escape = False
        for j in range(i, len(texto)):
            ch = texto[j]
            if em_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    em_string = False
                continue
            if ch == '"':
                em_string = True
            elif ch == "{":
                prof += 1
            elif ch == "}":
                prof -= 1
                if prof == 0:
                    cand = texto[i:j + 1]
                    try:
                        json.loads(cand)
                        return cand
                    except Exception:
                        break
        i = texto.find("{", i + 1)
    return None


def processar_casos(casos: list[dict], resultado_path: Path, n_lote: int,
                    aplicar: bool = True) -> None:
    """Processa casos com DeepSeek.

    Se aplicar=True: aplica as edições com segurança (backup, âncora, fonte+staging).
    Se aplicar=False (MODO VERIFICAÇÃO): decide SEM editar — registra o
    texto_correto proposto na nota, para revisão de escopo antes de aplicar.
    """
    resultados = []
    ja_backup: set[str] = set()
    cont = {"total": len(casos), "aplicado": 0, "sem_acao": 0, "duvida": 0, "erro": 0}
    glossario = _glossario_resumo()

    # RESUMIBILIDADE: carregar resultado parcial existente e pular processados
    ja_processadas: set[str] = set()
    if resultado_path.exists():
        try:
            prev = json.loads(resultado_path.read_text(encoding="utf-8"))
            for c in prev.get("casos", []):
                ja_processadas.add(c["chave"])
                if c["resultado"] == "APLICADO":
                    cont["aplicado"] += 1
                elif c["resultado"] == "SEM_ACAO":
                    cont["sem_acao"] += 1
                elif c["resultado"] == "ERRO":
                    cont["erro"] += 1
                else:
                    cont["duvida"] += 1
            resultados = list(prev.get("casos", []))
        except Exception:
            ja_processadas = set()
        if ja_processadas:
            print(f"  [resume] {len(ja_processadas)} casos já processados, retomando do restante")

    # JP: para o modelo conferir o sentido (ferramenta de leitura)
    JP = RAIZ / "reports/livros_trabalho/jp"

    for idx, caso in enumerate(casos):
        chave = caso["chave"]
        if chave in ja_processadas:
            continue
        obra = caso.get("obra", chave.split("|")[0])
        de = caso.get("de", "")
        para = caso.get("para", "")
        nota_decisao = caso.get("nota_decisao", "")
        lim = caso.get("lim") or [0, 0]
        # PRÉ-CARREGAR o contexto PT e JP (para o modelo ler SEM tool_calls)
        texto_pt = (PT / obra).read_text(encoding="utf-8") if (PT / obra).exists() else ""
        ini = max(0, lim[0] - 400)
        fim = min(len(texto_pt), lim[1] + 400)
        ctx_pt = texto_pt[ini:fim] if texto_pt else "(obra PT não encontrada)"
        jp_path = JP / obra
        texto_jp = jp_path.read_text(encoding="utf-8") if jp_path.exists() else ""
        # alinhamento JP PRECISO: pelo artigo (jp_anchor do spec), não por proporção
        ctx_jp = "(obra JP não encontrada)"
        if texto_jp:
            art = _artigo_da_chave(chave)
            janelas = _jp_janelas(obra)
            if janelas and art is not None and 0 <= art < len(janelas):
                s, e, t = janelas[art]
                ctx_jp = f"[artigo {art}: {t}]\n" + texto_jp[s:e]
            else:
                # fallback: janela proporcional ampla (600 chars) se não houver spec
                prop = lim[0] / max(1, len(texto_pt)) if texto_pt else 0
                jp_ini = max(0, int(prop * len(texto_jp)) - 600)
                jp_fim = min(len(texto_jp), int(prop * len(texto_jp)) + 600)
                ctx_jp = texto_jp[jp_ini:jp_fim]
        # montar prompt do caso — FLUXO SEMÂNTICO OBRIGATÓRIO, contexto embutido
        if aplicar:
            modo_linha = ("3. DECIDA SEMANTICAMENTE: o trecho atual está errado? Qual é a tradução CORRETA "
                          "segundo o JP? (o 'para' é só uma SUGESTÃO — confirme/ajuste pelo JP).")
        else:
            modo_linha = ("3. JULGUE SEMANTICAMENTE (MODO VERIFICAÇÃO — VOCÊ NÃO EDITA NADA): o trecho atual "
                          "está errado? Se sim, qual seria a tradução CORRETA segundo o JP? "
                          "(o 'para' é só uma SUGESTÃO — confirme/ajuste pelo JP). NÃO aplique nada.")
        sys_msg = (
            "Você é um revisor de tradução do corpus Goshinsho (textos de Meishu-Sama), "
            "especialista em japonês e português. O trabalho é LINHA A LINHA, DE FORMA SEMÂNTICA, "
            "um caso por vez — NUNCA substituição direta/mecânica.\n\n"
            "Você receberá: (a) o CONTEXTO do texto em português ao redor do trecho, e "
            "(b) o CONTEXTO do japonês original correspondente.\n\n"
            "Para CADA caso:\n"
            "1. LEIA o contexto PT fornecido.\n"
            "2. LEIA o contexto JP fornecido e confirme o sentido.\n"
            f"{modo_linha}\n"
            "4. Responda em JSON:\n"
            "   {\"resultado\": \"APLICADO\"|\"SEM_ACAO\"|\"DUVIDA\", "
            "\"trecho_alvo\": \"O trecho EXATO como está no contexto PT que precisa mudar (se APLICADO)\", "
            "\"texto_correto\": \"o trecho corrigido (se APLICADO)\", "
            "\"justificativa\": \"...\", \"nota\": \"...\"}\n\n"
            "REGRAS:\n"
            "- **REGRAGRAVE (âncora): só marque APLICADO se o trecho problemático** "
            "estiver LITERALMENTE PRESENTE no CONTEXTO PT fornecido acima. "
            "Se o 'de' (ou o trecho problemático) NÃO estiver no contexto PT, "
            "o problema não existe mais no texto atual -> SEM_ACAO (nada a corrigir aqui).\n"
            "- **trecho_alvo é OBRIGATÓRIO quando APLICADO**: deve ser o trecho LITERAL "
            "exatamente como aparece no contexto PT atual (sem inventar, sem generalizar), "
            "e deve ser ÚNICO o suficiente para localizar. O trecho_alvo é o que será "
            "substituído por texto_correto.\n"
            "- **AVALIE A QUALIDADE DA APLICAÇÃO ATUAL**: mesmo que o 'de' não exista mais, "
            "verifique se o trecho que está NO LUGAR dele no contexto PT é uma tradução "
            "CORRETA e de qualidade segundo o JP. Sinais de má aplicação a detectar:\n"
            "   * texto corrompido ou frase inteira colocada no lugar de trecho curto\n"
            "   * duplicação (ex: 'Kannon-Sama-Sama')\n"
            "   * gênero/concordância inconsistente (ex: 'obrigado' vs 'obrigada' no mesmo artigo)\n"
            "   * tradução infiel ao JP (sentido errado, termo trocado)\n"
            "   Se o texto atual no lugar tem esses problemas -> APLICADO com texto_correto.\n"
            "- Se o texto já estiver correto: SEM_ACAO.\n"
            "- Se não conseguir decidir com segurança pelo JP: DUVIDA (NÃO edite).\n"
            "- NUNCA invente texto. O texto_correto deve ser a tradução fiel ao JP.\n"
            "- Termos doutrinários/consagrados: siga o glossário canônico abaixo "
            "(a forma consagrada VENCE tradução livre).\n"
            "- Responda APENAS com o JSON (sem markdown, sem texto extra).\n\n"
            f"=== GLOSSÁRIO CANÔNICO (termos doutrinários) ===\n{glossario}"
        )
        user_msg = (
            f"CASO {idx + 1} de {len(casos)} (chave {chave}, obra {obra}):\n"
            f"SUGESTÃO de texto antigo ('de'): {de}\n"
            f"SUGESTÃO de texto novo ('para'): {para}\n"
            + (f"\nDECISÃO DO USUÁRIO (já definida — deve ser respeitada): {nota_decisao}\n" if nota_decisao else "")
            + f"\n=== CONTEXTO EM PORTUGUÊS (ao redor do trecho) ===\n{ctx_pt}\n\n"
            f"=== CONTEXTO EM JAPONÊS (correspondente) ===\n{ctx_jp}\n\n"
            "Decida semanticamente e responda APENAS o JSON final."
        )
        try:
            # RETRY: o deepseek-v4-flash às vezes "vaza" a sintaxe tool_call ou
            # devolve resposta vazia. Tentamos até 3x com reforço progressivo.
            resp = None
            final = ""
            for tentativa in range(3):
                reforco = ""
                if tentativa == 1:
                    reforco = "\n\nIMPORTANTE: responda APENAS o JSON puro, sem markdown, sem ```json, sem texto extra, sem chamada de ferramenta. Nada além do JSON."
                elif tentativa == 2:
                    reforco = "\n\nATENÇÃO: sua resposta anterior foi inválida (vazia ou não-JSON). Responda EXATAMENTE neste formato, nada mais:\n{\"resultado\": \"APLICADO\" ou \"SEM_ACAO\" ou \"DUVIDA\", \"texto_correto\": \"...\", \"justificativa\": \"...\"}"
                resp = _client().chat.completions.create(
                    model=MODELO,
                    max_tokens=MAX_TOKENS,
                    messages=[
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": user_msg + reforco},
                    ],
                    # sem tools: o contexto já está embutido, o modelo só decide
                )
                final = resp.choices[0].message.content or ""
                # parse robusto: um único objeto JSON balanceado (sem capturar 2 JSONs)
                m = _extrair_json(final)
                if m is not None:
                    try:
                        r = json.loads(m)
                        if r.get("resultado") in ("APLICADO", "SEM_ACAO", "DUVIDA"):
                            break  # resposta válida
                    except Exception:
                        pass
                # se chegou aqui, inválida/vazia -> tenta de novo (reforço)
                final = ""
            m = _extrair_json(final)
            if m is not None:
                try:
                    r = json.loads(m)
                    res = r.get("resultado", "DUVIDA")
                    nota = r.get("justificativa", "") + " | " + r.get("nota", "")
                    texto_correto = r.get("texto_correto", "")
                    trecho_alvo = r.get("trecho_alvo", "")
                except Exception:
                    res, nota = "DUVIDA", "resposta não-JSON: " + final[:80]
                    texto_correto = ""
                    trecho_alvo = ""
            else:
                res, nota = "DUVIDA", "sem JSON na resposta (após 3 tentativas)"
                texto_correto = ""
                trecho_alvo = ""

            editou = False
            if res == "APLICADO" and texto_correto:
                if not aplicar:
                    # MODO VERIFICAÇÃO: registra a proposta SEM editar
                    cont["aplicado"] += 1
                    nota = nota + f" | PROPOSTO (verificação, não aplicado): {texto_correto[:80]}"
                else:
                    # MODO APLICAÇÃO SEMÂNTICA: usa o trecho_alvo (trecho literal
                    # no texto atual indicado pelo modelo), NUNCA o 'de' do
                    # checkpoint desatualizado. Se trecho_alvo estiver vazio,
                    # recusa (DUVIDA) em vez de adivinhar.
                    alvo = trecho_alvo if trecho_alvo else de
                    if trecho_alvo:
                        aplicacao = _aplicar_decisao(obra, trecho_alvo, texto_correto, ja_backup)
                    else:
                        aplicacao = {"ok": False, "erro": "modelo não forneceu trecho_alvo (não aplicado)"}
                    if aplicacao.get("ok"):
                        editou = True
                        cont["aplicado"] += 1
                        nota = nota + " | APLICADO: " + str(aplicacao.get("motivo", ""))
                    else:
                        # não conseguiu aplicar (âncora quebrou ou trecho não achado)
                        cont["duvida"] += 1
                        res = "DUVIDA"
                        nota = nota + " | NÃO APLICADO: " + str(aplicacao.get("erro", ""))
            elif res == "APLICADO":
                cont["duvida"] += 1
                res = "DUVIDA"
                nota = nota + " | APLICADO sem texto_correto (não aplicado)"
            elif res == "SEM_ACAO":
                cont["sem_acao"] += 1
            else:
                cont["duvida"] += 1
            resultados.append({"chave": chave, "resultado": res, "nota": nota, "editou": editou})
            # SALVAMENTO INCREMENTAL: grava o parcial a cada N casos (resumível)
            if len(resultados) % 10 == 0 or len(resultados) == cont["total"]:
                resultado_path.write_text(json.dumps({
                    "lote": n_lote,
                    "resumo": cont,
                    "casos": resultados,
                }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            cont["erro"] += 1
            resultados.append({"chave": chave, "resultado": "ERRO", "nota": str(e)[:120]})
            if len(resultados) % 10 == 0:
                resultado_path.write_text(json.dumps({
                    "lote": n_lote,
                    "resumo": cont,
                    "casos": resultados,
                }, ensure_ascii=False, indent=2), encoding="utf-8")

    resultado_path.write_text(json.dumps({
        "lote": n_lote,
        "resumo": cont,
        "casos": resultados,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"lote {n_lote}: {cont}")


def _tool_results(tool_calls, ja_backup):
    """Executa as tool_calls e retorna (tool_call, args, resultado)."""
    out = []
    for tc in tool_calls:
        fn = tc.function.name
        try:
            args = json.loads(tc.function.arguments or "{}")
        except Exception:
            args = {}
        res = _executar_ferramenta(fn, args, ja_backup)
        out.append((tc, args, res))
    return out


def main() -> None:
    if len(sys.argv) < 4:
        print("uso: harness_deepseek_corpus.py <lote.json> <resultado.json> <n_lote> [--verificar]")
        sys.exit(1)
    lote_path = Path(sys.argv[1])
    resultado_path = Path(sys.argv[2])
    n_lote = int(sys.argv[3])
    aplicar = "--verificar" not in sys.argv
    casos = json.loads(lote_path.read_text(encoding="utf-8"))
    print(f"lote {n_lote}: {len(casos)} casos (modo {'VERIFICAÇÃO (não edita)' if not aplicar else 'APLICA'})")
    processar_casos(casos, resultado_path, n_lote, aplicar=aplicar)


if __name__ == "__main__":
    main()
