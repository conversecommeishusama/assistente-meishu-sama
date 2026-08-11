"""Reaplica, com reparo de âncora, os itens que ficaram pendentes (obra
revertida) nas rodadas de aplica_213.py / aplica_reformar.py -- mesmo
princípio de repara_pilha_a_revertidas.py, adaptado pra escrita via
emenda() (o DeepSeek reescreve o parágrafo) em vez de replace literal.
"""
import sys, json, shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors
from build_clean_large_indexes import clean_body
from aplica_no_artigo import janelas
from aplicar_semantico import SPEC_DIR, PT_FONTE, PT_STAGING, contido, emenda, paragrafo


def regenera_ancora(anc_velha, texto_novo):
    n = len(anc_velha)
    for corte in range(n, 14, -1):
        prefixo = anc_velha[:corte]
        if texto_novo.count(prefixo) == 1:
            pos = texto_novo.find(prefixo)
            return texto_novo[pos:pos + n + 60]
    return None


def roda(compara_path, registro_path, aplicar):
    COMPARA = Path(compara_path)
    REGISTRO = Path(registro_path)
    d = json.loads(COMPARA.read_text(encoding="utf-8"))
    feitos = set(json.loads(REGISTRO.read_text(encoding="utf-8")) if REGISTRO.exists() else [])

    def escolhe(v):
        nota = (v.get("nota") or "").strip()
        return v["t2"] if nota[:2].upper().startswith("B") else v["t1"]

    itens = []
    for k, v in d.items():
        if "erro" in v or not v.get("concordam") or k in feitos:
            continue
        alvo = escolhe(v)
        if not alvo.strip() or alvo.strip() == v["de"].strip():
            continue
        itens.append({"chave": k, "obra": v["obra"], "artigo": v["artigo"],
                      "de": v["de"], "para": alvo})

    por_obra = {}
    for it in itens:
        por_obra.setdefault(it["obra"], []).append(it)

    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    novas = []

    for obra, lst in sorted(por_obra.items()):
        f = PT_FONTE / obra
        if not f.exists():
            continue
        antes = f.read_text(encoding="utf-8")
        texto = antes
        try:
            spj = json.loads((SPEC_DIR / f"{obra}.json").read_text(encoding="utf-8"))
            jp = split_by_anchors(
                clean_body((RAIZ / f"reports/livros_trabalho/jp/{obra}").read_text(encoding="utf-8")),
                [a["jp_anchor"] for a in spj["articles"]], label=obra)
        except Exception:
            jp = None

        feitas = []
        for it in lst:
            jan = janelas(obra, texto)
            if jan is None or it["artigo"] >= len(jan):
                continue
            ini, fim = jan[it["artigo"]]
            lim = paragrafo(texto, ini, fim, it["de"])
            if lim is None:
                continue
            par = texto[lim[0]:lim[1]]
            if par.count(it["de"]) != 1:
                continue
            jpt = jp[it["artigo"]] if jp and it["artigo"] < len(jp) else ""
            try:
                novo_par = emenda(jpt, par, it["de"], it["para"])
            except Exception:
                continue
            if contido(par, novo_par, it["de"], it["para"]):
                continue
            texto = texto[:lim[0]] + novo_par + texto[lim[1]:]
            feitas.append(it["chave"])

        if not feitas:
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
                print(f"  *** {obra}: âncora não regenerável -- REVERTENDO ({len(feitas)} perdidas)")
                continue
            anc = [a.get("pt_anchor", "") for a in arts]
            try:
                ok = len(split_by_anchors(clean_body(texto), anc, label=obra)) == len(anc)
            except ValueError:
                ok = False

        if not ok:
            print(f"  *** {obra}: ainda quebrada mesmo após regenerar -- REVERTENDO ({len(feitas)} perdidas)")
            continue

        msg = f"  {obra[:44]:<46} {len(feitas):>3} aplicadas"
        if regeneradas:
            msg += f"  (âncoras regeneradas: {regeneradas})"
        print(msg)
        if not aplicar:
            continue
        shutil.copy(f, f.with_suffix(f".txt.bak_repara2_{carimbo}"))
        f.write_text(texto, encoding="utf-8")
        (PT_STAGING / obra).write_text(texto, encoding="utf-8")
        if regeneradas:
            sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        novas.extend(feitas)

    if aplicar and novas:
        REGISTRO.write_text(json.dumps(sorted(feitos | set(novas)), ensure_ascii=False, indent=1),
                            encoding="utf-8")
    print(f"\n{compara_path}: +{len(novas)} aplicadas nesta rodada")


if __name__ == "__main__":
    aplicar = "--aplicar" in sys.argv
    R = RAIZ / "reports/varredura_padronizacao"
    roda(R / "COMPARA_213.json", R / "APLICADO_213.json", aplicar)
    print()
    roda(R / "COMPARA_REFORMAR.json", R / "APLICADO_REFORMAR.json", aplicar)
