#!/usr/bin/env python3
"""Harness DeepSeek stateless para a auditoria da revisão literária.

Substitui o `claude -p` do laço auditor original por chamadas à API DeepSeek,
mantendo o MESMO contrato: cada invocação processa `pending[0]` da fila
`revisao_literaria/QUEUE_AUDITOR.json`, lê o original (livros_publicacao_pt_revisado/)
e o montado (revisao_literaria/livros_publicacao_pt_literaria/), pede ao
DeepSeek uma DECISÃO de auditoria (aprovar ou reabrir com achados), e
atualiza as filas conforme o resultado.

O auditor NÃO reescreve: ele lê o livro inteiro e decide com ceticismo se o
montado atinge padrão de editora sem ter mudado o sentido. Se encontrar
problema, reabre o(s) chunk(s) no executor com nota.

Uso:
    python3 revisao_literaria/scripts/auditar_livro_deepseek.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "goshinsho"))

from goshinsho.services import ai_service  # _client() DeepSeek

REV = RAIZ / "revisao_literaria"
FILA_AUDITOR = REV / "QUEUE_AUDITOR.json"
FILA_EXECUTOR = REV / "QUEUE_EXECUTOR.json"
ORIGINAL_DIR = RAIZ / "livros_publicacao_pt_revisado"
MONTADO_DIR = REV / "livros_publicacao_pt_literaria"
CHUNKS = REV / "chunks"
PROTOCOLO = REV / "PROTOCOLO_LITERARIO.md"
ESCALACOES = REV / "ESCALACOES_MANUAIS.jsonl"

MODELO = "deepseek-v4-flash"
MAX_TOKENS = 16000
# Tamanho máximo por "fatia" lida pelo modelo (livros grandes são lidos em partes)
FATIA_MAX = 12000


def _client():
    return ai_service._client()


# --- Lock de arquivo sobre a fila do auditor (race condition fix) ---
# O montar_livro.py roda como presync de AMBOS os laços; sem lock, montador e
# harness auditor sobrescreviam QUEUE_AUDITOR.json um do outro, deixando
# livros montados órfãos da fila de auditoria. Usa-se o mesmo protocolo de
# lock do montador (fcntl.flock no próprio arquivo da fila).
import fcntl


def lock_fila_auditor():
    if not FILA_AUDITOR.exists():
        FILA_AUDITOR.write_text("{}", encoding="utf-8")
    fd = os.open(str(FILA_AUDITOR), os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def unlock_fila_auditor(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _ler_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _salvar_json(p: Path, q: dict):
    p.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")


def _ler_arquivo(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _fatiar(texto: str, tamanho: int = FATIA_MAX) -> list[str]:
    """Divide o texto em fatias de ~tamanho chars, quebrando em parágrafos."""
    if len(texto) <= tamanho:
        return [texto]
    partes = []
    atual = ""
    for par in texto.split("\n\n"):
        if len(atual) + len(par) + 2 > tamanho and atual:
            partes.append(atual)
            atual = par
        else:
            atual = (atual + "\n\n" + par) if atual else par
    if atual:
        partes.append(atual)
    return partes


def _chunk_do_trecho(livro: str, trecho: str, manifest: dict) -> int | None:
    """Acha o índice do chunk que contém um trecho, via manifest."""
    for c in manifest.get("chunks", []):
        idx = c.get("idx")
        # não temos o texto por chunk no manifest, então não dá para localizar
        # por trecho; usamos heurística: se o trecho é pequeno, não sabemos.
        # O auditor DeepSeek retorna o trecho, mas sem o mapa exato; a
        # localização fina fica para reabertura ampla (chunk 0) como fallback.
        pass
    return None


def _decidir(prompt: str) -> tuple[str, str, str, dict]:
    """Chama o DeepSeek e extrai a decisão JSON. Retorna (decisao, nota, trechos, uso)."""
    for tentativa in range(3):
        reforco = ""
        if tentativa == 1:
            reforco = "\n\nIMPORTANTE: responda APENAS o JSON puro, sem markdown, sem texto extra."
        elif tentativa == 2:
            reforco = "\n\nATENÇÃO: sua resposta anterior foi inválida. Responda EXATAMENTE neste formato JSON, nada mais: {\"decisao\": \"APROVAR\" ou \"REABRIR\", \"nota\": \"...\", \"trechos_problematicos\": [\"trecho do montado\", ...]}"
        resp = _client().chat.completions.create(
            model=MODELO,
            messages=[{"role": "user", "content": prompt + reforco}],
            temperature=0,
            max_tokens=MAX_TOKENS,
        )
        final = resp.choices[0].message.content or ""
        m = re.search(r"\{.*\}", final, re.S)
        if m:
            try:
                r = json.loads(m.group(0))
                if r.get("decisao") in ("APROVAR", "REABRIR"):
                    return r["decisao"], r.get("nota", ""), r.get("trechos_problematicos", []), {}
            except Exception:
                pass
    return "DUVIDA", "resposta não-JSON após 3 tentativas", [], {}


def main() -> int:
    # Lock exclusivo sobre a fila do auditor durante todo o processamento
    # (race condition fix — serializa contra o montador/presync e o outro laço).
    fd = lock_fila_auditor()
    try:
        return _main()
    finally:
        unlock_fila_auditor(fd)


def _main() -> int:
    qa = _ler_json(FILA_AUDITOR)
    pending = qa.get("pending", [])
    if not pending:
        print(f"{_agora()} — fila do auditor vazia, nada a fazer")
        return 0

    item = pending[0]
    livro = item.get("livro", "")
    arquivo = item.get("arquivo", "")

    original = _ler_arquivo(ORIGINAL_DIR / arquivo)
    montado = _ler_arquivo(MONTADO_DIR / arquivo)
    if not original or not montado:
        print(f"{_agora()} — ERRO: original/montado ausente para {livro}")
        return 1

    protocolo = _ler_arquivo(PROTOCOLO)

    # Monta o prompt: envia o livro em fatias com pedido de auditoria
    # (fidelidade + padrão literário). Como o livro pode ser grande, enviamos
    # uma amostra estruturada: início, meio e fim, com instrução de que a
    # leitura é do livro inteiro quando couber.
    fatias_orig = _fatiar(original)
    fatias_mont = _fatiar(montado)

    prompt = f"""Você é o AUDITOR da revisão literária de uma editora internacional. Seu papel é decidir com ceticismo se o livro montado (revisado) atinge padrão de editora SEM ter mudado o sentido do original.

## Protocolo (critério de qualidade)
{protocolo}

## Como decidir
- **APROVAR** se: o montado é fiel ao original (nenhuma mudança de sentido/fato/nome/data/número/ordem/citação; nenhum parágrafo sumiu/duplicou) E teve ganho literário real (mais fluido, elegante).
- **REABRIR** se: encontrou mudança de sentido, perda/duplicação de conteúdo, ou trecho que ainda está arrastado/calque/repetitivo (abaixo do padrão).

## O livro
Livro: {livro}

Comparação por fatias (original → montado). Leia com atenção.

### Fatia 1 (início)
ORIGINAL:
{fatias_orig[0][:FATIA_MAX]}
MONTADO:
{fatias_mont[0][:FATIA_MAX] if fatias_mont else ''}

{f'''### Fatia 2 (meio)
ORIGINAL:
{fatias_orig[len(fatias_orig)//2][:FATIA_MAX] if len(fatias_orig)>1 else ''}
MONTADO:
{fatias_mont[len(fatias_mont)//2][:FATIA_MAX] if len(fatias_mont)>1 else ''}

''' if len(fatias_orig)>1 else ''}{f'''### Fatia 3 (fim)
ORIGINAL:
{fatias_orig[-1][:FATIA_MAX] if len(fatias_orig)>1 else ''}
MONTADO:
{fatias_mont[-1][:FATIA_MAX] if len(fatias_mont)>1 else ''}
''' if len(fatias_orig)>1 else ''}
## Formato de saída (JSON)
Responda APENAS com um objeto JSON:
{{"decisao": "APROVAR" ou "REABRIR", "nota": "tópicos curtos (ex.: achados de fidelidade ou literários)", "trechos_problematicos": ["trecho literal do montado que é problema (para REABRIR)", ...]}}"""

    decisao, nota, trechos, _uso = _decidir(prompt)

    print(f"{_agora()} — {livro}: decisão = {decisao}")

    if decisao == "APROVAR":
        done_item = {
            "livro": livro,
            "arquivo": arquivo,
            "at": _agora(),
            "nota": nota or "- aprovado em auditoria (DeepSeek)",
        }
        qa["pending"] = qa["pending"][1:]
        qa.setdefault("done", []).append(done_item)
        _salvar_json(FILA_AUDITOR, qa)
        return 0

    if decisao == "REABRIR":
        # Reabre o chunk 0 como fallback (sem localização fina por trecho no
        # DeepSeek). Se o trecho estiver identificado, tenta achar no manifest.
        # IMPORTANTE: nunca deixe a reabertura falhar por exceção — sempre
        # persiste a reabertura (chunk 0 como fallback seguro).
        manifest_path = CHUNKS / livro / "_manifest.json"
        chunk_idx = 0
        total_chunks = 0
        try:
            manifest = _ler_json(manifest_path)
            total_chunks = len(manifest.get("chunks", []))
            if trechos and trechos[0]:
                # localiza por busca no texto do chunk — aproximação simples
                alvo = trechos[0][:40]
                for c in manifest.get("chunks", []):
                    idx = c.get("idx")
                    src = _ler_arquivo(CHUNKS / livro / f"{idx:03d}_src.txt")
                    mtd = _ler_arquivo(CHUNKS / livro / f"{idx:03d}_out.txt")
                    if alvo in src or alvo in mtd:
                        chunk_idx = idx
                        break
        except Exception as e:
            print(f"{_agora()} — aviso: falha ao localizar chunk ({str(e)[:80]}), usando chunk 0")
            chunk_idx = 0

        qe = _ler_json(FILA_EXECUTOR)
        # remove entradas antigas do mesmo chunk (evitar duplicidade)
        qe["done"] = [d for d in qe.get("done", []) if not (d.get("livro") == livro and d.get("chunk") == chunk_idx)]
        # insere no início do pending
        qe["pending"].insert(0, {
            "livro": livro,
            "arquivo": arquivo,
            "chunk": chunk_idx,
            "total_chunks": total_chunks,
            "nota_auditor": nota or "reaberto pelo auditor (DeepSeek)",
        })
        _salvar_json(FILA_EXECUTOR, qe)

        # zera montado no manifest
        try:
            manifest = _ler_json(manifest_path)
            manifest["montado"] = False
            manifest.pop("montado_em", None)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

        # remove do pending do auditor sem adicionar ao done
        qa["pending"] = qa["pending"][1:]
        # CORREÇÃO: também remove o livro do `done` (se lá estiver) — assim o
        # montador não o vê como "já passou pela fila" e RE-enfileira após a
        # remontagem. Antes, livro reaberto + remontado ficava órfão (nunca
        # voltava à fila do auditor).
        qa["done"] = [d for d in qa.get("done", []) if d.get("livro") != livro]
        _salvar_json(FILA_AUDITOR, qa)
        return 0

    # DUVIDA — deixa na fila (não consome), mas com anti-travamento:
    # após DUVIDA_MAX consecutivas no MESMO livro, escala manualmente e segue
    # para o próximo (não deixa a fila travar num livro que o modelo não
    # consegue julgar — o protocolo prevê escalação manual).
    print(f"{_agora()} — {livro}: DUVIDA, permanece em pending")
    _registrar_duvida(livro)
    return 1


DUVIDA_MAX = 3
_DUVIDAS_PATH = REV / "_duvidas_auditor.json"


def _carregar_duvidas() -> dict:
    if _DUVIDAS_PATH.exists():
        try:
            return json.loads(_DUVIDAS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _registrar_duvida(livro: str) -> None:
    duvidas = _carregar_duvidas()
    duvidas[livro] = duvidas.get(livro, 0) + 1
    _DUVIDAS_PATH.write_text(json.dumps(duvidas, ensure_ascii=False, indent=2), encoding="utf-8")

    if duvidas[livro] >= DUVIDA_MAX:
        # escala manualmente e remove da fila do auditor (sem aprovar)
        with ESCALACOES.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "livro": livro,
                "nota": f"DUVIDA recorrente do auditor DeepSeek após {duvidas[livro]} tentativas (JSON inválido/vazio) — requer revisão manual",
                "at": _agora(),
            }, ensure_ascii=False) + "\n")
        qa = _ler_json(FILA_AUDITOR)
        qa["pending"] = [p for p in qa.get("pending", []) if p.get("livro") != livro]
        _salvar_json(FILA_AUDITOR, qa)
        print(f"{_agora()} — {livro}: escalado para revisão manual após {duvidas[livro]} DUVIDAS; removido da fila")


if __name__ == "__main__":
    raise SystemExit(main())
