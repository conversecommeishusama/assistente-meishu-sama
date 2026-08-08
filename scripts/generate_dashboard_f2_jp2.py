#!/usr/bin/env python3
"""Gera o HTML do dashboard do trabalho em andamento (CHUNK_TURNAWARE).

Determinístico, sem custo de API — só lê as filas em disco e escreve um
arquivo HTML estático. Pensado para rodar em loop próprio
(`run_dashboard_refresh_loop.sh`), mantendo o arquivo sempre atualizado em
disco. Publicar esse arquivo no link do Artifact ainda exige uma invocação
interativa (a ferramenta Artifact não está disponível em `claude -p`
não-interativo) — este script só prepara o conteúdo, não publica.

2026-07-14: simplificado a pedido do usuário — mostra só a fase em
andamento (CHUNK_TURNAWARE), não as fases já concluídas (F2, JP-2).
"""
import json
import html
import datetime
import subprocess

BASE = "reports/livros_trabalho/segmentacao_manual"
OUT_PATH = "reports/livros_trabalho/segmentacao_manual/DASHBOARD_F2_JP2.html"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_name(entry):
    if isinstance(entry, str):
        return entry
    for k in ("ficheiro", "file", "filename", "arquivo"):
        if k in entry:
            return entry[k]
    return "?"


def esc(s):
    return html.escape(str(s), quote=True)


def load_optional(path):
    try:
        return load(path)
    except FileNotFoundError:
        return {"pending": [], "in_progress": [], "done": [], "failed": [], "concluido": False}


def main():
    # Consolida os arquivos de staging de PENDENCIAS_REVISAO.json antes de
    # gerar o dashboard (2026-07-15) -- roda a cada ciclo deste loop, ja que
    # e o unico laco de fundo que nao compete por esse mesmo arquivo.
    try:
        subprocess.run(
            ["python3", "scripts/merge_pendencias_staging.py"],
            check=False, capture_output=True, text=True, timeout=30,
        )
    except Exception:
        pass  # nao deixa o dashboard quebrar por causa do merge

    chunk_exec = load(f"{BASE}/CHUNK_TURNAWARE_QUEUE.json")
    chunk_aud = load(f"{BASE}/CHUNK_TURNAWARE_AUDITORIA_EXTERNA_QUEUE.json")
    # Shard B (2026-07-15, paralelizacao apos upgrade de plano): fila irmã
    # com metade dos livros que estavam pendentes, processos independentes.
    # load_optional tolera o par B ainda nao existir (roda sozinho, sem B).
    chunk_exec_b = load_optional(f"{BASE}/CHUNK_TURNAWARE_QUEUE_B.json")
    chunk_aud_b = load_optional(f"{BASE}/CHUNK_TURNAWARE_AUDITORIA_EXTERNA_QUEUE_B.json")

    # Fase G (2026-07-15): nova rodada completa de revisao semantica linha a
    # linha JP<->PT, tambem em 2 shards. load_optional tolera nao existir
    # ainda (dashboard nao quebra se essa fase nao tiver sido criada).
    fg_exec = load_optional(f"{BASE}/FASE_G_REVISAO_SEMANTICA_QUEUE.json")
    fg_exec_b = load_optional(f"{BASE}/FASE_G_REVISAO_SEMANTICA_QUEUE_B.json")
    fg_aud = load_optional(f"{BASE}/FASE_G_AUDITORIA_EXTERNA_QUEUE.json")
    fg_aud_b = load_optional(f"{BASE}/FASE_G_AUDITORIA_EXTERNA_QUEUE_B.json")

    fg_total = (
        len(fg_exec.get("pending", [])) + len(fg_exec.get("in_progress", [])) + len(fg_exec.get("done", []))
        + len(fg_exec_b.get("pending", [])) + len(fg_exec_b.get("in_progress", [])) + len(fg_exec_b.get("done", []))
    )
    fg_active = fg_total > 0
    fg_total = fg_total or 1
    fg_exec_done_n = len(fg_exec.get("done", [])) + len(fg_exec_b.get("done", []))
    fg_aud_done_n = len(fg_aud.get("done", [])) + len(fg_aud_b.get("done", []))
    fg_pending_all = fg_exec.get("pending", []) + fg_exec_b.get("pending", [])
    fg_pending_preview = fg_pending_all[:12]
    fg_pending_more = len(fg_pending_all) - len(fg_pending_preview)
    fg_pending_more_note = (
        f'<div class="empty-note">+ {fg_pending_more} outros na fila</div>' if fg_pending_more > 0 else ""
    )
    fg_pending_rows = "".join(
        f'<tr><td class="book-title">{esc(f)}</td></tr>' for f in fg_pending_preview
    )
    fg_aud_done = fg_aud.get("done", []) + fg_aud_b.get("done", [])
    fg_aud_rows = ""
    if fg_aud_done:
        fg_aud_done_sorted = sorted(
            fg_aud_done,
            key=lambda e: (e.get("at", "") if isinstance(e, dict) else ""),
            reverse=True,
        )
        for e in fg_aud_done_sorted[:30]:
            n = esc(extract_name(e))
            nota = esc(e.get("nota", "") if isinstance(e, dict) else "")
            at = esc(e.get("at", "") if isinstance(e, dict) else "")
            fg_aud_rows += f'<tr><td class="book-title">{n}</td><td>{nota}</td><td class="num" style="white-space:nowrap;">{at}</td></tr>'
    else:
        fg_aud_rows = '<tr><td colspan="3" class="empty-note">Nenhum livro confirmado pelo auditor ainda.</td></tr>'
    fg_concluido = bool(fg_aud.get("concluido", False)) and bool(fg_aud_b.get("concluido", False))
    fg_chip = "chip-good" if fg_concluido else "chip-live"
    fg_chip_label = "concluído" if fg_concluido else "● ao vivo"
    fg_section = ""
    if fg_active:
        fg_section = f"""
  <h2 style="border-top:2px solid var(--accent); padding-top:2rem; margin-top:3rem;">Fase G — nova rodada de revisão semântica <span class="chip {fg_chip}">{fg_chip_label}</span></h2>
  <p class="section-note" style="margin-top:-0.4rem;">128 livros, revisão linha a linha JP↔PT de conteúdo (não estrutura) — considera as correções acumuladas desde o fechamento da Fase F (09/07–12/07). 2 shards paralelos (A+B). Protocolo: <code>PROTOCOLO_REVISAO_LITERARIA_FASE_F.md</code>.</p>
  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-card-label">Executor — marcado "done"</div>
      <div class="stat-row"><span class="stat-count">{fg_exec_done_n}</span><span class="stat-total">/ {fg_total}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{100*fg_exec_done_n/fg_total:.1f}%;"></div></div>
      <div class="section-note" style="margin:0;">{len(fg_pending_all)} pendentes</div>
    </div>
    <div class="stat-card">
      <div class="stat-card-label">Auditor externo — confirmado</div>
      <div class="stat-row"><span class="stat-count">{fg_aud_done_n}</span><span class="stat-total">/ {fg_total}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{100*fg_aud_done_n/fg_total:.1f}%;"></div></div>
      <div class="section-note" style="margin:0;">{len(fg_aud.get('pending',[])) + len(fg_aud_b.get('pending',[]))} aguardando reconferência</div>
    </div>
  </div>
  <h2>Fase G — confirmado pelo auditor (mais recentes primeiro)</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Livro</th><th>Nota</th><th>Confirmado em</th></tr></thead>
      <tbody>{fg_aud_rows}</tbody>
    </table>
  </div>
  <h2>Fase G — próximos na fila</h2>
  <div class="table-wrap" style="max-height:260px;">
    <table>
      <thead><tr><th>Livro (pending)</th></tr></thead>
      <tbody>{fg_pending_rows}</tbody>
    </table>
  </div>
  {fg_pending_more_note}
"""

    # Verificação Eiko x acervo (2026-07-17): fila de aproximação semântica
    # checando quais dos 368 artigos do periódico Eiko já têm versão revisada
    # dentro do acervo (128 livros). load_optional tolera não existir ainda.
    eiko_q = load_optional("reports/periodicos_trabalho/EIKO_CROSSREF_QUEUE.json")
    eiko_section = ""
    if eiko_q:
        eiko_pending = eiko_q.get("pending", [])
        eiko_done = eiko_q.get("done", [])
        eiko_total = len(eiko_pending) + len(eiko_done)
        eiko_total_safe = eiko_total or 1
        eiko_found = sum(1 for e in eiko_done if isinstance(e, dict) and e.get("status") == "found")
        eiko_not_found = sum(1 for e in eiko_done if isinstance(e, dict) and e.get("status") == "not_found")
        eiko_uncertain = sum(1 for e in eiko_done if isinstance(e, dict) and e.get("status") == "uncertain")
        eiko_concluido = bool(eiko_q.get("concluido", False)) or (eiko_total > 0 and len(eiko_pending) == 0)
        eiko_chip = "chip-good" if eiko_concluido else "chip-live"
        eiko_chip_label = "concluído" if eiko_concluido else "● ao vivo"

        eiko_found_rows = ""
        found_items = [e for e in eiko_done if isinstance(e, dict) and e.get("status") == "found"]
        for e in found_items[-30:][::-1]:
            title = esc(e.get("title_jp", "?"))
            match = e.get("acervo_match") or {}
            book = esc(match.get("file", "?")) if isinstance(match, dict) else ""
            eiko_found_rows += f'<tr><td class="book-title">{title}</td><td>{book}</td></tr>'
        if not eiko_found_rows:
            eiko_found_rows = '<tr><td colspan="2" class="empty-note">Nenhum achado confirmado ainda.</td></tr>'

        eiko_section = f"""
  <h2 style="border-top:2px solid var(--accent); padding-top:2rem; margin-top:3rem;">Verificação Eiko × acervo <span class="chip {eiko_chip}">{eiko_chip_label}</span></h2>
  <p class="section-note" style="margin-top:-0.4rem;">368 artigos do periódico Eiko (栄光), verificando por aproximação semântica (não regex) quais já têm versão revisada dentro dos 128 livros do acervo — essa versão substitui a tradução antiga (~08/07) do periódico. Protocolo: <code>reports/periodicos_trabalho/EIKO_CROSSREF_PROMPT.md</code>.</p>
  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-card-label">Processados</div>
      <div class="stat-row"><span class="stat-count">{len(eiko_done)}</span><span class="stat-total">/ {eiko_total}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{100*len(eiko_done)/eiko_total_safe:.1f}%;"></div></div>
      <div class="section-note" style="margin:0;">{len(eiko_pending)} pendentes</div>
    </div>
    <div class="stat-card">
      <div class="stat-card-label">Achados no acervo (found)</div>
      <div class="stat-row"><span class="stat-count">{eiko_found}</span></div>
      <div class="section-note" style="margin:0;">{eiko_not_found} só no periódico · {eiko_uncertain} incertos</div>
    </div>
  </div>
  <h2>Eiko — achados confirmados no acervo (mais recentes primeiro)</h2>
  <div class="table-wrap" style="max-height:260px;">
    <table>
      <thead><tr><th>Artigo (título JP)</th><th>Livro do acervo</th></tr></thead>
      <tbody>{eiko_found_rows}</tbody>
    </table>
  </div>
"""

    # Fase G periodicos (2026-07-18): revisao semantica linha a linha dos 627
    # artigos de periodico marcados uncertain/not_found pelo crossref contra o
    # acervo. 2 shards, mesmo padrao da Fase G dos 128 livros, mas a unidade
    # e' 1 artigo dentro de um arquivo consolidado, chave = entry_id (nao
    # ficheiro/arquivo).
    fgp_exec_a = load_optional("reports/periodicos_trabalho/FASE_G_PERIODICOS_EXECUCAO_QUEUE_A.json")
    fgp_exec_b = load_optional("reports/periodicos_trabalho/FASE_G_PERIODICOS_EXECUCAO_QUEUE_B.json")
    fgp_aud_a = load_optional("reports/periodicos_trabalho/FASE_G_PERIODICOS_AUDITORIA_QUEUE_A.json")
    fgp_aud_b = load_optional("reports/periodicos_trabalho/FASE_G_PERIODICOS_AUDITORIA_QUEUE_B.json")
    fgp_total = (
        len(fgp_exec_a.get("pending", [])) + len(fgp_exec_a.get("in_progress", [])) + len(fgp_exec_a.get("done", []))
        + len(fgp_exec_b.get("pending", [])) + len(fgp_exec_b.get("in_progress", [])) + len(fgp_exec_b.get("done", []))
    )
    fgp_active = fgp_total > 0
    fgp_total = fgp_total or 1
    fgp_exec_done_n = len(fgp_exec_a.get("done", [])) + len(fgp_exec_b.get("done", []))
    fgp_aud_done_n = len(fgp_aud_a.get("done", [])) + len(fgp_aud_b.get("done", []))
    fgp_pending_all = fgp_exec_a.get("pending", []) + fgp_exec_b.get("pending", [])

    def fgp_label(e):
        if not isinstance(e, dict):
            return "?"
        return f'{esc(e.get("periodico_arquivo","?"))} · {esc(e.get("title_jp") or e.get("entry_id","?"))}'

    fgp_pending_preview = fgp_pending_all[:12]
    fgp_pending_more = len(fgp_pending_all) - len(fgp_pending_preview)
    fgp_pending_more_note = (
        f'<div class="empty-note">+ {fgp_pending_more} outros na fila</div>' if fgp_pending_more > 0 else ""
    )
    fgp_pending_rows = "".join(f'<tr><td class="book-title">{fgp_label(e)}</td></tr>' for e in fgp_pending_preview)
    fgp_aud_done = fgp_aud_a.get("done", []) + fgp_aud_b.get("done", [])
    fgp_aud_rows = ""
    if fgp_aud_done:
        fgp_aud_done_sorted = sorted(fgp_aud_done, key=lambda e: (e.get("at", "") if isinstance(e, dict) else ""), reverse=True)
        for e in fgp_aud_done_sorted[:30]:
            nota = esc(e.get("nota", "") if isinstance(e, dict) else "")
            at = esc(e.get("at", "") if isinstance(e, dict) else "")
            fgp_aud_rows += f'<tr><td class="book-title">{fgp_label(e)}</td><td>{nota}</td><td class="num" style="white-space:nowrap;">{at}</td></tr>'
    else:
        fgp_aud_rows = '<tr><td colspan="3" class="empty-note">Nenhum artigo confirmado pelo auditor ainda.</td></tr>'
    fgp_concluido = bool(fgp_aud_a.get("concluido", False)) and bool(fgp_aud_b.get("concluido", False))
    fgp_chip = "chip-good" if fgp_concluido else "chip-live"
    fgp_chip_label = "concluído" if fgp_concluido else "● ao vivo"
    fgp_section = ""
    if fgp_active:
        fgp_section = f"""
  <h2 style="border-top:2px solid var(--accent); padding-top:2rem; margin-top:3rem;">Fase G — periódicos <span class="chip {fgp_chip}">{fgp_chip_label}</span></h2>
  <p class="section-note" style="margin-top:-0.4rem;">627 artigos de periódico (uncertain/not_found no crossref contra o acervo) recebendo a mesma revisão semântica linha a linha JP↔PT da Fase G dos 128 livros — unidade é 1 artigo, não 1 livro. 2 shards paralelos (A+B). Protocolo: <code>reports/periodicos_trabalho/PROTOCOLO_REVISAO_PERIODICOS.md</code>.</p>
  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-card-label">Executor — marcado "done"</div>
      <div class="stat-row"><span class="stat-count">{fgp_exec_done_n}</span><span class="stat-total">/ {fgp_total}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{100*fgp_exec_done_n/fgp_total:.1f}%;"></div></div>
      <div class="section-note" style="margin:0;">{len(fgp_pending_all)} pendentes</div>
    </div>
    <div class="stat-card">
      <div class="stat-card-label">Auditor externo — confirmado</div>
      <div class="stat-row"><span class="stat-count">{fgp_aud_done_n}</span><span class="stat-total">/ {fgp_total}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{100*fgp_aud_done_n/fgp_total:.1f}%;"></div></div>
      <div class="section-note" style="margin:0;">{len(fgp_aud_a.get('pending',[])) + len(fgp_aud_b.get('pending',[]))} aguardando reconferência</div>
    </div>
  </div>
  <h2>Fase G periódicos — confirmado pelo auditor (mais recentes primeiro)</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Artigo</th><th>Nota</th><th>Confirmado em</th></tr></thead>
      <tbody>{fgp_aud_rows}</tbody>
    </table>
  </div>
  <h2>Fase G periódicos — próximos na fila</h2>
  <div class="table-wrap" style="max-height:260px;">
    <table>
      <thead><tr><th>Artigo (pending)</th></tr></thead>
      <tbody>{fgp_pending_rows}</tbody>
    </table>
  </div>
  {fgp_pending_more_note}
"""

    # Revisao editorial (2026-07-20): revisao de gramatica/elegancia/fluidez
    # dos livros + periodicos para PUBLICACAO (livros_publicacao_pt/ ->
    # livros_publicacao_pt_revisado/), pipeline totalmente separado do motor
    # de busca. 138 itens (128 livros + 10 periodicos), 2 shards, mesmo
    # padrao executor/auditor externo das secoes acima.
    re_exec_a = load_optional("reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_QUEUE.json")
    re_exec_b = load_optional("reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_QUEUE_B.json")
    re_aud_a = load_optional("reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_AUDITORIA_EXTERNA_QUEUE.json")
    re_aud_b = load_optional("reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_AUDITORIA_EXTERNA_QUEUE_B.json")
    re_total = (
        len(re_exec_a.get("pending", [])) + len(re_exec_a.get("in_progress", [])) + len(re_exec_a.get("done", []))
        + len(re_exec_b.get("pending", [])) + len(re_exec_b.get("in_progress", [])) + len(re_exec_b.get("done", []))
    )
    re_active = re_total > 0
    re_total = re_total or 1
    re_exec_done_n = len(re_exec_a.get("done", [])) + len(re_exec_b.get("done", []))
    re_aud_done_n = len(re_aud_a.get("done", [])) + len(re_aud_b.get("done", []))
    re_pending_all = re_exec_a.get("pending", []) + re_exec_b.get("pending", [])

    def re_label(e):
        if not isinstance(e, dict):
            return esc(str(e))
        tipo = e.get("tipo", "?")
        return f'{esc(e.get("ficheiro","?"))} <span class="section-note" style="margin:0;display:inline;">({esc(tipo)})</span>'

    re_pending_preview = re_pending_all[:12]
    re_pending_more = len(re_pending_all) - len(re_pending_preview)
    re_pending_more_note = (
        f'<div class="empty-note">+ {re_pending_more} outros na fila</div>' if re_pending_more > 0 else ""
    )
    re_pending_rows = "".join(f'<tr><td class="book-title">{re_label(e)}</td></tr>' for e in re_pending_preview)
    re_aud_done = re_aud_a.get("done", []) + re_aud_b.get("done", [])
    re_aud_rows = ""
    if re_aud_done:
        re_aud_done_sorted = sorted(re_aud_done, key=lambda e: (e.get("at", "") if isinstance(e, dict) else ""), reverse=True)
        for e in re_aud_done_sorted[:30]:
            nota = esc(e.get("nota", "") if isinstance(e, dict) else "")
            at = esc(e.get("at", "") if isinstance(e, dict) else "")
            re_aud_rows += f'<tr><td class="book-title">{esc(extract_name(e))}</td><td>{nota}</td><td class="num" style="white-space:nowrap;">{at}</td></tr>'
    else:
        re_aud_rows = '<tr><td colspan="3" class="empty-note">Nenhum item confirmado pelo auditor ainda.</td></tr>'
    re_concluido = bool(re_aud_a.get("concluido", False)) and bool(re_aud_b.get("concluido", False))
    re_chip = "chip-good" if re_concluido else "chip-live"
    re_chip_label = "concluído" if re_concluido else "● ao vivo"
    re_section = ""
    if re_active:
        re_section = f"""
  <h2 style="border-top:2px solid var(--accent); padding-top:2rem; margin-top:3rem;">Revisão editorial — publicação <span class="chip {re_chip}">{re_chip_label}</span></h2>
  <p class="section-note" style="margin-top:-0.4rem;">128 livros + 10 periódicos, revisão de gramática/elegância/fluidez para publicação (nunca sentido) — pipeline separado do motor de busca, não afeta produção. 2 shards paralelos (A+B). Protocolo: <code>livros_publicacao_pt_revisado/PROTOCOLO_REVISAO_EDITORIAL.md</code>.</p>
  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-card-label">Executor — marcado "done"</div>
      <div class="stat-row"><span class="stat-count">{re_exec_done_n}</span><span class="stat-total">/ {re_total}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{100*re_exec_done_n/re_total:.1f}%;"></div></div>
      <div class="section-note" style="margin:0;">{len(re_pending_all)} pendentes</div>
    </div>
    <div class="stat-card">
      <div class="stat-card-label">Auditor externo — confirmado</div>
      <div class="stat-row"><span class="stat-count">{re_aud_done_n}</span><span class="stat-total">/ {re_total}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{100*re_aud_done_n/re_total:.1f}%;"></div></div>
      <div class="section-note" style="margin:0;">{len(re_aud_a.get('pending',[])) + len(re_aud_b.get('pending',[]))} aguardando reconferência</div>
    </div>
  </div>
  <h2>Revisão editorial — confirmado pelo auditor (mais recentes primeiro)</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Item</th><th>Nota</th><th>Confirmado em</th></tr></thead>
      <tbody>{re_aud_rows}</tbody>
    </table>
  </div>
  <h2>Revisão editorial — próximos na fila</h2>
  <div class="table-wrap" style="max-height:260px;">
    <table>
      <thead><tr><th>Item (pending)</th></tr></thead>
      <tbody>{re_pending_rows}</tbody>
    </table>
  </div>
  {re_pending_more_note}
"""

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total = (
        len(chunk_exec.get("pending", [])) + len(chunk_exec.get("in_progress", [])) + len(chunk_exec.get("done", []))
        + len(chunk_exec_b.get("pending", [])) + len(chunk_exec_b.get("in_progress", [])) + len(chunk_exec_b.get("done", []))
    )
    total = total or 1
    exec_done_n = len(chunk_exec.get("done", [])) + len(chunk_exec_b.get("done", []))
    aud_done_n = len(chunk_aud.get("done", [])) + len(chunk_aud_b.get("done", []))
    pending_all = chunk_exec.get("pending", []) + chunk_exec_b.get("pending", [])
    pending_preview = pending_all[:12]
    pending_more = len(pending_all) - len(pending_preview)
    pending_more_note = (
        f'<div class="empty-note">+ {pending_more} outros na fila</div>' if pending_more > 0 else ""
    )
    pending_rows = "".join(
        f'<tr><td class="book-title">{esc(f)}</td></tr>' for f in pending_preview
    )

    aud_done = chunk_aud.get("done", []) + chunk_aud_b.get("done", [])
    aud_rows = ""
    if aud_done:
        # mais recentes primeiro (ordena por "at" quando disponivel, shards intercalados)
        aud_done_sorted = sorted(
            aud_done,
            key=lambda e: (e.get("at", "") if isinstance(e, dict) else ""),
            reverse=True,
        )
        for e in aud_done_sorted[:30]:
            n = esc(extract_name(e))
            nota = esc(e.get("nota", "") if isinstance(e, dict) else "")
            at = esc(e.get("at", "") if isinstance(e, dict) else "")
            aud_rows += f'<tr><td class="book-title">{n}</td><td>{nota}</td><td class="num" style="white-space:nowrap;">{at}</td></tr>'
    else:
        aud_rows = '<tr><td colspan="3" class="empty-note">Nenhum livro confirmado pelo auditor ainda.</td></tr>'

    concluido = bool(chunk_aud.get("concluido", False)) and bool(chunk_aud_b.get("concluido", False))
    chip = "chip-good" if concluido else "chip-live"
    chip_label = "concluído" if concluido else "● ao vivo"

    html_out = f"""<title>Fechamento segmentação/pareamento + corte turn-aware</title>
<style>
  :root {{
    --paper: #e4e1d6; --paper-raised: #eeece3; --ink: #26241f; --ink-dim: #57534a;
    --line: #c9c4b4; --accent: #b7472a; --accent-dim: #b7472a33;
    --good: #3f6b52; --good-dim: #3f6b5222; --pending: #9c7a2e; --pending-dim: #9c7a2e22;
    --warn: #9c3f2e; --warn-dim: #9c3f2e1e;
    --mono: "IBM Plex Mono", "SF Mono", Menlo, Consolas, monospace;
    --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    --sans: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --paper: #171613; --paper-raised: #201e19; --ink: #e9e4d6; --ink-dim: #b3ac9a;
      --line: #3a372f; --accent: #e0824f; --accent-dim: #e0824f2b;
      --good: #6fa484; --good-dim: #6fa48425; --pending: #d1a94a; --pending-dim: #d1a94a22;
      --warn: #e08b6f; --warn-dim: #e08b6f22; }}
  }}
  :root[data-theme="dark"] {{ --paper: #171613; --paper-raised: #201e19; --ink: #e9e4d6; --ink-dim: #b3ac9a;
    --line: #3a372f; --accent: #e0824f; --accent-dim: #e0824f2b;
    --good: #6fa484; --good-dim: #6fa48425; --pending: #d1a94a; --pending-dim: #d1a94a22;
    --warn: #e08b6f; --warn-dim: #e08b6f22; }}
  :root[data-theme="light"] {{ --paper: #e4e1d6; --paper-raised: #eeece3; --ink: #26241f; --ink-dim: #57534a;
    --line: #c9c4b4; --accent: #b7472a; --accent-dim: #b7472a33;
    --good: #3f6b52; --good-dim: #3f6b5222; --pending: #9c7a2e; --pending-dim: #9c7a2e22;
    --warn: #9c3f2e; --warn-dim: #9c3f2e1e; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--paper); color: var(--ink); font-family: var(--sans);
    padding: 2.5rem 1.25rem 4rem; display: flex; justify-content: center; }}
  main {{ width: 100%; max-width: 800px; }}
  .eyebrow {{ font-family: var(--mono); font-size: 0.72rem; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--accent); }}
  h1 {{ font-family: var(--serif); font-weight: 500; font-size: 1.9rem; line-height: 1.15;
    margin: 0.35rem 0 0.4rem; text-wrap: balance; }}
  .sub {{ color: var(--ink-dim); font-size: 0.94rem; line-height: 1.5; max-width: 70ch; margin: 0 0 1.8rem; }}
  h2 {{ font-family: var(--serif); font-weight: 500; font-size: 1.15rem; margin: 2.4rem 0 0.9rem;
    padding-top: 1.6rem; border-top: 1px solid var(--line); display: flex; align-items: baseline; gap: 0.6rem; }}
  h2:first-of-type {{ border-top: none; padding-top: 0; margin-top: 0.4rem; }}
  .section-note {{ color: var(--ink-dim); font-size: 0.85rem; margin: -0.6rem 0 1rem; line-height: 1.5; }}
  .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.6rem; }}
  @media (max-width: 560px) {{ .stat-grid {{ grid-template-columns: 1fr; }} }}
  .stat-card {{ background: var(--paper-raised); border: 1px solid var(--line); border-radius: 10px;
    padding: 1.1rem 1.25rem; }}
  .stat-card-label {{ font-family: var(--mono); font-size: 0.68rem; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--ink-dim); margin-bottom: 0.4rem; }}
  .stat-row {{ display: flex; align-items: baseline; gap: 0.5rem; }}
  .stat-count {{ font-family: var(--mono); font-variant-numeric: tabular-nums; font-size: 2.2rem;
    font-weight: 600; letter-spacing: -0.02em; }}
  .stat-total {{ font-family: var(--mono); font-variant-numeric: tabular-nums; font-size: 1rem; color: var(--ink-dim); }}
  .bar-track {{ width: 100%; height: 8px; border-radius: 999px; background: var(--paper);
    border: 1px solid var(--line); overflow: hidden; margin: 0.5rem 0 0.3rem; }}
  .bar-fill {{ height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--accent), var(--good)); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.83rem; }}
  .table-wrap {{ overflow-x: auto; margin-bottom: 1rem; max-height: 420px; overflow-y: auto; }}
  th {{ text-align: left; font-family: var(--mono); font-size: 0.66rem; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--ink-dim); font-weight: 500; padding: 0 0.6rem 0.5rem 0;
    border-bottom: 1px solid var(--line); position: sticky; top: 0; background: var(--paper); }}
  td {{ padding: 0.5rem 0.6rem 0.5rem 0; border-bottom: 1px solid var(--line); vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  .book-title {{ line-height: 1.35; font-weight: 500; white-space: nowrap; }}
  .num {{ font-family: var(--mono); font-variant-numeric: tabular-nums; }}
  .chip {{ display: inline-block; font-family: var(--mono); font-size: 0.7rem; padding: 0.15rem 0.55rem;
    border-radius: 999px; white-space: nowrap; }}
  .chip-good {{ background: var(--good-dim); color: var(--good); }}
  .chip-pending {{ background: var(--pending-dim); color: var(--pending); }}
  .chip-warn {{ background: var(--warn-dim); color: var(--warn); }}
  .chip-live {{ background: var(--accent-dim); color: var(--accent); }}
  .empty-note {{ color: var(--ink-dim); font-size: 0.85rem; font-style: italic; padding: 0.6rem 0; }}
  footer {{ border-top: 1px solid var(--line); padding-top: 1rem; margin-top: 2rem; font-family: var(--mono);
    font-size: 0.72rem; color: var(--ink-dim); line-height: 1.6; }}
</style>
<main>
  <div class="eyebrow">Goshinsho · Acervo livros_trabalho</div>
  <h1>Fechamento segmentação/pareamento + corte turn-aware <span class="chip {chip}">{chip_label}</span></h1>
  <p class="sub">128 dos 128 livros do acervo (御教え集 3号/8号 voltaram ao escopo em 2026-07-15, pendência de rotulagem já corrigida). Fecha a 100% a segmentação JP e o pareamento PT de cada livro; os das séries Gokōwa/Gosuiji-roku/Mioshie-shū recebem também o corte por tamanho turn-aware, que nunca parte um par Interlocutor:/Meishu-Sama: ao meio. Executor aplica e confere; auditor externo reconfere de forma independente antes de qualquer livro contar como pronto. Processamento em 2 shards paralelos (A + B) desde 2026-07-15. Protocolo: <code>PROTOCOLO_CHUNK_TURNAWARE.md</code>.</p>

  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-card-label">Executor — marcado "done"</div>
      <div class="stat-row"><span class="stat-count">{exec_done_n}</span><span class="stat-total">/ {total}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{100*exec_done_n/total:.1f}%;"></div></div>
      <div class="section-note" style="margin:0;">{len(chunk_exec.get('pending',[]))} pendentes</div>
    </div>
    <div class="stat-card">
      <div class="stat-card-label">Auditor externo — confirmado</div>
      <div class="stat-row"><span class="stat-count">{aud_done_n}</span><span class="stat-total">/ {total}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{100*aud_done_n/total:.1f}%;"></div></div>
      <div class="section-note" style="margin:0;">{len(chunk_aud.get('pending',[]))} aguardando reconferência</div>
    </div>
  </div>

  <h2>Confirmado pelo auditor externo (mais recentes primeiro)</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Livro</th><th>Nota</th><th>Confirmado em</th></tr></thead>
      <tbody>{aud_rows}</tbody>
    </table>
  </div>

  <h2>Próximos na fila</h2>
  <div class="table-wrap" style="max-height:260px;">
    <table>
      <thead><tr><th>Livro (pending)</th></tr></thead>
      <tbody>{pending_rows}</tbody>
    </table>
  </div>
  {pending_more_note}
  {fg_section}
  {fgp_section}
  {re_section}
  {eiko_section}
  <footer>
    Gerado em {now} a partir de CHUNK_TURNAWARE_QUEUE(.json/_B.json) e
    CHUNK_TURNAWARE_AUDITORIA_EXTERNA_QUEUE(.json/_B.json), e (se ativa)
    FASE_G_REVISAO_SEMANTICA_QUEUE(.json/_B.json) — shards A e B somados em
    cada fase.<br>
    Arquivo regenerado automaticamente a cada poucos minutos por scripts/run_dashboard_refresh_loop.sh
    (deterministico, sem custo de API).
  </footer>
</main>
"""
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)


if __name__ == "__main__":
    main()
