#!/usr/bin/env python3
"""Comprehensive glossary batch: merges all prior safe/contextual rules plus extensions.

Processes every JP/PT pair (no text limit). Idempotent replacements only.
"""

from __future__ import annotations

import argparse
import re

from apply_confirmed_contextual_glossary_candidates import RULES as CONFIRMED_RULES
from apply_contextual_glossary_fixes import RULES as CONTEXTUAL_RULES
from apply_narrow_contextual_glossary_candidates import RULES as NARROW_RULES
from apply_safe_equivalent_glossary_batch import RULES as BATCH1_RULES
from apply_safe_equivalent_glossary_batch_2 import RULES as BATCH2_RULES
from apply_safe_equivalent_glossary_batch_3 import RULES as BATCH3_RULES
from apply_safe_glossary_fixes import RULES as SAFE_RULES
from glossary_apply_engine import DEFAULT_OUTPUT_DIR, apply_simple_rules, run_glossary_pass


EXTENDED_RULES = (
    # 固結
    type(SAFE_RULES[0])(
        name="kokei_solidificacao_ext",
        japanese_term="固結",
        replacements=(
            (re.compile(r"\bendurecimentos\b", flags=re.IGNORECASE), "solidificações"),
            (re.compile(r"\bendurecimento\b", flags=re.IGNORECASE), "solidificação"),
            (re.compile(r"\bcoagulações\b", flags=re.IGNORECASE), "solidificações"),
            (re.compile(r"\bcoagulação\b", flags=re.IGNORECASE), "solidificação"),
        ),
    ),
    # 霊界
    type(SAFE_RULES[0])(
        name="reikai_mundo",
        japanese_term="霊界",
        replacements=(
            (re.compile(r"\breinos espirituais\b", flags=re.IGNORECASE), "mundos espirituais"),
            (re.compile(r"\breino espiritual\b", flags=re.IGNORECASE), "mundo espiritual"),
            (re.compile(r"\bmundo dos espíritos\b", flags=re.IGNORECASE), "mundo espiritual"),
        ),
    ),
    # 神示
    type(SAFE_RULES[0])(
        name="shinji",
        japanese_term="神示",
        replacements=(
            (re.compile(r"\boráculos divinos\b", flags=re.IGNORECASE), "revelações divinas"),
            (re.compile(r"\boráculo divino\b", flags=re.IGNORECASE), "revelação divina"),
        ),
    ),
    # 善言讃詞
    type(SAFE_RULES[0])(
        name="zengen_sandji",
        japanese_term="善言讃詞",
        replacements=(
            (re.compile(r"\bOração Zengen Sandji\b"), "Oração Zengen-Sandji"),
            (re.compile(r"\bZengen Sandji\b"), "Zengen-Sandji"),
            (re.compile(r"\bOração de Zengen Sandji\b"), "Oração Zengen-Sandji"),
        ),
    ),
    # 水素
    type(SAFE_RULES[0])(
        name="suiso_elemento",
        japanese_term="水素",
        replacements=(
            (re.compile(r"\bhidrogênio\b", flags=re.IGNORECASE), "Elemento Água"),
            (re.compile(r"\bhidrogenio\b", flags=re.IGNORECASE), "Elemento Água"),
        ),
    ),
    # 自観
    type(SAFE_RULES[0])(
        name="jikan",
        japanese_term="自観",
        replacements=(
            (re.compile(r"\bauto-contemplação\b", flags=re.IGNORECASE), "Jikan"),
            (re.compile(r"\bautocontemplação\b", flags=re.IGNORECASE), "Jikan"),
        ),
    ),
    # 堆肥
    type(SAFE_RULES[0])(
        name="taihi",
        japanese_term="堆肥",
        replacements=(
            (re.compile(r"\badubos orgânicos\b", flags=re.IGNORECASE), "compostos naturais"),
            (re.compile(r"\badubo orgânico\b", flags=re.IGNORECASE), "composto natural"),
        ),
    ),
    # 霊体
    type(SAFE_RULES[0])(
        name="reitai",
        japanese_term="霊体",
        replacements=(
            (re.compile(r"\bcorpos astrais\b", flags=re.IGNORECASE), "corpos espirituais"),
            (re.compile(r"\bcorpo astral\b", flags=re.IGNORECASE), "corpo espiritual"),
        ),
    ),
    # 生霊
    type(SAFE_RULES[0])(
        name="seirei",
        japanese_term="生霊",
        replacements=(
            (re.compile(r"\balmas vivas\b", flags=re.IGNORECASE), "espíritos de pessoas vivas"),
            (re.compile(r"\balma viva\b", flags=re.IGNORECASE), "espírito de pessoa viva"),
            (re.compile(r"\bespíritos vivos\b", flags=re.IGNORECASE), "espíritos de pessoas vivas"),
            (re.compile(r"\bespírito vivo\b", flags=re.IGNORECASE), "espírito de pessoa viva"),
        ),
    ),
    # 大先生
    type(SAFE_RULES[0])(
        name="daisesei",
        japanese_term="大先生",
        replacements=((re.compile(r"\bGrande Mestre\b"), "Grão-Mestre"),),
    ),
    # 光明如来 / 様
    type(SAFE_RULES[0])(
        name="komyo_nyorai",
        japanese_term="光明如来",
        replacements=(
            (re.compile(r"\bSenhor Komyo Nyorai\b", flags=re.IGNORECASE), "Komyo-Nyorai"),
            (re.compile(r"\bKomyo Nyorai\b"), "Komyo-Nyorai"),
            (re.compile(r"\bBuda da Luz\b", flags=re.IGNORECASE), "Komyo-Nyorai"),
            (re.compile(r"\bBuda Komyo\b", flags=re.IGNORECASE), "Komyo-Nyorai"),
        ),
    ),
    type(SAFE_RULES[0])(
        name="komyo_nyorai_sama",
        japanese_term="光明如来様",
        replacements=(
            (re.compile(r"\bKomyo Nyorai-Sama\b", flags=re.IGNORECASE), "Komyo-Nyorai"),
            (re.compile(r"\bSenhor Komyo Nyorai\b", flags=re.IGNORECASE), "Komyo-Nyorai"),
            (re.compile(r"\bKomyo Nyorai\b"), "Komyo-Nyorai"),
        ),
    ),
    # お筆先
    type(SAFE_RULES[0])(
        name="ofudesaki",
        japanese_term="お筆先",
        replacements=(
            (re.compile(r"\bO-Fudesaki\b", flags=re.IGNORECASE), "Ofudesaki"),
            (re.compile(r"\bFudesaki\b"), "Ofudesaki"),
        ),
    ),
    # 後頭部
    type(SAFE_RULES[0])(
        name="koto_bu",
        japanese_term="後頭部",
        replacements=(
            (re.compile(r"\bparte posterior da cabeça\b", flags=re.IGNORECASE), "nuca"),
            (re.compile(r"\boccipício\b", flags=re.IGNORECASE), "nuca"),
        ),
    ),
    # 漢方薬
    type(SAFE_RULES[0])(
        name="kampo",
        japanese_term="漢方薬",
        replacements=(
            (re.compile(r"\bremédios da medicina tradicional chinesa\b", flags=re.IGNORECASE), "medicamentos da medicina chinesa"),
            (re.compile(r"\bremédios chineses\b", flags=re.IGNORECASE), "medicamentos da medicina chinesa"),
        ),
    ),
    # 御教え集
    type(SAFE_RULES[0])(
        name="mioshie_shu",
        japanese_term="御教え集",
        replacements=((re.compile(r"\bMioshie Shu\b"), "Mioshie-shū"),),
    ),
    # 言霊 — forma consagrada PT (sem «Kotodama»)
    type(SAFE_RULES[0])(
        name="kotodama_phrase",
        japanese_term="言霊",
        replacements=(
            (re.compile(r"\bKotodama\s*\(\s*espírito da palavra\s*\)", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\bKotodama\b", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\bkotodama\b", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\bciência da palavra espiritual\b", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\bciência da palavra\b", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\bpoder da palavra \(kotodama\)\b", flags=re.IGNORECASE), "espírito da palavra"),
        ),
    ),
    # 御論文 (title-like only)
    type(SAFE_RULES[0])(
        name="goronbun_meishu",
        japanese_term="御論文",
        replacements=(
            (re.compile(r"\bEnsaio de Meishu-Sama\b"), "artigo de Meishu-Sama"),
            (re.compile(r"\bensaio de Meishu-Sama\b"), "artigo de Meishu-Sama"),
            (re.compile(r"\btexto de Meishu-Sama\b"), "artigo de Meishu-Sama"),
            (re.compile(r"\bpublicação de Meishu-Sama\b"), "artigo de Meishu-Sama"),
        ),
    ),
    # 修業 (narrow spiritual compounds)
    type(SAFE_RULES[0])(
        name="shugyo_spiritual",
        japanese_term="修業",
        replacements=(
            (re.compile(r"\bausteridade espiritual\b", flags=re.IGNORECASE), "treino espiritual"),
            (re.compile(r"\bausteridades espirituais\b", flags=re.IGNORECASE), "treinos espirituais"),
            (re.compile(r"\bdisciplina espiritual\b", flags=re.IGNORECASE), "treino espiritual"),
            (re.compile(r"\bprática ascética\b", flags=re.IGNORECASE), "treino espiritual"),
        ),
    ),
    # 再生 — only explicit reincarnation compounds (not spiritual regeneration)
    type(SAFE_RULES[0])(
        name="saisei_reencarnacao",
        japanese_term="再生",
        replacements=((re.compile(r"\brenascimento humano\b", flags=re.IGNORECASE), "reencarnação humana"),),
    ),
    # 医術 (spiritual healing compounds)
    type(SAFE_RULES[0])(
        name="ijutsu_spiritual",
        japanese_term="医術",
        replacements=(
            (re.compile(r"\barte de cura espiritual\b", flags=re.IGNORECASE), "terapia espiritual"),
            (re.compile(r"\bArte da Cura Espiritual\b"), "terapia espiritual"),
            (re.compile(r"\barte médica espiritual\b", flags=re.IGNORECASE), "terapia espiritual"),
            (re.compile(r"\bmedicina espiritual\b", flags=re.IGNORECASE), "terapia espiritual"),
        ),
    ),
    # 神格
    type(SAFE_RULES[0])(
        name="shinkaku",
        japanese_term="神格",
        replacements=((re.compile(r"\bdeificação\b", flags=re.IGNORECASE), "qualificação divina"),),
    ),
    # 祀る
    type(SAFE_RULES[0])(
        name="matsuru_sufragar",
        japanese_term="祀る",
        replacements=(
            (re.compile(r"\bvenerar os espíritos ancestrais\b", flags=re.IGNORECASE), "sufragar os espíritos ancestrais"),
            (re.compile(r"\bvenerar os antepassados\b", flags=re.IGNORECASE), "sufragar os antepassados"),
        ),
    ),
    # 毒血
    type(SAFE_RULES[0])(
        name="dokketsu",
        japanese_term="毒血",
        replacements=(
            (re.compile(r"\bsangue impuro\b", flags=re.IGNORECASE), "sangue toxêmico"),
            (re.compile(r"\bsangue tóxico\b", flags=re.IGNORECASE), "sangue toxêmico"),
        ),
    ),
    # 凝り
    type(SAFE_RULES[0])(
        name="kori_nodulo",
        japanese_term="凝り",
        replacements=((re.compile(r"\brigidez localizada\b", flags=re.IGNORECASE), "Nódulo"),),
    ),
    # 安心立命
    type(SAFE_RULES[0])(
        name="anshin_ritsumei",
        japanese_term="安心立命",
        replacements=(
            (
                re.compile(r"\bestabelecimento da paz interior\b", flags=re.IGNORECASE),
                "realização da paz de espírito e firmeza do destino",
            ),
        ),
    ),
    # 世界人類
    type(SAFE_RULES[0])(
        name="sekai_jinrui",
        japanese_term="世界人類",
        replacements=((re.compile(r"\bHumanidade Mundial\b"), "Humanidade do Mundo"),),
    ),
    # 神仙郷
    type(SAFE_RULES[0])(
        name="shinsenkyo",
        japanese_term="神仙郷",
        replacements=((re.compile(r"\bParaíso dos Imortais\b", flags=re.IGNORECASE), "Shinsenkyō"),),
    ),
    # 副守護神 / 正守護神
    type(SAFE_RULES[0])(
        name="fukushugoshin",
        japanese_term="副守護神",
        replacements=((re.compile(r"\bdeus guardião secundário\b", flags=re.IGNORECASE), "deus guardião auxiliar"),),
    ),
    type(SAFE_RULES[0])(
        name="shoshugoshin",
        japanese_term="正守護神",
        replacements=((re.compile(r"\bdeus guardião principal\b", flags=re.IGNORECASE), "deus guardião principal"),),
    ),
    # 現当利益
    type(SAFE_RULES[0])(
        name="gento_rieki",
        japanese_term="現当利益",
        replacements=((re.compile(r"\bbenefícios terrenos imediatos\b", flags=re.IGNORECASE), "benefícios presentes e concretos"),),
    ),
    # 溜結
    type(SAFE_RULES[0])(
        name="tamari_ketsu",
        japanese_term="溜結",
        replacements=(
            (re.compile(r"\bacúmulo de toxinas\b", flags=re.IGNORECASE), "concentração de toxinas"),
            (re.compile(r"\bacúmulos de toxinas\b", flags=re.IGNORECASE), "concentrações de toxinas"),
        ),
    ),
    # 叡智
    type(SAFE_RULES[0])(
        name="eichi",
        japanese_term="叡智",
        replacements=((re.compile(r"\bsabedoria divina\b", flags=re.IGNORECASE), "sabedoria suprema"),),
    ),
    # 教線
    type(SAFE_RULES[0])(
        name="kyosen",
        japanese_term="教線",
        replacements=((re.compile(r"\blinha da doutrina\b", flags=re.IGNORECASE), "linha de transmissão do ensinamento"),),
    ),
    # 御神書
    type(SAFE_RULES[0])(
        name="goshinsho",
        japanese_term="御神書",
        replacements=((re.compile(r"\bEscrituras Sagradas\b", flags=re.IGNORECASE), "Escrituras Divinas"),),
    ),
    # 神憑り
    type(SAFE_RULES[0])(
        name="kamigakari",
        japanese_term="神憑り",
        replacements=((re.compile(r"\bpossessão divina\b", flags=re.IGNORECASE), "inspiração divina (kami-gakari)"),),
    ),
    # 殺菌
    type(SAFE_RULES[0])(
        name="sakkin",
        japanese_term="殺菌",
        replacements=((re.compile(r"\besterilização\b", flags=re.IGNORECASE), "eliminação de micróbios"),),
    ),
    # 救世教
    type(SAFE_RULES[0])(
        name="kyuseikyo",
        japanese_term="救世教",
        replacements=((re.compile(r"\bIgreja da Salvação\b", flags=re.IGNORECASE), "Kyusei-kyō"),),
    ),
    # 出血
    type(SAFE_RULES[0])(
        name="shukketsu",
        japanese_term="出血",
        replacements=((re.compile(r"\bsangramento\b", flags=re.IGNORECASE), "hemorragia"),),
    ),
    # 迷信邪教 compound
    type(SAFE_RULES[0])(
        name="meishin_jakyo",
        japanese_term="迷信邪教",
        replacements=((re.compile(r"\bsuperstições e religiões malignas\b", flags=re.IGNORECASE), "superstições e cultos malignos"),),
    ),
    # 真善美
    type(SAFE_RULES[0])(
        name="shinzembi",
        japanese_term="真善美",
        replacements=((re.compile(r"\bVerdade, Bondade e Beleza\b"), "Verdade, Bem e Beleza"),),
    ),
    # 明为様 OCR
    type(SAFE_RULES[0])(
        name="meishu_ocr",
        japanese_term="明为様",
        replacements=((re.compile(r"\bMeishu-sama\b"), "Meishu-Sama"),),
    ),
    # 毒素 — only explicit veneno/toxina confusion in toxin context
    type(SAFE_RULES[0])(
        name="dokuso_toxin",
        japanese_term="毒素",
        replacements=(
            (re.compile(r"\bveneno acumulado\b", flags=re.IGNORECASE), "toxina acumulada"),
            (re.compile(r"\bvenenos acumulados\b", flags=re.IGNORECASE), "toxinas acumuladas"),
        ),
    ),
    # 現界 extra
    type(SAFE_RULES[0])(
        name="genkai_extra",
        japanese_term="現界",
        replacements=((re.compile(r"\bmundo visível\b", flags=re.IGNORECASE), "mundo material"),),
    ),
    # 御守り
    type(SAFE_RULES[0])(
        name="omamori",
        japanese_term="御守り",
        replacements=((re.compile(r"\bamuleto\b", flags=re.IGNORECASE), "omamori (amuleto)"),),
    ),
    # 自然農法 — method name only (not every mention of agricultura natural)
    type(SAFE_RULES[0])(
        name="shizen_noho_extra",
        japanese_term="自然農法",
        replacements=(
            (re.compile(r"\bAgricultura Natural\b"), "método da agricultura natural"),
            (re.compile(r"\bmétodo de agricultura natural\b", flags=re.IGNORECASE), "método da agricultura natural"),
            (re.compile(r"\bMétodo de Agricultura Natural\b"), "método da agricultura natural"),
        ),
    ),
    # 地上天国 publication titles
    type(SAFE_RULES[0])(
        name="chijo_tengoku_titles",
        japanese_term="地上天国",
        replacements=(
            (re.compile(r"\bTijotengoku\b"), "Paraíso na Terra"),
            (re.compile(r"\bParaíso Terrestre\b", flags=re.IGNORECASE), "Paraíso na Terra"),
            (re.compile(r"\bCéu na Terra\b", flags=re.IGNORECASE), "Paraíso na Terra"),
            (re.compile(r"\bReino dos Céus na Terra\b", flags=re.IGNORECASE), "Paraíso na Terra"),
            (re.compile(r"\bTerra do Céu na Terra\b", flags=re.IGNORECASE), "Paraíso na Terra"),
        ),
    ),
    # 邪神 extra
    type(SAFE_RULES[0])(
        name="jashin_extra",
        japanese_term="邪神",
        replacements=(
            (re.compile(r"\bdeuses maus\b", flags=re.IGNORECASE), "Divindades malignas"),
            (re.compile(r"\bdeus mau\b", flags=re.IGNORECASE), "Divindade maligna"),
            (re.compile(r"\bespíritos malignos\b", flags=re.IGNORECASE), "Divindades malignas"),
            (re.compile(r"\bespírito maligno\b", flags=re.IGNORECASE), "Divindade maligna"),
            (re.compile(r"\bmaus espíritos\b", flags=re.IGNORECASE), "Divindades malignas"),
            (re.compile(r"\bdivindades maléficas\b", flags=re.IGNORECASE), "Divindades malignas"),
            (re.compile(r"\bdivindade maléfica\b", flags=re.IGNORECASE), "Divindade maligna"),
        ),
    ),
    # 薬毒 extra
    type(SAFE_RULES[0])(
        name="yakudoku_extra",
        japanese_term="薬毒",
        replacements=(
            (re.compile(r"\bveneno dos medicamentos\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\bvenenos dos medicamentos\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
            (re.compile(r"\bveneno de medicamentos\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\bvenenos de medicamentos\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
            (re.compile(r"\bveneno dos remédios\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\bvenenos dos remédios\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
            (re.compile(r"\btoxicidade dos medicamentos\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\bintoxicação medicamentosa\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\bintoxicações medicamentosas\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
            (re.compile(r"\btoxina dos medicamentos\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\btoxinas dos medicamentos\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
        ),
    ),
)


ALL_RULES = (
    SAFE_RULES
    + BATCH1_RULES
    + BATCH2_RULES
    + BATCH3_RULES
    + CONTEXTUAL_RULES
    + NARROW_RULES
    + CONFIRMED_RULES
    + EXTENDED_RULES
)


def apply_all(pt_text: str, jp_text: str) -> tuple[str, list[dict]]:
    return apply_simple_rules(pt_text, jp_text, ALL_RULES)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply comprehensive glossary batch (all rules, all texts).")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=DEFAULT_OUTPUT_DIR.__class__, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_glossary_pass(
        apply_fn=apply_all,
        report_name="comprehensive_glossary_batch.jsonl",
        apply=args.apply,
        output_dir=args.output_dir,
    )
    print(f"mode={'apply' if args.apply else 'dry-run'} texts={result['texts']} replacements={result['replacements']}")
    print("rules=" + __import__("json").dumps(result["rules"], ensure_ascii=False, sort_keys=True))
    print(f"report={result['report']}")
    if result["backup"]:
        print(f"backup={result['backup']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
