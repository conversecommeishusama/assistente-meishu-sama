#!/usr/bin/env python3
"""Integra a retradução das COLEÇÕES de orais (御光話録/御垂示録/御教え集) no
texto publicado em `textos_portugues/`, com VALIDAÇÃO DE PAREAMENTO.

ESTRATÉGIA — substituição turno-a-turno preservando a estrutura de produção:
  O texto publicado de produção tem estrutura HETEROGÊNEA (cabeçalho, poemas,
  narração, datas em formatos variados). Não se faz rebuild do corpo — faz-se
  substituição por TURNO de diálogo:
    - Separa a produção em blocos rotulados (linhas que começam com
      "Interlocutor:" ou "Meishu-Sama:", incluindo as linhas seguintes até o
      próximo rótulo/limite).
    - Para cada índice de turno i (0..n-1), o rótulo e o texto de fala da
      produção são substituídos por `falas[i].quem` + `falas[i].pt_contextual`
      do checkpoint da retradução.
    - Tudo que NÃO é bloco rotulado (cabeçalho, datas, poemas, narração) fica
      intocado — inclusive as datas/âncoras de segmentação.

VALIDAÇÕES (antes de gravar):
  1. PARIDADE: nº de blocos rotulados da produção == nº de turnos JP == nº de
     falas do checkpoint. Se não bater, NÃO grava (deixa para revisão).
  2. ORDEM: para cada turno, `falas[i].quem` deve bater com o rótulo JP.
  3. ÂNCORAS: roda `split_by_anchors` (função real de produção) sobre o texto
     novo; se a contagem de artigos não fechar, NÃO grava.

Uso:
  .venv/bin/python scripts/integrar_colecoes_retraduzidas.py --colecao gokowa [--dry-run]
  .venv/bin/python scripts/integrar_colecoes_retraduzidas.py --arquivo 19481208-御光話録1号 [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraduzir_colecao import EXTRATORES  # noqa: E402
from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

JP_DIR = RAIZ / "textos_japones"
PT_DIR = RAIZ / "textos_portugues"
CKPT_DIR = RAIZ / "reports" / "retraducao_colecoes"
SPEC_DIR = RAIZ / "reports" / "livros_trabalho" / "segmentacao_manual"
BACKUP_DIR = RAIZ / "reports" / "retraducao_colecoes" / "backup_integracao_prod"

# Padrões de arquivo por coleção (mesmos do retraduzir_colecao_massa.py)
PADROES = {
    "gokowa": "*御光話録*号*.txt",
    "gosuiji": "*御垂示録*.txt",
    "mioshie": "*御教え集*.txt",
}

ROTULO_RE = re.compile(r"^(Interlocutor|Meishu-Sama):\s*(.*)", re.S)

DATE_PT_RE = re.compile(
    r"^\d{1,2} de (?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|"
    r"setembro|outubro|novembro|dezembro)(?: \([^)]+\))?$"
)


def extrair_turnos_jp(stem_jp: str, colecao: str) -> list[tuple[str, str]]:
    """Extrai os turnos do JP na ORDEM (mesmo extrator da retradução)."""
    texto = (JP_DIR / f"{stem_jp}.txt").read_text(encoding="utf-8")
    return EXTRATORES[colecao](texto)


def separar_blocos(prod_text: str) -> tuple[list[str], list[int]]:
    """Separa a produção em pedaços atômicos.

    Retorna (pedacos, indices_blocos):
      - `pedacos`: lista de strings (linhas, mantendo quebras) — cada pedaço
        é uma linha OU um bloco rotulado (rótulo + linhas seguintes).
      - `indices_blocos`: índices em `pedacos` que são blocos rotulados de
        diálogo (na ordem do diálogo).
    """
    linhas = prod_text.splitlines(keepends=True)
    pedacos: list[str] = []
    indices_blocos: list[int] = []
    i = 0
    while i < len(linhas):
        m = ROTULO_RE.match(linhas[i].strip())
        if m:
            bloco = [linhas[i]]
            j = i + 1
            while j < len(linhas):
                linha_j = linhas[j].strip()
                if ROTULO_RE.match(linha_j):
                    break
                # interrompe em marcador de data de produção (sem rótulo),
                # para não engolir o cabeçalho de sessão seguinte
                if linha_j and DATE_PT_RE.match(linha_j.strip("[]")):
                    break
                bloco.append(linhas[j])
                j += 1
            indices_blocos.append(len(pedacos))
            pedacos.append("".join(bloco))
            i = j
        else:
            pedacos.append(linhas[i])
            i += 1
    return pedacos, indices_blocos


def montar_substituicoes(
    ckpt: dict,
    n_turnos: int,
) -> tuple[list[tuple[int, str, str]], list[dict]]:
    """Prepara (indice, quem, pt_novo) para cada turno, validando completude."""
    falas = ckpt.get("falas", {})
    subs: list[tuple[int, str, str]] = []
    problemas: list[dict] = []
    for i in range(n_turnos):
        f = falas.get(str(i))
        if not f or not f.get("pt_contextual"):
            problemas.append({"indice": i, "motivo": "fala ausente ou vazia no checkpoint"})
            continue
        quem = f.get("quem", "")
        if quem not in ("Interlocutor", "Meishu-Sama"):
            problemas.append({"indice": i, "motivo": f"quem inesperado: {quem!r}"})
            continue
        subs.append((i, quem, f["pt_contextual"].strip()))
    return subs, problemas


def checar_paridade(
    turnos_jp: list[tuple[str, str]],
    n_blocos_prod: int,
    subs: list[tuple[int, str, str]],
    stem_jp: str,
) -> tuple[bool, list[str]]:
    """Paridade: nº de blocos produção == nº turnos JP == nº falas checkpoint."""
    erros: list[str] = []
    n_jp = len(turnos_jp)
    if n_blocos_prod != n_jp:
        erros.append(f"{stem_jp}: produção tem {n_blocos_prod} blocos de diálogo, JP tem {n_jp}")
    if len(subs) != n_jp:
        erros.append(f"{stem_jp}: checkpoint tem {len(subs)} falas preenchidas, JP tem {n_jp}")
    if not erros:
        for i, (quem_jp, _) in enumerate(turnos_jp):
            esperado = "Interlocutor" if quem_jp == "Interlocutor" else "Meishu-Sama"
            if subs[i][1] != esperado:
                erros.append(f"{stem_jp}: turno {i} checkpoint={subs[i][1]} != JP={esperado}")
    return not erros, erros


def validar_ancoras(obra_prod: str, texto: str) -> tuple[bool, str]:
    """Valida âncoras PT do spec com split_by_anchors (função de produção).

    Retorna (ok, motivo). Quando ok=False e o motivo indica que uma âncora
    embutia texto de turno (que a retradução reescreveu), quem chama deve
    usar regenera_ancora para reparar a(s) âncora(s) antes de gravar.
    """
    sp = SPEC_DIR / f"{obra_prod}.json"
    if not sp.exists():
        return True, "sem spec (não valida)"
    try:
        spec = json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        return True, "spec ilegível (não valida)"
    arts = spec.get("articles", [])
    anc = [a.get("pt_anchor", "") for a in arts]
    if len(anc) <= 1:
        return True, "artigo único/sem âncoras"
    try:
        ok = len(split_by_anchors(clean_body(texto), anc, label=obra_prod)) == len(anc)
    except ValueError as exc:
        return False, f"split_by_anchors falhou: {exc}"
    if not ok:
        return False, "contagem de artigos não fecha com as âncoras"
    return True, "ok"


def achar_prod(stem_jp: str) -> Path | None:
    """Acha o arquivo de produção PT correspondente ao stem JP.

    O stem JP tem a forma '<data>-御光話録N号' / '御垂示録N号' / '御教え集N号';
    a produção usa '<data> - Gokōwa-roku nº N.txt' etc. Não basta casar por
    data (várias obras compartilham a data, ex.: 4号 e 5号 são ambos 19490000)
    — casa pelo número da edição extraído do nome JP.

    O Suplemento tem stem terminando em '（補）' (sem número de edição); casa
    pelo sufixo 'Suplemento' no nome PT.
    """
    data = stem_jp.split("-")[0]
    # mapear termo JP -> termo PT
    termo = None
    if "御光話録" in stem_jp:
        termo = "Gokōwa-roku"
    elif "御垂示録" in stem_jp:
        termo = "Gosuiji-roku"
    elif "御教え集" in stem_jp:
        termo = "Mioshie-shū"
    if not termo:
        return None

    if "（補）" in stem_jp:
        # Suplemento: nome PT é '<data> - <termo> (Suplemento).txt'
        candidatos = sorted(PT_DIR.glob(f"{data} - {termo} (Suplemento).txt"))
        if candidatos:
            return candidatos[0]
        return None

    m = re.search(r"([0-9０-９]+)号$", stem_jp)
    if not m:
        return None
    num = m.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    candidatos = sorted(PT_DIR.glob(f"{data} - {termo} nº {num}.txt"))
    if candidatos:
        return candidatos[0]
    # fallback: qualquer arquivo da data com o termo
    candidatos2 = sorted(PT_DIR.glob(f"{data} *{termo}*.txt"))
    return candidatos2[0] if candidatos2 else None


def integrar_arquivo(stem_jp: str, colecao: str, *, dry_run: bool = False) -> dict:
    prod_path = achar_prod(stem_jp)
    if prod_path is None:
        return {"arquivo": stem_jp, "status": "sem_prod_pt"}
    obra_prod = prod_path.name
    ckpt_path = CKPT_DIR / f"{stem_jp}.json"

    if not ckpt_path.is_file():
        return {"arquivo": stem_jp, "status": "sem_checkpoint"}

    turnos_jp = extrair_turnos_jp(stem_jp, colecao)
    if not turnos_jp:
        return {"arquivo": stem_jp, "status": "jp_sem_turnos"}

    ckpt = json.loads(ckpt_path.read_text(encoding="utf-8"))
    subs, problemas = montar_substituicoes(ckpt, len(turnos_jp))
    if problemas:
        return {
            "arquivo": stem_jp, "status": "checkpoint_incompleto",
            "problemas": problemas[:10], "n_problemas": len(problemas),
        }

    prod_text = prod_path.read_text(encoding="utf-8")
    pedacos, indices_blocos = separar_blocos(prod_text)

    # paridade (1)
    paridade_ok, erros_paridade = checar_paridade(
        turnos_jp, len(indices_blocos), subs, stem_jp
    )
    if not paridade_ok:
        return {"arquivo": stem_jp, "status": "paridade_falhou", "erros": erros_paridade[:10]}

    # aplicar substituições nos blocos rotulados
    for k, (i, quem, pt_novo) in enumerate(subs):
        idx = indices_blocos[k]
        bloco = pedacos[idx]
        m = ROTULO_RE.match(bloco.strip())
        if not m:
            return {"arquivo": stem_jp, "status": "erro_interno", "motivo": f"bloco {k} sem rótulo"}
        novo_bloco = f"{quem}: {pt_novo}\n"
        pedacos[idx] = novo_bloco

    novo_texto = "".join(pedacos)

    # valida âncoras (2). Se falhar, NÃO grava o texto — reporta para que as
    # âncoras sejam tratadas pelo fluxo estabelecido (resegmenta_pos_mescla /
    # repara_implanta_v2, que usam busca em janela sequencial). Não se faz
    # regeneração automática aqui: regenera_ancora busca no texto inteiro e
    # pode achar falso positivo (achado real: art3 de 4号 regenerado para uma
    # fala em posição ANTERIOR à do art2, violando a ordem das âncoras).
    ok_anc, motivo_anc = validar_ancoras(obra_prod, novo_texto)
    if not ok_anc:
        return {"arquivo": stem_jp, "status": "ancoras_falharam", "motivo": motivo_anc}

    if dry_run:
        return {
            "arquivo": stem_jp, "status": "dry_run_ok",
            "turnos": len(turnos_jp), "blocos_prod": len(indices_blocos),
            "tamanho": f"{len(prod_text)} -> {len(novo_texto)} chars", "ancoras": motivo_anc,
        }

    # backup + grava
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ")
    shutil.copy2(prod_path, BACKUP_DIR / f"{obra_prod}.bak_integracao_{stamp}")
    prod_path.write_text(novo_texto, encoding="utf-8")
    return {
        "arquivo": stem_jp, "status": "integrado", "obra_prod": obra_prod,
        "turnos": len(turnos_jp), "ancoras": motivo_anc, "backup": stamp,
    }


def detectar_colecao(stem: str) -> str:
    for c in ("gokowa", "gosuiji", "mioshie"):
        if (JP_DIR / f"{stem}.txt").is_file():
            if c == "gokowa" and "御光話録" in stem:
                return c
            if c == "gosuiji" and "御垂示録" in stem:
                return c
            if c == "mioshie" and "御教え集" in stem:
                return c
    raise ValueError(f"não identifiquei coleção de {stem}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--colecao", choices=["gokowa", "gosuiji", "mioshie"])
    ap.add_argument("--arquivo", help="stem JP específico (ex.: 19481208-御光話録1号)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.arquivo:
        alvos = [args.arquivo]
        if not args.colecao:
            args.colecao = detectar_colecao(args.arquivo)
    elif args.colecao:
        alvos = sorted(p.stem for p in JP_DIR.glob(PADROES[args.colecao]))
    else:
        ap.error("informe --colecao ou --arquivo")

    print(f"Integrando {len(alvos)} arquivos (coleção: {args.colecao}) | dry_run={args.dry_run}")
    print("=" * 70)
    ok = 0
    for stem in alvos:
        r = integrar_arquivo(stem, args.colecao, dry_run=args.dry_run)
        st = r["status"]
        print(f"  {stem}: {st}")
        if st in ("integrado", "dry_run_ok"):
            ok += 1
            for k in ("turnos", "blocos_prod", "tamanho", "ancoras"):
                if k in r:
                    print(f"      {k}: {r[k]}")
        elif st in ("paridade_falhou", "checkpoint_incompleto", "ancoras_falharam"):
            for k in ("erros", "problemas", "motivo"):
                if k in r:
                    print(f"      {k}: {r[k]}")

    print(f"\nConcluído: {ok}/{len(alvos)} {'(dry-run)' if args.dry_run else '(gravados)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
