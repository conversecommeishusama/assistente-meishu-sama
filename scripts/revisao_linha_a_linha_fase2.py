#!/usr/bin/env python3
"""Fase 2: revisão linha a linha semântica de cabeçalhos internos + citações.

Para CADA obra (137), com DeepSeek (JP vs PT):
1. Analisa o CABEÇALHO INTERNO (1ª linha) — deve refletir o nome aprovado,
   PRESERVANDO a data quando existir.
2. Analisa as CITAÇÕES de publicações no corpo (Shinkō Zatsuwa -> "Conversas
   sobre a Fé", etc.) — decide caso a caso se ajusta.
3. Aplica com segurança: backup + valida_ancoras + fonte==staging.
4. Grava checkpoint (resumível) — se cair, retoma de onde parou.

Não automatiza decisões: cada caso é julgado pelo modelo com o JP como base.
Uso:
    python3 scripts/revisao_linha_a_linha_fase2.py [--aplicar] [--max OBRAS]
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import mescla_e_aplica as me
from goshinsho.services import agentic_search as ag

PT = RAIZ / "reports/livros_trabalho/pt"
REV = RAIZ / "livros_publicacao_pt_revisado"
JP = RAIZ / "reports/livros_trabalho/jp"
SPEC = RAIZ / "reports/livros_trabalho/segmentacao_manual"
CKPT_PATH = RAIZ / "reports/varredura_padronizacao" / "FASE2_CKPT.json"
MAPA_PATH = RAIZ / "reports/varredura_padronizacao" / "MAPEAMENTO_RENOMEACAO_TXT.json"

MODELO = "deepseek-v4-flash"
MAX_TOKENS = 6000

SYSTEM = """Você é um revisor editorial do corpus Goshinsho (textos de Meishu-Sama),
especialista em japonês e português. Seu trabalho é LINHA A LINHA, SEMÂNTICO,
um arquivo por vez.

Você recebe:
1. O NOME DE ARQUIVO APROVADO (padrão da coleção, já decidido pelo editor).
2. O CABEÇALHO INTERNO atual (1ª linha do arquivo PT).
3. O COMEÇO do texto em português (primeiras ~1500 chars).
4. O COMEÇO do texto em japonês correspondente.

TAREFA:
A. CABEÇALHO INTERNO: decida se o cabeçalho interno atual deve ser ajustado
   para refletir o nome de arquivo aprovado. REGRAS:
   - Se o cabeçalho já reflete o nome aprovado (igual ou muito próximo), SEM_ACAO.
   - Se o cabeçalho usa versão antiga do nome (ex: 'Shinkō Zatsuwa' vs
     'Conversas sobre a Fé', 'Curso de Kannon' vs 'Curso Kannon',
     'Gokowa-roku no 1' vs 'Gokōwa-roku nº 1', 'Coletânea de Hinos' vs
     'Coletânea de Salmos'), proponha o ajuste para o nome aprovado.
   - PRESERVE a data quando existir (ex: 'publicado em 1º de julho de 1948',
     'Shōwa 24 (1949)', '24 de dezembro de 1949').
   - NÃO mude o título se for um TÍTULO EDITORIAL rico (ex: 'A Revolucionária
     Terapia da Tuberculose') que já é a tradução correta do original — aí
     apenas confirme SEM_ACAO, a menos que contenha nome de série errado.
B. CITAÇÕES DE PUBLICAÇÕES no corpo: verifique se as citações de obras do
   acervo usam o nome padrão aprovado. Troque nomes antigos (ex: 'Shinkō
   Zatsuwa' -> 'Conversas sobre a Fé'). Não altere nomes de periódicos
   (Tijotengoku, Hikari, Kyusei, Mugen, Eiko) que são transliterações.
   Liste as substituições necessárias (máx 5 para exemplificar).

Responda em JSON:
{
  "resultado": "APLICADO" | "SEM_ACAO" | "DUVIDA",
  "cabecalho_novo": "novo cabeçalho interno (se APLICADO; preservando data)",
  "substituicoes_corpo": ["de1 -> para1", "de2 -> para2"],
  "justificativa": "explicação curta"
}
Responda APENAS o JSON (sem markdown)."""


def _client():
    return ag._client()


def _texto(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _primeira_linha(t: str) -> str:
    for l in t.split("\n"):
        if l.strip():
            return l.strip()
    return ""


# Padrões de citações de publicações no corpo (nome antigo -> nome aprovado)
SUBSTITUICOES_PADRAO = [
    # Shinkō Zatsuwa / Shinko Zatsuwa -> Conversas sobre a Fé
    ("Shinkō Zatsuwa", "Conversas sobre a Fé"),
    ("Shinko Zatsuwa", "Conversas sobre a Fé"),
    ("Shinkō-Zatsuwa", "Conversas sobre a Fé"),
]


def _varre_citacoes(t: str) -> list[str]:
    """Varre o corpo inteiro e lista citações de publicações com nome antigo."""
    achados = []
    for de, para in SUBSTITUICOES_PADRAO:
        n = t.count(de)
        if n:
            achados.append((de, para, n))
    return achados


def _aplica_citacoes(t: str) -> tuple[str, list[str]]:
    """Aplica as substituições de nomes antigos no corpo. Retorna (novo_texto, substituicoes)."""
    novo = t
    substituidas = []
    for de, para in SUBSTITUICOES_PADRAO:
        if de in novo:
            n = novo.count(de)
            novo = novo.replace(de, para)
            substituidas.append(f"{de} -> {para} ({n}x)")
    return novo, substituidas


def revisar_obra(obra_antiga: str, obra_nova: str, aplicar: bool, ja_backup: set) -> dict:
    """Revisa cabeçalho interno + citações de uma obra."""
    t_pt = _texto(PT / obra_nova)
    t_jp = _texto(JP / obra_antiga)
    if not t_pt:
        return {"obra": obra_nova, "resultado": "ERRO", "nota": "PT ausente"}

    cabecalho = _primeira_linha(t_pt)
    inicio_pt = t_pt[:1500]
    inicio_jp = t_jp[:1500] if t_jp else "(JP ausente)"

    # Varredura completa das citações no corpo
    citacoes = _varre_citacoes(t_pt)
    citacoes_txt = "\n".join(f"  - '{de}' ({n}x) -> deveria ser '{para}'" for de, para, n in citacoes) or "  (nenhuma citação de obra com nome antigo encontrada)"

    user_msg = (
        f"ARQUIVO: {obra_nova}\n"
        f"NOME APROVADO: {obra_nova.replace('.txt','')}\n\n"
        f"=== CABEÇALHO INTERNO ATUAL ===\n{cabecalho}\n\n"
        f"=== INÍCIO DO TEXTO PT ===\n{inicio_pt}\n\n"
        f"=== INÍCIO DO TEXTO JP ===\n{inicio_jp}\n\n"
        f"=== CITAÇÕES DE PUBLICAÇÕES NO CORPO (nome antigo) ===\n{citacoes_txt}\n\n"
        "Decida (A) cabeçalho e (B) citações no corpo, e responda o JSON. "
        "Para (B), se as citações listadas usam nome antigo, confirme a substituição "
        "para o nome aprovado (será aplicada em todo o corpo)."
    )

    resp = None
    final = ""
    for tentativa in range(3):
        reforco = ""
        if tentativa == 1:
            reforco = "\n\nResponda APENAS o JSON puro, sem markdown, sem ```json, sem texto extra."
        elif tentativa == 2:
            reforco = "\n\nResposta inválida. Responda EXATAMENTE: {\"resultado\": \"APLICADO\" ou \"SEM_ACAO\" ou \"DUVIDA\", \"cabecalho_novo\": \"...\", \"substituicoes_corpo\": [...], \"justificativa\": \"...\"}"
        try:
            r = _client().chat.completions.create(
                model=MODELO, max_tokens=MAX_TOKENS,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": user_msg + reforco}],
            )
            final = r.choices[0].message.content or ""
            m = re.search(r'\{.*\}', final, re.S)
            if m:
                d = json.loads(m.group(0))
                if d.get("resultado") in ("APLICADO", "SEM_ACAO", "DUVIDA"):
                    break
            final = ""
        except Exception:
            final = ""
    try:
        m = re.search(r'\{.*\}', final, re.S)
        dec = json.loads(m.group(0)) if m else {}
        res = dec.get("resultado", "DUVIDA")
        cab_novo = dec.get("cabecalho_novo", "")
        subst = dec.get("substituicoes_corpo", [])
        just = dec.get("justificativa", "")
    except Exception:
        res, cab_novo, subst, just = "DUVIDA", "", [], "resposta inválida"

    editou = False
    nota = just
    # há correções de corpo a aplicar mesmo sem mudança de cabeçalho?
    corpo_a_aplicar = bool(citacoes)
    if res == "APLICADO" and (cab_novo or corpo_a_aplicar):
        if not aplicar:
            nota = nota + f" | PROPOSTO cabecalho: {cab_novo[:60] if cab_novo else '(sem mudança de cabeçalho)'}"
        else:
            novo_texto = t_pt
            if cab_novo:
                primeira = _primeira_linha(novo_texto)
                if primeira:
                    novo_texto = novo_texto.replace(primeira, cab_novo, 1)
            # aplicar substituições no corpo (padrão definido, corpo inteiro)
            novo_texto, substituidas = _aplica_citacoes(novo_texto)
            # backup
            carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            if obra_nova not in ja_backup:
                shutil.copy(PT / obra_nova, PT / f"{obra_nova}.bak_fase2_{carimbo}")
                ja_backup.add(obra_nova)
            # valida_ancoras
            try:
                ok, motivo = me.valida_ancoras(obra_nova, novo_texto)
                if not ok:
                    res = "DUVIDA"
                    nota = nota + f" | NÃO APLICADO (âncora): {str(motivo)[:80]}"
                else:
                    (PT / obra_nova).write_text(novo_texto, encoding="utf-8")
                    (REV / obra_nova).write_text(novo_texto, encoding="utf-8")
                    editou = True
                    if cab_novo:
                        nota = nota + f" | APLICADO cabeçalho: {cab_novo[:60]}"
                    if substituidas:
                        nota = nota + " | Corpo: " + "; ".join(substituidas[:3])
                    elif not cab_novo:
                        nota = nota + " | APLICADO (sem mudança de cabeçalho)"
            except Exception as e:
                res = "DUVIDA"
                nota = nota + f" | NÃO APLICADO (erro): {str(e)[:80]}"
    elif res == "APLICADO":
        res = "DUVIDA"
        nota = nota + " | APLICADO sem cabecalho_novo e sem citações no corpo"

    return {"obra": obra_nova, "resultado": res, "nota": nota,
            "cabecalho": cabecalho, "editou": editou, "substituicoes": subst}


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    max_obras = None
    if "--max" in sys.argv:
        max_obras = int(sys.argv[sys.argv.index("--max") + 1])

    mapa = json.loads(MAPA_PATH.read_text(encoding="utf-8"))
    # ordem: por nome novo
    obras = sorted(mapa, key=lambda m: m["novo"])
    if max_obras:
        obras = obras[:max_obras]

    # checkpoint
    feitos = {}
    if CKPT_PATH.exists():
        feitos = json.loads(CKPT_PATH.read_text(encoding="utf-8"))
    print(f"Total: {len(obras)} | já feitos: {len(feitos)}")

    ja_backup: set = set()
    cont = {"aplicado": 0, "sem_acao": 0, "duvida": 0, "erro": 0}
    for m in obras:
        antigo, novo = m["antigo"], m["novo"]
        if novo in feitos:
            continue
        r = revisar_obra(antigo, novo, aplicar, ja_backup)
        feitos[novo] = r
        cont[r["resultado"]] = cont.get(r["resultado"], 0) + 1
        CKPT_PATH.write_text(json.dumps(feitos, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  [{sum(cont.values())}/{len(obras)}] {r['resultado']:9s} {novo}")
        if r["resultado"] != "SEM_ACAO":
            print(f"      {r['nota'][:150]}")

    print(f"\n=== RESUMO ===")
    print(cont)
    print(f"Checkpoint: {CKPT_PATH}")
    if not aplicar:
        print("(modo verificação — use --aplicar para editar)")


if __name__ == "__main__":
    main()
