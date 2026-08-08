#!/usr/bin/env python3
"""Sincroniza a fila do auditor externo da JP-2 com a fila do executor da JP-2.

Copia direta do padrao de `sync_fase_f_auditor_queue.py` (Fase F, portugues),
adaptada para os arquivos da JP-2. Roda a cada iteracao do laco
`run_jp2_auditor_loop.sh`, ANTES de invocar o Claude Code -- e deterministico e
nao custa nenhuma chamada de API.

Efeito: todo item que o executor da JP-2 ja marcou como `done` e que o auditor
ainda nao marcou como `done` nem tem em `pending` e adicionado ao final de
`pending` do auditor, para ser conferido de forma independente.

Quando dar por concluido: so quando o executor nao tiver mais nada em
`pending` (terminou de processar os 108 arquivos) E o auditor ja tiver
confirmado (ou reaberto e nao estar mais esperando) tudo que esta em `done` do
executor. Nesse caso o campo `concluido` e marcado `true` na fila do auditor,
e o laco externo encerra.
"""
import sys
import json

EXECUTOR_QUEUE = "reports/livros_trabalho/segmentacao_manual/JP2_VERIFICACAO_ESTRUTURAL_QUEUE.json"
AUDITOR_QUEUE = "reports/livros_trabalho/segmentacao_manual/JP2_AUDITORIA_EXTERNA_QUEUE.json"

# Mesma cautela do script irmao da Fase F: invocacoes stateless independentes
# (chamadas separadas de `claude -p`, sem contexto entre si) podem nao
# convergir no nome do campo que guarda o nome do arquivo em cada entrada de
# `done`. Fallback por substring para nunca lancar excecao aqui -- um crash
# neste script para a sincronizacao inteira silenciosamente (o laco externo
# nao verifica o codigo de saida do presync).
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
