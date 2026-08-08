#!/usr/bin/env python3
"""Gera periodicos_glossary_patches.jsonl a partir dos artigos sinalizados."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from audit_translation_glossary import load_translation_glossary, phrase_present  # noqa: E402
from periodicos_traducao_glossary import (  # noqa: E402
    WORK_ROOT,
    audit_article_row,
    collect_articles,
    expanded_candidates,
)

PATCHES_PATH = WORK_ROOT / "periodicos_glossary_patches.jsonl"


def add_patch(patches: list[dict], *, entry_id: str, term: str, jp_gate: str, old: str, new: str, note: str = "") -> None:
    if old == new or not old:
        return
    patches.append(
        {
            "entry_id": entry_id,
            "term": term,
            "jp_gate": jp_gate,
            "old": old,
            "new": new,
            "note": note,
        }
    )


def replace_once(text: str, old: str, new: str) -> tuple[str, bool]:
    if old not in text:
        return text, False
    return text.replace(old, new, 1), True


def fix_article(entry_id: str, jp: str, pt: str, glossary: dict) -> list[dict]:
    patches: list[dict] = []
    body = pt

  # --- 排泄 ---
    if "排泄" in jp:
        subs = [
            ("tentativa do corpo de excretá-la através da diarreia", "tentativa do corpo de promover a excreção através da diarreia"),
            ("tenta ser excretado pela ponta do dedo", "tenta promover a excreção pela ponta do dedo"),
            ("pelo qual o sangue tóxico da cabeça é excretado", "pela qual ocorre a excreção do sangue tóxico da cabeça"),
            ("prestes a ser excretadas", "prestes a passar por excreção"),
            ("eles são excretados de dentro para fora", "eles passam por excreção de dentro para fora"),
            ("estão sendo excretadas", "passam por excreção"),
            ("é excretado pelo ânus", "ocorre a excreção pelo ânus"),
            ("são excretadas junto com a urina", "passam por excreção junto com a urina"),
            ("excrementos de humanos e animais", "produtos de excreção de humanos e animais"),
        ]
        for old, new in subs:
            if old in body:
                add_patch(patches, entry_id=entry_id, term="排泄", jp_gate="排泄", old=old, new=new)

    # --- 教修 ---
    if "教修" in jp and "教修者" not in jp[: jp.find("教修") + 3]:
        pass  # handled below
    if "教修" in jp:
        subs = [
            ("taxas de ensino", "Kyoshu"),
            ("três dias de instrução", "três dias de Kyoshu"),
            ("dias de instrução", "dias de Kyoshu"),
            ("treino espiritual", "Kyoshu"),
            ("desejo de treino espiritual", "desejo de Kyoshu"),
            ("praticantes de instrução religiosa", "praticantes de Kyoshu"),
        ]
        for old, new in subs:
            if old in body:
                add_patch(patches, entry_id=entry_id, term="教修", jp_gate="教修", old=old, new=new)
    if "教修者" in jp:
        if "praticantes de instrução" in body:
            add_patch(
                patches,
                entry_id=entry_id,
                term="教修",
                jp_gate="教修者",
                old="praticantes de instrução",
                new="praticantes de Kyoshu",
            )

    # --- 神霊 (não compostos cobertos à parte) ---
    if "神霊" in jp and "神霊医学" not in jp and "神霊界" not in jp and "理論神霊学" not in jp:
        subs = [
            ("um espírito de divindade habita", "espíritos de divindades habitam"),
            ("o mais elevado espírito de divindade", "os mais elevados espíritos de divindades"),
            ("espíritos das divindades", "espíritos de divindades"),
            ("espírito da divindade", "espírito de divindade"),
            ("poder desse espíritos de divindades", "poder desses espíritos de divindades"),
            ("ciência espiritual", "espíritos de divindades"),
        ]
        for old, new in subs:
            if old in body:
                add_patch(patches, entry_id=entry_id, term="神霊", jp_gate="神霊", old=old, new=new)

    # --- 神霊医学 ---
    if "神霊医学" in jp:
        for old in [
            "Medicina do espíritos de divindades",
            "medicina dos espíritos de divindades",
            "Medicina dos espíritos de divindades",
            "medicina do espíritos de divindades",
        ]:
            if old in body:
                add_patch(
                    patches,
                    entry_id=entry_id,
                    term="神霊医学",
                    jp_gate="神霊医学",
                    old=old,
                    new="Medicina do Espírito Divino",
                )

    # --- 理論神霊学 / 神霊界 ---
    if "理論神霊学" in jp:
        for old in [
            "ciência teórica do espíritos de divindades",
            "ciência teórica dos espíritos de divindades",
        ]:
            if old in body:
                add_patch(
                    patches,
                    entry_id=entry_id,
                    term="理論神霊学",
                    jp_gate="理論神霊学",
                    old=old,
                    new="ciência teórica do espírito divino",
                )
    if "神霊界" in jp:
        for old in [
            "ante-sala do Mundo do espíritos de divindades",
            "Mundo do espíritos de divindades",
        ]:
            if old in body:
                add_patch(
                    patches,
                    entry_id=entry_id,
                    term="神霊界",
                    jp_gate="神霊界",
                    old=old,
                    new="ante-sala do Mundo do espírito divino" if "ante-sala" in old else "Mundo do espírito divino",
                )

    # --- 大本教 ---
    if "大本教" in jp:
        subs = [
            ("Quando me converti à nossa Igreja", "Quando me converti à religião Oomoto", "大本教へ入信"),
            ("fui à nossa Igreja", "fui à religião Oomoto"),
            ("a nossa Igreja Omoto", "a religião Oomoto"),
            ("Igreja Oomoto", "religião Oomoto"),
            ("da Igreja Tenrikyo", "da religião Oomoto"),  # careful - only if wrong context
        ]
        for item in subs:
            if len(item) == 3:
                old, new, gate = item
            else:
                old, new = item
                gate = "大本教"
            if old in body and gate in jp:
                add_patch(patches, entry_id=entry_id, term="大本教", jp_gate=gate, old=old, new=new)

    # --- 本守護神 ---
    if "本守護神" in jp:
        subs = [
            ("comandante do bem absoluto é o espírito protetor da nossa Igreja", "comandante do bem absoluto é o espírito protetor primordial"),
            ("aumentar o poder do espírito protetor da nossa Igreja", "aumentar o poder do espírito protetor primordial"),
            ("espírito protetor supremo", "espírito protetor primordial"),
        ]
        for old, new in subs:
            if old in body:
                add_patch(patches, entry_id=entry_id, term="本守護神", jp_gate="本守護神", old=old, new=new)

    # --- 地上天国 ---
    if "地上天国" in jp:
        if "Paraísos na Terra" in body:
            add_patch(patches, entry_id=entry_id, term="地上天国", jp_gate="地上天国", old="Paraísos na Terra", new="Paraíso na Terra")
        if "paraísos na terra" in body:
            add_patch(patches, entry_id=entry_id, term="地上天国", jp_gate="地上天国", old="paraísos na terra", new="Paraíso na Terra")

    # --- 天国 (天国的 etc.) ---
    if "天国" in jp and "地上天国" not in jp:
        if "era de cultura paradisíaca" in body:
            add_patch(
                patches,
                entry_id=entry_id,
                term="天国",
                jp_gate="天国的",
                old="era de cultura paradisíaca",
                new="era de cultura do Paraíso",
            )
        if "este mundo é o Paraíso" in body and "天国的" not in jp:
            pass
        if "Paraíso neste mundo" in body:
            pass  # already has Paraíso

    # --- 米国 / 英国 ---
    if "米国" in jp:
        if "à moda americana" in body:
            add_patch(patches, entry_id=entry_id, term="米国", jp_gate="米国", old="à moda americana", new="dos Estados Unidos")
        if "americanos" in body and "Estados Unidos" not in body:
            # only if 米国人 etc in jp
            if "米国人" in jp:
                add_patch(patches, entry_id=entry_id, term="米国", jp_gate="米国人", old="americanos", new="norte-americanos dos Estados Unidos")

    if "英国" in jp:
        if "à moda inglesa" in body:
            add_patch(patches, entry_id=entry_id, term="英国", jp_gate="英国", old="à moda inglesa", new="da Inglaterra")

    # --- 生霊 ---
    if "生霊" in jp:
        if "espíritos de pessoas vivas" in body:
            add_patch(
                patches,
                entry_id=entry_id,
                term="生霊",
                jp_gate="生霊",
                old="espíritos de pessoas vivas",
                new="espíritos de pessoa viva",
            )
        if "milhões de espíritos de pessoa viva" in body:
            add_patch(
                patches,
                entry_id=entry_id,
                term="生霊",
                jp_gate="生霊",
                old="milhões de espíritos de pessoa viva",
                new="milhões de espíritos de pessoas vivas",
            )

    # --- 憑依 ---
    if "憑依" in jp:
        subs = [
            ("possessão demoníaca", "possessão espiritual"),
            ("possuído por demônios", "possuído por encosto"),
            ("apossam dos seres humanos", "exercem possessão espiritual sobre os seres humanos"),
            ("está possuído por uma divindade maligna", "está sob possessão espiritual de uma divindade maligna"),
        ]
        for old, new in subs:
            if old in body:
                add_patch(patches, entry_id=entry_id, term="憑依", jp_gate="憑依", old=old, new=new)

    # --- 道理 ---
    if "道理" in jp:
        subs = [
            ("a verdade clara", "o Caminho Perfeito"),
            ("razão evidente", "Caminho Perfeito"),
            ("a razão evidente", "o Caminho Perfeito"),
        ]
        for old, new in subs:
            if old in body:
                add_patch(patches, entry_id=entry_id, term="道理", jp_gate="道理", old=old, new=new)

    # --- 主神の経綸 ---
    if "主神の経綸" in jp:
        if "Plano Divino de Deus" in body:
            add_patch(
                patches,
                entry_id=entry_id,
                term="主神の経綸",
                jp_gate="主神",
                old="Plano Divino de Deus",
                new="desígnio do Deus Supremo",
            )
        if "Plano Divino" in body and "desígnio do Deus Supremo" not in body:
            add_patch(
                patches,
                entry_id=entry_id,
                term="主神の経綸",
                jp_gate="経綸",
                old="Plano Divino",
                new="desígnio do Deus Supremo",
            )

    return patches


def main() -> int:
    glossary = load_translation_glossary()
    all_patches: list[dict] = []
    seen: set[tuple] = set()

    for row in collect_articles():
        audit = audit_article_row(row, glossary)
        if audit["ok"]:
            continue
        eid = audit["entry_id"]
        jp = row["jp_art"].meta + "\n" + row["jp_art"].content
        pt = row["pt_art"].content
        for p in fix_article(eid, jp, pt, glossary):
            key = (p["entry_id"], p["old"], p["new"])
            if key not in seen:
                seen.add(key)
                all_patches.append(p)

    PATCHES_PATH.write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in all_patches) + ("\n" if all_patches else ""),
        encoding="utf-8",
    )
    print(f"wrote {len(all_patches)} patches to {PATCHES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
