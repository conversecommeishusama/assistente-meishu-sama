"""Aplica UMA correção de cada vez (protocolo dos 213), com guardas.

Recebe um JSON com a lista de correções JÁ DECIDIDAS manualmente
(cada uma lida JP<->PT antes), e aplica uma a uma:

  - o `de` tem que ocorrer EXATAMENTE 1 vez no arquivo (senão recusa);
  - backup da obra uma vez por execução, antes da primeira escrita;
  - `valida_ancoras` depois de cada troca -- se quebrar, DESFAZ a troca e
    marca DUVIDA (nunca grava âncora quebrada);
  - grava FONTE e STAGING idênticos ao final da obra.

Formato de entrada: [{"chave":..., "obra":..., "de":..., "para":...}, ...]
Uso: python3 scripts/ajuste_aplica.py <correcoes.json> [--aplicar]
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from mescla_e_aplica import valida_ancoras  # noqa: E402
from implanta_semantico_v2 import PT_FONTE, PT_STAGING  # noqa: E402


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    entrada = [a for a in sys.argv[1:] if a != "--aplicar"][0]
    itens = json.loads(Path(entrada).read_text(encoding="utf-8"))
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    por_obra: dict[str, list[dict]] = {}
    for it in itens:
        por_obra.setdefault(it["obra"], []).append(it)

    resultado = []
    for obra, casos in por_obra.items():
        f = PT_FONTE / obra
        texto = f.read_text(encoding="utf-8")
        original = texto
        for c in casos:
            de, para = c["de"], c["para"]
            n = texto.count(de)
            if n != 1:
                resultado.append({"chave": c["chave"], "resultado": "DUVIDA",
                                  "nota": f"`de` ocorre {n}x no arquivo (não é único)"})
                continue
            if para in texto and de != para:
                # já aplicado de outra forma em outro ponto? só informativo
                pass
            novo = texto.replace(de, para, 1)
            ok, motivo = valida_ancoras(obra, novo)
            if not ok:
                resultado.append({"chave": c["chave"], "resultado": "DUVIDA",
                                  "nota": f"quebraria âncora ({motivo}) -- não aplicado"})
                continue
            texto = novo
            resultado.append({"chave": c["chave"], "resultado": "APLICADO",
                              "nota": c.get("nota", "")})
        if texto != original and aplicar:
            shutil.copy(f, f.with_name(f.name + f".bak_ajuste_{carimbo}"))
            f.write_text(texto, encoding="utf-8")
            (PT_STAGING / obra).write_text(texto, encoding="utf-8")
            print(f"[gravado] {obra}  ({sum(1 for r in resultado if r['resultado']=='APLICADO')} acumulados)")
        elif texto != original:
            print(f"[ensaio] {obra}: {len(casos)} casos, texto mudaria")

    print(json.dumps(resultado, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
