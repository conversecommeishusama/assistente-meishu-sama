#!/usr/bin/env python3
"""Auditor da retradução contextual do Gokōwa-roku (Suplemento).

Segundo agente (auditor) que revisa de forma cética e independente as
traduções produzidas pelo executor (retraducao_completa_gokowa.py).

Audita FIDELIDADE e QUALIDADE, não estilo:
  1. A tradução está COMPLETA (não cortada no meio)?
  2. Preserva o sentido do JP (não inverte sujeito/objeto)?
  3. Tem palavras/termos estranhos ou inadequados ao contexto?
  4. Esclarece referências ambíguas sem inventar conteúdo?
  5. Mantém o tom truncado/coloquial quando o original é assim?

Marca cada fala como: aprovado | corrigir | retraduzir.
Quando "corrigir" ou "retraduzir", registra o motivo. O laço externo
pode reenviar ao executor as que precisam de retradução.

Uso:
    python3 scripts/auditar_retraducao_gokowa.py            # audita todas pendentes
    python3 scripts/auditar_retraducao_gokowa.py --indice=0  # audita 1 fala
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
OUT = RAIZ / "reports" / "amostragem_semantica_gokowa"
CHECKPOINT = OUT / "retraducao_completa_checkpoint.json"
AUDITORIA = OUT / "auditoria_retraducao_checkpoint.json"

MODELO = "deepseek-v4-flash"

PROMPT_AUDITOR = """Você é um AUDITOR cético de tradução japonês→português. Um executor traduziu uma fala do Gokōwa-roku (Suplemento) — registro manuscrito de conversas de Meishu-Sama (o original é naturalmente truncado, com falas curtas e referências sem contexto).

ESTILO DESEJADO (do usuário): traduções que ESCLARECEM o contexto para o leitor. Inserções esclarecedoras com [colchetes] ou parênteses SÃO DESEJADAS — tornam explícito o que o contexto já indica (quem é a pessoa, o que é a coisa). Isso NÃO é considerado "inventar conteúdo" — é clarificação legítima.

Sua tarefa: auditar a tradução. Verifique:
1. **Completude**: a tradução está completa (não cortada no meio da frase)?
2. **Fidelidade de sentido**: preserva o sentido do japonês? NÃO inverteu sujeito/objeto? NÃO mudou quem faz a ação?
3. **Inserções esclarecedoras**: são REAIS (refletem o contexto da obra) e não contradizem o original? Se sim, NÃO marque como problema — é o estilo desejado.
4. **Palavras inadequadas**: há palavras/termos estranhos, incorretos ou com conotação errada no contexto? (ex: "infiltrando" quando o sentido é "escondendo-se")
5. **Tom**: mantém o tom truncado/coloquial quando o original é assim?

Classifique como UMA das opções:
- "aprovado" — tradução boa, pode seguir (incluindo inserções esclarecedoras legítimas)
- "retraduzir" — há erro de sentido, corte, ou palavra inadequada; precisa retraduzir
- "revisar" — há pequeno ajuste sugerido, mas o sentido está correto

Responda SOMENTE com JSON:
{{"decisao": "aprovado" ou "retraduzir" ou "revisar", "motivo": "1 frase curta", "sugestao": "sugestão de correção, se houver"}}

---
JAPONÊS ORIGINAL:
{jp}

---
TRADUÇÃO DO EXECUTOR (a auditar):
{pt_executor}

---
"""


def _extrair_json(raw: str) -> str | None:
    if not raw:
        return None
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(raw)):
        c = raw[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]
    return None


def auditar(jp: str, pt_executor: str, max_retries: int = 6) -> dict:
    from goshinsho.services.agentic_search import _client

    for tentativa in range(max_retries):
        reforco = ""
        if tentativa == 1:
            reforco = "\n\nResponda APENAS o JSON puro, sem markdown, sem texto extra."
        elif tentativa == 2:
            reforco = '\n\nResponda EXATAMENTE: {"decisao": "...", "motivo": "...", "sugestao": "..."}'
        try:
            resp = _client().chat.completions.create(
                model=MODELO,
                max_tokens=300,
                messages=[{"role": "user", "content": PROMPT_AUDITOR.format(jp=jp, pt_executor=pt_executor) + reforco}],
                temperature=0,
            )
            raw = resp.choices[0].message.content or ""
            m = _extrair_json(raw)
            if m:
                r = json.loads(m)
                if r.get("decisao") in ("aprovado", "retraduzir", "revisar"):
                    return r
        except Exception:
            pass
        time.sleep(1 + tentativa)
    return {"decisao": "retraduzir", "motivo": "auditor não respondeu", "sugestao": ""}


def carregar_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def main() -> None:
    dados = carregar_json(CHECKPOINT, {})
    resultados = dados.get("resultados", {})
    auditoria = carregar_json(AUDITORIA, {})

    if "--indice" in sys.argv:
        idx = sys.argv[sys.argv.index("--indice") + 1]
        indices = [idx]
    else:
        indices = [str(i) for i in sorted(int(k) for k in resultados)]

    print(f"Auditando {len(indices)} falas...")
    for i in indices:
        r = resultados.get(i)
        if not r or not r.get("pt_contextual"):
            print(f"[{i}] sem tradução do executor, pulando")
            continue
        jp = r["jp"]
        pt_executor = r["pt_contextual"]
        print(f"[{i}] auditando...", flush=True)
        resp = auditar(jp, pt_executor)
        auditoria[i] = {**resp, "jp": jp[:100], "pt_executor": pt_executor[:100]}
        print(f"    → {resp.get('decisao')}: {resp.get('motivo','')[:80]}")
        if (len(auditoria) % 5) == 0:
            OUT.mkdir(parents=True, exist_ok=True)
            AUDITORIA.write_text(json.dumps(auditoria, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"    (checkpoint auditoria: {len(auditoria)})")

    OUT.mkdir(parents=True, exist_ok=True)
    AUDITORIA.write_text(json.dumps(auditoria, ensure_ascii=False, indent=2), encoding="utf-8")

    from collections import Counter
    cont = Counter(v.get("decisao", "?") for v in auditoria.values())
    print(f"\n=== Resumo auditoria ===")
    for k, v in cont.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
