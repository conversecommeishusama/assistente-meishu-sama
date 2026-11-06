#!/usr/bin/env python3
"""Orquestrador da FILA de ajustes pontuais — processa todos os arquivos com
auditoria até o fim.

Para cada checkpoint de retradução que TEM auditoria (reports/auditoria_colecoes)
e AINDA NÃO foi ajustado (sem marca `ajustes_aplicados` no checkpoint), chama
`ajustar_pontos_auditoria.py <ckpt>` (executor corrige → auditor verifica →
até 3x → não-resolvidos vão para reports/ajustes_pontuais/).

Marca `ajustes_aplicados: true` no checkpoint ao concluir (mesmo se houver
não-resolvidos, para não reprocessar — os não-resolvidos ficam no relatório).

Roda em LOOP (intervalo): a cada rodada re-verifica se novos arquivos ganharam
auditoria (a auditoria contínua segue rodando em paralelo). Só termina quando
NENHUM arquivo do escopo tiver auditoria pendente de ajuste.

Uso:
  .venv/bin/python scripts/ajustar_fila_colecoes.py [--intervalo 180]
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RETR = RAIZ / "reports" / "retraducao_colecoes"
AUD = RAIZ / "reports" / "auditoria_colecoes"
LOG = RAIZ / "logs" / "ajustes_fila.log"

# arquivos do escopo (gokowa, gosuiji, mioshie 1-8)
def no_escopo(nome: str) -> bool:
    if "御光話録" in nome or "御垂示録" in nome:
        # EXCLUI o Suplemento (補) da fila — é processado à parte (massa própria),
        # para não conflitar (2 processos no mesmo checkpoint).
        if "（補）" in nome or "(補)" in nome:
            return False
        return True
    if "御教え集" in nome:
        import re
        m = re.search(r"御教え集(\d+)号", nome)
        return bool(m) and int(m.group(1)) <= 8
    return False


def log(msg: str) -> None:
    linha = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(linha, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def ja_ajustado(ckpt_path: Path) -> bool:
    try:
        d = json.loads(ckpt_path.read_text(encoding="utf-8"))
        return bool(d.get("ajustes_aplicados"))
    except Exception:
        return False


def marcar_ajustado(ckpt_path: Path) -> None:
    try:
        d = json.loads(ckpt_path.read_text(encoding="utf-8"))
        d["ajustes_aplicados"] = True
        d["ajustes_aplicados_em"] = time.strftime("%Y-%m-%d %H:%M:%S")
        ckpt_path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"  ERRO ao marcar ajustado {ckpt_path.name}: {e}")


def fila_pendente() -> list[Path]:
    """Checkpoints do escopo que TÊM auditoria e NÃO foram ajustados."""
    auditados = {p.stem for p in AUD.glob("*.json") if "backup" not in p.name}
    pendentes = []
    for ckpt in sorted(RETR.glob("*.json")):
        if ".bak" in ckpt.name or ckpt.name.endswith(".lock"):
            continue
        if not no_escopo(ckpt.stem):
            continue
        if ckpt.stem not in auditados:
            continue  # sem auditoria ainda
        if ja_ajustado(ckpt):
            continue  # já ajustado
        pendentes.append(ckpt)
    return pendentes


def main() -> None:
    intervalo = 180
    if "--intervalo" in sys.argv:
        k = sys.argv.index("--intervalo")
        intervalo = int(sys.argv[k + 1])

    log(f"=== Orquestrador de fila de ajustes iniciado (intervalo {intervalo}s) ===")
    while True:
        pendentes = fila_pendente()
        if not pendentes:
            log("Nenhum arquivo com auditoria pendente de ajuste. "
                "(Se a auditoria ainda roda, aguardando novos auditados...)")
            time.sleep(intervalo)
            continue

        log(f"{len(pendentes)} arquivos na fila de ajustes")
        for ckpt in pendentes:
            log(f"  → Ajustando {ckpt.name} ...")
            r = subprocess.run(
                [sys.executable, "scripts/ajustar_pontos_auditoria.py", str(ckpt)],
                cwd=str(RAIZ),
            )
            if r.returncode != 0:
                log(f"    ERRO (code {r.returncode}) — registrando e seguindo")
            marcar_ajustado(ckpt)
            log(f"    ✅ {ckpt.name} ajustado e marcado")

        # se ainda houver pendentes após a rodada (novos auditados), continua;
        # senão aguarda a auditoria avançar
        time.sleep(intervalo)


if __name__ == "__main__":
    main()
