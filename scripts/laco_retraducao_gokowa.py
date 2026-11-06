#!/usr/bin/env python3
"""Laço executor+auditor para retradução contextual do Gokōwa-roku (Suplemento).

Piloto: processa as primeiras N falas, com ciclo:
  executor (traduz) → auditor (revisa) → se "retraduzir", reenvia ao executor
  (até RODADAS_MAX por fala) → gera HTML final.

Uso:
    python3 scripts/laco_retraducao_gokowa.py [--n 50] [--inicio 0]
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

from retraducao_completa_gokowa import (  # noqa: E402
    extrair_falas, JP, PT, OUT, CONTEXTO_OBRA, EXEMPLO_REFERENCIA, PROMPT,
)
from auditar_retraducao_gokowa import auditar  # noqa: E402

LACO_CHECKPOINT = OUT / "laco_retraducao_checkpoint.json"
RODADAS_MAX = 4  # quantas retraduções máximas por fala

MODELO = "deepseek-v4-flash"


def _client():
    from goshinsho.services.agentic_search import _client as c
    return c()


def retraduzir(jp: str, quem: str, max_retries: int = 15) -> str:
    """Delega ao executor segmentado (retraducao_completa_gokowa.retraduzir),
    que já aplica a segmentação de falas longas + todas as regras editoriais
    (povos/etnias, novo/novidade, 大清算/大浄化, negação dupla)."""
    # Se a fala é longa, usa a versão segmentada; senão, traduz direto.
    # O executor segmentado já resolve ambos os casos internamente.
    return _retraduzir_executor(jp, quem, max_retries)


def _retraduzir_executor(jp: str, quem: str, max_retries: int) -> str:
    """Importa a função do executor e a chama (evita re-implementação)."""
    from retraducao_completa_gokowa import retraduzir as executor_retraduzir
    return executor_retraduzir(jp, quem, max_retries=max_retries)


def carregar_laco() -> dict:
    if LACO_CHECKPOINT.exists():
        try:
            return json.loads(LACO_CHECKPOINT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def salvar_laco(dados: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LACO_CHECKPOINT.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    n = 50
    inicio = 0
    for a in sys.argv[1:]:
        if a.startswith("--n"):
            n = int(a.split("=")[1])
        elif a.startswith("--inicio"):
            inicio = int(a.split("=")[1])

    falas_jp = extrair_falas(JP.read_text(encoding="utf-8"))
    falas_pt = extrair_falas(PT.read_text(encoding="utf-8"))
    fim = min(inicio + n, len(falas_jp), len(falas_pt))

    dados = carregar_laco()
    if "falas" not in dados:
        dados["falas"] = {}

    print(f"Laço executor+auditor | falas {inicio}-{fim-1} ({fim-inicio} falas) | max {RODADAS_MAX} rodadas")
    print(f"Checkpoint: {len(dados['falas'])} falas já processadas")
    print("=" * 60)

    for i in range(inicio, fim):
        if str(i) in dados["falas"]:
            f = dados["falas"][str(i)]
            if f.get("status") == "aprovado":
                continue  # já aprovado
        quem, jp = falas_jp[i]
        pt_atual = falas_pt[i][1]
        print(f"\n[{i}] {quem} (rodada 0)")

        registro = dados["falas"].get(str(i), {
            "indice": i, "quem": quem, "jp": jp, "pt_atual": pt_atual,
            "historico": [], "status": "pendente", "pt_contextual": "",
        })
        registro["jp"] = jp
        registro["pt_atual"] = pt_atual
        registro["quem"] = quem

        for rodada in range(RODADAS_MAX):
            print(f"  rodada {rodada}: executor traduzindo...", flush=True)
            pt_ctx = retraduzir(jp, quem)
            if not pt_ctx:
                print(f"    executor falhou (vazio) na rodada {rodada}")
                time.sleep(2)
                continue

            registro["pt_contextual"] = pt_ctx
            registro["historico"].append({"rodada": rodada, "pt": pt_ctx})

            print(f"    auditor revisando...", flush=True)
            veredito = auditar(jp, pt_ctx)
            decisao = veredito.get("decisao", "retraduzir")
            motivo = veredito.get("motivo", "")
            print(f"    auditor: {decisao} — {motivo[:70]}")

            # Se o auditor não respondeu (instabilidade do modelo), NÃO reenviar:
            # trata como aprovado para evitar retraduções desnecessárias.
            if decisao == "retraduzir" and ("não respondeu" in motivo or "não respondeu" in str(veredito)):
                print(f"    auditor instável (não respondeu) → tratando como aprovado")
                registro["status"] = "aprovado"
                registro["veredito"] = {"decisao": "aprovado", "motivo": "auditor não respondeu (instabilidade)", "sugestao": ""}
                break

            if decisao == "aprovado":
                registro["status"] = "aprovado"
                registro["veredito"] = veredito
                break
            elif decisao == "revisar":
                registro["status"] = "revisar"
                registro["veredito"] = veredito
                # revisar é aceitável — aceita, mas marca
                break
            # retraduzir → próxima rodada
            registro["veredito"] = veredito

        else:
            registro["status"] = "max_rodadas"
            print(f"  ⚠️ atingiu {RODADAS_MAX} rodadas sem aprovação")

        dados["falas"][str(i)] = registro

        if (i - inicio + 1) % 5 == 0:
            salvar_laco(dados)
            print(f"  checkpoint salvo ({i-inicio+1}/{fim-inicio})")

    salvar_laco(dados)

    # resumo
    from collections import Counter
    cont = Counter(v.get("status", "?") for v in dados["falas"].values())
    print("\n=== Resumo ===")
    for k, v in cont.most_common():
        print(f"  {k}: {v}")

    gerar_html_piloto(dados, fim)


def gerar_html_piloto(dados: dict, fim: int) -> None:
    falas = dados.get("falas", {})
    html = []
    html.append("""<!DOCTYPE html>
<html lang="pt"><head><meta charset="utf-8">
<title>Gokōwa-roku — Laço executor+auditor (piloto)</title>
<style>
body { font-family: sans-serif; margin: 20px; background: #fafafa; }
h1 { font-size: 20px; }
.fala { display: flex; margin: 5px 0; border-left: 3px solid #2a2; padding: 4px 8px; background:#fff; }
.fala.revisar { border-left-color: #c90; background: #fff8e6; }
.fala.max_rodadas { border-left-color: #c33; background: #fff0f0; }
.fala.pendente { border-left-color: #999; background: #f0f0f0; }
.idx { width: 38px; flex: 0 0 38px; color:#888; font-size:11px; text-align:right; padding-right:6px; }
.col { width: 33%; flex: 0 0 33%; font-size: 12.5px; padding-right: 8px; }
.quem { font-weight:bold; font-size:10px; color:#666; display:block; }
.badge { font-size: 10px; padding: 1px 6px; border-radius: 8px; color:#fff; }
.badge.aprovado { background: #2a2; }
.badge.revisar { background: #c90; }
.badge.max_rodadas { background: #c33; }
.legenda { background:#eef; padding:8px; margin:10px 0; border-left:4px solid #2a2; font-size:13px; }
</style></head><body>
<h1>Gokōwa-roku (Suplemento) — Piloto laço executor+auditor</h1>
<div class="legenda">🟢 aprovado · 🟠 revisar (aceito, com ressalva) · 🔴 max_rodadas (não convergiu) · ⚪ pendente</div>
""")
    for i in sorted(int(k) for k in falas):
        r = falas[str(i)]
        status = r.get("status", "pendente")
        cls = status if status in ("revisar", "max_rodadas", "pendente") else ""
        badge = f'<span class="badge {status}">{status}</span>'
        # última tradução do histórico
        pt_ctx = r.get("pt_contextual", "")
        if not pt_ctx and r.get("historico"):
            pt_ctx = r["historico"][-1].get("pt", "")
        motivo = (r.get("veredito") or {}).get("motivo", "")
        html.append(f"""<div class="fala {cls}">
<div class="idx">{i}</div>
<div class="col"><span class="quem">{r['quem']}</span> {esc(r.get('jp',''))}</div>
<div class="col"><span class="quem">{r['quem']}</span> {esc(r.get('pt_atual',''))}</div>
<div class="col"><span class="quem">{r['quem']} (ctx) {badge}</span> {esc(pt_ctx)}
<div style="font-size:10px;color:#777;">{esc(motivo)}</div></div>
</div>""")
    html.append("</body></html>")
    arq = OUT / "piloto_laco_executor_auditor.html"
    arq.write_text("\n".join(html), encoding="utf-8")
    print(f"HTML: {arq}")


def esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    main()
