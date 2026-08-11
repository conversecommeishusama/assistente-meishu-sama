"""Reaplica pilha A nas 6 obras revertidas, regenerando a âncora do(s)
artigo(s) cujo texto de abertura foi tocado pela correção -- mesmo padrão em
todas: a âncora é um prefixo de comprimento fixo do texto do próprio artigo,
e a correção aprovada altera texto bem na fronteira desse corte.
"""
import sys, json, shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import auditoria as A
import triagem as T
from apply_manual_livros_segmentacao import split_by_anchors
from build_clean_large_indexes import clean_body
from aplica_no_artigo import janelas

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
REGISTRO = RAIZ / "reports/varredura_padronizacao/APLICADO.json"

REVERTIDAS = [
    "19491130-自観叢書第8篇『明麿近詠集』.txt",
    "19520420-御教え集8号.txt",
    "19521215-御教え集16号.txt",
    "19541120-浄霊法講座（四）薬理批判『浄霊法講座』4号.txt",
    "Eiko.txt",
    "Tijotengoku.txt",
]

d1 = T._le(T.DS1)
proc = {A.chave(r): r for r in A.procedentes()}


def regenera_ancora(anc_velha: str, texto_novo: str) -> str | None:
    """Acha a posição via o maior prefixo da âncora velha que sobrevive
    intacto no texto novo, e recorta a âncora nova do mesmo comprimento."""
    n = len(anc_velha)
    for corte in range(n, 14, -1):
        prefixo = anc_velha[:corte]
        if texto_novo.count(prefixo) == 1:
            pos = texto_novo.find(prefixo)
            return texto_novo[pos:pos + n + 60]  # folga p/ conteúdo inserido
    return None


def main():
    aplicar = "--aplicar" in sys.argv
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    feitos_reg = set(json.loads(REGISTRO.read_text(encoding="utf-8"))
                      if REGISTRO.exists() else [])
    novas_feitas = []

    for obra in REVERTIDAS:
        itens = []
        for k in T.pilhas()["A"]:
            if not k.startswith(obra + "|") or k in feitos_reg:
                continue
            if d1[k]["veredito"] != "aprovado" or k not in proc:
                continue
            it = proc[k]
            itens.append({"chave": k, "artigo": it["artigo"], "de": it["de"], "para": it["para"]})

        f = PT_FONTE / obra
        texto = f.read_text(encoding="utf-8")
        antes = texto
        jan = janelas(obra, texto)
        feitas = []

        for it in itens:
            if jan is None or it["artigo"] >= len(jan):
                print(f"  PULO {it['chave']}: janela indisponível")
                continue
            ini, fim = jan[it["artigo"]]
            bloco = texto[ini:fim]
            if bloco.count(it["de"]) != 1:
                print(f"  PULO {it['chave']}: {bloco.count(it['de'])} ocorrências na janela")
                continue
            texto = texto[:ini] + bloco.replace(it["de"], it["para"]) + texto[fim:]
            jan = janelas(obra, texto) or jan
            feitas.append(it["chave"])

        print(f"\n{obra}: {len(feitas)}/{len(itens)} aplicadas nesta passada")
        if not feitas:
            continue

        # acha e regenera âncoras quebradas
        sp = SPEC_DIR / f"{obra}.json"
        spec = json.loads(sp.read_text(encoding="utf-8"))
        arts = spec["articles"]
        anc = [a.get("pt_anchor", "") for a in arts]

        try:
            ok = len(split_by_anchors(clean_body(texto), anc, label=obra)) == len(anc)
        except ValueError:
            ok = False

        if not ok:
            corrigidas = []
            for i, a in enumerate(arts):
                velha = a.get("pt_anchor", "")
                if not velha:
                    continue
                if velha in texto:
                    continue  # ainda bate, não mexe
                nova = regenera_ancora(velha, texto)
                if nova is None:
                    print(f"  *** não consegui regenerar a âncora do art{i} — abortando obra")
                    corrigidas = None
                    break
                a["pt_anchor"] = nova
                corrigidas.append(i)
            if corrigidas is None:
                print(f"  *** REVERTENDO {obra} (âncora não regenerável)")
                continue
            if corrigidas:
                print(f"  âncoras regeneradas: art{corrigidas}")

            anc = [a.get("pt_anchor", "") for a in arts]
            try:
                ok = len(split_by_anchors(clean_body(texto), anc, label=obra)) == len(anc)
            except ValueError:
                ok = False

        if not ok:
            print(f"  *** AINDA QUEBRADA — REVERTENDO {obra}, nada gravado")
            continue

        print(f"  {obra}: OK, {len(feitas)} aplicadas + âncoras revalidadas")
        if not aplicar:
            continue

        shutil.copy(f, f.with_suffix(f".txt.bak_pilhaA_repara_{carimbo}"))
        f.write_text(texto, encoding="utf-8")
        (PT_STAGING / obra).write_text(texto, encoding="utf-8")
        sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        novas_feitas.extend(feitas)

    if aplicar and novas_feitas:
        REGISTRO.write_text(
            json.dumps(sorted(feitos_reg | set(novas_feitas)), ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"\nregistro atualizado: +{len(novas_feitas)} (total {len(feitos_reg | set(novas_feitas))})")
    if not aplicar:
        print("\n(diagnóstico -- rode com --aplicar)")


if __name__ == "__main__":
    main()
