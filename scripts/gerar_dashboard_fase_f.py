#!/usr/bin/env python3
"""Gera o dashboard HTML da Fase F2 (verificação rigorosa + auditoria externa).

Lê só as filas em disco (determinístico, sem custo de API) e escreve um HTML
autocontido em reports/livros_trabalho/segmentacao_manual/dashboard_fase_f2.html.
Esse arquivo é depois publicado/atualizado via a ferramenta Artifact por uma
invocação com acesso a ela (os laços headless run_fase_f_rigorosa_loop.sh e
run_fase_f_auditor_loop.sh não têm essa ferramenta) — ver
scripts/run_fase_f_dashboard_update.sh, chamado periodicamente por um agente
agendado.
"""
import datetime
import html
import json

EXECUTOR_QUEUE = "reports/livros_trabalho/segmentacao_manual/FASE_F_VERIFICACAO_RIGOROSA_QUEUE.json"
AUDITOR_QUEUE = "reports/livros_trabalho/segmentacao_manual/FASE_F_AUDITORIA_EXTERNA_QUEUE.json"
REABERTURAS = "reports/livros_trabalho/segmentacao_manual/FASE_F_AUDITORIA_EXTERNA_REABERTURAS.json"
OUT_PATH = "reports/livros_trabalho/segmentacao_manual/dashboard_fase_f2.html"

_FILENAME_KEYS = ("ficheiro", "file", "filename")
_NOTE_KEYS = ("nota", "note")
_AT_KEYS = ("at", "done_at", "verified_at")


def get_field(entry, keys, default=""):
    if isinstance(entry, str):
        return entry if keys is _FILENAME_KEYS else default
    for k in keys:
        if k in entry:
            return entry[k]
    return default


def esc(s):
    return html.escape(str(s), quote=True)


def truncate(s, n=280):
    s = str(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def main():
    executor = json.load(open(EXECUTOR_QUEUE, encoding="utf-8"))
    auditor = json.load(open(AUDITOR_QUEUE, encoding="utf-8"))
    reaberturas = json.load(open(REABERTURAS, encoding="utf-8")).get("itens", {})

    exec_done = executor.get("done", [])
    exec_pending_n = len(executor.get("pending", []))
    exec_done_names = {get_field(e, _FILENAME_KEYS) for e in exec_done}

    aud_done = auditor.get("done", [])
    aud_pending_n = len(auditor.get("pending", []))
    aud_done_by_name = {get_field(e, _FILENAME_KEYS): e for e in aud_done}

    total = 128
    exec_done_n = len(exec_done_names)
    aud_done_n = len(aud_done_by_name)
    exec_pct = round(100 * exec_done_n / total)
    aud_pct = round(100 * aud_done_n / total)

    reabertos_ativos = sorted(reaberturas.keys())

    # Tabela 1: confirmados pelo auditor externo (fonte independente e confiavel)
    aud_rows = []
    for name in sorted(aud_done_by_name, key=lambda n: aud_done_by_name[n].get("at", "")):
        e = aud_done_by_name[name]
        nota = get_field(e, _NOTE_KEYS)
        at = get_field(e, _AT_KEYS)
        aud_rows.append(
            f'<tr><td class="book-title">{esc(name)}</td>'
            f'<td>{esc(truncate(nota, 320))}</td>'
            f'<td class="num" style="white-space:nowrap;">{esc(at)}</td></tr>'
        )

    # Tabela 2: reabertos ativos (executor esta reprocessando por desvio real encontrado)
    reab_rows = []
    for name in reabertos_ativos:
        nota = reaberturas[name]
        reab_rows.append(
            f'<tr><td class="book-title">{esc(name)}</td>'
            f'<td>{esc(truncate(nota, 320))}</td></tr>'
        )

    # Tabela 3: marcado done pelo executor, aguardando auditoria independente
    aguardando = []
    for e in exec_done:
        name = get_field(e, _FILENAME_KEYS)
        if name in aud_done_by_name or name in reaberturas:
            continue
        nota = get_field(e, _NOTE_KEYS)
        at = get_field(e, _AT_KEYS)
        aguardando.append((at, name, nota))
    aguardando.sort()
    aguard_rows = [
        f'<tr><td class="book-title">{esc(name)}</td>'
        f'<td>{esc(truncate(nota, 240))}</td>'
        f'<td class="num" style="white-space:nowrap;">{esc(at)}</td></tr>'
        for at, name, nota in aguardando
    ]

    now_local = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z")

    html_out = f"""<title>Fase F2 — Verificação rigorosa + Auditoria externa</title>
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
    padding-top: 1.6rem; border-top: 1px solid var(--line); }}
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
  .table-wrap {{ overflow-x: auto; margin-bottom: 1rem; max-height: 520px; overflow-y: auto; }}
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
  .empty-note {{ color: var(--ink-dim); font-size: 0.85rem; font-style: italic; padding: 0.6rem 0; }}
  footer {{ border-top: 1px solid var(--line); padding-top: 1rem; margin-top: 2rem; font-family: var(--mono);
    font-size: 0.72rem; color: var(--ink-dim); line-height: 1.6; }}
</style>
<main>
  <div class="eyebrow">Goshinsho · Acervo livros_trabalho — Fase F2</div>
  <h1>Verificação rigorosa + auditoria externa</h1>
  <p class="sub">Dashboard limpo, gerado direto das filas em disco (sem histórico de fases anteriores). Dois processos independentes: o <b>executor</b> aplica correções e faz sua própria autoconferência interna; o <b>auditor externo</b> reconfere de forma separada e cética antes de qualquer livro contar como realmente pronto. Os dois números abaixo não são a mesma coisa — só o segundo é confirmação independente.</p>

  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-card-label">Executor — marcado "done"</div>
      <div class="stat-row"><span class="stat-count">{exec_done_n}</span><span class="stat-total">/ {total}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{exec_pct}%;"></div></div>
      <div class="section-note" style="margin:0;">{exec_pending_n} na fila do executor (inclui {len(reabertos_ativos)} reabertos por auditoria)</div>
    </div>
    <div class="stat-card">
      <div class="stat-card-label">Auditor externo — confirmado de forma independente</div>
      <div class="stat-row"><span class="stat-count">{aud_done_n}</span><span class="stat-total">/ {total}</span></div>
      <div class="bar-track"><div class="bar-fill" style="width:{aud_pct}%;"></div></div>
      <div class="section-note" style="margin:0;">{aud_pending_n} aguardando reconferência do auditor</div>
    </div>
  </div>

  <h2>Confirmado pelo auditor externo</h2>
  <p class="section-note">Reverificação independente e cética concluída — auditor reabriu o arquivo, refez a verificação estrutural do zero e conferiu contra o japonês. Nota com evidência concreta de cada auditor, não resumo do executor.</p>
  <div class="table-wrap">
  <table>
    <thead><tr><th>Livro</th><th>Evidência da auditoria</th><th>Confirmado em</th></tr></thead>
    <tbody>
      {"".join(aud_rows) if aud_rows else '<tr><td colspan="3" class="empty-note">Nenhum ainda.</td></tr>'}
    </tbody>
  </table>
  </div>

  <h2>Reabertos por desvio — em reprocessamento</h2>
  <p class="section-note">A auditoria externa encontrou um desvio real de protocolo nestes livros (não confiar no "done" anterior) e os devolveu para o início da fila do executor, com a nota de instrução abaixo anexada.</p>
  <div class="table-wrap">
  <table>
    <thead><tr><th>Livro</th><th>Motivo da reabertura</th></tr></thead>
    <tbody>
      {"".join(reab_rows) if reab_rows else '<tr><td colspan="2" class="empty-note">Nenhum no momento.</td></tr>'}
    </tbody>
  </table>
  </div>

  <h2>Marcado "done" pelo executor — aguardando auditoria</h2>
  <p class="section-note">Nota <b>autorrelatada pelo executor</b> (com sua própria autoconferência interna), ainda <b>não</b> reconfirmada por um processo independente separado. Não tratar como prova de conclusão — é o próximo trabalho do auditor.</p>
  <div class="table-wrap">
  <table>
    <thead><tr><th>Livro</th><th>Nota do executor</th><th>Marcado em</th></tr></thead>
    <tbody>
      {"".join(aguard_rows) if aguard_rows else '<tr><td colspan="3" class="empty-note">Nenhum no momento — auditor está em dia com o executor.</td></tr>'}
    </tbody>
  </table>
  </div>

  <footer>
    Atualizado {esc(now_local)} · gerado por scripts/gerar_dashboard_fase_f.py a partir de
    FASE_F_VERIFICACAO_RIGOROSA_QUEUE.json + FASE_F_AUDITORIA_EXTERNA_QUEUE.json +
    FASE_F_AUDITORIA_EXTERNA_REABERTURAS.json — sem edição manual.
  </footer>
</main>
"""

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"escrito: {OUT_PATH} ({len(html_out)} bytes)")
    print(f"executor done={exec_done_n} pending={exec_pending_n} | auditor done={aud_done_n} pending={aud_pending_n}")


if __name__ == "__main__":
    main()
