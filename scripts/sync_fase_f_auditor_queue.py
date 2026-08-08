#!/usr/bin/env python3
"""Sincroniza a fila do auditor externo com a fila do executor (Fase F).

Roda a cada iteração do laço `run_fase_f_auditor_loop.sh`, ANTES de invocar o
Claude Code — é determinístico e não custa nenhuma chamada de API.

Efeito: todo item que o executor já marcou como `done` e que o auditor ainda
não marcou como `done` nem tem em `pending` é adicionado ao final de
`pending` do auditor, para ser conferido de forma independente.

Quando dar por concluído: só quando o executor não tiver mais nada em
`pending` (terminou de processar os 128 arquivos) E o auditor já tiver
confirmado (ou reaberto e não estar mais esperando) tudo que está em
`done` do executor. Nesse caso o campo `concluido` é marcado `true` na fila
do auditor, e o laço externo encerra.
"""
import sys
import json

EXECUTOR_QUEUE = "reports/livros_trabalho/segmentacao_manual/FASE_F_VERIFICACAO_RIGOROSA_QUEUE.json"
AUDITOR_QUEUE = "reports/livros_trabalho/segmentacao_manual/FASE_F_AUDITORIA_EXTERNA_QUEUE.json"

# As invocacoes stateless do executor (chamadas independentes de claude -p,
# sem contexto entre si) nao convergiram no nome do campo que guarda o nome
# do arquivo em cada entrada de `done` -- ja apareceram 'ficheiro', 'file',
# 'filename' e 'arquivo' no mesmo array, e provavelmente mais variantes vao
# aparecer (cada invocacao nova pode inventar uma diferente). Por isso, alem
# das chaves conhecidas, ha um fallback por substring nunca lancar excecao
# aqui -- um crash neste script para a sincronizacao inteira silenciosamente
# (o laco externo nao verifica o codigo de saida do presync), entao e melhor
# logar um aviso e pular a entrada do que travar tudo (ja aconteceu uma vez:
# 2026-07-11, chave 'arquivo' nao reconhecida, sync parado por horas).
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
