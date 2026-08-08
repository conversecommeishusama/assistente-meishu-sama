#!/usr/bin/env python3
"""Agente autónomo Acervo Studio — fila contínua trecho → livro → gate."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(PROJECT_ROOT))

from protocol_line_revision import (  # noqa: E402
    extract_segment_slices,
    invalidate_slice_cache,
    process_segment_protocol,
)
from acervo_work_paths import work_root, article_sep  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402

STUDIO_DIR = PROJECT_ROOT / "reports" / "acervo_studio"
AGENT_STATE_PATH = STUDIO_DIR / "agent_state.json"
AGENT_LOG_PATH = STUDIO_DIR / "agent.log"
AGENT_PID_PATH = STUDIO_DIR / "agent.pid"
FAILURE_LEDGER_PATH = STUDIO_DIR / "failure_ledger.jsonl"
SPEC_DIR = PROJECT_ROOT / "reports/livros_trabalho/segmentacao_manual"
GOKOWA_QUEUE = SPEC_DIR / "GOKOWA_GATE_QUEUE.json"
GATE_SCRIPT = SCRIPTS / "gate_gokowa_linha.py"

MAX_TRANSLATE_PER_SEGMENT = 40


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_failure(
    filename: str,
    segment_index: int,
    *,
    issues: list[str],
    notes: list[str],
) -> None:
    """Registo estruturado de falhas — base para correcções sistémicas."""
    import json as _json

    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": _utc(),
        "file": filename,
        "segment_index": segment_index,
        "issues": issues,
        "notes": notes[:6],
    }
    with FAILURE_LEDGER_PATH.open("a", encoding="utf-8") as fh:
        fh.write(_json.dumps(entry, ensure_ascii=False) + "\n")


def _log(msg: str) -> None:
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{_utc()} {msg}\n"
    with AGENT_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line)
    try:
        print(line, end="", flush=True)
    except BrokenPipeError:
        pass


CRASH_ALERTS_PATH = STUDIO_DIR / "CRASH_ALERTS.jsonl"


def _write_crash_alert(filename: str, segment_index: int, exc: BaseException, streak: int) -> None:
    """Regista um bug de código que travou o mesmo trecho repetidamente, para
    ficar visível de imediato (sem depender de vasculhar o journalctl)."""
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": _utc(),
        "filename": filename,
        "segment_index": segment_index,
        "exception": str(exc),
        "streak": streak,
    }
    with CRASH_ALERTS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def agent_state() -> dict[str, Any]:
    default = {
        "mode": "agent",
        "status": "stopped",
        "paused": True,
        "continuous": True,
        "phase": None,
        "current_file": None,
        "current_segment_index": 0,
        "segments_total": 0,
        "policy": "segment_queue_then_book_gate",
        "last_run_at": None,
        "last_error": None,
        "volumes_completed": [],
        "segments_completed": [],
        "turns_translated": 0,
        "pid": None,
    }
    if AGENT_STATE_PATH.is_file():
        default.update(json.loads(AGENT_STATE_PATH.read_text(encoding="utf-8")))
    return default


def set_agent_state(**updates: Any) -> dict[str, Any]:
    st = agent_state()
    st.update(updates)
    st["updated_at"] = _utc()
    AGENT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    AGENT_STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return st


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_lock() -> bool:
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    if AGENT_PID_PATH.is_file():
        try:
            old = int(AGENT_PID_PATH.read_text(encoding="utf-8").strip())
        except ValueError:
            old = 0
        if old and _pid_alive(old):
            return False
    AGENT_PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    set_agent_state(pid=os.getpid(), status="running")
    return True


def release_lock() -> None:
    if AGENT_PID_PATH.is_file():
        AGENT_PID_PATH.unlink(missing_ok=True)
    set_agent_state(pid=None)


def _extract_body(content: str) -> str:
    if "---" in content:
        return content.split("---", 1)[-1].strip()
    return content.strip()


def _load_spec(filename: str) -> dict[str, Any]:
    path = SPEC_DIR / f"{filename}.json"
    if not path.is_file():
        return {"filename": filename, "articles": [{"kind": "monolith", "jp_anchor": "", "title_jp": filename}]}
    return json.loads(path.read_text(encoding="utf-8"))


def _split_dialogue(body: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for p in re.split(r"\n\s*\n", body.strip()):
        p = p.strip()
        if p.startswith("Interlocutor:"):
            out.append(("Interlocutor", p[len("Interlocutor:") :].strip()))
        elif p.startswith("Meishu-Sama:"):
            out.append(("Meishu-Sama", p[len("Meishu-Sama:") :].strip()))
    return out


def _translate_turn(jp_text: str, *, label: str, pt_context: str = "") -> str:
    from goshinsho.services.acervo_studio_service import suggest_turn_translation  # noqa: WPS433

    return (suggest_turn_translation(jp_text, label=label, pt_context=pt_context).get("suggested_pt") or "").strip()


def _apply_pt_body(filename: str, pt_body: str) -> None:
    wr = work_root("livros_acervo")
    pt_path = wr / "pt" / filename
    raw = pt_path.read_text(encoding="utf-8")
    file_pre, blocks = split_file(raw)
    art = parse_article(blocks[0])
    pre = [f"{k}: {v}" for k, v in art.fields.items()] + ["---"]
    block = "\n".join(pre)
    block += ("\n" + art.meta + "\n\n") if art.meta else "\n\n"
    block += pt_body.strip() + "\n"
    pt_path.write_text(file_pre.rstrip() + f"\n{article_sep()}\n" + block, encoding="utf-8")


def _read_pt_body(filename: str) -> str:
    wr = work_root("livros_acervo")
    raw = (wr / "pt" / filename).read_text(encoding="utf-8")
    _, blocks = split_file(raw)
    return _extract_body(parse_article(blocks[0]).content)


def _read_jp_body(filename: str) -> str:
    wr = work_root("livros_acervo")
    raw = (wr / "jp" / filename).read_text(encoding="utf-8")
    _, blocks = split_file(raw)
    return _extract_body(parse_article(blocks[0]).content)


def run_gate(filename: str) -> dict[str, Any]:
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(GATE_SCRIPT), "--file", filename, "--json", "--refresh-queue"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    out: dict[str, Any] = {"ok": proc.returncode == 0, "exit_code": proc.returncode}
    if proc.stdout.strip():
        try:
            rows = json.loads(proc.stdout)
            out["gate"] = rows[0] if isinstance(rows, list) else rows
        except json.JSONDecodeError:
            out["raw"] = proc.stdout.strip()[:500]
    return out


def _validate_segment_on_disk(
    filename: str,
    segment_index: int,
    spec: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Revalida trecho a partir do PT gravado — bloqueia só dúvidas semânticas."""
    from line_by_line_revision import (  # noqa: WPS433
        build_jp_content_units,
        classify_segment_review,
        pair_units_to_pt,
        pt_slice_tail_for_align,
    )
    from apply_manual_livros_segmentacao import Boundary  # noqa: WPS433

    jp_body = _read_jp_body(filename)
    pt_body = _read_pt_body(filename)
    invalidate_slice_cache(filename)
    jp_slice, pt_slice, _ = extract_segment_slices(filename, segment_index, jp_body, pt_body, spec)
    pt_tail = pt_slice_tail_for_align(filename, segment_index, jp_body, pt_body, spec)
    bound = Boundary.from_article(spec["articles"][segment_index])
    profile = spec.get("profile") or "gokowa_roku_qa"
    units = build_jp_content_units(jp_slice)
    pairs = pair_units_to_pt(units, pt_slice, pt_tail=pt_tail)
    review = classify_segment_review(
        jp_slice,
        pt_slice,
        pairs,
        filename=filename,
        bound=bound,
        profile=profile,
        segment_index=segment_index,
    )
    blocking = bool(review.get("needs_human"))
    issues = list(review.get("issues") or [])
    if review.get("mechanical") and not blocking:
        issues = issues or ["desalinhamento"]
    return blocking, issues


def _next_segment_index(filename: str, spec: dict[str, Any]) -> int:
    """Primeiro trecho ainda não aprovado no disco."""
    from goshinsho.services.acervo_studio_service import first_pending_segment_index  # noqa: WPS433

    return first_pending_segment_index(filename)


def process_segment(
    filename: str, segment_index: int, *, translate: bool = True, dry_run: bool = False
) -> dict[str, Any]:
    """Processa um trecho: protocolo A→D linha a linha (pareamento, busca, tradução)."""
    spec = _load_spec(filename)
    articles = spec.get("articles") or []
    if segment_index >= len(articles):
        raise IndexError(f"segment_index {segment_index} fora do intervalo")

    art = articles[segment_index]
    title = art.get("title_pt") or art.get("title_jp") or art.get("kind") or str(segment_index)

    set_agent_state(
        phase=f"A→D trecho {segment_index + 1}/{len(articles)}: {title[:40]}",
        current_segment_index=segment_index,
        segments_total=len(articles),
        protocol_phase="A",
    )
    _log(f"{filename} TRECHO {segment_index + 1}/{len(articles)} ({title}) — protocolo linha a linha")

    jp_body = _read_jp_body(filename)
    pt_body = _read_pt_body(filename)

    old_jp_slice, old_pt_slice, _ = extract_segment_slices(
        filename, segment_index, jp_body, pt_body, spec
    )
    _log(f"  pareamento: JP {len(old_jp_slice)} chars | PT {len(old_pt_slice)} chars")

    def _phase_log(msg: str) -> None:
        _log(msg)
        m = msg.strip()
        if m.startswith("[A]"):
            set_agent_state(protocol_phase="A", live_action=m[4:80])
        elif m.startswith("[B]"):
            set_agent_state(protocol_phase="B", live_action=m[4:80])
        elif m.startswith("[B→C]"):
            set_agent_state(protocol_phase="B", live_action=m[6:80])
        elif m.startswith("[C]"):
            set_agent_state(protocol_phase="C", live_action=m[4:80])
            m2 = re.search(r"L(\d+)", m)
            if m2:
                set_agent_state(live_line_no=int(m2.group(1)))
        elif m.startswith("[D]"):
            set_agent_state(protocol_phase="D", live_action=m[4:80])
        elif m.startswith("  busca:"):
            set_agent_state(live_action=m.strip()[:80])

    result = process_segment_protocol(
        filename,
        segment_index,
        jp_body,
        pt_body,
        spec,
        translate=translate,
        max_translate=MAX_TRANSLATE_PER_SEGMENT,
        log_fn=_phase_log,
    )

    disk_issues: list[str] = []
    invalidate_slice_cache(filename)
    if result.slice_invalid or result.persist_blocked:
        reason = "saída" if result.persist_blocked else "entrada"
        _log(f"  PT não gravado — slice estruturalmente inválido (fase A/D, {reason})")
    elif result.blocking:
        _log("  PT não gravado — trecho ainda com problemas editoriais (fase D)")
    elif dry_run:
        _log("  PT não gravado — dry-run (validação em memória)")
    else:
        pt_body = _read_pt_body(filename)
        jp_body = _read_jp_body(filename)
        from line_by_line_slices import splice_pt_slice, validate_segment_slice  # noqa: WPS433
        from apply_manual_livros_segmentacao import Boundary  # noqa: WPS433

        bound = Boundary.from_article(spec["articles"][segment_index])
        jp_slice, _, _ = extract_segment_slices(filename, segment_index, jp_body, pt_body, spec)
        out_ok, out_issues = validate_segment_slice(
            jp_slice,
            result.pt_slice,
            segment_index,
            title=bound.title_pt or bound.title_jp or "",
            kind=getattr(bound, "kind", "") or "",
        )
        if not out_ok:
            _log(f"  PT não gravado — validação final falhou: {out_issues[0]}")
            result.slice_invalid = True
        else:
            pt_body = splice_pt_slice(pt_body, jp_body, spec, segment_index, result.pt_slice)
            _apply_pt_body(filename, pt_body)
            invalidate_slice_cache(filename)
            set_agent_state(live_action="PT gravado", last_pt_update_at=_utc())

        disk_blocking, disk_issues = _validate_segment_on_disk(filename, segment_index, spec)
        if disk_blocking and not result.blocking:
            _log(f"  AVISO: memória OK mas ficheiro ainda falha após gravação — {disk_issues[:2]}")
        result.blocking = disk_blocking or result.blocking

    if not dry_run:
        from goshinsho.services.acervo_studio_service import (  # noqa: WPS433
            finalize_segment_after_agent,
            post_protocol_verify_and_close,
            segments_agent_completed,
        )

        invalidate_slice_cache(filename)
        systemic = bool(result.slice_invalid or result.persist_blocked)
        systemic_notes = ""
        if result.slice_invalid:
            systemic_notes = "Slice JP/PT estruturalmente inválido (fases A/D)."
        elif result.persist_blocked:
            systemic_notes = "Saída PT não persistível (validação estrutural)."

        if systemic:
            final_status = finalize_segment_after_agent(
                filename,
                segment_index,
                systemic=True,
                systemic_notes=systemic_notes,
            )
        else:
            _log("  [pós-D] verificação pós-retradução — autofix + fecho do trecho")
            close = post_protocol_verify_and_close(filename, segment_index)
            final_status = close["status"]
            if close.get("fixed"):
                _log(
                    f"  autofix: {len(close['fixed'])} unidade(s) corrigida(s) "
                    f"após verificação"
                )
            if close.get("stuck"):
                _log(
                    f"  autofix: {len(close['stuck'])} unidade(s) — "
                    "agente continua retradução automática"
                )
            _log(
                f"  verificação: flags {close['issue_before']}→{close['issue_after']} "
                f"| dúvidas semânticas={close.get('semantic', 0)}"
            )

        result.blocking = False
        done = segments_agent_completed(filename)
    else:
        done = agent_state().get("segments_completed") or []
        final_status = "pending"

    if final_status == "approved":
        _log("  trecho OK — aprovado (fase D)")
    elif final_status == "human_review":
        _log("  dúvidas semânticas — fila do tradutor humano; agente avança")
    elif final_status == "fail":
        _log(f"  falha sistémica — {systemic_notes or 'estrutura/gravação'}")
        _record_failure(
            filename,
            segment_index,
            issues=["systemic_fail"],
            notes=[systemic_notes] if systemic_notes else [],
        )
    else:
        _log(f"  trecho ainda com problemas — {result.review_issues[:3]}")
    set_agent_state(
        turns_translated=agent_state().get("turns_translated", 0) + result.turns_translated,
        segments_completed=done,
        live_action=None,
        live_turn_index=None,
        protocol_phase="D",
    )
    return {
        "segment_index": segment_index,
        "translated": result.turns_translated,
        "corpus_fixes": result.turns_fixed_corpus,
        "blocking": result.blocking,
        "phase_log": result.phase_log,
        "review_issues": result.review_issues,
    }


def process_volume_segments(filename: str, *, start_segment: int = 0, translate: bool = True) -> dict[str, Any]:
    spec = _load_spec(filename)
    articles = spec.get("articles") or []
    set_agent_state(current_file=filename, segments_total=len(articles))

    for i in range(start_segment, len(articles)):
        if agent_state().get("paused"):
            _log("Pausado — a sair do volume")
            return {"ok": False, "paused": True, "next_segment": i}
        process_segment(filename, i, translate=translate)

    _log(f"{filename} todos os trechos processados — a correr gate")
    set_agent_state(phase="gate")
    gate = run_gate(filename)
    _log(f"  gate: {'PASS' if gate.get('ok') else 'FAIL'}")
    return {"ok": gate.get("ok", False), "gate": gate, "file": filename}


def load_queue() -> dict[str, Any]:
    if GOKOWA_QUEUE.is_file():
        return json.loads(GOKOWA_QUEUE.read_text(encoding="utf-8"))
    return {"volumes": [], "current": None}


def next_failed_volume(after: str | None = None) -> str | None:
    q = load_queue()
    failed = [v["file"] for v in q.get("volumes", []) if v.get("status") == "failed"]
    if not failed:
        return None
    if after and after in failed:
        idx = failed.index(after) + 1
        return failed[idx] if idx < len(failed) else None
    return failed[0]


def run_continuous_loop(*, once: bool = False) -> int:
    from goshinsho.services.acervo_studio_service import (  # noqa: WPS433
        reconcile_human_review_queue,
        segments_agent_completed,
    )

    if not acquire_lock():
        _log("Outro agente já está a correr — abortar")
        return 1

    set_agent_state(status="running", paused=False)
    _log("Agente contínuo iniciado (trechos → livro → gate → próximo livro)")
    try:
        rec = reconcile_human_review_queue()
        if rec.get("dismissed") or rec.get("reopened"):
            _log(
                f"  fila reconciliada: {len(rec.get('dismissed') or [])} mecânicos removidos, "
                f"{len(rec.get('reopened') or [])} trecho(s) reaberto(s) para autofix"
            )
    except Exception as exc:
        _log(f"  aviso: reconcile human review falhou: {exc}")

    try:
        while True:
            st = agent_state()
            if st.get("paused"):
                set_agent_state(status="paused")
                _log("Agente em pausa")
                if once:
                    return 0
                time.sleep(10)
                continue

            q = load_queue()
            filename = st.get("current_file") or q.get("current")
            if not filename:
                _log("Fila vazia — a aguardar")
                if once:
                    return 0
                time.sleep(60)
                continue

            seg_start = int(st.get("current_segment_index") or 0)
            spec = _load_spec(filename)
            n_seg = len(spec.get("articles") or [])

            # Sempre o primeiro trecho FAIL/pending no disco — ignora current_segment_index stale
            seg_start = _next_segment_index(filename, spec)

            # Se todos processados, ir para gate
            if seg_start >= n_seg:
                _log(f"{filename} todos os trechos concluídos — a correr gate")
                set_agent_state(phase="gate", current_segment_index=-1, live_action=None)
                gate = run_gate(filename)
                _log(f"  gate: {'PASS' if gate.get('ok') else 'FAIL'}")
                if gate.get("ok"):
                    completed = st.get("volumes_completed") or []
                    if filename not in completed:
                        completed.append(filename)
                    nxt = next_failed_volume(filename)
                    set_agent_state(
                        volumes_completed=completed,
                        current_file=nxt,
                        current_segment_index=0,
                        segments_completed=[],
                        phase=None,
                        status="running" if nxt else "idle",
                        last_error=None,
                        stuck_streak=0,
                    )
                    _log(f"LIVRO FECHADO: {filename} → próximo: {nxt or '—'}")
                    if once:
                        return 0
                    time.sleep(5)
                    continue
                # Gate falha e não há trecho pendente a reprocessar (todos já
                # marcados concluídos) — reprocessar aqui em loop nunca vai
                # resolver, pois não há ação disponível ao nível do trecho.
                # Estrutural: bloquear este ficheiro e avançar para o próximo
                # da fila, em vez de re-verificar o gate indefinidamente
                # (bug anterior: loop infinito de gate FAIL observado por
                # horas sem progresso, a consumir CPU sem necessidade).
                stuck = int(st.get("stuck_streak") or 0) + 1
                if stuck >= 2:
                    nxt = next_failed_volume(filename)
                    set_agent_state(
                        status="blocked",
                        phase="gate",
                        last_error=f"gate FAIL sem trecho pendente: {gate.get('errors')}",
                        current_file=nxt,
                        current_segment_index=0,
                        segments_completed=[],
                        stuck_streak=0,
                    )
                    _log(
                        f"Livro {filename} bloqueado (gate FAIL, sem trecho pendente) "
                        f"— avançar para: {nxt or '—'} (requer reconciliação estrutural dedicada)"
                    )
                else:
                    set_agent_state(stuck_streak=stuck)
                if once:
                    return 0
                time.sleep(10)
                continue

            art = (spec.get("articles") or [])[seg_start]
            title = art.get("title_pt") or art.get("title_jp") or str(seg_start)
            set_agent_state(
                current_file=filename,
                current_segment_index=seg_start,
                last_run_at=_utc(),
                status="running",
                last_error=None,
                phase=f"trecho {seg_start + 1}/{n_seg}: {title[:40]}",
                protocol_phase="init",
                live_action=f"a preparar trecho #{seg_start}",
                live_turn_index=None,
                live_line_no=None,
                segments_completed=segments_agent_completed(filename),
            )

            try:
                if st.get("continuous", True):
                    # Um trecho por iteração — prioriza trechos com problemas
                    if seg_start < n_seg:
                        from goshinsho.services.acervo_studio_service import (  # noqa: WPS433
                            _handoff_agent_done,
                            autofix_segment_issues,
                            file_segment_statuses,
                            finalize_segment_after_agent,
                            first_pending_segment_index,
                            get_segment_handoff,
                            set_segment_handoff,
                        )
                        from line_by_line_slices import invalidate_slice_cache  # noqa: WPS433

                        seg_st = file_segment_statuses(filename, respect_processing=False)
                        seg_info = seg_st["segments"][seg_start]
                        af: dict[str, Any] = {"fixed": [], "stuck": [], "escalated": []}
                        needs_work = not _handoff_agent_done(get_segment_handoff(filename, seg_start))
                        handoff_before = get_segment_handoff(filename, seg_start) or {}
                        issue_before = int(handoff_before.get("issue_count") or 0)
                        notes = handoff_before.get("notes") or ""
                        skip_preflight = (
                            "Reaberto" in notes
                            or issue_before >= 3
                        )

                        if (
                            needs_work
                            and seg_info["status"] in ("pending", "processing")
                            and not skip_preflight
                        ):
                            art = (spec.get("articles") or [])[seg_start]
                            title = art.get("title_pt") or art.get("title_jp") or str(seg_start)
                            set_agent_state(
                                phase=f"autofix trecho {seg_start + 1}/{n_seg}: {title[:40]}",
                                current_segment_index=seg_start,
                                protocol_phase="autofix",
                                live_action=f"retradução automática trecho #{seg_start}",
                            )
                            _log(f"  trecho #{seg_start} — autofix rápido (até 4 unidades)")
                            af = autofix_segment_issues(
                                filename,
                                seg_start,
                                max_fixes=4,
                                escalate_human=False,
                            )
                            if af.get("fixed"):
                                _log(
                                    f"  autofix mecânico: {len(af['fixed'])} unidade(s) "
                                    f"corrigida(s) no trecho #{seg_start}"
                                )
                            if af.get("escalated"):
                                _log(
                                    f"  autofix: {len(af['escalated'])} dúvida(s) "
                                    "semântica(s) → tradutor"
                                )
                            if af.get("stuck"):
                                _log(
                                    f"  autofix preso em {len(af['stuck'])} unidade(s) "
                                    f"no trecho #{seg_start}"
                                )
                            invalidate_slice_cache(filename)
                            final = finalize_segment_after_agent(filename, seg_start)
                            if final != "pending":
                                _log(f"  trecho #{seg_start} concluído após autofix — {final}")
                                seg_info = {"status": final}
                                needs_work = False
                            else:
                                seg_info = file_segment_statuses(
                                    filename, respect_processing=False
                                )["segments"][seg_start]

                        issue_after = int(
                            (get_segment_handoff(filename, seg_start) or {}).get("issue_count") or 0
                        )
                        no_net_progress = (
                            needs_work
                            and seg_info.get("status") == "pending"
                            and issue_after >= issue_before
                            and bool(af.get("fixed") or af.get("stuck") or af.get("attempts"))
                        )
                        streak = int(st.get("stuck_streak") or 0)
                        run_protocol = (
                            needs_work
                            and seg_info.get("status") == "pending"
                            and (
                                af.get("stuck")
                                or no_net_progress
                                or streak >= 2
                                or (skip_preflight and streak == 0 and not af.get("attempts"))
                            )
                        )
                        if run_protocol:
                            reason = "autofix preso"
                            if no_net_progress and not af.get("stuck"):
                                reason = f"sem progresso ({issue_before}→{issue_after} flags)"
                            elif streak >= 4 and not af.get("stuck"):
                                reason = f"repetido {streak + 1}x no mesmo trecho"
                            if streak >= 5:
                                from goshinsho.services.acervo_studio_service import (  # noqa: WPS433
                                    force_retranslate_segment_api,
                                )

                                fr = force_retranslate_segment_api(filename, seg_start)
                                _log(
                                    f"  trecho #{seg_start} — retradução estruturada API "
                                    f"({fr.get('issue_before')}→{fr.get('issue_after')}) "
                                    f"{'OK' if fr.get('ok') else fr.get('message', 'skip')}"
                                )
                                invalidate_slice_cache(filename)
                                handoff_fr = get_segment_handoff(filename, seg_start) or {}
                                issue_before = int(handoff_fr.get("issue_count") or issue_before)
                            # Portão de frescor: o "streak" e o handoff persistido podem estar
                            # desactualizados (ex.: o trecho já foi corrigido por autofix numa
                            # volta anterior, mas o contador de repetição continuou a subir
                            # antes do bookkeeping ser confirmado). Reavaliar agora, com dados
                            # frescos, evita destruir/retraduzir do zero um trecho que já está
                            # correcto — que era exactamente o que causava o ciclo
                            # 8→7→8→8→... observado no trecho #5.
                            fresh_status = finalize_segment_after_agent(filename, seg_start)
                            if fresh_status != "pending":
                                _log(
                                    f"  trecho #{seg_start} — já estava resolvido "
                                    f"({fresh_status}) numa verificação fresca; "
                                    "protocolo completo A→D dispensado"
                                )
                            else:
                                _log(
                                    f"  trecho #{seg_start} — {reason}; "
                                    "a executar protocolo completo A→D"
                                )
                                process_segment(filename, seg_start, translate=True)
                                handoff_after = get_segment_handoff(filename, seg_start) or {}
                                if handoff_after.get("status") == "pending":
                                    issue_n = int(handoff_after.get("issue_count") or 0)
                                    _log(
                                        f"  trecho #{seg_start} — pós-protocolo: "
                                        f"{issue_n} flag(s) mecânica(s) residual(is)"
                                    )
                        elif needs_work and seg_info.get("status") == "pending" and af.get("fixed"):
                            _log(
                                f"  trecho #{seg_start} — autofix progrediu "
                                f"({len(af['fixed'])} un.); continua na próxima volta"
                            )
                        elif (
                            needs_work
                            and seg_info.get("status") == "pending"
                            and af.get("stuck")
                            and streak >= 5
                        ):
                            from goshinsho.services.acervo_studio_service import (  # noqa: WPS433
                                force_retranslate_segment_api,
                            )

                            fr = force_retranslate_segment_api(filename, seg_start)
                            _log(
                                f"  trecho #{seg_start} — retradução estruturada ({streak}x) "
                                f"{fr.get('issue_before')}→{fr.get('issue_after')}"
                            )
                            final = finalize_segment_after_agent(filename, seg_start)
                            _log(f"  trecho #{seg_start} → {final}")

                        # Válvula de segurança final: um trecho pode ficar preso
                        # indefinidamente em falhas puramente mecânicas (ex.: a
                        # API devolve sempre um trecho desproporcional e o guard
                        # de tamanho rejeita-o correctamente) sem nunca ser
                        # "needs_human" — e sem isto bloquearia o LIVRO inteiro
                        # para sempre (nenhum outro ficheiro da fila avançaria).
                        # Ao fim de tentativas automáticas suficientes, escalar
                        # tudo o que resta (mecânico incluído) para revisão
                        # humana em vez de repetir para sempre; o guard de
                        # tamanho continua a ser a última palavra sobre o que é
                        # gravado — isto só decide quando parar de tentar.
                        if (
                            needs_work
                            and seg_info.get("status") == "pending"
                            and streak >= 9
                        ):
                            from goshinsho.services.acervo_studio_service import (  # noqa: WPS433
                                escalate_flagged_turns,
                            )

                            esc = escalate_flagged_turns(
                                filename, seg_start, semantic_only=False
                            )
                            set_segment_handoff(
                                filename,
                                seg_start,
                                "human_review",
                                issue_count=len(esc),
                                escalated=len(esc),
                                notes=(
                                    f"Excedeu {streak}x tentativas automáticas sem "
                                    "convergir (falhas mecânicas persistentes) — "
                                    "escalado para revisão humana."
                                ),
                            )
                            _log(
                                f"  trecho #{seg_start} — {streak}x sem convergir; "
                                f"escalado para revisão humana ({len(esc)} unidade(s))"
                            )

                        invalidate_slice_cache(filename)
                        nxt = first_pending_segment_index(filename)
                        art_nxt = (spec.get("articles") or [])[nxt] if nxt < n_seg else {}
                        title_nxt = art_nxt.get("title_pt") or art_nxt.get("title_jp") or str(nxt)
                        set_agent_state(
                            current_segment_index=nxt if nxt < n_seg else -1,
                            phase=f"trecho {nxt + 1}/{n_seg}: {title_nxt[:40]}" if nxt < n_seg else "gate",
                            live_action=f"a preparar trecho #{nxt}" if nxt < n_seg else None,
                            stuck_streak=0 if nxt != seg_start else int(st.get("stuck_streak") or 0),
                        )
                        prev = int(st.get("current_segment_index") or -1)
                        if nxt == seg_start and nxt == prev and nxt < n_seg:
                            if _handoff_agent_done(get_segment_handoff(filename, nxt)):
                                set_agent_state(stuck_streak=0, stuck_segment=None)
                            else:
                                streak = int(st.get("stuck_streak") or 0) + 1
                                set_agent_state(stuck_streak=streak, stuck_segment=nxt)
                                wait = min(30 + streak * 15, 300)
                                _log(f"  trecho #{nxt} repetido ({streak}x) — pausa {wait}s antes de reprocessar")
                                set_agent_state(
                                    live_action=f"pausa {wait}s — trecho #{nxt} aguarda retry",
                                    protocol_phase="wait",
                                )
                                time.sleep(wait)
                        else:
                            set_agent_state(stuck_streak=0, stuck_segment=None)
                        set_agent_state(current_segment_index=nxt)
                        if once:
                            return 0
                        time.sleep(3)
                        continue
                    result = process_volume_segments(filename, start_segment=n_seg, translate=False)
                else:
                    result = process_volume_segments(filename, start_segment=seg_start, translate=True)
                    set_agent_state(current_segment_index=n_seg)
            except Exception as exc:
                # Disjuntor: uma excepção Python (bug de código, spec malformado,
                # etc.) não deve poder repetir-se indefinidamente sem limite —
                # incidente real (03/07): loop de 7h a repetir o mesmo erro no
                # mesmo trecho, sem nunca acionar nenhuma válvula de escape,
                # porque este except não tinha contador próprio (só os caminhos
                # de "gate FAIL" e "trecho não converge" tinham).
                crash_key = f"{filename}#{seg_start}:{exc}"
                crash_streak = (
                    int(st.get("crash_streak") or 0) + 1
                    if st.get("crash_key") == crash_key
                    else 1
                )
                set_agent_state(
                    status="error",
                    last_error=str(exc),
                    crash_key=crash_key,
                    crash_streak=crash_streak,
                )
                _log(f"ERRO: {exc}")
                if crash_streak >= 3:
                    _write_crash_alert(filename, seg_start, exc, crash_streak)
                    nxt = next_failed_volume(filename)
                    set_agent_state(
                        status="blocked",
                        phase="crash",
                        last_error=f"excepção repetida {crash_streak}x: {exc}",
                        current_file=nxt,
                        current_segment_index=0,
                        segments_completed=[],
                        crash_streak=0,
                        crash_key=None,
                    )
                    _log(
                        f"ALERTA: Livro {filename} bloqueado — excepção repetida {crash_streak}x "
                        f"no trecho #{seg_start} ({exc}); requer correção de código. "
                        f"Ver reports/acervo_studio/CRASH_ALERTS.jsonl — avançar para: {nxt or '—'}"
                    )
                if once:
                    return 1
                time.sleep(60)
                continue

            if result.get("paused"):
                return 0

            if result.get("ok"):
                completed = st.get("volumes_completed") or []
                if filename not in completed:
                    completed.append(filename)
                nxt = next_failed_volume(filename)
                set_agent_state(
                    volumes_completed=completed,
                    current_file=nxt,
                    current_segment_index=0,
                    segments_completed=[],
                    phase=None,
                    status="running" if nxt else "idle",
                    last_error=None,
                )
                _log(f"LIVRO FECHADO: {filename} → próximo: {nxt or '—'}")
                if once:
                    return 0
                time.sleep(5)
            else:
                set_agent_state(status="blocked", phase="gate", last_error="gate FAIL")
                _log(f"Livro {filename} bloqueado no gate — reprocessar trechos com problemas")
                from goshinsho.services.acervo_studio_service import (  # noqa: WPS433
                    first_pending_segment_index,
                    recompute_segments_completed_from_disk,
                )

                set_agent_state(
                    current_segment_index=first_pending_segment_index(filename),
                    segments_completed=recompute_segments_completed_from_disk(filename),
                )
                if once:
                    return 1
                time.sleep(120)

    except KeyboardInterrupt:
        _log("Interrompido")
        return 0
    finally:
        release_lock()


def main() -> int:
    p = argparse.ArgumentParser(description="Acervo Studio agent")
    p.add_argument("--once", action="store_true", help="Uma iteração (um trecho ou gate)")
    p.add_argument("--continuous", action="store_true", default=True)
    p.add_argument("--no-continuous", action="store_true", help="Processar livro inteiro de uma vez")
    p.add_argument("--file", help="Volume específico")
    p.add_argument("--segment", type=int, default=-1, help="Trecho específico")
    p.add_argument("--pause", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--stop", action="store_true")
    args = p.parse_args()

    if args.stop or args.pause:
        set_agent_state(paused=True, status="paused")
        pid = agent_state().get("pid")
        if pid and _pid_alive(int(pid)):
            try:
                os.kill(int(pid), 15)
            except OSError:
                pass
        release_lock()
        _log("Agente parado")
        return 0

    continuous = not args.no_continuous
    if args.file:
        set_agent_state(current_file=args.file, paused=False, continuous=continuous)
    if args.resume:
        set_agent_state(paused=False, continuous=continuous)

    if args.segment >= 0 and args.file:
        if not acquire_lock():
            return 1
        try:
            process_segment(args.file, args.segment)
            return 0
        finally:
            release_lock()

    if args.file and not args.resume:
        set_agent_state(current_segment_index=0)
        r = process_volume_segments(args.file, translate=True)
        return 0 if r.get("ok") else 1

    return run_continuous_loop(once=args.once)


if __name__ == "__main__":
    raise SystemExit(main())
