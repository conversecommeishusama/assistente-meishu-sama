#!/usr/bin/env python3
"""Executor semântico (reescrita localizada) da revisão literária — DeepSeek.

Versão de produção do teste validado (2026-08-18): em vez de pedir a
reescrita integral do chunk (que introduzia perda de conteúdo e inflação de
quantificador em ~57% dos achados do auditor), este executor pede ao DeepSeek
EDIÇÕES LOCALIZADAS — cada uma com trecho `de` (literal, deve existir) e `para`
(nova versão), aplicadas com validação de âncora e backup. O texto que já está
bom permanece intocado.

Mesmo contrato do executor integral: processa `pending[0]` da fila, lê o
chunk `*_src.txt`, aplica as edições, grava `*_out.txt`, move para `done`.

Segurança:
- cada edição: `de` DEVE existir literalmente e ser ÚNICO (senão rejeitada)
- backup automático do _out.txt existente antes da 1ª gravação
- validação de tamanho (ratio 0.5-2.0) e de âncoras de conteúdo
- retry com reforço progressivo (JSON inválido)
- nunca toca fora de revisao_literaria/

Uso:
    python3 revisao_literaria/scripts/processar_chunk_semantico_deepseek.py
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
MAX_TOKENS = 16000
RATIO_MIN = 0.5
RATIO_MAX = 2.0
# Tamanho máximo de chunk enviado por chamada (chunks grandes são divididos)
FATIA_MAX = 12000


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


def _extrair_json(resposta: str) -> dict | None:
    """Extrai um objeto JSON balanceado da resposta (robusto a texto extra)."""
    m = re.search(r"\{.*\}", resposta, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _pedir_edicoes(texto: str, protocolo: str) -> list[dict]:
    """Chama o DeepSeek pedindo edições localizadas. Retorna lista de {de, para}."""
    prompt = f"""{protocolo}

## Tarefa
Identifique os trechos que merecem revisão literária no texto abaixo e proponha EDIÇÕES LOCALIZADAS.
Regras:
- `de` deve ser um trecho LITERAL EXATO do texto atual.
- `para` é a versão revisada (fluidez/elegância) SEM mudar sentido/fato/nome/número/ordem/citação.
- NÃO reescreva trechos que já estão bons. Só proponha onde há ganho real de fluidez/ritmo/precisão.
- Não altere numeração, nomes próprios, números, datas, citações entre aspas, títulos, divisórias, estrofes.

## Texto atual
{texto}

## Formato de saída (JSON puro, nada mais)
{{"edicoes": [{{"de": "trecho literal exato", "para": "novo texto"}}]}}
Se não houver nada a melhorar, retorne {{"edicoes": []}}."""

    for tentativa in range(3):
        reforco = ""
        if tentativa == 1:
            reforco = "\n\nIMPORTANTE: retorne APENAS o JSON puro, sem markdown, sem texto extra."
        elif tentativa == 2:
            reforco = "\n\nATENÇÃO: resposta anterior inválida. Formato EXATO: {\"edicoes\": [{\"de\": \"...\", \"para\": \"...\"}]}"
        resp = _client().chat.completions.create(
            model=MODELO,
            messages=[{"role": "user", "content": prompt + reforco}],
            temperature=0,
            max_tokens=MAX_TOKENS,
        )
        final = resp.choices[0].message.content or ""
        data = _extrair_json(final)
        if data and isinstance(data.get("edicoes"), list):
            return data["edicoes"]
    return []


def _aplicar_edicoes(texto: str, edicoes: list[dict]) -> tuple[str, list[dict], list[dict]]:
    """Aplica edições com validação de âncora. Retorna (novo_texto, aplicadas, rejeitadas)."""
    novo = texto
    aplicadas = []
    rejeitadas = []
    for ed in edicoes:
        de = str(ed.get("de", "")).strip()
        para = str(ed.get("para", "")).strip()
        if not de or not para:
            continue
        n = novo.count(de)
        if n != 1:
            rejeitadas.append({"de": de[:60], "motivo": f"aparece {n}x (exigido 1x)"})
            continue
        novo = novo.replace(de, para)
        aplicadas.append({"de": de, "para": para})
    return novo, aplicadas, rejeitadas


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

    # Divide em fatias (se chunk > FATIA_MAX) e processa cada uma
    fatias = []
    if len(src_texto) <= FATIA_MAX:
        fatias = [src_texto]
    else:
        atual = ""
        for par in src_texto.split("\n\n"):
            if len(atual) + len(par) + 2 > FATIA_MAX and atual:
                fatias.append(atual)
                atual = par
            else:
                atual = (atual + "\n\n" + par) if atual else par
        if atual:
            fatias.append(atual)

    texto_final = src_texto
    total_aplicadas = 0
    total_rejeitadas = 0

    for fatia in fatias:
        edicoes = _pedir_edicoes(fatia, protocolo)
        # aplica sobre o texto_final (que pode ter mudado por edições anteriores)
        novo, aplicadas, rejeitadas = _aplicar_edicoes(texto_final, edicoes)
        # aplica apenas as que ainda encontram âncora no texto_final atual
        texto_final = novo
        total_aplicadas += len(aplicadas)
        total_rejeitadas += len(rejeitadas)

    # Validação final de tamanho
    ratio = len(texto_final) / len(src_texto) if src_texto else 0
    if not (RATIO_MIN <= ratio <= RATIO_MAX):
        print(f"{_agora()} — FALHA: ratio {ratio:.2f} fora da faixa para {livro} chunk {chunk}")
        return 1

    if texto_final == src_texto and total_aplicadas == 0:
        # nenhuma edição — chunk já está bom, grava igual (sem backup desnecessário)
        print(f"{_agora()} — {livro} chunk {chunk}: nenhuma edição (texto já bom)")
    else:
        if arquivo_out.exists():
            carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            shutil.copy(arquivo_out, arquivo_out.with_suffix(f".txt.bak_semantico_{carimbo}"))
        arquivo_out.parent.mkdir(parents=True, exist_ok=True)
        arquivo_out.write_text(texto_final + "\n", encoding="utf-8")
        print(f"{_agora()} — {livro} chunk {chunk}: {total_aplicadas} edições aplicadas, {total_rejeitadas} rejeitadas")

    # atualizar fila
    item_done = {
        "livro": item["livro"],
        "arquivo": item["arquivo"],
        "chunk": item["chunk"],
        "total_chunks": item["total_chunks"],
        "at": _agora(),
        "nota": f"- processado via executor SEMÂNTICO ({MODELO})\n- {total_aplicadas} edições localizadas, {total_rejeitadas} rejeitadas\n- tamanho: {len(src_texto)} -> {len(texto_final)} chars",
    }
    q["pending"] = q["pending"][1:]
    q.setdefault("done", []).append(item_done)
    _salvar_fila(q)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
