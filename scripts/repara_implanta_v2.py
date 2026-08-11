"""Reaplica, com reparo de âncora, as correções das obras que
`implanta_semantico_v2.py --aplicar` reverteu por inteiro (uma âncora
quebrou no meio do lote e derrubou tudo). Mesmo princípio de
`repara_pilha_a_revertidas.py`/`repara_convergentes_ancora.py`: aplica
UM item de cada vez, checando a âncora depois de cada um, regenerando
quando quebra em vez de reverter o lote inteiro; só pula o item
específico se nem a regeneração salvar.

    python3 scripts/repara_implanta_v2.py <checkpoint.json>            # ensaio
    python3 scripts/repara_implanta_v2.py <checkpoint.json> --aplicar
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

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402
from aplica_no_artigo import janelas  # noqa: E402
from implanta_semantico_v2 import paragrafo, PT_FONTE, PT_STAGING, SPEC_DIR  # noqa: E402

OBRAS_REVERTIDAS = [
    "19490825-自観叢書第3篇『霊界叢談』.txt", "19491130-自観叢書第8篇『明麿近詠集』.txt",
    "19491223-山と水.txt", "19510815-結核の革命的療法.txt", "19521115-御教え集15号.txt",
    "19530505-革命的増産の自然農法解説.txt", "19530615-御教え集22号.txt",
    "19530910-世界救世教奇蹟集.txt", "19531015-御教え集26号.txt", "19540825-天国の福音書.txt",
    "Eiko.txt", "19480701-御讃歌集.txt",
]


def regenera_ancora(anc_velha: str, texto_novo: str) -> str | None:
    """Acha onde a âncora velha (ou o maior prefixo dela) ficou única no
    texto novo. Livros com muito conteúdo repetitivo (depoimentos-padrão)
    às vezes precisam de MUITO mais contexto que o tamanho original da
    âncora pra virar único de novo -- achado real tentando 結核の革命的療法,
    onde o prefixo da própria âncora nunca bastava. Busca primeiro
    encolhendo (até 14 chars), depois -- se nada funcionar -- CRESCENDO
    além do tamanho original, com o mesmo teto usado nos reparos manuais
    de hoje (até 1500 chars, contra o texto inteiro do livro, não só perto
    da posição velha -- e por isso funciona mesmo sem saber onde a âncora
    foi parar)."""
    n = len(anc_velha)
    for corte in range(n, 14, -1):
        prefixo = anc_velha[:corte]
        if texto_novo.count(prefixo) == 1:
            pos = texto_novo.find(prefixo)
            # achado real (御讃歌集 art13): pegar sempre n+60 chars, sem olhar
            # a fronteira natural, engolia o poema SEGUINTE inteiro quando o
            # texto corrigido ficava mais curto que o original (poemas
            # curtos, "\n\n" logo depois) -- a âncora nova incluía o começo
            # do artigo 14 dentro do artigo 13. Nunca passar de "\n\n".
            fim_natural = texto_novo.find("\n\n", pos)
            teto = pos + n + 60
            fim = min(teto, fim_natural) if fim_natural >= 0 else teto
            fim = max(fim, pos + corte)   # nunca mais curto que o prefixo que já bateu
            return texto_novo[pos:fim]
    # não achou nem encolhendo -- tenta achar a posição aproximada (maior
    # prefixo que ainda ocorre pelo menos 1x, mesmo não-único) e crescer
    # a partir dali até virar único
    for corte in range(n, 14, -1):
        prefixo = anc_velha[:corte]
        pos = texto_novo.find(prefixo)
        if pos >= 0:
            for tamanho in range(corte, min(1500, len(texto_novo) - pos)):
                candidato = texto_novo[pos:pos + tamanho]
                if texto_novo.count(candidato) == 1:
                    return candidato
            break
    return None


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    checkpoint = Path(sys.argv[1])
    ck = json.loads(checkpoint.read_text(encoding="utf-8"))
    aceitas = [r for r in ck.values() if "novo_paragrafo" in r]
    por_obra: dict[str, list[dict]] = {}
    for r in aceitas:
        if r["obra"] in OBRAS_REVERTIDAS:
            por_obra.setdefault(r["obra"], []).append(r)

    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    total_aplicadas, total_puladas, obras_ainda_quebradas = 0, 0, []

    for obra in OBRAS_REVERTIDAS:
        itens = por_obra.get(obra, [])
        f = PT_FONTE / obra
        if not f.exists() or not itens:
            print(f"  {obra[:50]:<52} sem itens ou obra ausente")
            continue
        antes = f.read_text(encoding="utf-8")
        texto = antes
        feitas, puladas = 0, 0
        regeneradas: list[int] = []
        falhou_obra = False

        sp = SPEC_DIR / f"{obra}.json"
        spec_original_texto = sp.read_text(encoding="utf-8") if sp.exists() else None
        spec = json.loads(spec_original_texto) if spec_original_texto else None
        arts = spec["articles"] if spec else None

        for it in sorted(itens, key=lambda x: x["artigo"], reverse=True):
            jan = janelas(obra, texto)
            if jan is None:
                # uma âncora quebrou por causa de uma correção anterior nesta
                # mesma obra -- regenera na hora, não espera o final do laço.
                # janelas() lê o spec DO DISCO a cada chamada -- tem de gravar
                # a âncora regenerada agora, senão a próxima chamada falha de
                # novo com a mesma âncora velha (achado real, testado: sem
                # isto o ensaio inteiro reporta 0 aplicadas). Revertido do
                # disco no final se a obra afinal não se resolver.
                if not arts:
                    puladas += 1
                    continue
                limpo = clean_body(texto)
                consertou_alguma = False
                for i, a in enumerate(arts):
                    velha = a.get("pt_anchor", "")
                    if not velha or velha in limpo:
                        continue
                    # PRIMEIRO tenta a via segura: se alguma correção JÁ
                    # aplicada a este mesmo artigo tinha "de" batendo com a
                    # âncora antiga, a âncora nova é literalmente de->para
                    # dessa correção -- não precisa procurar no livro
                    # inteiro, e por isso nunca confunde com outro
                    # testemunho parecido (achado real: 世界救世教奇蹟集 art140,
                    # a busca cega trocou "Tuberculose" por "Varíola" de um
                    # depoimento diferente porque os dois começam com "A
                    # Alegria de Curar..." -- essa é a classe de erro que
                    # este caminho evita).
                    # achado real (世界救世教奇蹟集 art134, título "O Grande
                    # Poder da Cura Divina: Tifo Exantemático com 100%" ->
                    # "A Grande Terapia Divina: ...100% de Taxa de Cura"):
                    # `de` cobre só PARTE da linha do título, e o texto real
                    # foi trocado pelo parágrafo INTEIRO (`novo_paragrafo`),
                    # não por um replace pontual de "de" por "para" -- usar
                    # velha.replace(de, para) duplicava o resto da linha
                    # ("...de Taxa de Cura de Taxa de Cura"). Reproduz o
                    # mesmo corte de parágrafo usado na aplicação real
                    # (paragrafo(), por "\n\n") sobre a PRÓPRIA âncora, e
                    # substitui esse span por `novo_paragrafo` -- não por
                    # `para` -- pra bater exatamente com o que foi escrito
                    # no corpo.
                    nova = None
                    for outro in itens:
                        if outro["artigo"] != i:
                            continue
                        if outro["de"] and outro["de"] in velha:
                            lim = paragrafo(velha, 0, len(velha), outro["de"])
                            if lim is None:
                                continue
                            np = outro.get("novo_paragrafo", outro["para"])
                            candidata = velha[:lim[0]] + np + velha[lim[1]:]
                            if limpo.count(candidata) == 1:
                                nova = candidata
                                break
                    # SEGUNDO: se a via segura não resolveu, usa title_pt como
                    # âncora de verdade -- achado real (世界救世教奇蹟集 art134/
                    # art140, 明麿近詠集 art29): em vários livros a corrupção é
                    # ANTERIOR a esta sessão, e o pt_anchor está simplesmente
                    # errado (aponta para posição de outro trecho), enquanto
                    # title_pt continua correto (é o campo que
                    # find_best_article usa de verdade em produção). Só aceita
                    # se title_pt for único no texto -- nunca substring solta.
                    if nova is None:
                        tp = a.get("title_pt", "")
                        if tp and limpo.count(tp) == 1:
                            pos = limpo.find(tp)
                            candidata = limpo[pos:pos + len(velha)]
                            if limpo.count(candidata) == 1:
                                nova = candidata
                    # a busca cega (regenera_ancora) só entra como ÚLTIMO
                    # recurso, e só quando não há title_pt pra conferir --
                    # achado real (世界救世教奇蹟集 art134): um item tinha "de"
                    # de um artigo diferente (índice provavelmente errado na
                    # origem), a busca cega sozinha "achou" algo que passava
                    # no teste de unicidade mas ainda quebrava janelas() depois
                    # -- e antes disso, no art140, ela já tinha trocado
                    # "Tuberculose" por "Varíola" de outro depoimento. Com
                    # title_pt ausente, a busca cega é a única opção que
                    # sobra -- mas fica marcada como candidata frágil, revista
                    # à mão antes de aceitar em definitivo.
                    if nova is None and not a.get("title_pt", ""):
                        candidata = regenera_ancora(velha, limpo)
                        if candidata is not None:
                            nova = candidata
                    if nova is not None:
                        a["pt_anchor"] = nova
                        if i not in regeneradas:
                            regeneradas.append(i)
                        consertou_alguma = True
                if not consertou_alguma:
                    falhou_obra = True
                    break
                sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
                jan = janelas(obra, texto)
                if jan is None:
                    falhou_obra = True
                    break
            if it["artigo"] >= len(jan):
                puladas += 1
                continue
            ini, fim = jan[it["artigo"]]
            lim = paragrafo(texto, ini, fim, it["de"])
            if lim is None or texto[lim[0]:lim[1]].count(it["de"]) != 1:
                puladas += 1
                continue
            texto = texto[:lim[0]] + it["novo_paragrafo"] + texto[lim[1]:]
            feitas += 1

        anc_ok = not falhou_obra
        if anc_ok and arts:
            anc = [a.get("pt_anchor", "") for a in arts]
            if len(anc) > 1 and all(anc):
                try:
                    anc_ok = len(split_by_anchors(clean_body(texto), anc, label=obra)) == len(anc)
                except ValueError:
                    anc_ok = False

        if not anc_ok:
            print(f"  *** {obra[:50]:<52} ÂNCORA NÃO REGENERÁVEL — mantendo revertida "
                  f"({feitas} correções perdidas)")
            obras_ainda_quebradas.append(obra)
            if spec_original_texto is not None:
                sp.write_text(spec_original_texto, encoding="utf-8")  # desfaz regeneração parcial
            continue

        msg = f"  {obra[:50]:<52} {feitas:>3} aplicadas, {puladas} puladas"
        if regeneradas:
            msg += f"  (âncoras regeneradas: {regeneradas})"
        print(msg)
        total_aplicadas += feitas
        total_puladas += puladas

        if not aplicar:
            # ensaio: já sabemos que resolveria -- desfaz a escrita de teste
            # do spec (feita só pra janelas() poder validar) antes de sair
            if spec_original_texto is not None:
                sp.write_text(spec_original_texto, encoding="utf-8")
            continue
        shutil.copy(f, f.with_suffix(f".txt.bak_reparaimplantav2_{carimbo}"))
        f.write_text(texto, encoding="utf-8")
        (PT_STAGING / obra).write_text(texto, encoding="utf-8")
        if regeneradas and spec_original_texto is not None:
            shutil.copy(sp, sp.with_suffix(f".json.bak_reparaimplantav2_{carimbo}"))
            sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{total_aplicadas} aplicadas no total, {total_puladas} puladas, "
          f"{len(obras_ainda_quebradas)} obras ainda sem solução automática:")
    for o in obras_ainda_quebradas:
        print(f"  {o}")
    if not aplicar:
        print("\n(ensaio — nada gravado; rode com --aplicar)")


if __name__ == "__main__":
    main()
