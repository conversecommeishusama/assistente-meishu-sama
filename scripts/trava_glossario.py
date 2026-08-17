#!/usr/bin/env python3
"""TRAVA DETERMINÍSTICA DE GLOSSÁRIO — verifica se o PT usa a forma fixada.

Papel 2 da arquitetura (Claude): depois de cada turno traduzido, verifica
automaticamente contra a lista de termos fixos. Se o JP contém um termo fixo
mas o PT NÃO contém a forma aprovada → o turno é REJEITADO (retorna False),
para ser devolvido ao DeepSeek antes de chegar a qualquer auditor.

Isso elimina os erros de glossário (25 casos no relatório do Claude) sem gastar
uma única leitura semântica.

Uso:
    from trava_glossario import verificar_trava_glossario
    ok, motivo = verificar_trava_glossario(jp, pt)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GLOSSARIO = RAIZ / "glossario_traducao.json"

# Termos fixos críticos que SEMPRE devem ter a forma aprovada no PT.
# (retirados do relatório do Claude — os que falharam nos dois textos)
TERMOS_FIXOS = {
    # (termo_jp, forma_pt_aprovada_ou_alternativas)
    "信者": ("fiel", "fiéis"),
    "信者たち": ("fiéis",),
    "信徒": ("fiel", "fiéis"),
    "邪神": ("divindade maligna", "divindades malignas", "divindade(s) maligna(s)"),
    "邪霊": ("espírito maligno", "espíritos malignos"),
    "御守り": ("Ohikari",),
    "御軸": ("Imagem da Luz Divina",),
    "五六七": ("Miroku",),
    "大清算": ("Grande Acerto de Contas",),
    "大浄化": ("Grande Purificação",),
    "土人": ("povos originários", "povos primitivos"),
    "ニグロ的": ("de caráter negro", "caráter negro"),
    "ニグロ": ("negro",),
    "野蛮人": ("povos primitivos", "povos originários"),
    "野蛮人的趣味": ("gosto primitivo", "gosto dos povos primitivos", "gosto dos povos originários"),
    "大光明如来": ("Daikōmyō Nyorai", "Daikomyo Nyorai"),
    "光明如来様": ("Kōmyō Nyorai", "Komyo Nyorai"),
    # Amuletos (御守り) — carregados no pescoço; distintos das imagens (如来)
    "大光明の御守り": ("Ohikari Daikōmyō", "Daikōmyō", "Daikomyo"),
    "光明の御守り": ("Ohikari Kōmyō", "Kōmyō", "Komyo"),
    "大光明": ("Daikōmyō", "Daikomyo", "Ohikari Daikōmyō"),
    "光明": ("Kōmyō", "Komyo", "Ohikari Kōmyō"),
    "茂吉": ("Mokichi",),
    "金神": ("Konjin",),
    "御浄化": ("purificação pessoal",),
    "三宝": ("Sanpō", "bandeja ritual"),
    "御木徳一": ("Miki Tokuichi",),
    # ---- Ampliação 2026-08-15 (diagnóstico da auditoria do lote 1) ----
    # Termos que a auditoria apontou como erro de glossário e que NÃO estavam
    # cobertos antes (o tradutor os vertia errado e a trava não pegava).
    "大先生": ("Grão-Mestre",),
    "善言讃詞": ("Oração Zengen-Sandji", "Zengen-Sandji", "Zengen Sandji"),
    "ミロクロッジ": ("Miroku Lodge",),
    "審神者": ("médium",),
    "生霊": ("espírito de pessoa viva",),
    "御神体": ("Imagem da Luz Divina",),
    "御額": ("caligrafia",),
    "光明如来": ("Kōmyō Nyorai", "Komyo Nyorai", "Komyo-Nyorai"),
    # ---- Ampliação 2026-08-17 (auditoria do lote 2) ----
    # Termos que a auditoria apontou e que faltavam na trava. Inclui variações
    # de grafia JP (伊都能売大神 sem 之) que o texto usa e o glossário não cobre
    # literalmente, e termos cuja forma canónica tem nota editorial longa.
    "伊都能売大神": ("Izunome", "Izunome-Ōkami", "Izunome-Ōmikami"),
    "伊都能売之大御神": ("Izunome-Ōmikami", "Izunome"),
    "教導師": ("Ministro Responsável", "Ministro Responsável de Unidade Religiosa"),
    "教導師補": ("Ministro Responsável Assistente", "Ministro Responsável de Unidade Religiosa Assistente"),
    "大光明如来様": ("Daikōmyō Nyorai", "Daikomyo Nyorai"),
    "大光明如来": ("Daikōmyō Nyorai", "Daikomyo Nyorai"),
}


def carregar_glossario() -> dict:
    try:
        return json.loads(GLOSSARIO.read_text(encoding="utf-8"))
    except Exception:
        return {}


def verificar_trava_glossario(jp: str, pt: str) -> tuple[bool, str]:
    """Verifica se o PT usa a forma fixada para cada termo JP presente.

    Regra (2026-08-17, pedido do usuário): além do TERMOS_FIXOS (críticos, com
    alternativas), verifica TODO o glossário de tradução (glossario_traducao.json,
    730 termos). Se um termo JP do glossário estiver no texto e o PT não usar a
    forma canónica, REJEITA (retorna False, motivo) para devolver ao executor.

    Retorna (True, "") se OK; (False, motivo) se um termo precisa ser corrigido.
    """
    if not jp or not pt:
        return False, "JP ou PT vazio"

    glossario = carregar_glossario()
    if not glossario:
        # sem glossário em disco: só usa TERMOS_FIXOS
        glossario = {}

    # 1) TERMOS_FIXOS primeiro (prioridade, com alternativas explícitas)
    for termo_jp, formas in TERMOS_FIXOS.items():
        if termo_jp not in jp:
            continue  # termo não está neste turno

        # verifica se alguma forma aprovada aparece no PT (case-insensitive)
        encontrado = False
        for forma in formas:
            if re.search(re.escape(forma), pt, re.IGNORECASE):
                encontrado = True
                break
        if not encontrado:
            # tenta a forma do glossário como fallback
            forma_glossario = glossario.get(termo_jp, "")
            if forma_glossario and re.search(re.escape(forma_glossario), pt, re.IGNORECASE):
                encontrado = True
        if not encontrado:
            return False, f"termo '{termo_jp}' no JP, mas PT não usa forma aprovada: {formas}"

    # 2) GLOSSÁRIO COMPLETO (todos os 730 termos do glossario_traducao.json)
    #    — se o termo JP aparece no texto, o PT DEVE conter a forma canónica.
    #    Ignora termos que já foram validados em TERMOS_FIXOS acima (evita
    #    duplicar motivo; TERMOS_FIXOS já é mais permissivo com alternativas).
    #    Também ignora formas canónicas com NOTA EDITORIAL (parênteses/aspas/
    #    "—"/"na 1ª menção"), pois essas não são a forma literal única a exigir
    #    (ex.: 教導師 → "Ministro Responsável de Unidade Religiosa (na 1ª menção...)").
    for termo_jp, forma_canonica in glossario.items():
        if termo_jp in TERMOS_FIXOS:
            continue  # já verificado acima
        if not forma_canonica or not isinstance(forma_canonica, str):
            continue
        if termo_jp not in jp:
            continue  # termo não está neste turno
        # pula formas com nota editorial (não são a forma literal única)
        if any(c in forma_canonica for c in ("(", ")", "—", "・", "na ", "em ", "abreviada", "ou ")):
            continue
        # normaliza acentuação/macrons para comparação tolerante:
        # Kōmyō/Komyo, Daikōmyō/Daikomyo, etc.
        pt_norm = re.sub(r"[ōōŌŌ]", "o", pt)
        forma_norm = re.sub(r"[ōōŌŌ]", "o", forma_canonica)
        if re.search(re.escape(forma_norm), pt_norm, re.IGNORECASE):
            continue  # forma canónica presente no PT (tolerante a macron) — OK
        return False, (
            f"termo '{termo_jp}' no JP, mas PT não usa a forma canónica do "
            f"glossário: '{forma_canonica}'"
        )

    return True, ""


def relatorio_glossario(jp: str, pt: str) -> list[dict]:
    """Relatório COMPLETO de termos do glossário que não estão na forma canónica.

    Diferente de `verificar_trava_glossario` (que para no primeiro erro), esta
    função lista TODOS os termos JP presentes no texto cujo PT não usa a forma
    aprovada — para correção PONTUAL (substituição determinística), sem
    re-tradução nem loop.

    Retorna lista de dicts: {"termo_jp", "formas", "ocorrencias"} onde
    "formas" são as formas aprovadas (do TERMOS_FIXOS ou do glossário).
    """
    if not jp or not pt:
        return []

    glossario = carregar_glossario()
    relatorio: list[dict] = []

    def _formas_do(termo_jp: str) -> tuple[str, ...]:
        if termo_jp in TERMOS_FIXOS:
            return TERMOS_FIXOS[termo_jp]
        v = glossario.get(termo_jp, "")
        if isinstance(v, str) and v and not any(c in v for c in ("(", ")", "—", "・", "na ", "em ", "abreviada", "ou ")):
            return (v,)
        return ()

    for termo_jp, formas in TERMOS_FIXOS.items():
        if termo_jp not in jp:
            continue
        encontrado = any(re.search(re.escape(f), pt, re.IGNORECASE) for f in formas)
        if not encontrado:
            fg = glossario.get(termo_jp, "")
            if fg and re.search(re.escape(fg), pt, re.IGNORECASE):
                encontrado = True
        if not encontrado:
            relatorio.append({
                "termo_jp": termo_jp,
                "formas": list(formas),
                "ocorrencias": jp.count(termo_jp),
            })

    for termo_jp, forma_canonica in glossario.items():
        if termo_jp in TERMOS_FIXOS:
            continue
        if not isinstance(forma_canonica, str) or not forma_canonica:
            continue
        if any(c in forma_canonica for c in ("(", ")", "—", "・", "na ", "em ", "abreviada", "ou ")):
            continue
        if termo_jp not in jp:
            continue
        pt_norm = re.sub(r"[ōōŌŌ]", "o", pt)
        forma_norm = re.sub(r"[ōōŌŌ]", "o", forma_canonica)
        if re.search(re.escape(forma_norm), pt_norm, re.IGNORECASE):
            continue
        relatorio.append({
            "termo_jp": termo_jp,
            "formas": [forma_canonica],
            "ocorrencias": jp.count(termo_jp),
        })

    return relatorio


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        jp_arg = sys.argv[1]
        pt_arg = sys.argv[2]
        ok, motivo = verificar_trava_glossario(jp_arg, pt_arg)
        print(f"OK: {ok}" if ok else f"REJEITADO: {motivo}")
    else:
        # autoteste
        print("=== Autoteste da trava de glossário ===")
        ok, m = verificar_trava_glossario("信者が来た", "O fiel veio")
        print(f"1. 信者→fiel: {'✅' if ok else f'❌ {m}'}")
        ok, m = verificar_trava_glossario("信者が来た", "O crente veio")
        print(f"2. 信者→crente (deve REJEITAR): {'✅ rejeitou' if not ok else '❌ passou'}")
        ok, m = verificar_trava_glossario("御守りを頂いた", "Recebi o Ohikari")
        print(f"3. 御守り→Ohikari: {'✅' if ok else f'❌ {m}'}")
        ok, m = verificar_trava_glossario("大清算が始まる", "A Grande Purificação começa")
        print(f"4. 大清算→Grande Purificação (deve REJEITAR): {'✅ rejeitou' if not ok else '❌ passou'}")
        ok, m = verificar_trava_glossario("大清算が始まる", "O Grande Acerto de Contas começa")
        print(f"5. 大清算→Grande Acerto: {'✅' if ok else f'❌ {m}'}")
