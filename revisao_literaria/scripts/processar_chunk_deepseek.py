#!/usr/bin/env python3
"""Harness DeepSeek stateless para a revisão literária (executor).

Substitui o `claude -p` do laço original por chamadas à API DeepSeek,
mantendo o MESMO contrato: cada invocação processa `pending[0]` da fila
`revisao_literaria/QUEUE_EXECUTOR.json`, lê o chunk `*_src.txt`, pede ao
DeepSeek a reescrita literária, valida, grava `*_out.txt` e move o item
para `done`. O estado inteiro vive na fila em disco — o laço pode ser
interrompido e retomado a qualquer momento.

Segurança:
- backup automático do _out.txt existente antes da 1ª gravação
- validação de tamanho (ratio 0.5-2.0) e de âncoras de conteúdo
- retry com reforço progressivo
- nunca toca fora de revisao_literaria/

Uso:
    python3 revisao_literaria/scripts/processar_chunk_deepseek.py
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "goshinsho"))

from goshinsho.services import ai_service  # _client() DeepSeek

REV = RAIZ / "revisao_literaria"
FILA = REV / "QUEUE_EXECUTOR.json"
CHUNKS = REV / "chunks"
PROTOCOLO = REV / "PROTOCOLO_LITERARIO.md"

MODELO = "deepseek-v4-flash"
MAX_TOKENS = 32000
RATIO_MIN = 0.5
RATIO_MAX = 2.0


def _client():
    return ai_service._client()


def _agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _carregar_fila():
    return json.loads(FILA.read_text(encoding="utf-8"))


def _salvar_fila(q):
    FILA.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")


def _ler_arquivo(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _montar_prompt(item: dict, src_texto: str, protocolo: str) -> str:
    """Monta o prompt enxuto para o DeepSeek."""
    livro = item["livro"]
    chunk = item["chunk"]
    contexto = ""
    if chunk > 0:
        ant = CHUNKS / livro / f"{chunk-1:03d}_out.txt"
        if ant.exists():
            txt = _ler_arquivo(ant)
            contexto = txt[-500:]
            contexto = contexto[contexto.rfind("\n") :] if "\n" in contexto else contexto

    ctx_bloco = ""
    if contexto:
        ctx_bloco = f"""
## Contexto (fim do chunk anterior, para tom/terminologia — NÃO reescrever)
{contexto}
"""

    return f"""Você é o revisor literário de uma editora internacional. Sua tarefa é elevar a prosa portuguesa a um padrão de leitura fluida, elegante e agradável, SEM alterar o sentido em nenhum grau.

## Regras de qualidade (obrigatórias)
{protocolo}

{ctx_bloco}## Tarefa desta invocação
Processe APENAS o chunk {chunk} do livro "{livro}".

O texto-fonte é fornecido abaixo entre <<<SRC>>> e <<<FIM_SRC>>>. Reescreva-o aplicando as regras (fluidez, precisão lexical, coesão) sem mudar sentido/fato/nome/data/número/ordem/citação. Preserve cabeçalho (só no chunk 0), divisórias, estrofes, rótulos de diálogo.

<<<SRC>>>
{src_texto}
<<<FIM_SRC>>>

## Formato de saída (CRÍTICO)
Retorne APENAS o texto revisado completo, SEM comentários, SEM justificativas, SEM JSON, SEM markdown. Apenas o texto do novo arquivo, que deve ter tamanho compatível com o original."""


def _chamar_deepseek(prompt: str) -> tuple[str, dict]:
    resp = _client().chat.completions.create(
        model=MODELO,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=MAX_TOKENS,
    )
    usage = {}
    if resp.usage:
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        }
    return resp.choices[0].message.content or "", usage


def _validar(texto_revisado: str, src_texto: str) -> tuple[bool, str]:
    if not texto_revisado:
        return False, "texto revisado vazio"
    ratio = len(texto_revisado) / len(src_texto) if src_texto else 0
    if not (RATIO_MIN <= ratio <= RATIO_MAX):
        return False, f"ratio de tamanho fora da faixa ({ratio:.2f})"
    numeros = re.findall(r"\b\d[\d.,]*\b", src_texto)
    for n in numeros:
        if len(n) > 1 and n not in texto_revisado:
            return False, f"número '{n}' sumiu do texto revisado"
    return True, "ok"


def main() -> int:
    q = _carregar_fila()
    pending = q.get("pending", [])
    if not pending:
        print(f"{_agora()} — pending vazio, nada a fazer")
        return 0

    item = pending[0]
    livro = item["livro"]
    chunk = item["chunk"]
    arquivo_out = CHUNKS / livro / f"{chunk:03d}_out.txt"

    src_texto = _ler_arquivo(CHUNKS / livro / f"{chunk:03d}_src.txt")
    if not src_texto:
        print(f"{_agora()} — ERRO: src vazio para {livro} chunk {chunk}")
        return 1

    protocolo = _ler_arquivo(PROTOCOLO)
    prompt = _montar_prompt(item, src_texto, protocolo)

    final = ""
    for tentativa in range(3):
        reforco = ""
        if tentativa == 1:
            reforco = "\n\nIMPORTANTE: retorne APENAS o texto revisado, sem nenhum comentário ou marcação. Nada além do texto."
        elif tentativa == 2:
            reforco = "\n\nATENÇÃO: sua resposta anterior foi vazia ou inválida. Retorne o texto revisado completo agora, apenas o texto, sem comentários."
        try:
            final, usage = _chamar_deepseek(prompt + reforco)
        except Exception as e:
            print(f"{_agora()} — tentativa {tentativa+1} falhou: {str(e)[:100]}")
            final = ""
            continue
        texto = final.strip()
        if texto:
            ok, motivo = _validar(texto, src_texto)
            if ok:
                break
            print(f"{_agora()} — tentativa {tentativa+1} inválida: {motivo}")
            final = ""
        else:
            print(f"{_agora()} — tentativa {tentativa+1} resposta vazia")
            final = ""

    texto = final.strip()
    if not texto:
        print(f"{_agora()} — FALHA: não foi possível obter texto válido para {livro} chunk {chunk}")
        return 1

    if arquivo_out.exists():
        carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shutil.copy(arquivo_out, arquivo_out.with_suffix(f".txt.bak_deepseek_{carimbo}"))

    arquivo_out.parent.mkdir(parents=True, exist_ok=True)
    arquivo_out.write_text(texto + "\n", encoding="utf-8")

    item_done = {
        "livro": item["livro"],
        "arquivo": item["arquivo"],
        "chunk": item["chunk"],
        "total_chunks": item["total_chunks"],
        "at": _agora(),
        "nota": f"- processado via DeepSeek ({MODELO})\n- tamanho: {len(src_texto)} chars fonte -> {len(texto)} chars revisado",
    }
    q["pending"] = q["pending"][1:]
    q.setdefault("done", []).append(item_done)
    _salvar_fila(q)

    print(f"{_agora()} — OK: {livro} chunk {chunk} processado ({len(src_texto)} -> {len(texto)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
