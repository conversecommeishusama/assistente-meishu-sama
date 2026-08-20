#!/usr/bin/env python3
"""Verificação INTEGRAL de integridade dos Mioshie (texto completo, não sonda).

Para cada arquivo (1-8):
1. PRESENÇA TOTAL: o texto NORMALIZADO COMPLETO de cada fala do checkpoint
   deve aparecer como substring do consolidado normalizado (não só o início).
2. BALANÇO DE CARACTERES: soma dos comprimentos normalizados de todas as falas
   vs. comprimento do consolidado (descontando ficha, marcadores [data] e
   rótulos Interlocutor:/Meishu-Sama:). Diferença ≈ 0 ⇒ nada perdido/duplicado.
3. DUPLICAÇÃO: para cada fala com texto substancial (>40 chars norm), o texto
   completo não deve aparecer mais de 1x no consolidado (a menos que seja uma
   frase comum repetida — nesse caso sinaliza para revisão manual).

Uso: .venv/bin/python scripts/verificar_integridade_texto_completo.py
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


def limpar_rotulo(pt: str) -> str:
    return re.sub(r"^(Interlocutor|Meishu-Sama)[:：]\s*", "", pt or "").strip()


def main() -> int:
    total_ok = 0
    total_falas = 0
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

        # 1. PRESENÇA TOTAL de cada fala
        faltando = []
        soma_falas = 0
        for k in ks:
            f = falas[k]
            pt = limpar_rotulo(f.get("pt_contextual", ""))
            pt_norm = norm(pt)
            soma_falas += len(pt_norm)
            if pt_norm and pt_norm not in oral_norm:
                faltando.append((k, pt[:70]))

        # 2. BALANÇO DE CARACTERES
        # conteúdo do consolidado = oral_norm - ficha - marcadores [data] - rótulos
        # marcadores [data]: extrai os que estão entre colchetes em linha própria
        marcadores = re.findall(r"^\[([^\]]+)\]\s*$", oral, flags=re.M)
        soma_marcadores = sum(len(norm(m)) for m in marcadores)
        # rótulos: contagem de "Interlocutor:" e "Meishu-Sama:" (com dois-pontos)
        n_int = len(re.findall(r"Interlocutor[:：]", oral))
        n_ms = len(re.findall(r"Meishu-Sama[:：]", oral))
        soma_rotulos = n_int * len("Interlocutor:") + n_ms * len("Meishu-Sama:")
        # ficha: primeira linha (título) — comprimento
        ficha = oral.splitlines()[0] if oral.splitlines() else ""
        soma_ficha = len(norm(ficha))

        conteudo_consolidado = len(oral_norm) - soma_ficha - soma_marcadores - soma_rotulos
        dif = conteudo_consolidado - soma_falas

        # 3. DUPLICAÇÃO (falas substanciais > 40 chars norm)
        duplicadas = []
        for k in ks:
            f = falas[k]
            pt = limpar_rotulo(f.get("pt_contextual", ""))
            pt_norm = norm(pt)
            if len(pt_norm) > 40:
                ocorr = oral_norm.count(pt_norm)
                if ocorr > 1:
                    duplicadas.append((k, pt[:50], ocorr))

        n_falas = len(ks)
        total_falas += n_falas
        ok = (len(faltando) == 0 and abs(dif) <= 5 and len(duplicadas) == 0)
        if ok:
            total_ok += 1

        print(f"[nº {n}] {nome_pt}")
        print(f"  falas: {n_falas} | presentes(total): {n_falas - len(faltando)} | FALTANDO: {len(faltando)}")
        for k, motivo in faltando[:5]:
            print(f"    - fala {k}: {motivo!r}")
        print(f"  balanço: conteúdo_consolidado={conteudo_consolidado} vs soma_falas={soma_falas} => dif={dif} (≈0 = ok)")
        print(f"  duplicadas(substanciais): {len(duplicadas)}")
        for k, txt, ocorr in duplicadas[:5]:
            print(f"    - fala {k}: '{txt}' x{ocorr}")
        print()

    print(f"=== RESULTADO: {total_ok}/8 arquivos OK | {total_falas} falas ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
