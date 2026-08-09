"""Sincroniza a fila da auditoria com o que a verificação já aprovou.

Roda antes de cada iteração do laço, sem custo de API. A leitura e a
verificação continuam produzindo achados enquanto a auditoria corre, então a
fila não pode ser fixa -- ela cresce sozinha.

Ordem: GRAVE antes de MEDIO, e dentro de cada grau na ordem em que saíram.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, "/var/www/goshinsho"); sys.path.insert(0, "/var/www/goshinsho/scripts")
import auditoria as A

Q = Path("/var/www/goshinsho/reports/auditoria_loop/AUDITORIA_QUEUE.json")
feitos = set(A.carrega())
proc = A.procedentes()
graves = [A.chave(r) for r in proc if r["grau"] == "GRAVE"]
medios = [A.chave(r) for r in proc if r["grau"] == "MEDIO"]
pend = [k for k in graves + medios if k not in feitos]

antes = json.loads(Q.read_text()) if Q.exists() else {"pending": [], "done": []}
Q.write_text(json.dumps({"pending": pend, "done": sorted(feitos)},
                        ensure_ascii=False, indent=1), encoding="utf-8")
print(f"fila: {len(pend)} pendentes ({len(graves)} graves, {len(medios)} médios "
      f"procedentes; {len(feitos)} já auditados)")
