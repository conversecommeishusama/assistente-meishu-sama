"""Correção semântica linha a linha dos 213 problemas encontrados pela
verificação da pilha A/C (2026-08-12).

Para cada caso: localiza o trecho no artigo real (por palavras-chave da
razão), extrai o parágrafo, o modelo reescreve o parágrafo lendo o JP +
contexto + razão, verifica que só a região da correção mudou, e aplica com
backup e validação de âncora por obra.

Uso:
    python3 scripts/corrigir_213_semantico.py            # cálculo (ensaio)
    python3 scripts/corrigir_213_semantico.py --aplicar  # aplica no corpus
    python3 scripts/corrigir_213_semantico.py --resumo   # estado
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402
from aplica_no_artigo import janelas  # noqa: E402
from implanta_semantico_v2 import PT_FONTE, PT_STAGING, SPEC_DIR, carrega_jp_por_obra  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

ENTRADA = RAIZ / "reports/varredura_padronizacao/CORRECOES_213_PROPOSTAS.json"
SAIDA = RAIZ / "reports/varredura_padronizacao/CORRECOES_213_FINAIS.json"
MODELO = "deepseek-v4-flash"

SYSTEM = """Você aplica uma correção a um parágrafo de tradução japonês-português
do acervo de Meishu-Sama. O japonês é a fonte de verdade.

Recebe o JAPONÊS do artigo, o PARÁGRAFO atual, e a RAZAO do erro (com o
japonês).

Reescreva o parágrafo aplicando a correção, ajustando concordância de gênero/
número, artigo, preposição e ordem se a troca exigir. NÃO toque em nada fora da
região da correção — o resto tem de sair EXATAMENTE como entrou. Não use kanji
nem kana no português. Preserve citações entre colchetes, marcação de turno e
numeração de item.

Devolva SÓ o parágrafo corrigido, sem comentário.
"""


def extrai_kw_razao(razao: str) -> list[str]:
    """Palavras-chave da razão para localizar o trecho no artigo.

    Inclui tanto palavras portuguesas quanto trechos em japonês citados na
    razão (ex.: 氷枕, 左進右退) -- o trecho JP pode aparecer no texto ou ter
    equivalente em PT. Achado 2026-08-12: buscar só em português deixava 44
    casos não localizados cuja razão citava o trecho em kanji."""
    stop = {
        'final', 'japonês', 'japones', 'correto', 'correção', 'correcao',
        'original', 'significa', 'deveria', 'trecho', 'este', 'esta', 'não',
        'nao', 'mas', 'porque', 'isso', 'para', 'seria', 'está', 'esta', 'que',
        'com', 'dos', 'das', 'uma', 'vai', 'foi', 'são', 'sao', 'omite',
        'inverte', 'traduz', 'acerta', 'troca', 'escreve', 'corresponde',
        'presente', 'diz', 'dizem', 'indica', 'sentido', 'fiel', 'ausente',
        'título', 'titulo', 'trecho', 'frase', 'expressão', 'expressao',
        'palavra', 'original', 'correspondente', 'conteúdo', 'conteudo',
        'sentido', 'afirma', 'afirmação', 'afirmacao', 'quando', 'somente',
        'apenas', 'como', 'também', 'tambem', 'ainda', 'mesmo', 'muito',
        'correta', 'corretamente', 'sobre', 'entre', 'através', 'atraves',
        'devem', 'deve', 'pode', 'podem', 'ser', 'estão', 'estao', 'foram',
        'eram', 'sendo', 'seria', 'serão', 'serao',
    }
    # trechos em japonês (kanji/kana) citados na razão
    japones = re.findall(r'[\u3000-\u9fff]{2,8}', razao)
    kws = []
    for j in japones:
        jl = re.sub(r'[\s\u3000]', '', j)
        if len(jl) >= 2 and jl not in kws:
            kws.append(jl)
    # palavras portuguesas significativas
    palavras = re.findall(r'[A-Za-zÀ-ú]{5,}', razao)
    for w in palavras:
        wl = w.lower()
        if wl not in stop and wl not in kws:
            kws.append(wl)
    return kws[:8]


def localiza(obra: str, artigo: int, razao: str) -> tuple[str | None, str | None]:
    """Retorna (trecho_localizado, escopo_do_artigo) ou (None, None)."""
    fname = obra if obra.endswith('.txt') else obra + '.txt'
    f = PT_FONTE / fname
    if not f.exists():
        return None, None
    texto = f.read_text(encoding="utf-8")
    limpo = clean_body(texto)
    jan = janelas(fname, limpo)
    if not jan or not isinstance(artigo, int) or artigo >= len(jan):
        return None, None
    escopo = limpo[jan[artigo][0]:jan[artigo][1]]
    kws = extrai_kw_razao(razao)
    # procurar a sequência mais longa de palavras-chave juntas (melhor âncora)
    for tamanho in range(len(kws), 1, -1):
        for i in range(0, len(kws) - tamanho + 1):
            seq = ' '.join(kws[i:i + tamanho])
            if seq in escopo:
                p = escopo.find(seq)
                return escopo[max(0, p - 40):p + len(seq) + 40], escopo
    # fallback: primeira palavra-chave
    for kw in kws:
        if kw in escopo:
            p = escopo.find(kw)
            return escopo[max(0, p - 40):p + len(kw) + 40], escopo
    return None, escopo


def extrai_paragrafo(escopo: str, artigo_ini: int, trecho_local: str) -> tuple[str, int, int] | None:
    """Extrai o parágrafo que contém o trecho localizado. Retorna (par, ini, fim)."""
    p = escopo.find(trecho_local[:30] if len(trecho_local) > 30 else trecho_local)
    if p < 0:
        # tentar com um fragmento menor
        frag = re.sub(r'\s+', ' ', trecho_local)[:25]
        p = escopo.find(frag)
        if p < 0:
            return None
    ini_par = escopo.rfind('\n\n', 0, p)
    ini = artigo_ini if ini_par < 0 else artigo_ini + ini_par + 2
    fim_par = escopo.find('\n\n', p)
    fim = artigo_ini + len(escopo) if fim_par < 0 else artigo_ini + fim_par
    return escopo[ini - artigo_ini:fim - artigo_ini], ini, fim


def emenda(obra: str, artigo: int, razao: str) -> dict:
    """Processa um caso: localiza, corrige, devolve resultado."""
    fname = obra if obra.endswith('.txt') else obra + '.txt'
    trecho_local, escopo = localiza(obra, artigo, razao)
    if trecho_local is None or escopo is None:
        return {"status": "nao_localizado", "obra": obra, "artigo": artigo, "razao": razao[:150]}
    jan = janelas(fname, clean_body((PT_FONTE / fname).read_text(encoding="utf-8")))
    artigo_ini = jan[artigo][0]
    par_info = extrai_paragrafo(escopo, artigo_ini, trecho_local)
    if par_info is None:
        return {"status": "paragrafo_nao_extraido", "obra": obra, "artigo": artigo, "razao": razao[:150]}
    par, ini, fim = par_info
    jp = carrega_jp_por_obra(fname)
    jp_art = jp[artigo] if jp and artigo < len(jp) else ""
    pedido = (f"=== JAPONÊS DO ARTIGO ===\n{(jp_art or '(não localizado)')[:8000]}\n\n"
              f"=== PARÁGRAFO ATUAL ===\n{par}\n\n"
              f"=== RAZAO ===\n{razao}\n\n"
              f"Parágrafo corrigido:")
    try:
        resp = ag._client().chat.completions.create(
            model=MODELO, max_tokens=4000,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": pedido}])
        novo_par = (resp.choices[0].message.content or "").strip()
        # retentativa para resposta vazia (achado 2026-08-12: 84 vazios com
        # max_tokens=2500 -- parágrafos longos + JP grande esgotavam o teto)
        if not novo_par:
            resp = ag._client().chat.completions.create(
                model=MODELO, max_tokens=8000,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": pedido}])
            novo_par = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        return {"status": "erro_api", "obra": obra, "artigo": artigo, "razao": razao[:150], "erro": repr(exc)[:100]}
    if not novo_par:
        return {"status": "vazio", "obra": obra, "artigo": artigo, "razao": razao[:150], "par": par}
    if novo_par == par:
        return {"status": "sem_mudanca", "obra": obra, "artigo": artigo, "razao": razao[:150], "par": par}
    # verificação: a mudança deve ser pequena (parágrafo não pode inchar/encolher demais)
    if len(novo_par) > len(par) * 1.6:
        return {"status": "cresceu_demais", "obra": obra, "artigo": artigo, "par": par, "novo_par": novo_par}
    return {"status": "ok", "obra": obra, "artigo": artigo, "par": par, "novo_par": novo_par,
            "ini": ini, "fim": fim, "razao": razao[:150]}


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    if "--resumo" in sys.argv:
        if SAIDA.exists():
            d = json.loads(SAIDA.read_text(encoding="utf-8"))
            from collections import Counter
            print(Counter(x.get("status") for x in d))
        return
    casos = json.loads(ENTRADA.read_text(encoding="utf-8"))
    # só os que têm correção não-vazia e diferente do original
    casos = [c for c in casos
             if c.get("corrigido", "").strip() and c["corrigido"].strip() != c.get("final", "").strip()]
    # já processados?
    feitos: dict = {}
    if SAIDA.exists():
        feitos = {(x["obra"], x["artigo"]) for x in json.loads(SAIDA.read_text(encoding="utf-8"))}
    pendentes = [c for c in casos if (c["obra"], c["artigo"]) not in feitos]
    print(f"{len(casos)} casos no total, {len(pendentes)} a processar", flush=True)

    resultados = []
    if SAIDA.exists():
        resultados = json.loads(SAIDA.read_text(encoding="utf-8"))
    trava, n = threading.Lock(), [0]

    def trabalho(c):
        r = emenda(c["obra"], c["artigo"], c.get("razao", ""))
        r["final"] = c.get("final", "")
        with trava:
            resultados.append(r)
            n[0] += 1
            if n[0] % 20 == 0:
                ok = sum(1 for x in resultados if x["status"] == "ok")
                print(f"  [{n[0]}/{len(pendentes)}] {ok} ok", flush=True)
            SAIDA.write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")

    if pendentes:
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(trabalho, pendentes))

    from collections import Counter
    print(f"\ncálculo: {Counter(x['status'] for x in resultados)}", flush=True)

    if not aplicar:
        print("(ensaio -- nada gravado; rode com --aplicar)")
        return

    # APLICAÇÃO por obra (em série, pois cada emenda desloca posições)
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    por_obra: dict[str, list[dict]] = {}
    for r in resultados:
        if r["status"] == "ok":
            por_obra.setdefault(r["obra"], []).append(r)
    for obra, itens in sorted(por_obra.items()):
        fname = obra if obra.endswith('.txt') else obra + '.txt'
        f = PT_FONTE / fname
        if not f.exists():
            continue
        texto = f.read_text(encoding="utf-8")
        aplicou = 0
        # aplicar de trás pra frente (posição descendente)
        for it in sorted(itens, key=lambda x: -x["ini"]):
            par_atual = texto[it["ini"]:it["fim"]]
            if par_atual != it["par"]:
                # posição deslocada por emendas anteriores — tentar localizar de novo
                p = texto.find(it["par"])
                if p < 0:
                    print(f"  PULADO {obra} art{it['artigo']} (parágrafo não encontrado)")
                    continue
                it["ini"], it["fim"] = p, p + len(it["par"])
            texto = texto[:it["ini"]] + it["novo_par"] + texto[it["fim"]:]
            aplicou += 1
        # validar âncora antes de gravar
        from mescla_e_aplica import valida_ancoras
        ok, motivo = valida_ancoras(fname, texto)
        if not ok:
            print(f"  *** NÃO GRAVADO {obra}: âncora quebrada ({motivo})")
            continue
        shutil.copy(f, f.with_suffix(f".txt.bak_corrigir213_{carimbo}"))
        f.write_text(texto, encoding="utf-8")
        (PT_STAGING / fname).write_text(texto, encoding="utf-8")
        print(f"  {obra[:40]:<42} {aplicou} emendas aplicadas, âncora OK")
    print("\naplicação concluída")


if __name__ == "__main__":
    main()
