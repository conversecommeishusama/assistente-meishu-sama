"""Reaplica as decisões de glossário LENDO cada artigo, JP e PT lado a lado.

Determinação do usuário (2026-08-08), depois de os scripts de substituição
terem produzido 355 erros em 1.292 alterações:

    "TODO O TRABALHO DEVE SER FEITO LINHA A LINHA COMPARANDO JP PT DE FORMA
     SEMÂNTICA."

Nenhuma alteração aqui nasce de busca-e-troca. O modelo recebe o artigo
japonês e o artigo português, lê os dois, e devolve por ocorrência o trecho
exato e o trecho corrigido. Cada proposta é conferida antes de gravar, e só
grava se o trecho for único no arquivo.

O que produziu o estrago e não se repete: aprovar um artigo e aplicar no
livro; trocar substring sem fronteira de palavra ("coração" virou "cnorito");
presumir que contagem igual significa correspondência.

Uso:
    python3 scripts/reaplica_semantico.py            # lê e propõe
    python3 scripts/reaplica_semantico.py --aplicar  # grava o já lido
"""

from __future__ import annotations

import json
import re
import sys
import threading
from collections import Counter
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
DESTINO = RAIZ / "reports/varredura_padronizacao/REAPLICACAO_SEMANTICA.json"
MODELO = "deepseek-v4-flash"
PARALELISMO = 8

# Chaves japonesas que fazem um artigo entrar na leitura.
CHAVES = [
    "地上天国", "浄化作用", "解毒作用", "溶解作用", "野菜", "御屏風観音様",
    "御屏風観音", "祝詞", "支部", "大光明如来", "悪霊", "中教会", "大教会",
    "大先生", "真善美", "五六七の世", "副霊", "濁血", "本守護神", "根底の国",
    "メシヤ会館", "救世会館", "肺結核", "千手観音様", "日光殿", "信仰雑話",
    "証覚", "報恩感謝", "凝結", "因縁", "経綸", "現界", "神格", "念被観音力",
    "凝結毒素", "弥勒大神", "閻魔の帳", "光波", "唯物論", "唯心論",
]

SYSTEM = """Você é revisor de tradução japonês→português do acervo de Meishu-Sama (Igreja Messiânica Mundial).

Recebe UM artigo em japonês e o MESMO artigo em português. Leia os dois frase a frase, do início ao fim, e aplique as decisões de glossário abaixo — mas SOMENTE onde o japonês daquele ponto sustentar.

DECISÕES (todas tomadas pelo usuário, especialista do domínio):

地上天国 → "Paraíso Terrestre"
    EXCEÇÃO: quando for o nome do PERIÓDICO (『地上天国』, 雑誌『地上天国』),
    a citação vira "Tijotengoku" — como os irmãos Eikō, Hikari, Kyusei,
    Mioshie-shū. Ex.: "Paraíso na Terra nº 25" → "Tijotengoku nº 25".
浄化作用 → "processo de purificação"; pode alternar com "ação purificadora"
    se a repetição ficar próxima e redundante
解毒作用 → "processo de desintoxicação"   溶解作用 → "processo de dissolução"
野菜 → "hortaliças"; "legumes" se o texto enumera só não-folhas; "verduras"
    se só folhas. NUNCA "vegetais" (abrange fruta, e o japonês contrapõe
    野菜 a 果実). CUIDADO: 植物 é "planta" e "vegetal" ali está CERTO —
    "óleo vegetal", "reino vegetal", "origem vegetal", "vegetariano".
御屏風観音様/御屏風観音 → "Byōbu Kannon", SEM ARTIGO (como Komyo-Nyorai).
    Só na 1ª menção do artigo: "Byōbu Kannon (Kannon do biombo)".
    Preposição contraída vira simples: "diante DA" → "diante DE".
祝詞 → "norito" (masculino: "o norito"). CUIDADO: 祈り/祈願/お祈り são
    "oração"/"prece" e NÃO mudam.
支部 → "filial"        中教会 → "Igreja Média"     大教会 → "Igreja Grande"
大光明如来 → "Daikōmyō Nyorai". CUIDADO GRAVE: 光明如来 sem o 大 é
    "Komyo-Nyorai", OUTRA Imagem. Nunca converta uma na outra.
悪霊 → "espíritos malignos". CUIDADO: 邪神 é "Divindades malignas", termo
    distinto que não muda.
大先生 → "Grão-Mestre", só quando for título de Meishu-Sama. CUIDADO:
    先生 sozinho e 〇〇先生 (Mestre Inoue etc.) são "Mestre" e não mudam.
真善美 → "a Verdade, o Bem e o Belo" (ou "Verdade, Bem e Belo" conforme a
    frase). Bem por oposição a Mal; nunca "Bondade".
五六七の世 → "Mundo de Miroku"      副霊 → "Espírito Secundário"
濁血 → "sangue turvo"              本守護神 → "espírito protetor primordial"
根底の国 → "Reino do Fundo da Raiz"
メシヤ会館 e 救世会館 → "Templo Messiânico" (o mesmo prédio de Atami)
肺結核 → "tuberculose pulmonar"    千手観音様/千手観音 → "Kannon de Mil Braços"
日光殿 → "Nikkōden (Palácio da Luz Solar)" na 1ª menção, depois "Nikkōden"
信仰雑話 → "Shinkō Zatsuwa"        証覚/智慧証覚 → "Chieshōkaku"
報恩感謝 → "retribuição em gratidão"   凝結 → "solidificação"
因縁 → "innen"        経綸 → "Plano Divino"      現界 → "mundo material"
神格 → "qualificação divina"       念被観音力 → "Graça do Poder Kannon"
凝結毒素 → "toxinas solidificadas"  弥勒大神 → "Miroku Ōkami"
閻魔の帳 → "registo de Enma"        光波 → "ondas de Luz"
唯物論 → "teoria materialista"      唯心論 → "teoria espiritualista"
    (唯物主義 é "materialismo" e 唯物思想 é "pensamento materialista" —
     estes NÃO mudam)

REGRAS DE OURO:
1. Só proponha troca se o japonês DAQUELE ponto trouxer a chave. Se não
   conseguir localizar a correspondência, não proponha.
2. Preserve a gramática: gênero, número, artigo, preposição contraída. Se a
   troca mudar o gênero da palavra, ajuste o que a acompanha.
3. Nunca toque numa palavra portuguesa que apenas contenha o termo como
   pedaço ("coração" contém "oração"; "preceito" contém "prece").
4. O trecho que você citar precisa existir LITERALMENTE no português dado.

FORMATO — uma linha por ocorrência, nada mais:

TROCA | <trecho português exato, 4 a 10 palavras> | <o mesmo trecho corrigido>

Se o artigo não precisar de nenhuma mudança:

NADA
"""


def artigos(caminho: Path, campo: str, obra: str) -> list[str]:
    spec_path = SPEC_DIR / f"{obra}.json"
    if not spec_path.exists() or not caminho.exists():
        return []
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    texto = clean_body(caminho.read_text(encoding="utf-8", errors="replace"))
    arts = spec.get("articles", [])
    anc = [a.get(campo, "") for a in arts]
    if len(arts) <= 1 or not all(anc):
        return [texto]
    try:
        pedacos = split_by_anchors(texto, anc, label=obra)
    except ValueError:
        return [texto]
    return pedacos if len(pedacos) == len(arts) else [texto]


def alvos() -> list[dict]:
    saida = []
    for p in sorted(PT_FONTE.glob("*.txt")):
        obra = p.name
        ajp = artigos(JP_DIR / obra, "jp_anchor", obra)
        apt = artigos(p, "pt_anchor", obra)
        if not ajp or len(ajp) != len(apt):
            continue
        for i, (jp, pt) in enumerate(zip(ajp, apt)):
            if not any(k in jp for k in CHAVES):
                continue
            saida.append({"obra": obra, "artigo": i,
                          "jp": jp[:14000], "pt": pt[:14000]})
    return saida


def julga(item: dict) -> dict:
    pedido = (f"ORIGEM: {item['obra']} (artigo {item['artigo']})\n\n"
              f"=== JAPONÊS ===\n{item['jp']}\n\n"
              f"=== PORTUGUÊS ===\n{item['pt']}")
    texto, tokens, tent = "", 0, 0
    while not texto.strip() and tent < 3:
        tent += 1
        extra = "\n\nIMPORTANTE: responda DIRETAMENTE no formato." if tent > 1 else ""
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
            # exige que o trecho citado exista MESMO no português deste artigo
            if partes[1] in item["pt"]:
                trocas.append({"de": partes[1], "para": partes[2]})
    return {"obra": item["obra"], "artigo": item["artigo"],
            "trocas": trocas, "tokens": tokens, "bruto": texto[:4000]}


def aplicar() -> None:
    dados = json.loads(DESTINO.read_text(encoding="utf-8"))
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    por_obra: dict[str, list[dict]] = {}
    for d in dados:
        for t in d.get("trocas", []):
            por_obra.setdefault(d["obra"], []).append(t)

    apl = ign = 0
    for obra, ts in por_obra.items():
        for base in (PT_FONTE, PT_STAGING):
            f = base / obra
            if not f.exists():
                continue
            texto = f.read_text(encoding="utf-8")
            if base is PT_FONTE:
                f.with_suffix(f".txt.bak_pre_reaplica_{carimbo}").write_text(
                    texto, encoding="utf-8")
            for t in ts:
                # só grava trecho ÚNICO -- nunca replace global
                if texto.count(t["de"]) != 1:
                    if base is PT_FONTE:
                        ign += 1
                    continue
                texto = texto.replace(t["de"], t["para"])
                if base is PT_FONTE:
                    apl += 1
            f.write_text(texto, encoding="utf-8")
    print(f"{apl} trocas aplicadas, {ign} ignoradas (trecho não único no arquivo)")

    ruins = 0
    for obra in por_obra:
        sp = SPEC_DIR / f"{obra}.json"
        if not sp.exists():
            continue
        spec = json.loads(sp.read_text(encoding="utf-8"))
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
            for corte in (50, 38, 26):
                ch = alvo[:corte]
                if texto.count(ch) == 1:
                    a["pt_anchor"] = texto[texto.find(ch): texto.find(ch) + len(alvo)]
                    mudou = True
                    break
        if mudou:
            sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
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
    feitos = []
    if DESTINO.exists():
        feitos = json.loads(DESTINO.read_text(encoding="utf-8"))
        vistos = {(r["obra"], r["artigo"]) for r in feitos}
        itens = [i for i in itens if (i["obra"], i["artigo"]) not in vistos]
        print(f"retomando: {len(feitos)} lidos, {len(itens)} restantes", flush=True)
    print(f"{len(itens)} artigos a ler\n", flush=True)

    trava, n = threading.Lock(), [0]

    def trabalho(it):
        try:
            r = julga(it)
        except Exception as exc:
            r = {"obra": it["obra"], "artigo": it["artigo"],
                 "erro": repr(exc)[:140], "trocas": []}
        with trava:
            feitos.append(r)
            n[0] += 1
            if n[0] % 25 == 0:
                print(f"[{n[0]:>4}/{len(itens)}] {r['obra'][:30]:<32} "
                      f"{sum(len(x.get('trocas', [])) for x in feitos)} trocas acumuladas",
                      flush=True)
            DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                               encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, itens))
    tk = sum(r.get("tokens", 0) for r in feitos)
    tot = sum(len(r.get("trocas", [])) for r in feitos)
    print(f"\n{len(feitos)} artigos lidos | {tot} trocas propostas | "
          f"{tk:,} tokens | ~US$ {tk / 1e6 * 0.0424:.3f}")


if __name__ == "__main__":
    main()
