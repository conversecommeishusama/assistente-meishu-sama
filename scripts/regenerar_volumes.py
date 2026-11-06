#!/usr/bin/env python3
"""Regenera os 32 volumes em publicacao_livros/ com o conteúdo FINAL corrigido.

Antes deste script, os volumes apontavam para nomes JP antigos e conteúdo
desatualizado (pré-renomeação e pré-correções 995+). Esta regeneração:

1. Lê os MANIFESTO.json existentes (definem a composição e ordem de cada volume).
2. Para cada arquivo, resolve a fonte ATUALIZADA na ordem de prioridade:
   a. livros_publicacao_pt_revisado/  (fonte de verdade PT, nomes novos)
   b. backups/remocao_fora_escopo_*/pt/ (casos especiais fora do escopo do app
      mas que ENTRAM nos livros -- Jikan nº6/13/15, 世界救世教教義解説, Keiko,
      Relatos_de_Milagres)
   c. fallback: o próprio arquivo já copiado no volume atual.
3. Copia com o nome PT novo (via MAPEAMENTO_RENOMEACAO_TXT.json) e reescreve o
   MANIFESTO com os nomes novos e a fonte real usada.

Uso:
    python3 regenerar_volumes.py            # executa
    python3 regenerar_volumes.py --dry-run  # só mostra o que faria
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path("/var/www/goshinsho")
PUB = ROOT / "publicacao_livros"
FONTE_PRINCIPAL = ROOT / "livros_publicacao_pt_revisado"
FONTE_ESPECIAL = ROOT / "backups" / "remocao_fora_escopo_20260813T225444Z" / "pt"
MAPA_FILE = ROOT / "reports" / "varredura_padronizacao" / "MAPEAMENTO_RENOMEACAO_TXT.json"


def carregar_mapa() -> dict[str, str]:
    """JP antigo -> PT novo."""
    if not MAPA_FILE.exists():
        return {}
    try:
        data = json.loads(MAPA_FILE.read_text(encoding="utf-8"))
        return {item["antigo"]: item["novo"] for item in data}
    except Exception:
        return {}


def sem_prefixo(nome: str) -> str:
    """Remove prefixo NN_ do nome do arquivo (ordem no volume)."""
    return re.sub(r"^\d+_", "", nome)


def resolver_fonte(nome_antigo: str, mapa: dict[str, str]) -> tuple[Path | None, str]:
    """Resolve a fonte atualizada para um arquivo.

    Retorna (caminho_da_fonte, nome_pt). nome_pt é o nome novo (sem prefixo).
    Ordem de prioridade:
      1. fonte principal (livros_publicacao_pt_revisado) com nome PT novo
      2. fonte principal com nome antigo (se ainda existir)
      3. fonte especial (backup de remoção) com nome antigo
      4. None (fallback para o arquivo já no volume)
    """
    nome_pt = mapa.get(nome_antigo, nome_antigo)

    # 1. fonte principal com nome novo
    p = FONTE_PRINCIPAL / nome_pt
    if p.exists():
        return p, nome_pt

    # 2. fonte principal com nome antigo (não renomeado)
    p = FONTE_PRINCIPAL / nome_antigo
    if p.exists():
        return p, nome_pt

    # 3. fonte especial (backup de remoção)
    p = FONTE_ESPECIAL / nome_antigo
    if p.exists():
        return p, nome_pt

    return None, nome_pt


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    mapa = carregar_mapa()
    print(f"Mapeamento carregado: {len(mapa)} entradas")

    volumes = sorted([p for p in PUB.iterdir() if p.is_dir()])
    print(f"Volumes: {len(volumes)}")

    total_ok = 0
    total_fallback = 0
    total_erro = 0

    for vol in volumes:
        mf = vol / "MANIFESTO.json"
        if not mf.exists():
            print(f"  ⚠️ {vol.name}: SEM MANIFESTO (pulando)")
            continue

        data = json.loads(mf.read_text(encoding="utf-8"))
        novos_arquivos = []
        problemas = []

        for arq in data.get("arquivos", []):
            dest = arq.get("arquivo_destino", "")
            fonte_ref = arq.get("fonte", "")
            # nome antigo = nome do arquivo de origem no manifesto (após prefixo)
            nome_antigo = sem_prefixo(Path(fonte_ref).name if fonte_ref else dest)

            fonte, nome_pt = resolver_fonte(nome_antigo, mapa)

            if fonte is None:
                # Fallback: usa o arquivo já presente no volume
                existente = vol / dest
                if existente.exists():
                    total_fallback += 1
                    problemas.append(f"    ⚠️ {dest}: sem fonte atualizada, usando volume atual")
                    novos_arquivos.append({
                        "arquivo_destino": dest,
                        "fonte": f"publicacao_livros/{vol.name}/{dest} (fallback)",
                        "caracteres": arq.get("caracteres"),
                    })
                    continue
                total_erro += 1
                problemas.append(f"    ❌ {dest}: SEM FONTE (não encontrado em lugar nenhum)")
                continue

            # nome final com prefixo de ordem (mantém a numeração original)
            prefixo = re.match(r"^\d+_", dest)
            prefixo_str = prefixo.group(0) if prefixo else ""
            dest_final = prefixo_str + nome_pt

            if not dry_run:
                shutil.copy2(fonte, vol / dest_final)

            novos_arquivos.append({
                "arquivo_destino": dest_final,
                "fonte": str(fonte.relative_to(ROOT)),
                "caracteres": fonte.stat().st_size,
            })
            total_ok += 1

        if not dry_run and novos_arquivos:
            data["arquivos"] = novos_arquivos
            # re-calculando caracteres totais
            data["caracteres_totais"] = sum(a.get("caracteres") or 0 for a in novos_arquivos)
            mf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        if problemas:
            print(f"--- {vol.name} ---")
            for p in problemas:
                print(p)

    print()
    print(f"OK: {total_ok} | fallback: {total_fallback} | erro: {total_erro}")
    if dry_run:
        print("(dry-run — sem --dry-run para executar)")
    else:
        print("Regeneração concluída.")


if __name__ == "__main__":
    main()
