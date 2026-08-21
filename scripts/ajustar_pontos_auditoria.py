#!/usr/bin/env python3
"""Ajustes pontuais da retradução por trechos (executor + auditor, até 3x).

Fluxo (decisão do usuário 18/08):
1. EXECUTOR corrige cada ponto: re-traduz a fala com JP + contexto (5 anteriores)
   + o erro apontado + a correção sugerida, com o GLOSSÁRIO COMPLETO no prompt
   e max_tokens=40000. Trabalho SEMÂNTICO (JP/PT lado a lado).
2. AUDITOR re-audita o ponto corrigido (mesmo SYSTEM_PROMPT com glossário
   completo, max_tokens=40000).
3. Se ainda ERRO → executor corrige de novo (até 3 tentativas).
4. Se após 3x o executor não conseguir → RELATÓRIO para decisão humana
   (não força).

Os pontos a corrigir = SOMA de duas listas:
  - Relatórios de glossário da execução (relatorios_glossario nos checkpoints)
  - ERRO_TRADUCAO da auditoria (reports/auditoria_colecoes/*.json)

Uso:
  .venv/bin/python scripts/ajustar_pontos_auditoria.py <arquivo_ckpt.json>
  # processa um arquivo de retradução; resume via checkpoint.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

from retraducao_completa_gokowa import (
    CONTEXTO_OBRA,
    EXEMPLO_REFERENCIA,
    PROMPT,
    carregar_glossario_completo,
    extrair_falas,
)  # noqa: E402
from retraduzir_colecao import EXTRATORES  # noqa: E402

OUT = RAIZ / "reports" / "retraducao_colecoes"
AUD_OUT = RAIZ / "reports" / "auditoria_colecoes"
REG_OUT = RAIZ / "reports" / "ajustes_pontuais"
MAX_TENTATIVAS = 3   # executor corrige até 3x
MAX_TOKENS = 40000   # janela de contexto (mesmo que não use toda)

# MESMO SYSTEM_PROMPT da auditoria (com glossário completo) — para re-auditar.
_spec = importlib.util.spec_from_file_location(
    "auditor_base", RAIZ / "scripts" / "auditar_lote_gokowa_api.py"
)
_auditor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_auditor)
SYSTEM_PROMPT_AUDITOR = _auditor.SYSTEM_PROMPT


def _client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")


def coletar_pontos(ckpt: dict) -> list[dict]:
    """SOMA dos pontos: relatórios de glossário da execução + (auditoria é
    lida por arquivo separado, pois o ckpt não guarda os erros)."""
    pontos = []
    falas = ckpt.get("falas", {})
    # 1) relatórios de glossário da execução
    for trecho, itens in (ckpt.get("relatorios_glossario") or {}).items():
        for item in itens:
            idx = str(item.get("indice"))
            f = falas.get(idx, {})
            if not f or not f.get("jp"):
                continue
            pontos.append({
                "indice": idx,
                "quem": f.get("quem"),
                "jp": f.get("jp"),
                "pt_atual": f.get("pt_contextual", ""),
                "origem": "relatorio_glossario",
                "detalhe": f"termo '{item.get('termo_jp')}' não usa forma aprovada: {item.get('formas')}",
                "sugestao": item.get("formas", [None])[0] if item.get("formas") else None,
            })
    return pontos


def coletar_erros_auditoria(arquivo_stem: str) -> list[dict]:
    """Lê a auditoria do arquivo e retorna os ERRO_TRADUCAO."""
    p = AUD_OUT / f"{arquivo_stem}.json"
    if not p.exists():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    erros = []
    for v in d.get("vereditos", []):
        if v.get("veredito") == "ERRO_TRADUCAO":
            erros.append({
                "indice": str(v.get("indice")),
                "erro_auditoria": v.get("erro"),
                "correcao_auditoria": v.get("correcao"),
            })
    return erros


def _chave_ord(chave) -> int:
    """Ordena chaves de fala: numéricas (diálogo) OU t{n} (prosa contínua)."""
    if isinstance(chave, str) and chave.startswith("t") and chave[1:].isdigit():
        return int(chave[1:])
    try:
        return int(chave)
    except (TypeError, ValueError):
        return 0


def montar_contexto(ckpt: dict, idx, janela: int = 5) -> str | None:
    falas = ckpt.get("falas", {})
    # chaves ordenadas (numéricas ou t{n}) — contexto = falas ANTERIORES a idx
    chaves_ord = sorted(falas.keys(), key=_chave_ord)
    try:
        pos = chaves_ord.index(str(idx))
    except ValueError:
        return None
    ctx = []
    for chave in chaves_ord[max(0, pos - janela):pos]:
        f = falas[chave]
        if f and f.get("pt_contextual"):
            ctx.append(f"[fala {chave}] {f['quem']}: JP: {f['jp']} | PT: {f['pt_contextual']}")
    return "\n".join(ctx).strip() or None


def executor_corrigir(fala: dict, erro: dict | None, contexto: str | None) -> str:
    """Re-traduz a fala com o erro/correção como reforço (semântico, glossário
    no prompt, max_tokens=40000)."""
    jp = fala["jp"]
    quem = fala["quem"]
    prompt_base = PROMPT.format(
        contexto=CONTEXTO_OBRA,
        exemplo=EXEMPLO_REFERENCIA,
        glossario_completo=carregar_glossario_completo(),
        jp=jp,
        quem=quem,
    )

    # reforço com o erro apontado + correção sugerida
    reforco = ""
    if erro and erro.get("erro_auditoria"):
        reforco = (
            "\n\nAUDITORIA APONTOU UM ERRO NESTA TRADUÇÃO. Corrija o problema "
            "semanticamente (JP/PT lado a lado), mantendo TODO o sentido do JP.\n"
            f"ERRO apontado: {erro['erro_auditoria']}\n"
        )
        if erro.get("correcao_auditoria"):
            reforco += f"CORREÇÃO SUGERIDA pela auditoria (avalie e aplique se correta): {erro['correcao_auditoria']}\n"
        reforco += "Responda apenas com a tradução corrigida."
    if contexto:
        reforco += f"\n\nCONTEXTO (falas anteriores):\n{contexto}"

    reforcos = [
        "",
        "\n\nResponda APENAS com a tradução corrigida, sem comentários.",
        "\n\nSaída: só o texto traduzido corrigido.",
        "\n\nNão deixe em branco. Corrija e responda a tradução.",
        "\n\nIMPORTANTE: sua resposta anterior veio vazia. Escreva a tradução corrigida agora.",
    ]
    ultimo_erro = None
    for tentativa in range(8):
        r = reforcos[tentativa] if tentativa < len(reforcos) else "\n\nCorrija agora."
        try:
            resp = _client().chat.completions.create(
                model="deepseek-v4-flash",
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt_base + reforco + r}],
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip().strip('"').strip()
            raw = re.sub(r"^(Meishu-Sama|Interlocutor)[:：]\s*", "", raw)
            if raw and len(re.sub(r"\s", "", raw)) >= 3:
                return raw
            raise ValueError("resposta vazia")
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            time.sleep(3 * (tentativa + 1))
    return ""


def auditor_verificar(fala: dict) -> str:
    """Re-audita a fala corrigida (mesma régua da auditoria). Retorna 'OK' ou 'ERRO'."""
    ultimo_erro = None
    for tentativa in range(5):
        try:
            prompt_usuario = (
                f"AUDITORIA DE TRADUÇÃO — fala índice {fala.get('indice')}\n"
                f"Falante: {fala.get('quem', '')}\n\n"
                f"--- JP (original) ---\n{fala.get('jp', '')}\n\n"
                f"--- PT (tradução a auditar) ---\n{fala.get('pt_contextual', '')}\n\n"
                "Compare o PT com o JP e responda com o JSON de veredito."
            )
            resp = _client().chat.completions.create(
                model="deepseek-v4-flash",
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_AUDITOR},
                    {"role": "user", "content": prompt_usuario},
                ],
            )
            texto = resp.choices[0].message.content or ""
            dados = _auditor.extrair_json(texto)
            if dados is None:
                raise ValueError("sem JSON")
            veredito = dados.get("veredito")
            if veredito == "OK":
                return "OK"
            if veredito == "ERRO_TRADUCAO":
                return "ERRO"
            raise ValueError(f"veredito inválido: {veredito}")
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            time.sleep(3 * (tentativa + 1))
    return "FALHA_API"


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: .venv/bin/python scripts/ajustar_pontos_auditoria.py <arquivo_ckpt.json>")
        sys.exit(1)
    ckpt_path = Path(sys.argv[1])
    if not ckpt_path.exists():
        print(f"checkpoint não existe: {ckpt_path}")
        sys.exit(1)

    stem = ckpt_path.stem
    ckpt = json.loads(ckpt_path.read_text(encoding="utf-8"))
    falas = ckpt.setdefault("falas", {})

    # RETOMADA (fix 18/08): se houver backup pré-ajustes, uma fala cujo
    # pt_contextual atual difere do backup JÁ FOI corrigida → pula (não
    # reprocessa, economiza API). O backup fica em reports/ajustes_pontuais/backup/.
    backup_path = REG_OUT / "backup" / f"{stem}.json.pre_ajustes"
    pre_falas = {}
    if backup_path.exists():
        try:
            pre_falas = json.loads(backup_path.read_text(encoding="utf-8")).get("falas", {})
        except Exception:
            pre_falas = {}

    # 1) pontos da execução (relatórios de glossário)
    pontos_exec = coletar_pontos(ckpt)
    # 2) erros da auditoria (ERRO_TRADUCAO)
    erros_aud = coletar_erros_auditoria(stem)
    erros_map = {e["indice"]: e for e in erros_aud}

    # união por índice (soma das duas listas, sem duplicar)
    indices_pontos = {p["indice"] for p in pontos_exec} | set(erros_map.keys())

    # RETOMADA: remove índices já corrigidos (pt atual != pt do backup pré-ajustes)
    if pre_falas:
        ja_corrigidos = [
            idx for idx in indices_pontos
            if falas.get(idx, {}).get("pt_contextual")
            and falas[idx]["pt_contextual"] != pre_falas.get(idx, {}).get("pt_contextual")
        ]
        if ja_corrigidos:
            indices_pontos -= set(ja_corrigidos)
            print(f"[{stem}] retomada: {len(ja_corrigidos)} pontos já corrigidos — pulando")

    print(f"[{stem}] pontos a corrigir (soma exec+auditoria): {len(indices_pontos)} "
          f"(exec {len(pontos_exec)} + audit {len(erros_aud)})")

    REG_OUT.mkdir(parents=True, exist_ok=True)
    relatorio = []
    for idx in sorted(indices_pontos, key=_chave_ord):
        f = falas.get(idx)
        if not f or not f.get("jp"):
            continue
        erro = erros_map.get(idx)
        print(f"\n  [fala {idx}] corrigindo (origem: {'auditoria' if erro else 'glossario'})...", flush=True)

        resolvido = False
        tentativas = []
        for tent in range(MAX_TENTATIVAS):
            contexto = montar_contexto(ckpt, idx)
            novo_pt = executor_corrigir(f, erro, contexto)
            if not novo_pt:
                tentativas.append({"tentativa": tent + 1, "status": "executor_falhou"})
                continue
            f["pt_contextual"] = novo_pt
            # auditor verifica
            resultado = auditor_verificar({
                "indice": idx, "quem": f.get("quem"), "jp": f.get("jp"), "pt_contextual": novo_pt,
            })
            tentativas.append({"tentativa": tent + 1, "status": resultado, "pt": novo_pt})
            if resultado == "OK":
                resolvido = True
                print(f"    ✅ tentativa {tent+1}: OK", flush=True)
                break
            print(f"    ⚠️ tentativa {tent+1}: ainda ERRO → corrigindo de novo", flush=True)

        if resolvido:
            # salva checkpoint a cada ponto resolvido
            ckpt_path.write_text(json.dumps(ckpt, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            # NÃO força: registra no relatório para decisão nossa
            item = {
                "arquivo": stem, "indice": idx, "quem": f.get("quem"),
                "jp": f.get("jp"), "pt_atual": f.get("pt_contextual"),
                "erro_auditoria": erro.get("erro_auditoria") if erro else None,
                "correcao_auditoria": erro.get("correcao_auditoria") if erro else None,
                "origem": "auditoria" if erro else "glossario",
                "tentativas": tentativas,
                "status": "NAO_RESOLVIDO_APOS_3X",
            }
            relatorio.append(item)
            print(f"    ❌ NÃO resolvido após {MAX_TENTATIVAS}x → relatório para decisão", flush=True)

    # relatório dos não resolvidos
    if relatorio:
        rel_path = REG_OUT / f"{stem}_nao_resolvidos.json"
        rel_path.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n{len(relatorio)} pontos NÃO resolvidos → relatório: {rel_path}")

    n_ok_total = sum(1 for f in falas.values() if f.get("pt_contextual"))
    print(f"[{stem}] total falas com pt: {n_ok_total}/{len(falas)}")


if __name__ == "__main__":
    main()
