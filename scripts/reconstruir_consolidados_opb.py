#!/usr/bin/env python3
"""Opção B — reconstrói os consolidados dos Mioshie-shū (1-8) com a estrutura
de sessão CORRETA, sem modificar os checkpoints.

Estratégia:
1. Para cada arquivo, usa a spec (que define as sessões via jp_anchor) para
   criar FAIXAS de posição no JP original (de uma âncora até a próxima).
2. Mapeia cada fala do checkpoint para a sessão, achando a posição do seu JP
   no JP original (com fallback de tamanhos e herança da sessão anterior).
3. Agrupa as falas por sessão, no formato canônico:
     [data_pt]        (marcador = title_pt da sessão)
     Interlocutor: ...
     Meishu-Sama: ...
   com blocos do mesmo falante fundidos (como no consolidador).
4. Escreve em revisao_literaria/orais/ e reports/livros_trabalho/pt/.

O checkpoint NÃO é alterado (é a fonte da verdade para o texto; a estrutura
de sessão vem da spec + mapeamento por posição JP).

Uso:
  .venv/bin/python scripts/reconstruir_consolidados_opb.py [--dry-run] [--arquivo N]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CKPT_DIR = ROOT / "reports/retraducao_colecoes"
JP_DIR = ROOT / "textos_japones"
SPEC_DIR = ROOT / "reports/livros_trabalho/segmentacao_manual"
ORAL_DIR = ROOT / "revisao_literaria/orais"
PT_DIR = ROOT / "reports/livros_trabalho/pt"

# nº -> (stem JP, nome PT, nome arquivo JP original)
MAPA = {
    1: ("19510920-御教え集1号", "19510920 - Mioshie-shū nº 1", "19510920-御教え集1号.txt"),
    2: ("19511025-御教え集2号", "19511025 - Mioshie-shū nº 2", "19511025-御教え集2号.txt"),
    3: ("19511125-御教え集3号", "19511125 - Mioshie-shū nº 3", "19511125-御教え集3号.txt"),
    4: ("19511215-御教え集4号", "19511215 - Mioshie-shū nº 4", "19511215-御教え集4号.txt"),
    5: ("19520115-御教え集5号", "19520115 - Mioshie-shū nº 5", "19520115-御教え集5号.txt"),
    6: ("19510225-御教え集6号", "19510225 - Mioshie-shū nº 6", "19510225-御教え集6号.txt"),
    7: ("19520320-御教え集7号", "19520320 - Mioshie-shū nº 7", "19520320-御教え集7号.txt"),
    8: ("19520420-御教え集8号", "19520420 - Mioshie-shū nº 8", "19520420-御教え集8号.txt"),
}

# Título PT do livro por nº (para a ficha)
OBRA_PT = "Mioshie-shū"


def norm_jp(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def data_pt_de_title(title_pt: str) -> str:
    """Normaliza o title_pt da sessão para o marcador canônico.
    Ex: '1 de agosto' -> '1 de agosto'; mantém como está."""
    return title_pt.strip()


def gerar_ficha(spec: dict, obra_pt: str, n_ed: str) -> str:
    """Gera a ficha canônica a partir da jp_anchor do prefácio.
    Ex: 'Mioshie-shū nº 1, publicado em 20 de setembro do ano 26 da Era Showa (1951)'"""
    # importa a lógica do consolidador (ficha_jp_para_pt)
    import importlib.util as _ilu
    import sys as _sys
    _spec = _ilu.spec_from_file_location("consolidar_colecoes_orais", str(ROOT / "scripts" / "consolidar_colecoes_orais.py"))
    cons = _ilu.module_from_spec(_spec)
    _sys.modules["consolidar_colecoes_orais"] = cons
    _spec.loader.exec_module(cons)

    pref = next((a for a in spec.get("articles", []) if a.get("kind") == "preface"), None)
    if pref:
        jp_anchor = pref.get("jp_anchor", "")
        ficha = cons.ficha_jp_para_pt(jp_anchor, obra_pt, n_ed)
        return ficha
    return f"{obra_pt} nº {n_ed}"


def mapear_falas_para_sessoes(ckpt_path: Path, spec: dict, jp_orig_path: Path):
    """Mapeia cada fala do checkpoint para o índice da sessão da spec.

    Retorna lista de (indice_fala, indice_sessao, fala) em ordem.
    """
    falas = json.loads(ckpt_path.read_text(encoding="utf-8"))["falas"]
    ks = sorted(falas.keys(), key=lambda x: int(x))

    jp_norm = norm_jp(jp_orig_path.read_text(encoding="utf-8"))

    # Faixas de sessão por posição JP, processadas EM ORDEM com cursor
    # (como o split_by_anchors faz: cada âncora é buscada a partir do fim
    # da anterior, evitando menções anteriores no texto).
    arts = spec.get("articles", [])
    cursor = 0
    faixas = []
    for i, a in enumerate(arts):
        anc = norm_jp(a.get("jp_anchor", ""))
        pos = jp_norm.find(anc, cursor)
        if pos < 0:
            # fallback: procura no texto inteiro
            pos = jp_norm.find(anc)
        faixas.append((pos, i, a.get("title_jp", "")))
        if pos >= 0:
            cursor = pos + max(1, len(anc))
    faixas.sort(key=lambda x: x[0])
    # converte em faixas [início, fim)
    faixas_intervalo = []
    for j, (pos, i, t) in enumerate(faixas):
        fim = faixas[j + 1][0] if j + 1 < len(faixas) and faixas[j + 1][0] >= 0 else len(jp_norm)
        faixas_intervalo.append((pos, fim, i, t))

    def sessao_de(pos: int):
        for (ps, pf, i, _t) in faixas_intervalo:
            if ps <= pos < pf:
                return i
        return None

    # Mapear cada fala
    resultado = []
    sessao_atual = None
    ultima_pos = -1
    for k in ks:
        f = falas[k]
        jpf = f.get("jp", "")
        pos = -1
        if jpf.strip():
            for tam in (60, 40, 25, 15, 10):
                pos = jp_norm.find(norm_jp(jpf[:tam]))
                if pos >= 0:
                    break
        # Rejeita posições não-monotônicas (regressão) — o JP da fala está
        # deslocado/corrompido (ex: fala 61 do nº 3 pula de ~14k para 48k e
        # depois regride para 15k). Herda a sessão da fala anterior.
        if pos >= 0:
            if ultima_pos >= 0 and pos < ultima_pos:
                pos = -1  # regressão: JP corrompido, herda sessão anterior
            elif ultima_pos >= 0 and pos > ultima_pos * 2 + 5000:
                # salto anômalo muito grande: provável JP corrompido
                # (verifica se a posição "esperada" (última + pequeno) está
                # livre — se sim, trata como herança)
                pos = -1
        if pos >= 0:
            s = sessao_de(pos)
            if s is not None:
                sessao_atual = s
                ultima_pos = pos
        if sessao_atual is None:
            sessao_atual = 0  # fallback: prefácio
        resultado.append((k, sessao_atual, f))
    return resultado


def montar_consolidado(spec: dict, mapeamento, obra_pt: str, n_ed: str, ficha: str) -> str:
    """Monta o consolidado no formato canônico."""
    arts = spec.get("articles", [])
    linhas = [ficha, ""]

    # Agrupar falas por sessão
    sessoes: dict[int, list] = {}
    for k, s_idx, f in mapeamento:
        sessoes.setdefault(s_idx, []).append(f)

    # Conteúdo que caiu no prefácio (sessão 0) mas não é a ficha → pertence à
    # primeira sessão (ex: nº 4, a fala de Motoyama antes de [1º de novembro]).
    # O prefácio em si não tem conteúdo (só a ficha).
    if 0 in sessoes and len(sessoes) > 1:
        # acha a primeira sessão real (a de menor índice > 0 que tem conteúdo
        # na ordem do texto)
        primeira_sessao = None
        for _k, s_idx, _f in mapeamento:
            if s_idx > 0:
                primeira_sessao = s_idx
                break
        if primeira_sessao is not None:
            # move todo o conteúdo do prefácio para a primeira sessão
            sessoes[primeira_sessao] = sessoes.get(0, []) + sessoes.get(primeira_sessao, [])
            sessoes[0] = []

    # Ordem das sessões = ordem de primeira ocorrência no mapeamento
    # (que segue a ordem das posições JP — a ordem real do texto)
    ordem = []
    vistos = set()
    for _k, s_idx, _f in mapeamento:
        if s_idx not in vistos:
            vistos.add(s_idx)
            ordem.append(s_idx)

    def limpar_rotulo_duplicado(pt: str, quem: str) -> str:
        """Remove rótulo 'Interlocutor:'/'Meishu-Sama:' já presente no início
        do texto (a retradução às vezes inclui o rótulo no próprio texto)."""
        pt = pt.strip()
        rotulo = "Interlocutor" if quem == "Interlocutor" else "Meishu-Sama"
        # padrões: "Interlocutor:", "Interlocutor: ", "Interlocutor：", etc.
        for padrao in [f"{rotulo}:", f"{rotulo}：", f"{rotulo}: ", f"{rotulo}： "]:
            if pt.startswith(padrao):
                pt = pt[len(padrao):].strip()
                break
        return pt

    def emitir_blocos(falas_sessao: list) -> None:
        """Funde blocos do mesmo falante e escreve com rótulos."""
        agrupados = []
        for f in falas_sessao:
            quem = f.get("quem")
            pt = f.get("pt_contextual", "").strip()
            # remove rótulo duplicado da PRIMEIRA fala do grupo
            if not agrupados or agrupados[-1]["quem"] != quem:
                pt = limpar_rotulo_duplicado(pt, quem)
            if agrupados and agrupados[-1]["quem"] == quem:
                agrupados[-1]["pt"] += " " + pt
            else:
                agrupados.append({"quem": quem, "pt": pt})
        for g in agrupados:
            rotulo = "Interlocutor" if g["quem"] == "Interlocutor" else "Meishu-Sama"
            linhas.append(f"{rotulo}: {g['pt']}")
            linhas.append("")

    for s_idx in ordem:
        art = arts[s_idx] if s_idx < len(arts) else None
        if art is None:
            continue
        if art.get("kind") == "preface":
            # Prefácio: conteúdo direto, sem marcador de sessão
            emitir_blocos(sessoes[s_idx])
            continue
        # Sessão: marcador = pt_anchor (que é o que split_by_anchors usa),
        # com fallback para title_pt
        marcador = art.get("pt_anchor", "").strip() or data_pt_de_title(art.get("title_pt", ""))
        if not marcador:
            continue
        linhas.append(f"[{marcador}]")
        linhas.append("")
        emitir_blocos(sessoes[s_idx])

    return "\n".join(linhas).strip() + "\n"


def main() -> int:
    dry = "--dry-run" in sys.argv
    apenas = None
    for a in sys.argv:
        if a.startswith("--arquivo"):
            apenas = int(a.split("=")[1])

    for n in range(1, 9):
        if apenas and n != apenas:
            continue
        stem_jp, nome_pt, jp_orig_name = MAPA[n]
        ckpt = CKPT_DIR / f"{stem_jp}.json"
        spec_path = SPEC_DIR / f"{nome_pt}.txt.json"
        jp_orig = JP_DIR / jp_orig_name
        if not ckpt.exists() or not spec_path.exists() or not jp_orig.exists():
            print(f"[nº {n}] arquivos ausentes")
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        n_ed = str(n)
        mapeamento = mapear_falas_para_sessoes(ckpt, spec, jp_orig)
        ficha = gerar_ficha(spec, OBRA_PT, n_ed)
        texto = montar_consolidado(spec, mapeamento, OBRA_PT, n_ed, ficha)

        # estatísticas
        n_sessoes = len(set(s for _k, s, _f in mapeamento if s > 0))
        n_falas = len(mapeamento)

        if dry:
            print(f"[dry-run] nº {n}: {n_falas} falas, {n_sessoes} sessões, {len(texto)} chars")
        else:
            oral_out = ORAL_DIR / f"{nome_pt}.txt"
            pt_out = PT_DIR / f"{nome_pt}.txt"
            oral_out.write_text(texto, encoding="utf-8")
            pt_out.write_text(texto, encoding="utf-8")
            print(f"✓ nº {n}: {n_falas} falas, {n_sessoes} sessões, {len(texto)} chars")

    return 0


if __name__ == "__main__":
    sys.exit(main())
