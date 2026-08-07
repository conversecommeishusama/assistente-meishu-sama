"""Separa 野菜 (hortaliça) de 植物 (planta) no português.

Decisão do usuário (2026-08-07): 野菜 -> "hortaliças"; "legumes" quando o
texto enumera só não-folhas; "verduras" quando só folhas. A forma "vegetais"
sai, porque em português abrange fruta -- e o japonês contrasta 野菜 com 果実
explicitamente (「野菜と果実」).

O problema é que "vegetais" está traduzindo DUAS coisas:

    野菜   85 artigos   hortaliça, o alimento
    植物  149 no JP     planta, o organismo -- e aí "vegetal" está certo
                        ("óleo vegetal", "reino vegetal", "vida vegetal")

Uma troca cega de "vegetais" transformaria óleo de planta em óleo de
hortaliça. Por isso cada ocorrência é julgada pelo modelo, com o japonês ao
redor na mão, e só as que rendem 野菜 são trocadas.

Uso:
    python3 scripts/classifica_yasai.py           # gera o julgamento
    python3 scripts/classifica_yasai.py --aplicar # aplica o já julgado
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
JP_DIR = RAIZ / "reports/livros_trabalho/jp"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
DESTINO = RAIZ / ("reports/varredura_padronizacao/YASAI_JULGAMENTO%s.json"
            % ("_2" if "--passo2" in sys.argv else ""))
MODELO = "deepseek-v4-flash"
PARALELISMO = 6

SYSTEM = """Você revisa a tradução japonês→português do acervo de Meishu-Sama.

Recebe um artigo: as frases japonesas que contêm 野菜, e o texto português correspondente.

野菜 significa hortaliça — o alimento. Em português decidiu-se:
  - "hortaliças" como forma geral
  - "legumes" quando o texto enumera só não-folhas (pepino, abóbora, cenoura, berinjela, taro)
  - "verduras" quando o texto trata só de folhas (couve, alface, acelga)

A palavra "vegetais" NÃO deve ser usada para 野菜, porque em português abrange fruta, e o japonês contrasta 野菜 com 果実.

CUIDADO — o português também usa "vegetal/vegetais" para 植物 (planta, o organismo): "óleo vegetal", "reino vegetal", "adubo vegetal", "vida vegetal". Essas ocorrências estão CORRETAS e não devem ser tocadas.

Sua tarefa: para cada frase japonesa com 野菜, encontre a palavra portuguesa que a traduz e diga qual deve ser a forma correta.

FORMATO — uma linha por ocorrência, nada mais:

TROCA | <trecho português exato, com 3 a 8 palavras, contendo a palavra a mudar> | <o mesmo trecho já corrigido>

Se a ocorrência já estiver correta, ou se não conseguir localizar o trecho português com segurança, escreva:

MANTEM | <motivo em poucas palavras>

Nunca proponha trocar uma ocorrência que traduz 植物. Nunca invente trecho que não esteja no português fornecido."""


def artigos(caminho: Path, spec: dict, campo: str) -> list[str]:
    texto = clean_body(caminho.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n"))
    arts = spec.get("articles", [])
    anc = [a.get(campo, "") for a in arts]
    if len(arts) <= 1 or not all(anc):
        return [texto]
    try:
        pedacos = split_by_anchors(texto, anc, label=caminho.name)
    except ValueError:
        return [texto]
    return pedacos if len(pedacos) == len(arts) else [texto]


_cache: dict[str, tuple[list[str], list[str]]] = {}


def par(obra: str):
    if obra not in _cache:
        spec = json.loads((SPEC_DIR / f"{obra}.json").read_text(encoding="utf-8"))
        _cache[obra] = (artigos(JP_DIR / obra, spec, "jp_anchor"),
                        artigos(PT_FONTE / obra, spec, "pt_anchor"))
    return _cache[obra]


def alvos() -> list[dict]:
    saida = []
    for p in sorted(PT_FONTE.glob("*.txt")):
        obra = p.name
        if not (SPEC_DIR / f"{obra}.json").exists() or not (JP_DIR / obra).exists():
            continue
        ajp, apt = par(obra)
        if len(ajp) != len(apt):
            continue
        for i, (jp, pt) in enumerate(zip(ajp, apt)):
            if "野菜" not in jp:
                continue
            # 2ª passada: só artigos que ainda têm "vegetal/vegetais" solto
            # (não "vegetariano", que é outra palavra) e limites maiores. A
            # 1ª passada perdeu ~63 ocorrências por truncar em 6 frases e
            # 6.000 caracteres.
            if "--passo2" in sys.argv:
                if not re.search(r"\bvegeta(l|is)\b", pt, re.IGNORECASE):
                    continue
            frases = [re.sub(r"\s+", " ", jp[max(0, m.start() - 70): m.start() + 80])
                      for m in re.finditer("野菜", jp)]
            limite_f, limite_pt = (14, 14000) if "--passo2" in sys.argv else (6, 6000)
            saida.append({"obra": obra, "artigo": i, "frases_jp": frases[:limite_f],
                          "pt": pt[:limite_pt]})
    return saida


def julga(item: dict) -> dict:
    pedido = (
        f"ORIGEM: {item['obra']} (artigo {item['artigo']})\n\n"
        "FRASES JAPONESAS COM 野菜:\n"
        + "\n".join(f"  {k}. {f}" for k, f in enumerate(item["frases_jp"], 1))
        + f"\n\nTEXTO PORTUGUÊS DO MESMO ARTIGO:\n{item['pt']}")
    texto, tokens, tent = "", 0, 0
    while not texto.strip() and tent < 3:
        tent += 1
        extra = ("\n\nIMPORTANTE: responda DIRETAMENTE no formato pedido."
                 if tent > 1 else "")
        r = ag._client().chat.completions.create(
            model=MODELO, max_tokens=16000,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": pedido + extra}])
        u = r.usage
        tokens += (u.prompt_tokens or 0) + (u.completion_tokens or 0)
        texto = r.choices[0].message.content or ""
    trocas = []
    for ln in texto.splitlines():
        if not ln.strip().upper().startswith("TROCA"):
            continue
        partes = [x.strip() for x in ln.split("|")]
        if len(partes) >= 3 and partes[1] and partes[2] and partes[1] != partes[2]:
            trocas.append({"de": partes[1], "para": partes[2]})
    return {**{k: v for k, v in item.items() if k != "pt"},
            "trocas": trocas, "tokens": tokens, "bruto": texto}


def aplicar() -> None:
    dados = json.loads(DESTINO.read_text(encoding="utf-8"))
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    por_obra: dict[str, list[dict]] = {}
    for d in dados:
        for t in d.get("trocas", []):
            por_obra.setdefault(d["obra"], []).append(t)

    aplicadas = ignoradas = 0
    for obra, ts in por_obra.items():
        for base in (PT_FONTE, PT_STAGING):
            f = base / obra
            if not f.exists():
                continue
            texto = f.read_text(encoding="utf-8")
            if base is PT_FONTE:
                f.with_suffix(f".txt.bak_pre_yasai_{carimbo}").write_text(texto, encoding="utf-8")
            for t in ts:
                n = texto.count(t["de"])
                if n != 1:          # ambíguo ou inexistente: não toca
                    if base is PT_FONTE:
                        ignoradas += 1
                    continue
                texto = texto.replace(t["de"], t["para"])
                if base is PT_FONTE:
                    aplicadas += 1
            f.write_text(texto, encoding="utf-8")
    print(f"{aplicadas} trocas aplicadas, {ignoradas} ignoradas (trecho não único)")

    ruins = 0
    for obra in por_obra:
        spec_path = SPEC_DIR / f"{obra}.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        arts = spec.get("articles", [])
        anc = [a.get("pt_anchor", "") for a in arts]
        if len(anc) <= 1 or not all(anc):
            continue
        texto = clean_body((PT_FONTE / obra).read_text(encoding="utf-8"))
        mudou = False
        for a in arts:
            alvo = a.get("pt_anchor", "")
            if not alvo or alvo in texto:
                continue
            chv = alvo[:45]
            pos = texto.find(chv)
            if pos < 0 or texto.count(chv) != 1:
                continue
            a["pt_anchor"] = texto[pos: pos + len(alvo)]
            mudou = True
        if mudou:
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
            anc = [a["pt_anchor"] for a in arts]
        for base in (PT_FONTE, PT_STAGING):
            f = base / obra
            if not f.exists():
                continue
            try:
                c = split_by_anchors(clean_body(f.read_text(encoding="utf-8")), anc, label=obra)
                if len(c) != len(anc):
                    raise ValueError("contagem")
            except ValueError as exc:
                print(f"  QUEBROU {base.name}/{obra}: {exc}")
                ruins += 1
    print(f"  {len(por_obra)} obras tocadas, {ruins} âncoras quebradas")


def main() -> None:
    if "--aplicar" in sys.argv:
        aplicar()
        return
    itens = alvos()
    print(f"{len(itens)} artigos com 野菜\n", flush=True)
    feitos, trava, n = [], threading.Lock(), [0]

    def trabalho(it):
        try:
            r = julga(it)
        except Exception as exc:
            r = {**{k: v for k, v in it.items() if k != "pt"},
                 "erro": repr(exc)[:150], "trocas": []}
        with trava:
            feitos.append(r)
            n[0] += 1
            print(f"[{n[0]:>3}/{len(itens)}] {it['obra'][:30]:<32} art{it['artigo']:<4} "
                  f"{len(r.get('trocas', []))} trocas", flush=True)
            DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                               encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, itens))
    tk = sum(r.get("tokens", 0) for r in feitos)
    tot = sum(len(r.get("trocas", [])) for r in feitos)
    print(f"\n{tot} trocas propostas | {tk:,} tokens | ~US$ {tk / 1e6 * 0.0424:.4f}")


if __name__ == "__main__":
    main()
