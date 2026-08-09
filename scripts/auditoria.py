"""Registro das minhas decisões de auditoria sobre os achados verificados.

Nada é gravado no corpus sem passar por aqui. Cada achado que sobrevive à
verificação adversarial recebe um veredito meu, lido contra o japonês:

  aprovado  -- erro real, correção correta na forma e no conteúdo
  recusado  -- não é erro, ou a correção proposta está errada
  reformar  -- o erro é real mas a correção proposta viola o protocolo
               (kanji solto no português, termo fora do glossário…)

Por que existe o `reformar`: dois dos vinte primeiros graves que li eram
omissões verdadeiras, mas a correção proposta enfiava kanji cru no português
(«e "エ"», «flexibilidade perfeita (円転滑脱)»), contra o §5.2 do protocolo.
Aplicar como veio consertaria o sentido e quebraria a forma.

Uso:
    python3 scripts/auditoria.py --pendentes [N]   # o que falta eu ler
    python3 scripts/auditoria.py --resumo
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
VERIF = RAIZ / "reports/varredura_padronizacao/VERIFICACAO_FIDELIDADE.json"
DESTINO = RAIZ / "reports/varredura_padronizacao/AUDITORIA.json"


def chave(r: dict) -> str:
    return f"{r['obra']}|{r['artigo']}|{r.get('parte', 0)}|{r['i']}"


def carrega() -> dict[str, dict]:
    if DESTINO.exists():
        return json.loads(DESTINO.read_text(encoding="utf-8"))
    return {}


def grava(d: dict) -> None:
    DESTINO.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                       encoding="utf-8")


def registra(vereditos: dict[str, tuple[str, str]]) -> None:
    """chave -> (veredito, nota). Acumula, nunca sobrescreve o arquivo todo."""
    d = carrega()
    for k, (v, nota) in vereditos.items():
        d[k] = {"veredito": v, "nota": nota}
    grava(d)
    print(f"{len(vereditos)} vereditos registrados ({len(d)} no total)")


def procedentes() -> list[dict]:
    if not VERIF.exists():
        return []
    return [r for r in json.loads(VERIF.read_text(encoding="utf-8"))
            if "erro" not in r and r.get("procede")]


def pendentes(n: int = 20, grau: str = "GRAVE") -> list[dict]:
    feitos = set(carrega())
    return [r for r in procedentes()
            if r["grau"] == grau and chave(r) not in feitos][:n]


def resumo() -> None:
    d = carrega()
    c = Counter(v["veredito"] for v in d.values())
    proc = procedentes()
    pg = sum(1 for r in proc if r["grau"] == "GRAVE")
    pm = sum(1 for r in proc if r["grau"] == "MEDIO")
    print(f"procedentes hoje: {pg:,} graves, {pm:,} médios")
    print(f"auditados: {len(d):,}")
    for k, v in c.most_common():
        print(f"  {k:<10} {v:,}")


def dossie(k: str) -> str:
    """Tudo o que é preciso para julgar um achado -- montado por código.

    A checagem de âncora fica AQUI, não no julgamento: em 2026-08-09 eu aprovei
    três correções que mexiam em âncora de segmentação porque julguei de
    cabeça, e o DeepSeek, consultando, acertou os três. Fato consultável não
    se decide por opinião.

    A contagem no acervo entra como CONTEXTO, nunca como autoridade: no mesmo
    teste ela fez recusar duas correções certas (重吉->Jūkichi, 伊都能売->Izunome)
    porque a forma errada era a dominante. Erro dominante continua erro.
    """
    import verifica_fidelidade as V
    it = {A2["chave"]: A2 for A2 in
          [{**r, "chave": chave(r)} for r in procedentes()]}.get(k)
    if not it:
        return f"(achado {k} não está mais na lista de procedentes)"
    jp, pt = V.textos(it["obra"], it["artigo"])
    p_ = pt.find(it["de"])
    viz = pt[max(0, p_ - 900):p_ + len(it["de"]) + 900] if p_ >= 0 else it["de"]

    # âncora: fato, verificado em código
    sp = RAIZ / f"reports/livros_trabalho/segmentacao_manual/{it['obra']}.json"
    aviso = ""
    if sp.exists():
        arts = json.loads(sp.read_text(encoding="utf-8")).get("articles", [])
        for i, a in enumerate(arts):
            anc = a.get("pt_anchor", "")
            if anc and (it["de"] in anc or anc[:40] in it["de"]):
                aviso = (f"\n*** ÂNCORA DE SEGMENTAÇÃO do artigo {i}. Mudar o "
                         f"texto quebra a busca: veredito REFORMAR. ***\n")
                break

    # o texto vem do arquivo ATUAL -- um achado pode já ter sido consertado
    atual = (RAIZ / f"livros_publicacao_pt_revisado/{it['obra']}").read_text(
        encoding="utf-8")
    if it["de"] not in atual:
        aviso += ("\n*** O trecho NÃO existe mais no arquivo atual — já foi "
                  "corrigido ou reescrito. Veredito RECUSADO (obsoleto). ***\n")

    glos = V.glossario_do_trecho(it.get("jp_apoio", "") + it["de"], viz,
                                 it["para"] + it["motivo"])
    return (f"CHAVE: {k}\nOBRA: {it['obra']}  artigo {it['artigo']}\n{aviso}{glos}"
            f"\n=== JAPONÊS (artigo inteiro) ===\n{jp[:14000]}\n"
            f"\n=== PORTUGUÊS (em volta do trecho) ===\n{viz}\n"
            f"\n=== CORREÇÃO PROPOSTA ===\ntrecho atual: {it['de']}\n"
            f"viraria:      {it['para']}\nalegação:     {it['motivo']}\n")


def main() -> None:
    if "--dossie" in sys.argv:
        print(dossie(sys.argv[sys.argv.index("--dossie") + 1]))
        return
    if "--veredito" in sys.argv:
        i = sys.argv.index("--veredito")
        k, v, nota = sys.argv[i + 1], sys.argv[i + 2], sys.argv[i + 3]
        if v not in ("aprovado", "recusado", "reformar"):
            print(f"veredito inválido: {v}")
            sys.exit(1)
        registra({k: (v, nota)})
        return
    if "--resumo" in sys.argv:
        resumo()
        return
    if "--pendentes" in sys.argv:
        i = sys.argv.index("--pendentes")
        n = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 20
        grau = "MEDIO" if "--medio" in sys.argv else "GRAVE"
        for r in pendentes(n, grau):
            print(f"@{chave(r)}")
            print(f"    PT : {r['de'][:100]}")
            print(f"    ->  : {r['para'][:100]}")
            print(f"    JP : {r['jp_apoio'][:80]}")
            print(f"    por: {r['razao'][:110]}")


if __name__ == "__main__":
    main()
