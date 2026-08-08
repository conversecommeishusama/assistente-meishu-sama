#!/usr/bin/env python3
"""Orquestrador da Fase 5 (parte JP) -- espera a JP-2 fechar e executa, em
sequência, com verificação de segurança antes de cada passo:

1. Promover reports/livros_trabalho/{jp,pt} -> textos_japones/textos_portugues.
2. Regenerar specs (jp_anchor/pt_anchor) via rebuild_all_livros_segmentation.py.
3. Construir chunks/índice novos (build_clean_large_indexes.py, sem --install).
4. Verificação própria (smoke test) dos artefatos jp_* construídos.
5. Instalar SÓ os artefatos jp_* em produção (install_jp_indexes_only.py --apply).

O lado PT é promovido e tem as specs regeneradas (passos 1-2), mas o índice
pt_* construído no passo 3 NUNCA é instalado -- fica em staging, esperando a
verificação semântica linha a linha e decisão explícita do usuário, separada
desta automação.

Se qualquer passo falhar ou o resultado parecer anômalo, o script escreve o
motivo em STATUS_PATH e para -- nunca segue adiante sobre um erro.

Sem custo de API/IA -- é só orquestração de scripts Python já existentes.
"""
from __future__ import annotations

import json
import pickle
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = str(PROJECT_ROOT / "venv" / "bin" / "python3")
JP2_EXEC_QUEUE = PROJECT_ROOT / "reports/livros_trabalho/segmentacao_manual/JP2_VERIFICACAO_ESTRUTURAL_QUEUE.json"
JP2_AUD_QUEUE = PROJECT_ROOT / "reports/livros_trabalho/segmentacao_manual/JP2_AUDITORIA_EXTERNA_QUEUE.json"
STATUS_PATH = PROJECT_ROOT / "reports/livros_trabalho/segmentacao_manual/FASE5_JP_STATUS.json"
STAGING_DIR = PROJECT_ROOT / "experiments/rebuilt_large_indexes"
CURRENT_DIR = PROJECT_ROOT / "experiments/uploaded_indexes"

POLL_INTERVAL_S = 180


def write_status(step: str, state: str, detail: dict | str = "") -> None:
    status = {
        "step": step,
        "state": state,  # "aguardando" | "em_andamento" | "ok" | "parado_erro" | "concluido"
        "detail": detail,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{status['updated_at']}] {step}: {state} -- {json.dumps(detail, ensure_ascii=False) if isinstance(detail, dict) else detail}")


def jp2_finished() -> bool:
    try:
        exec_q = json.loads(JP2_EXEC_QUEUE.read_text(encoding="utf-8"))
        aud_q = json.loads(JP2_AUD_QUEUE.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        write_status("aguardando_jp2", "parado_erro", f"nao consegui ler filas JP2: {exc}")
        return False
    return (
        len(exec_q.get("pending", [])) == 0
        and len(aud_q.get("pending", [])) == 0
        and bool(aud_q.get("concluido", False))
    )


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)


def step_promote() -> bool:
    write_status("promocao_texto", "em_andamento")
    proc = run([VENV_PYTHON, "scripts/promote_livros_trabalho_to_produção.py", "--lang", "both", "--apply"])
    if proc.returncode != 0:
        write_status("promocao_texto", "parado_erro", {"stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:]})
        return False
    try:
        report = json.loads(proc.stdout)
    except Exception:
        write_status("promocao_texto", "parado_erro", {"motivo": "saida nao era JSON valido", "stdout": proc.stdout[-4000:]})
        return False
    for r in report["reports"]:
        if r["erros"]:
            write_status("promocao_texto", "parado_erro", {"lang": r["lang"], "erros": r["erros"]})
            return False
    write_status("promocao_texto", "ok", {"reports": [{"lang": r["lang"], "alterados": len(r["alterados"]), "identicos": len(r["identicos"])} for r in report["reports"]]})
    return True


def step_rebuild_specs() -> bool:
    write_status("regeneracao_specs", "em_andamento")
    proc = run([VENV_PYTHON, "scripts/rebuild_all_livros_segmentation.py"])
    if proc.returncode != 0:
        write_status("regeneracao_specs", "parado_erro", {"stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:]})
        return False
    lines = [l for l in proc.stdout.splitlines() if l.strip()]
    json_start = next((i for i, l in enumerate(lines) if l.strip().startswith("{")), None)
    if json_start is None:
        write_status("regeneracao_specs", "parado_erro", {"motivo": "sem resumo JSON na saida", "stdout": proc.stdout[-4000:]})
        return False
    try:
        summary = json.loads("\n".join(lines[json_start:]))
    except Exception:
        write_status("regeneracao_specs", "parado_erro", {"motivo": "resumo JSON invalido", "stdout": proc.stdout[-4000:]})
        return False
    if summary.get("fail", 1) != 0:
        write_status("regeneracao_specs", "parado_erro", {"motivo": "houve falhas por arquivo", "summary": summary})
        return False
    write_status("regeneracao_specs", "ok", summary)
    return True


def step_build_indexes() -> bool:
    write_status("construcao_indices", "em_andamento", "pode levar varios minutos (embeddings e5-large)")
    proc = run([VENV_PYTHON, "scripts/build_clean_large_indexes.py"])
    if proc.returncode != 0:
        write_status("construcao_indices", "parado_erro", {"stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:]})
        return False
    for name in ("chunks_jp.pkl", "metadados_jp.pkl", "indice_jp.faiss"):
        if not (STAGING_DIR / name).exists():
            write_status("construcao_indices", "parado_erro", {"motivo": f"arquivo esperado ausente em staging: {name}"})
            return False
    write_status("construcao_indices", "ok", {"stdout_tail": proc.stdout[-2000:]})
    return True


def step_smoke_test() -> bool:
    write_status("verificacao_jp", "em_andamento")
    try:
        with (STAGING_DIR / "chunks_jp.pkl").open("rb") as f:
            new_chunks = pickle.load(f)
        with (STAGING_DIR / "metadados_jp.pkl").open("rb") as f:
            new_meta = pickle.load(f)
        import faiss  # type: ignore

        new_index = faiss.read_index(str(STAGING_DIR / "indice_jp.faiss"))
    except Exception as exc:  # noqa: BLE001
        write_status("verificacao_jp", "parado_erro", f"falha ao carregar artefatos novos: {exc}")
        return False

    old_count = None
    if (CURRENT_DIR / "chunks_jp.pkl").exists():
        try:
            with (CURRENT_DIR / "chunks_jp.pkl").open("rb") as f:
                old_chunks = pickle.load(f)
            old_count = len(old_chunks)
        except Exception:
            old_count = None

    new_count = len(new_chunks)
    checks = {
        "chunks_novos": new_count,
        "chunks_antigos": old_count,
        "metadados_novos": len(new_meta),
        "faiss_ntotal": int(new_index.ntotal),
    }

    if len(new_meta) != new_count:
        write_status("verificacao_jp", "parado_erro", {"motivo": "chunks e metadados com contagem diferente", **checks})
        return False
    if int(new_index.ntotal) != new_count:
        write_status("verificacao_jp", "parado_erro", {"motivo": "faiss ntotal nao bate com numero de chunks", **checks})
        return False
    if old_count is not None:
        variacao = abs(new_count - old_count) / old_count
        if variacao > 0.5:
            write_status("verificacao_jp", "parado_erro", {"motivo": f"variacao de {variacao:.0%} no numero de chunks -- fora da faixa esperada (>50%), parando para revisao humana", **checks})
            return False

    write_status("verificacao_jp", "ok", checks)
    return True


def step_install() -> bool:
    write_status("instalacao_jp", "em_andamento")
    proc = run([VENV_PYTHON, "scripts/install_jp_indexes_only.py", "--apply"])
    if proc.returncode != 0:
        write_status("instalacao_jp", "parado_erro", {"stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:]})
        return False
    try:
        result = json.loads(proc.stdout)
    except Exception:
        write_status("instalacao_jp", "parado_erro", {"motivo": "saida nao era JSON valido", "stdout": proc.stdout[-4000:]})
        return False
    write_status("instalacao_jp", "ok", result)
    return True


def main() -> int:
    write_status("aguardando_jp2", "aguardando", "esperando JP2 fechar 108/108 nos dois lacos")
    while not jp2_finished():
        time.sleep(POLL_INTERVAL_S)

    write_status("jp2_fechada", "ok", "JP-2 concluida -- iniciando Fase 5 (parte JP)")

    if not step_promote():
        return 1
    if not step_rebuild_specs():
        return 1
    if not step_build_indexes():
        return 1
    if not step_smoke_test():
        return 1
    if not step_install():
        return 1

    write_status(
        "concluido",
        "concluido",
        "JP instalado em produção. PT promovido e com specs atualizadas, mas indice PT NAO instalado -- aguarda verificacao semantica linha a linha e decisao explicita do usuario.",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
