#!/usr/bin/env python3
"""Sincroniza a fila do auditor externo da Revisao Editorial com a fila do
executor. Mesmo padrao de sync_chunk_turnaware_auditor_queue.py /
sync_fase_g_periodicos_auditor_queue_{a,b}.py, com uma correcao adicional
(2026-07-20): o script original so ADICIONA itens novos ao pending do
auditor, nunca remove -- quando um item e reaberto (removido de done do
executor), ele fica preso em pending do auditor pra sempre ate o executor
reprocessar, e cada invocacao do auditor via bater no MESMO item reaberto
sem nada novo pra auditar (bug real, documentado varias vezes em
PENDENCIAS_REVISAO.json nas filas irmas desta, nunca corrigido la). Aqui:
tambem remove de pending do auditor qualquer nome que nao esteja mais em
done do executor (foi reaberto, aguardando o executor de novo) -- ele volta
sozinho a pending do auditor assim que o executor marcar done de novo.
"""
import sys
import json

EXECUTOR_QUEUE = sys.argv[1] if len(sys.argv) > 1 else "reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_QUEUE.json"
AUDITOR_QUEUE = sys.argv[2] if len(sys.argv) > 2 else "reports/livros_trabalho/segmentacao_manual/REVISAO_EDITORIAL_AUDITORIA_EXTERNA_QUEUE.json"

_FILENAME_KEYS = ("ficheiro", "file", "filename", "arquivo")
_FILENAME_KEY_SUBSTRINGS = ("arquiv", "fich", "file", "livro", "book")


def extract_filename(entry):
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        for key in _FILENAME_KEYS:
            if key in entry:
                return entry[key]
        for key in entry:
            lower = key.lower()
            if any(sub in lower for sub in _FILENAME_KEY_SUBSTRINGS):
                value = entry[key]
                if isinstance(value, str) and value.strip():
                    print(f"sync: aviso -- chave de nome de arquivo desconhecida '{key}' aceita por fallback de substring: {value!r}", file=sys.stderr)
                    return value
    print(f"sync: aviso -- entrada de done sem campo de nome de arquivo reconhecido, pulando: {entry!r}", file=sys.stderr)
    return None


def main():
    with open(EXECUTOR_QUEUE, encoding="utf-8") as f:
        executor = json.load(f)
    with open(AUDITOR_QUEUE, encoding="utf-8") as f:
        auditor = json.load(f)

    executor_done_names = [n for n in (extract_filename(e) for e in executor.get("done", [])) if n]
    executor_done = set(executor_done_names)
    auditor_done = set(n for n in (extract_filename(e) for e in auditor.get("done", [])) if n)
    auditor_pending = auditor.get("pending", [])
    auditor_pending_set = set(auditor_pending)

    novos = [
        f
        for f in executor_done_names
        if f not in auditor_done and f not in auditor_pending_set
    ]
    if novos:
        print(f"sync: {len(novos)} item(ns) novo(s) do executor adicionado(s) a pending do auditor: {novos}")
        auditor_pending.extend(novos)

    # 2026-07-20: remove de pending do auditor qualquer item que nao esteja
    # mais em done do executor (foi reaberto -- ver docstring acima).
    obsoletos = [f for f in auditor_pending if f not in executor_done]
    if obsoletos:
        print(f"sync: {len(obsoletos)} item(ns) removido(s) de pending do auditor por nao estarem mais em done do executor (reabertos, aguardando reprocessamento): {obsoletos}")
        auditor_pending = [f for f in auditor_pending if f in executor_done]

    auditor["pending"] = auditor_pending

    executor_finished = len(executor.get("pending", [])) == 0
    auditor_caught_up = executor_done.issubset(auditor_done) and len(auditor["pending"]) == 0
    concluido = executor_finished and auditor_caught_up
    if concluido != auditor.get("concluido", False):
        print(f"sync: campo concluido -> {concluido}")
    auditor["concluido"] = concluido

    with open(AUDITOR_QUEUE, "w", encoding="utf-8") as f:
        json.dump(auditor, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
