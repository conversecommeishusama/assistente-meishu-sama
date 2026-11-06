#!/usr/bin/env python3
"""Auditoria contínua (DeepSeek) dos arquivos retraduzidos das coleções.

Roda em loop: a cada intervalo, verifica se há arquivos NOVOS concluídos em
`reports/retraducao_colecoes/` (checkpoint com todas as falas preenchidas) e
audita cada fala com DeepSeek (mesmo prompt/julgamento da auditoria do lote).

Grava resultados em:
  reports/auditoria_colecoes/<arquivo>.json  (vereditos por fala)

Uso:
  .venv/bin/python scripts/auditar_colecoes_loop.py [--intervalo 300]
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

from openai import OpenAI  # noqa: E402

# Reutiliza prompt do auditor Claude (mesmo critério) — importa sem disparar main
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("auditor_claude", RAIZ / "scripts" / "auditar_lote_gokowa_api.py")
_auditor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_auditor)

COLECOES = RAIZ / "reports" / "retraducao_colecoes"
SAIDA = RAIZ / "reports" / "auditoria_colecoes"

MODELO = "deepseek-v4-flash"
MAX_TOKENS = 20000  # mesmo padrão do executor: falas longas não cortam a resposta
RETRIES = 4
RETRIES_FALHA = 10  # reauditoria de falhas de API com mais tentativas
BASE_BACKOFF_S = 3

# Modo --rejulgar-erros: rejulga apenas os ERRO_TRADUCAO (para descartar falsos
# positivos gerados com MAX_TOKENS curto = resposta cortada antes do JSON).
REJULGAR_ERROS = False


def arquivo_concluido(ckpt_path: Path) -> tuple[bool, dict]:
    try:
        dados = json.loads(ckpt_path.read_text(encoding="utf-8"))
    except Exception:
        return False, {}
    falas = dados.get("falas", {})
    preench = sum(1 for f in falas.values() if f.get("pt_contextual"))
    return (preench >= len(falas) and len(falas) > 0), dados


def auditar_fala(client: OpenAI, fala: dict, max_retries: int | None = None) -> dict:
    ultimo_erro = None
    limite = max_retries or RETRIES
    for tentativa in range(limite):
        try:
            jp = fala.get("jp", "")
            pt = fala.get("pt_contextual", "")
            prompt = (
                f"AUDITORIA DE TRADUÇÃO — fala índice {fala.get('indice')}\n"
                f"Falante: {fala.get('quem', '')}\n\n"
                f"--- JP (original) ---\n{jp}\n\n"
                f"--- PT (tradução a auditar) ---\n{pt}\n\n"
                "Compare o PT com o JP e responda com o JSON de veredito."
            )
            resp = client.chat.completions.create(
                model=MODELO,
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": _auditor.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            texto = resp.choices[0].message.content or ""
            dados = _auditor.extrair_json(texto)
            if dados is None:
                raise ValueError("resposta sem JSON válido")
            veredito = dados.get("veredito")
            if veredito not in ("OK", "ERRO_TRADUCAO"):
                raise ValueError(f"veredito inválido: {veredito!r}")
            if veredito == "OK":
                return {"indice": fala.get("indice"), "veredito": "OK", "erro": None}
            return {
                "indice": fala.get("indice"),
                "veredito": "ERRO_TRADUCAO",
                "erro": (dados.get("erro") or "")[:500],
                "correcao": (dados.get("correcao") or "")[:500],
            }
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            if any(k in str(e).lower() for k in ["balance", "spend", "rate", "insufficient"]):
                time.sleep(BASE_BACKOFF_S * (2 ** tentativa))
                continue
            time.sleep(BASE_BACKOFF_S * (tentativa + 1))
    return {
        "indice": fala.get("indice"),
        "veredito": "ERRO_TRADUCAO",
        "erro": f"[FALHA DE AUDITORIA: {ultimo_erro}]",
        "correcao": "Reauditar esta fala manualmente.",
    }


def auditar_arquivo(client: OpenAI, ckpt_path: Path) -> bool:
    """Audita um arquivo concluído (se ainda não auditado). Retorna True se auditou."""
    saida = SAIDA / f"{ckpt_path.stem}.json"
    if saida.exists():
        try:
            prev = json.loads(saida.read_text(encoding="utf-8"))
            if prev.get("total_auditadas", 0) > 0 and not any("FALHA DE AUDITORIA" in str(v.get("erro", "")) for v in prev.get("vereditos", [])):
                return False  # já auditado sem falhas
        except Exception:
            pass

    concluido, dados = arquivo_concluido(ckpt_path)
    if not concluido:
        return False

    falas = dados["falas"]
    # ordena por número (índice numérico OU chave t{n} da prosa contínua)
    def _chave_ord(chave):
        if isinstance(chave, str) and chave.startswith("t") and chave[1:].isdigit():
            return int(chave[1:])
        try:
            return int(chave)
        except (TypeError, ValueError):
            return 0
    ordenadas = [falas[k] for k in sorted(falas, key=_chave_ord)]
    print(f"  Auditando {ckpt_path.stem}: {len(ordenadas)} falas...", flush=True)

    # Carrega vereditos já existentes (retomável)
    vereditos = {}
    if saida.exists():
        try:
            prev = json.loads(saida.read_text(encoding="utf-8"))
            for v in prev.get("vereditos", []):
                vereditos[v["indice"]] = v
        except Exception:
            pass

    for i, fala in enumerate(ordenadas, 1):
        idx = fala.get("indice", i - 1)
        eh_falha = idx in vereditos and "FALHA DE AUDITORIA" in str(vereditos[idx].get("erro", ""))
        eh_erro_real = idx in vereditos and not eh_falha and vereditos[idx].get("veredito") == "ERRO_TRADUCAO"
        # Rejulga (com MAX_TOKENS=20000): falhas de API E erros reais (que podem
        # ter sido julgados com token curto = falso positivo por resposta cortada)
        if eh_falha:
            max_r = RETRIES_FALHA
            print(f"    [reauditando falha] fala {idx}...", flush=True)
        elif eh_erro_real and REJULGAR_ERROS:
            max_r = RETRIES_FALHA
            print(f"    [rejulgando erro] fala {idx}...", flush=True)
        else:
            if idx in vereditos:
                continue  # OK já válido
            max_r = RETRIES
        v = auditar_fala(client, fala, max_retries=max_r)
        vereditos[idx] = v
        print(f"    [{i}/{len(ordenadas)}] fala {idx}: {v['veredito']}", flush=True)
        if i % 5 == 0:
            _salvar(saida, ckpt_path.stem, vereditos)

    _salvar(saida, ckpt_path.stem, vereditos)
    return True


def _salvar(saida: Path, nome: str, vereditos: dict) -> None:
    todos = list(vereditos.values())
    ok = sum(1 for v in todos if v["veredito"] == "OK")
    erro = sum(1 for v in todos if v["veredito"] == "ERRO_TRADUCAO")
    SAIDA.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps({
        "arquivo": nome,
        "total_auditadas": len(todos),
        "resumo": {"ok": ok, "erro_traducao": erro},
        "vereditos": todos,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    global REJULGAR_ERROS
    intervalo = 300
    if "--intervalo" in sys.argv:
        k = sys.argv.index("--intervalo")
        intervalo = int(sys.argv[k + 1])
    if "--rejulgar-erros" in sys.argv:
        REJULGAR_ERROS = True

    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")
    modo = "REJULGANDO erros reais (MAX_TOKENS=20000)" if REJULGAR_ERROS else "normal"
    print(f"Auditoria contínua das coleções — modo: {modo} — intervalo {intervalo}s", flush=True)

    while True:
        pendentes = sorted(COLECOES.glob("*.json"))
        auditou_algum = False
        for ckpt in pendentes:
            try:
                auditou = auditar_arquivo(client, ckpt)
                auditou_algum = auditou_algum or auditou
            except Exception as e:  # noqa: BLE001
                print(f"  ERRO ao auditar {ckpt.stem}: {e}", flush=True)
        if auditou_algum:
            print("  ...nova rodada de auditoria concluída", flush=True)
        else:
            print(f"  ({time.strftime('%H:%M:%S')}) sem arquivos novos para auditar", flush=True)
        time.sleep(intervalo)


if __name__ == "__main__":
    main()
