import sys, json, shutil
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

REVERTIDOS_CHAVES = {
    "REFORMAR:19480701-御讃歌集.txt|215|0|0",
    "REFORMAR:19491130-自観叢書第8篇『明麿近詠集』.txt|214|0|0",
    "REFORMAR:19491130-自観叢書第8篇『明麿近詠集』.txt|241|0|0",
    "REFORMAR:19491130-自観叢書第8篇『明麿近詠集』.txt|28|0|0",
    "REFORMAR:19491223-山と水.txt|171|0|0",
    "REFORMAR:19491223-山と水.txt|81|0|0",
    "REFORMAR:19491223-山と水.txt|99|0|0",
    "REFORMAR:19491230-自観叢書第9篇『光への道』.txt|19|0|0",
    "REFORMAR:19530101-アメリカを救う.txt|10|0|2",
}

ITENS = [it for it in json.loads(Path("/tmp/claude-0/-var-www-goshinsho/9b3b11e7-4883-4ae9-9b3b-2fbf84182cdd/scratchpad/residual_itens_para_aplicar.json").read_text(encoding="utf-8"))
         if it["chave"] in REVERTIDOS_CHAVES]


def regenera_ancora(anc_velha, texto_novo):
    n = len(anc_velha)
    for corte in range(n, 14, -1):
        prefixo = anc_velha[:corte]
        if texto_novo.count(prefixo) == 1:
            pos = texto_novo.find(prefixo)
            return texto_novo[pos:pos + n + 60]
    return None


def main():
    aplicar = "--aplicar" in sys.argv
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    por_obra = {}
    for it in ITENS:
        por_obra.setdefault(it["obra"], []).append(it)

    for obra, itens in sorted(por_obra.items()):
        f = PT_FONTE / obra
        antes = f.read_text(encoding="utf-8")
        texto = antes
        ok_n = 0
        for it in itens:
            n = texto.count(it["de"])
            if n != 1:
                print(f"  PULO {it['chave']}: {n} ocorrências")
                continue
            texto = texto.replace(it["de"], it["para"])
            ok_n += 1
        if not ok_n:
            continue

        sp = SPEC_DIR / f"{obra}.json"
        spec = json.loads(sp.read_text(encoding="utf-8"))
        arts = spec["articles"]
        anc = [a.get("pt_anchor", "") for a in arts]
        try:
            ok = len(split_by_anchors(clean_body(texto), anc, label=obra)) == len(anc)
        except ValueError:
            ok = False

        regeneradas = []
        if not ok:
            falhou = False
            for i, a in enumerate(arts):
                velha = a.get("pt_anchor", "")
                if not velha or velha in texto:
                    continue
                nova = regenera_ancora(velha, texto)
                if nova is None:
                    falhou = True
                    break
                a["pt_anchor"] = nova
                regeneradas.append(i)
            if falhou:
                print(f"  *** {obra}: âncora não regenerável -- pulando")
                continue
            anc = [a.get("pt_anchor", "") for a in arts]
            try:
                ok = len(split_by_anchors(clean_body(texto), anc, label=obra)) == len(anc)
            except ValueError:
                ok = False

        if not ok:
            print(f"  *** {obra}: ainda quebrada -- pulando")
            continue

        msg = f"  {obra[:44]:<46} {ok_n:>3} aplicadas"
        if regeneradas:
            msg += f"  (âncoras regeneradas: {regeneradas})"
        print(msg)
        if not aplicar:
            continue
        shutil.copy(f, f.with_suffix(f".txt.bak_residual3_{carimbo}"))
        f.write_text(texto, encoding="utf-8")
        (PT_STAGING / obra).write_text(texto, encoding="utf-8")
        if regeneradas:
            sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")

    if not aplicar:
        print("(ensaio -- rode com --aplicar)")


if __name__ == "__main__":
    main()
