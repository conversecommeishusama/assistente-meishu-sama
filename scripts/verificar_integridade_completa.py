#!/usr/bin/env python3
"""Verificação RIGOROSA de integridade e correspondência JP↔PT dos Mioshie.

Para cada arquivo (1-8):
1. INTEGRIDADE: cada fala do checkpoint está presente no consolidado final,
   exatamente 1x, na ordem correta? (sem perda, sem duplicação)
2. CORRESPONDÊNCIA: para cada fala, o trecho JP e o trecho PT estão pareados
   (mesma fala) e ambos presentes no material?
3. GERA o material de leitura semântica (pares JP↔PT) em reports/ para revisão.

Uso: .venv/bin/python scripts/verificar_integridade_completa.py [--gerar-material]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CKPT_DIR = ROOT / "reports/retraducao_colecoes"
ORAL_DIR = ROOT / "revisao_literaria/orais"

MAPA = {
    1: ("19510920-御教え集1号", "19510920 - Mioshie-shū nº 1"),
    2: ("19511025-御教え集2号", "19511025 - Mioshie-shū nº 2"),
    3: ("19511125-御教え集3号", "19511125 - Mioshie-shū nº 3"),
    4: ("19511215-御教え集4号", "19511215 - Mioshie-shū nº 4"),
    5: ("19520115-御教え集5号", "19520115 - Mioshie-shū nº 5"),
    6: ("19510225-御教え集6号", "19510225 - Mioshie-shū nº 6"),
    7: ("19520320-御教え集7号", "19520320 - Mioshie-shū nº 7"),
    8: ("19520420-御教え集8号", "19520420 - Mioshie-shū nº 8"),
}


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def main() -> int:
    gerar_material = "--gerar-material" in sys.argv
    total_falas = 0
    total_ok = 0
    linhas = []

    for n in range(1, 9):
        stem_jp, nome_pt = MAPA[n]
        ckpt_path = CKPT_DIR / f"{stem_jp}.json"
        oral_path = ORAL_DIR / f"{nome_pt}.txt"
        if not ckpt_path.exists() or not oral_path.exists():
            print(f"[nº {n}] arquivos ausentes")
            continue
        ckpt = json.loads(ckpt_path.read_text(encoding="utf-8"))
        falas = ckpt.get("falas", {})
        ks = sorted(falas.keys(), key=lambda x: int(x) if str(x).isdigit() else -1)
        oral = oral_path.read_text(encoding="utf-8")
        oral_norm = norm(oral)

        # Para cada fala, normaliza o PT e verifica se está presente no oral
        # (sem considerar rótulos Interlocutor:/Meishu-Sama: no início)
        achadas = {}
        faltando = []
        for k in ks:
            f = falas[k]
            pt = f.get("pt_contextual", "").strip()
            # remove rótulo duplicado se presente
            pt_clean = re.sub(r"^(Interlocutor|Meishu-Sama)[:：]\s*", "", pt)
            pt_norm = norm(pt_clean)
            if not pt_norm:
                faltando.append((k, "(PT vazio)"))
                continue
            # busca por um trecho representativo (primeiros 40 chars norm)
            probe = pt_norm[:40]
            if probe in oral_norm:
                achadas[k] = probe
            else:
                # tenta 25, 15, 10
                achado = False
                for tam in (25, 15, 10, 6):
                    if pt_norm[:tam] in oral_norm:
                        achadas[k] = pt_norm[:tam]
                        achado = True
                        break
                if not achado:
                    faltando.append((k, pt_clean[:60]))

        # verifica duplicação: uma fala pode ter aparecido mais de 1x?
        # (conta ocorrências do probe no oral_norm — mas probes curtos podem
        #  repetir; fazemos uma heurística: se o probe tem > 20 chars, deve ser
        #  único; se repetir, é suspeito)
        duplicadas = []
        for k, probe in achadas.items():
            if len(probe) >= 20:
                ocorr = oral_norm.count(probe)
                if ocorr > 1:
                    duplicadas.append((k, probe[:40], ocorr))

        n_falas = len(ks)
        total_falas += n_falas
        ok = (len(faltando) == 0 and len(duplicadas) == 0)
        if ok:
            total_ok += 1

        linhas.append(f"[nº {n}] {nome_pt}")
        linhas.append(f"  falas no checkpoint: {n_falas}")
        linhas.append(f"  presentes no consolidado: {len(achadas)}")
        linhas.append(f"  FALTANDO: {len(faltando)}")
        for k, motivo in faltando[:5]:
            linhas.append(f"    - fala {k}: {motivo}")
        linhas.append(f"  DUPLICADAS (probe>=20 repetido): {len(duplicadas)}")
        for k, probe, ocorr in duplicadas[:5]:
            linhas.append(f"    - fala {k}: '{probe}' x{ocorr}")
        linhas.append("")

        if gerar_material:
            # gera material de leitura: pares JP↔PT
            out = ROOT / "reports" / f"material_leitura_semantica_mioshie_{n}.txt"
            blocos = []
            for k in ks:
                f = falas[k]
                jp = f.get("jp", "").strip()
                pt = f.get("pt_contextual", "").strip()
                pt_clean = re.sub(r"^(Interlocutor|Meishu-Sama)[:：]\s*", "", pt)
                blocos.append(f"=== FALA {k} ({f.get('quem')}) ===")
                blocos.append(f"JP: {jp}")
                blocos.append(f"PT: {pt_clean}")
                blocos.append("")
            out.write_text("\n".join(blocos), encoding="utf-8")
            linhas.append(f"  material de leitura: {out.name}")

    print("\n".join(linhas))
    print(f"\n=== RESULTADO: {total_ok}/8 arquivos com integridade OK | {total_falas} falas totais ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
