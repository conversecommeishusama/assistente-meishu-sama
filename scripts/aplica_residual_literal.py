"""Aplica os 58 itens decididos (A/B/OUTRO) por substituição literal
direta -- as leituras já foram verificadas semanticamente por mim (não
pelo DeepSeek reescrevendo), então não precisa passar por emenda()/
contido(). Mesma segurança de sempre: backup por obra, âncora
revalidada, reversão se a contagem de artigos mudar.
"""
import json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors
from build_clean_large_indexes import clean_body

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"

ITENS = json.loads(Path("/tmp/claude-0/-var-www-goshinsho/9b3b11e7-4883-4ae9-9b3b-2fbf84182cdd/scratchpad/residual_itens_para_aplicar.json").read_text(encoding="utf-8"))

REPLACE_ALL_CHAVES = {"REFORMAR:Eiko.txt|331|3|2"}  # mesma frase repetida no artigo, corrige as 2


def main():
    aplicar = "--aplicar" in sys.argv
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    por_obra = {}
    for it in ITENS:
        por_obra.setdefault(it["obra"], []).append(it)

    aplicadas, recusadas = [], []
    for obra, itens in sorted(por_obra.items()):
        f = PT_FONTE / obra
        if not f.exists():
            for it in itens:
                recusadas.append((it["chave"], "obra inexistente"))
            continue
        antes = f.read_text(encoding="utf-8")
        texto = antes
        ok_n = 0
        for it in itens:
            n = texto.count(it["de"])
            if it["chave"] in REPLACE_ALL_CHAVES:
                if n < 1:
                    recusadas.append((it["chave"], f"{n} ocorrências"))
                    continue
                texto = texto.replace(it["de"], it["para"])
            else:
                if n != 1:
                    recusadas.append((it["chave"], f"{n} ocorrências (esperava 1)"))
                    continue
                texto = texto.replace(it["de"], it["para"])
            aplicadas.append(it["chave"])
            ok_n += 1
        if not ok_n:
            continue
        if not aplicar:
            print(f"  {obra[:44]:<46} {ok_n:>3} emendadas (ensaio)")
            continue
        shutil.copy(f, f.with_suffix(f".txt.bak_residual2_{carimbo}"))
        f.write_text(texto, encoding="utf-8")
        (PT_STAGING / obra).write_text(texto, encoding="utf-8")
        sp = SPEC_DIR / f"{obra}.json"
        if sp.exists():
            anc = [x.get("pt_anchor", "") for x in
                   json.loads(sp.read_text(encoding="utf-8")).get("articles", [])]
            if len(anc) > 1 and all(anc):
                try:
                    if len(split_by_anchors(clean_body(texto), anc, label=obra)) != len(anc):
                        raise ValueError("contagem")
                except ValueError:
                    print(f"  *** ÂNCORA QUEBRADA — REVERTENDO {obra}")
                    f.write_text(antes, encoding="utf-8")
                    (PT_STAGING / obra).write_text(antes, encoding="utf-8")
                    aplicadas = [c for c in aplicadas
                                 if not any(c == it["chave"] for it in itens)]
                    continue
        print(f"  {obra[:44]:<46} {ok_n:>3} aplicadas")

    print(f"\n{len(aplicadas)} aplicadas, {len(recusadas)} recusadas")
    for k, m in recusadas:
        print(f"  {k}: {m}")
    if not aplicar:
        print("(ensaio — nada gravado; rode com --aplicar)")


if __name__ == "__main__":
    main()
