#!/usr/bin/env python3
"""Auditoria JP-first dos specs P1b: pareia PT com fatias JP, valida cabeçalhos, corrige anchors."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root  # noqa: E402
from apply_manual_livros_segmentacao import (  # noqa: E402
    Boundary,
    split_by_anchors,
    _find_anchor,
)
from fix_periodicos_work_headers import format_article, parse_article, split_file  # noqa: E402

MANUAL_DIR_NAME = "segmentacao_manual"
RATIO_OK = (1.15, 4.8)
RATIO_OK_POEM = (0.25, 10.0)

JP_OSHIRASE_RE = re.compile(r"^（お伺）")
from livros_qa_markers import is_jp_question_line, is_pt_question_line  # noqa: E402

JP_QUESTION_RE = None  # compat; use is_jp_question_line
PT_QUESTION_RE = None
PT_PERGUNTA_RE = re.compile(r"^\(Pergunta\)")
PT_DATE_LINE_RE = re.compile(
    r"^\[?\d{1,2}(?:º)? de (?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|dezembro)",
    re.I,
)
KOZA_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7}
KOZA_PT_SUBTITLES = (
    "O Propósito do Deus Principal e a Verdade da Ordem Celestial e Terrestre",
    "A Origem da Religião e o Advento do Salvador",
    "A Essência do Bodhisattva Kannon",
    "A Realidade dos Três Mundos: Divino, Espiritual e Material",
    "A Verdade do Bem e do Mal e a Construção do Mundo Luminoso",
    "A Missão do Japão e dos Países Estrangeiros",
    "Princípio da Doença e do Método de Saúde Absoluta",
)


@dataclass
class ArticleAudit:
    index: int
    title_jp: str
    jp_chars: int
    pt_chars: int
    ratio: float
    status: str
    pt_anchor_old: str
    pt_anchor_new: str
    title_pt_old: str
    title_pt_new: str
    pt_prefix_new: str
    notes: list[str] = field(default_factory=list)


@dataclass
class FileAudit:
    filename: str
    profile: str
    articles: list[ArticleAudit]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pt_repaired: bool = False


from livros_segmentacao_pairing import (  # noqa: E402
    content_start as _content_start,
    find_pt_by_needles,
    jp_session_needles,
    pair_positions,
    split_pt_chunks,
    title_pt_from_jp,
    yamamizu_jp_date_to_pt,
)


def derive_anchor(pt: str, pos: int, *, max_len: int = 120) -> str:
    if pos < 0 or pos >= len(pt):
        return ""
    snippet = pt[pos : pos + max_len * 2]
    # Cada entrada mantém o offset real dentro de `snippet`, não só o texto
    # stripado -- necessário para poder devolver um trecho estendido (linha
    # seguinte incluída) que continue sendo um substring literal contíguo de
    # `pt` (ver nota abaixo sobre by "Achado real").
    raw_lines = snippet.splitlines(keepends=True)
    entries: list[tuple[str, int]] = []
    running = 0
    for raw in raw_lines:
        stripped = raw.strip()
        if stripped:
            entries.append((stripped, running + raw.find(stripped)))
        running += len(raw)
    lines = [e[0] for e in entries]
    # Achado real 2026-07-14 (19520615-御教え集10号, sessão 5 de maio): datas
    # com sufixo de ano/era ("5 de maio de 1952 (Showa 27)") não batiam com a
    # forma antiga do regex (só a data pura), então essa linha virava o
    # próprio anchor -- e como a posição encontrada é o INÍCIO da sessão, o
    # cursor de busca sequencial de split_by_anchors ficava colado no próprio
    # marcador "[Ensinamento]" daquela sessão, confundindo-o com o da sessão
    # seguinte (ambas usam o mesmo texto genérico curto). Sufixo opcional
    # aceito para tratar essa linha como data a pular, igual às demais.
    # Achado real 2026-07-15 (19540315-御教え集31号, sessão 4 de fevereiro):
    # a primeira sessão de um número cita o ano por extenso antes do número
    # ("4 de fevereiro de Showa 29 (Festa do Início da Primavera)"), sem
    # nenhum dígito logo após "de" -- o sufixo `\d{3,4}` da correção acima
    # não cobre "de Showa 29"; sem isso, essa linha virava o próprio anchor
    # e o pt_prefix (recalculado à parte por perfil) duplicava a data no
    # corpo final. Sufixo estendido para aceitar também "de <era> <número>"
    # seguido de parêntese descritivo opcional. "novembro" também faltava na
    # lista de meses.
    date_re = re.compile(
        r"^\d{1,2}(?:º)? de (?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
        r"(?:\s+de\s+(?:\d{3,4}|\w+\s+\d{1,3}))?(?:\s*\([^)]*\))?$",
        re.I,
    )
    for idx, (line, start) in enumerate(entries):
        if date_re.match(line):
            continue
        if len(line) >= 20:
            return line[:max_len]
        if len(line) >= 8:
            # Achado real (mesmo caso acima): um marcador curto e genérico
            # ("[Ensinamento]", "Interlocutor:") sozinho se repete várias
            # vezes no livro -- não é único o bastante para a busca
            # sequencial de split_by_anchors relocalizar a MESMA ocorrência
            # de onde foi derivado. Estende até a linha seguinte (substring
            # literal real de `snippet`, preservando quebras/linhas em
            # branco no meio) para desambiguar -- nunca reconstrói com
            # separador artificial, que quebraria a busca literal depois.
            if idx + 1 < len(entries):
                # Achado real 2026-07-14 (19530115-御教え集17号, sessão 5 de
                # dezembro): estender por uma janela fixa de max_len chars a
                # partir de `start` ultrapassava o fim da entries[idx+1] e
                # engolia o marcador de data da sessão SEGUINTE (2 linhas à
                # frente) sempre que entries[idx+1] era curta -- corrompendo
                # o pt_anchor a cada `--fix`, mesmo depois de corrigido à
                # mão. Estender só até o fim de entries[idx+1] (a "linha
                # seguinte" que o comentário acima já dizia ser a intenção),
                # nunca além dela.
                next_line, next_start = entries[idx + 1]
                end = next_start + len(next_line)
                extended = snippet[start:end].rstrip()
                if len(extended) > len(line) and len(extended) <= max_len:
                    return extended
                if len(extended) > len(line) and pt.count(line) > 1:
                    # Achado real 2026-07-15 (19490830-自観叢書第5篇『自観隨談』,
                    # "湯西川温泉"/Yunishigawa Onsen): quando a linha seguinte
                    # sozinha já ultrapassa max_len, a extensão inteira era
                    # descartada (condição `<= max_len` falhava) e caía de
                    # volta no título curto isolado -- que, tendo só 17 chars,
                    # se repetia em prosa de um artigo anterior, corrompendo a
                    # fronteira entre os dois. Restrito a `pt.count(line) > 1`
                    # (linha genuinamente ambígua no corpo inteiro) para não
                    # alterar o resultado dos livros onde a linha curta já é
                    # única e o fallback antigo era inofensivo -- checado por
                    # regressão no acervo inteiro antes de aplicar.
                    return extended[:max_len]
            return line[:max_len]
    line = snippet.splitlines()[0].strip() if snippet else ""
    if len(line) >= 20:
        return line[:max_len]
    if "\n" in snippet:
        two = "\n".join(snippet.splitlines()[:2]).strip()
        return two[:max_len]
    return snippet.strip()[:max_len]


def repair_gosuiji_pt(pt: str) -> tuple[str, bool]:
    """Remove duplicação L115–127 no monólito PT do Gosuiji-roku 1号."""
    marker = "Adorem a Kannon do biombo e Komyo-Nyorai."
    aug8 = "[8 de agosto] O jornal Tokyo Nichi Nichi"
    first = pt.find(marker)
    aug = pt.find(aug8)
    if first < 0 or aug < 0 or aug <= first:
        return pt, False
    # Cortar lixo entre fim legítimo da sessão 5/8 e início 8/8
    end_good = first + len(marker)
    tail = pt[aug:]
    repaired = pt[:end_good].rstrip() + "\n\n" + tail.lstrip()
    return repaired, repaired != pt


def koza_title_pt(n: int, subtitle: str, existing: str = "") -> tuple[str, str]:
    ordinals = ("Primeira", "Segunda", "Terceira", "Quarta", "Quinta", "Sexta", "Sétima")
    label = ordinals[n - 1] if 1 <= n <= 7 else f"Aula {n}"
    sub = KOZA_PT_SUBTITLES[n - 1] if 1 <= n <= len(KOZA_PT_SUBTITLES) else subtitle
    title = f"{label} Aula — {sub}"
    prefix = f"{label} Aula\n\n{sub}" if n == 1 else f"{label} Aula"
    return title, prefix


def audit_file(
    spec_path: Path,
    work_dir: Path,
    *,
    fix: bool = False,
    repair_pt: bool = False,
) -> FileAudit:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    fn = spec["filename"]
    profile = spec.get("profile", "")
    bounds = [Boundary.from_article(a) for a in spec["articles"]]

    jp_path = work_dir / "jp" / fn
    pt_path = work_dir / "pt" / fn
    jp_text = jp_path.read_text(encoding="utf-8")
    pt_text = pt_path.read_text(encoding="utf-8")
    _, jp_blocks = split_file(jp_text)
    _, pt_blocks = split_file(pt_text)
    jp_body = parse_article(jp_blocks[0]).content
    pt_body = parse_article(pt_blocks[0]).content

    pt_repaired = False
    if repair_pt and profile == "ochishiji_roku":
        pt_body, pt_repaired = repair_gosuiji_pt(pt_body)
        if pt_repaired and fix:
            pt_art = parse_article(pt_blocks[0])
            pt_header, _ = split_file(pt_text)
            pt_path.write_text(
                pt_header.rstrip()
                + "\n"
                + format_article(
                    {**pt_art.fields, "title_pt": pt_art.fields.get("title_pt", "")},
                    pt_art.meta,
                    pt_body,
                )
                + "\n",
                encoding="utf-8",
            )

    jp_slices = split_by_anchors(jp_body, [b.jp_anchor for b in bounds], label="JP")
    positions = pair_positions(profile, jp_slices, pt_body, bounds)
    import livros_segmentacao_pairing as _lsp
    diag = dict(_lsp.LAST_PAIRING_DIAGNOSTIC)
    shinko_pt_anchors = (
        _lsp.LAST_SHINKO_PT_ANCHORS
        if profile == "article_collection" and _lsp.LAST_SHINKO_PT_ANCHORS is not None
        else None
    )
    if len(positions) != len(jp_slices):
        fa = FileAudit(fn, profile, [], errors=[f"positions={len(positions)} != slices={len(jp_slices)}"])
        return fa
    if diag.get("method") == "UNRESOLVED_degenerate_no_heading_match":
        fa = FileAudit(
            fn, profile, [],
            errors=[
                "PAREAMENTO_DEGENERADO: needle-match e heading-match falharam para "
                f"{diag.get('n_jp_slices')} trechos -- requer investigação manual, "
                "NÃO aplicado fallback proporcional por tamanho (proibido)."
            ],
        )
        return fa

    audits: list[ArticleAudit] = []
    file_warnings: list[str] = []
    if diag.get("method") == "pt_heading_match":
        file_warnings.append("PT_HEADING_MATCH: pareado por linha-título do PT (needle de conteúdo falhou, mas contagem de títulos bateu exatamente)")
    if diag.get("gap_filled_indices"):
        file_warnings.append(f"GAP_FILLED: índices interpolados por proporção (needle falhou): {diag['gap_filled_indices']}")
    updated_articles = []

    for i, (b, jp_sl, start) in enumerate(zip(bounds, jp_slices, positions, strict=True)):
        end = positions[i + 1] if i + 1 < len(positions) else len(pt_body)
        if i + 1 < len(positions):
            end = positions[i + 1]
        pt_slice = pt_body[start:end].strip()
        ratio = len(pt_slice) / len(jp_sl) if jp_sl else 0
        new_anchor = derive_anchor(pt_body, start)
        old_anchor = b.pt_anchor

        title_pt_new = b.title_pt
        pt_prefix_new = b.pt_prefix
        notes: list[str] = list(b.notes.split("; ") if b.notes else [])
        notes = [n for n in notes if n]

        if profile == "koza_lectures":
            # Achado real (2026-07-15, 19541120-御教え集4号): koza_title_pt()
            # aplica o template fixo de "Primeira Aula.../Segunda Aula..."
            # (7 aulas do 観音講座, KOZA_PT_SUBTITLES) -- só faz sentido para
            # livros que de fato usam cabeçalho "第N講座" (ex. 観音講座). Sem
            # esse match, o `else i + 1` gerava um ordinal falso e sobrescrevia
            # title_pt/pt_anchor manualmente corrigidos com o subtítulo errado
            # em TODOS os outros livros do perfil (série 浄霊法講座, que usa
            # capítulos "一"/"二" + itens numerados, sem relação com Aulas).
            m = re.search(r"第([一二三四五六七八九十\d]+)講座", b.title_jp)
            if m:
                n = KOZA_NUM.get(m.group(1), i + 1)
                subtitle = b.title_jp.split("講座", 1)[-1].strip()
                title_pt_new, pt_prefix_new = koza_title_pt(n, subtitle, b.title_pt)
        elif profile == "ochishiji_roku":
            title_pt_new = title_pt_from_jp(profile, b.title_jp)
            if b.kind == "preface":
                pt_prefix_new = "Prefácio"
            elif re.search(r" de \w+$", title_pt_new):
                # NAO sobrescrever new_anchor com o titulo "limpo" aqui (bug
                # real, 2026-07-14): title_pt_new e' uma forma normalizada
                # (ex. "1 de agosto") que frequentemente NAO e' substring
                # literal do corpo PT real (ex. "[1º de agosto]", com
                # colchetes/ordinal) -- split_by_anchors entao falha com
                # "anchor nao encontrado". new_anchor ja foi calculado por
                # derive_anchor(pt_body, start) na linha acima (posicao real,
                # sempre literal), que deliberadamente pula a propria linha de
                # data e devolve a 1a linha de conteudo substantivo -- deixar
                # esse valor real ficar em pe. pt_prefix_new continua sendo o
                # titulo bonito, usado so como prefixo de exibicao.
                pt_prefix_new = title_pt_new
        elif profile == "gokowa_roku_qa":
            title_pt_new = title_pt_from_jp(profile, b.title_jp)
            if re.search(r" de \w+$", title_pt_new):
                # Mesmo bug/correcao do ramo ochishiji_roku acima.
                pt_prefix_new = title_pt_new
            elif i == 0:
                pt_prefix_new = title_pt_new
        elif profile == "mioshie_shu":
            title_pt_new = title_pt_from_jp(profile, b.title_jp)
            if re.search(r" de \w+$", title_pt_new):
                # Mesmo bug/correcao do ramo ochishiji_roku acima.
                pt_prefix_new = title_pt_new
        elif profile == "poem_collection":
            title_pt_new = yamamizu_jp_date_to_pt(b.title_jp) or b.title_jp.split(" — ")[-1][:80]
            if b.kind == "preface":
                title_pt_new = "Prefácio"
                pt_prefix_new = "Prefácio"
        elif profile == "wara_collection":
            theme = b.title_jp.split(" — ")[-1].strip()
            title_pt_new = theme if theme not in ("はしがき",) else "Prefácio"
        elif profile == "article_collection" and shinko_pt_anchors is not None:
            # derive_anchor genérico escolhe a 1a linha >=8 chars a partir da
            # posição -- como cada ensaio deste perfil tem 3 divisores ────
            # idênticos internos, isso costuma devolver só o divisor (ambíguo
            # para a busca sequencial de split_by_anchors). Usa o anchor
            # divisor+título já calculado por _pair_shinko_positional.
            new_anchor = shinko_pt_anchors[i]

        split_method = spec.get("split_method", "")
        ratio_bounds = (
            RATIO_OK_POEM
            if profile in ("poem_collection", "wara_collection", "hymn_collection", "numbered_collection")
            or split_method in ("line_shinko", "line_miracle")
            else RATIO_OK
        )
        status = "ok"
        if not (ratio_bounds[0] <= ratio <= ratio_bounds[1]):
            status = "ratio_warn"
            notes.append(f"ratio PT/JP={ratio:.2f}")
        if old_anchor and new_anchor and old_anchor[:30] != new_anchor[:30]:
            status = "anchor_fixed" if fix else "anchor_diff"
        if not new_anchor:
            status = "error"
            notes.append("pt_anchor não encontrado")
        if i in diag.get("unresolved_indices", []):
            status = "error"
            new_anchor = ""
            notes.append("PAREAMENTO_NAO_RESOLVIDO: needle e heading falharam para este trecho (posição não confiável, não gravada) -- requer investigação manual")

        aa = ArticleAudit(
            index=i + 1,
            title_jp=b.title_jp,
            jp_chars=len(jp_sl),
            pt_chars=len(pt_slice),
            ratio=round(ratio, 2),
            status=status,
            pt_anchor_old=old_anchor,
            pt_anchor_new=new_anchor,
            title_pt_old=b.title_pt,
            title_pt_new=title_pt_new,
            pt_prefix_new=pt_prefix_new,
            notes=notes,
        )
        audits.append(aa)

        art = dict(spec["articles"][i])
        if fix:
            art["pt_anchor"] = new_anchor
            art["title_pt"] = title_pt_new
            if pt_prefix_new:
                art["pt_prefix"] = pt_prefix_new
            if notes and status not in ("ok", "anchor_fixed"):
                art["notes"] = "; ".join(dict.fromkeys(notes))
            elif fix and status in ("ok", "anchor_fixed"):
                art["notes"] = ""
        updated_articles.append(art)

    if fix:
        spec["articles"] = updated_articles
        spec["audited_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        spec["audit_method"] = "jp_first_content_pair"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return FileAudit(fn, profile, audits, warnings=file_warnings, pt_repaired=pt_repaired)


def write_audit_report(manual_dir: Path, results: list[FileAudit]) -> Path:
    out = manual_dir / "AUDIT_REPORT.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": [
            {
                "filename": r.filename,
                "profile": r.profile,
                "pt_repaired": r.pt_repaired,
                "errors": r.errors,
                "warnings": r.warnings,
                "articles": [a.__dict__ for a in r.articles],
            }
            for r in results
        ],
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Audita e corrige pareamento PT dos specs P1b")
    p.add_argument("--file", help="Um ficheiro; omitir = todos os specs")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--fix", action="store_true", help="Atualiza pt_anchor/title_pt nos specs")
    p.add_argument("--repair-pt", action="store_true", help="Repara corrupção PT conhecida (Gosuiji)")
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    manual_dir = wr / MANUAL_DIR_NAME

    if args.file:
        specs = [manual_dir / f"{args.file}.json"]
    else:
        specs = sorted(manual_dir.glob("*.txt.json"))

    results: list[FileAudit] = []
    for sp in specs:
        if not sp.is_file():
            print(f"SKIP {sp.name}", file=sys.stderr)
            continue
        try:
            r = audit_file(sp, wr, fix=args.fix, repair_pt=args.repair_pt)
        except Exception as exc:  # noqa: BLE001 - manter lote vivo; registar e continuar
            fn_guess = sp.name[:-5] if sp.name.endswith(".json") else sp.name
            r = FileAudit(fn_guess, "?", [], errors=[f"CRASH: {type(exc).__name__}: {exc}"])
            print(f"CRASH {r.filename}: {exc}", file=sys.stderr)
        results.append(r)
        ok = sum(1 for a in r.articles if a.status == "ok")
        fixed = sum(1 for a in r.articles if a.status == "anchor_fixed")
        warn = sum(1 for a in r.articles if a.status != "ok" and a.status != "anchor_fixed")
        print(f"{r.filename}: {ok} ok, {fixed} fixed, {warn} warn/err, pt_repaired={r.pt_repaired}, errors={r.errors}")

    report = write_audit_report(manual_dir, results)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
