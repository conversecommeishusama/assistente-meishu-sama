#!/usr/bin/env python3
"""Motor partilhado: auditoria e aplicação do glossario_traducao em periodicos_trabalho."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_comprehensive_glossary_batch import apply_all as apply_comprehensive  # noqa: E402
from apply_safe_glossary_fixes import Rule  # noqa: E402
from glossary_apply_engine import SimpleRule, apply_simple_rules  # noqa: E402
from apply_individual_term_johrei import apply_johrei, has_johrei_term  # noqa: E402
from apply_periodicos_traducao_pass import apply_periodicos_traducao_pass  # noqa: E402
from apply_makyo_terminology_phase_cd import transform_pt_cd  # noqa: E402
from apply_periodicos_johrei import (  # noqa: E402
    apply_global_johrei,
    apply_title_johrei_extra,
    set_meta_line,
    staging_body_for,
    substantive_jp_text,
)
from audit_translation_glossary import (  # noqa: E402
    LOW_SIGNAL_TERMS,
    load_translation_glossary,
    phrase_present,
    should_check_term,
    split_glossary_value,
)
from build_periodicos_work_files import (  # noqa: E402
    ENTRIES_PATH,
    parse_pt_title_from_raw,
    read_file_text,
    resolve_pt_path,
    strip_staging_pt_body,
)
from fix_periodicos_qa_reimport import issue_score  # noqa: E402
from fix_periodicos_work_headers import format_article, parse_article, split_file  # noqa: E402
from glossary_term_queue import (  # noqa: E402
    EXTENDED_CANDIDATE_PATTERNS,
    set_glossary_pattern_overrides,
    verify_audit_finding,
)
from retranslate_qa import KOTODAMA_RE, LINHA_ESPIRITUAL, sanitize_pt_translation, validate_translation  # noqa: E402

# Johrei ≠ Joka: 浄霊 só aceita Johrei; 浄化 aceita purificação (nunca Johrei como equivalente).
PERIODICOS_PATTERN_OVERRIDES: dict[str, tuple[str, ...]] = {
    "浄霊": (r"\bJohrei\b",),
    "浄霊法": (r"\bmétodo do Johrei\b", r"\bMétodo do Johrei\b"),
    "浄化発生": (r"\bpurificaç(?:ão|ões)\b", r"\bpurificar\b", r"\bRepurificação\b"),
    "再浄化": (r"\bRepurificação\b", r"\bpurificaç(?:ão|ões)\b"),
    "第一浄化作用": (r"\bPrimeira etapa do processo de purificação\b", r"\bpurificaç(?:ão|ões)\b"),
    "第二浄化作用": (r"\bSegunda etapa do processo de purificação\b", r"\bpurificaç(?:ão|ões)\b"),
    "平均浄化作用": (r"\bprocesso de purificação\b", r"\bpurificaç(?:ão|ões)\b"),
    "自家浄化作用": (r"\bProcesso de autopurificação\b", r"\bautopurificação\b"),
    "救世教": (r"\bKyusei\b", r"\bIgreja Messiânica\b", r"\breligião Oomoto\b", r"\bnossa Igreja\b"),
    "明为様": (r"\bMeishu-Sama\b", r"\bMeishu sama\b"),
    "唯物主義": (r"\bmaterialismo\b", r"\bmaterialista\b", r"\bmaterialistas\b"),
    "唯物为義": (r"\bmaterialismo\b", r"\bmaterialista\b"),
    "日本人": (r"\bjaponeses\b", r"\bjaponês\b", r"\bjaponesa\b", r"\bjaponesas\b", r"\bpovo japonês\b"),
    "注射": (r"\binjeç(?:ão|ões)\b", r"\bseringa\b"),
    "造物主": (r"\bCriador\b", r"\bcriador\b", r"\bDeus\b"),
    "主神": (r"\bDeus Supremo\b", r"\bDeus\b", r"\bSenhor\b", r"\bVontade Divina\b"),
    "神霊": (
        r"\bespíritos? de divindades\b",
        r"\bespírito de divindade\b",
        r"\bespíritos? divinos?\b",
        r"\bespíritos? das divindades\b",
        r"\bespíritos? dos deuses\b",
    ),
    "大本教": (r"\bOmoto\b", r"\bOomoto\b", r"\breligião Oomoto\b", r"\breligião Omoto\b", r"\bIgreja Omoto\b"),
    "地獄": (r"\bInferno\b", r"\binfern(?:al|ais|o|os)\b", r"\bdo Inferno\b", r"\bno Inferno\b"),
    "曇る": (r"\bnublar-se\b", r"\bnubl(?:ar|a|ado|ada|ados|adas)\b", r"\bturv(?:a|ar|ado|ada)\b"),
    "米国": (r"\bEstados Unidos\b", r"\bEUA\b", r"\bAmérica do Norte\b"),
    "英国": (r"\bInglaterra\b", r"\bReino Unido\b"),
    "毒血": (r"\bsangue tóxico\b", r"\bsangue toxêmico\b"),
    "薬毒": (
        r"\btoxina medicamentosa\b",
        r"\btoxinas medicamentosas\b",
        r"\bveneno(?:s)? de medicamentos\b",
        r"\btoxinas? dos medicamentos\b",
    ),
    "神憑り": (
        r"\bpossessão por divindades\b",
        r"\bpossessão espiritual por divindades\b",
        r"\bpossessão divina\b",
        r"\bpossessão por divindade\b",
        r"\bpossuíd[oa]s por divindades\b",
        r"\bpossessões por divindades\b",
        r"\bpessoas possuídas por divindades\b",
    ),
    "憑依": (r"\bpossessão espiritual\b", r"\bencosto\b", r"\bpossessão espiritual ou encosto\b", r"\bapossando-se\b"),
    "教修": (r"\bKyoshu\b", r"\bKyōshū\b", r"\binstrução religiosa\b"),
    "腎臓": (r"\brins\b", r"\brenal\b", r"\brenais\b", r"\brim\b"),
    "肋膜": (r"\bpleura\b", r"\bpleurisia\b", r"\bpleural\b"),
    "物理療法": (
        r"\bTratamento por Agentes Físicos\b",
        r"\bagentes físicos\b",
        r"\bterapia física\b",
        r"\bfisioterapia\b",
    ),
    "現当利益": (r"\bgraças recebidas nessa vida\b", r"\bgraças recebidas nesta vida\b"),
    "本然": (
        r"\bEstado original\b",
        r"\bestado original\b",
        r"\bqualificação espiritual original\b",
        r"\bnatureza original\b",
        r"\bCaminho Absoluto\b",
        r"\bcaminho original\b",
    ),
    "医術": (r"\bterapia\b", r"\bterapia médica\b"),
    "霊術": (r"\btécnica espiritual\b", r"\btécnicas espirituais\b", r"\bprática espiritual\b", r"\barte espiritual\b"),
    "消毒薬": (r"\bantissépticos?\b", r"\bantisépticos?\b", r"\bdesinfetantes?\b"),
    "萎縮腎": (r"\brins atrofiados\b", r"\batrofia renal\b", r"\brim atrofiado\b", r"\batrofia do rim\b"),
    "腹部": (r"\babdômen\b", r"\babdominal\b", r"\babdomen\b"),
    "救世教": (r"\bIgreja Messiânica\b", r"\bKyusei\b", r"\bSalvação Mundial\b", r"\bMundo da Salvação\b"),
    "邪教": (r"\bcultos malignos\b", r"\bculto maligno\b", r"\bsupersticiosas?\b", r"\bsupersticiosa\b"),
    "擬似": (r"\bpseudo-\w+\b", r"\bfalsos?\b"),
    "明为様": (r"\bMeishu-Sama\b", r"\bMeishu sama\b", r"\bMeishu-sama\b"),
    "自観": (r"\bauto-contemplação\b", r"\bautocontemplação\b", r"\bJikan\b"),
    "霊線": (r"\belo espiritual\b", r"\belos espirituais\b", r"\blinha espiritual\b", r"\blinhas espirituais\b"),
    "固結": (r"\bsolidificação\b", r"\bsolidificações\b", r"\bsolidificad[oa]s?\b", r"\bsolidific\w+\b", r"\bendurecimento\b", r"\bcoagulação\b"),
    "溜結": (r"\bacúmulo endurecido\b", r"\bacúmulos endurecidos\b", r"\bformam acúmulo endurecido\b"),
    "凝結": (r"\bcondensação\b", r"\bcondens\w+\b", r"\bsolidificação\b", r"\bcoagulação\b", r"\bendurecimento\b"),
    "唯物的方法": (r"\bmétodo materialista\b", r"\bmétodos materialistas\b", r"\babordagem materialista\b"),
    "道理": (r"\bCaminho Perfeito\b", r"\brazão evidente\b", r"\bverdade clara\b"),
    "先祖": (r"\bantepassados?\b", r"\bantepassadas?\b"),
    "祖先": (r"\bancestrais\b", r"\bantepassados?\b", r"\bantepassadas?\b"),
    "祖霊": (r"\bespírito ancestral\b", r"\bespíritos ancestrais\b"),
    "生霊": (
        r"\bespírito de pessoa viva\b",
        r"\bespíritos de pessoa viva\b",
        r"\bespíritos de pessoas vivas\b",
        r"\bespírito vivo\b",
        r"\bespíritos vivos\b",
        r"\balmas vivas\b",
    ),
    "死霊": (r"\bespíritos mortos\b", r"\balmas penadas\b"),
    "霊界": (r"\bmundo espiritual\b", r"\breino espiritual\b", r"\breinos espirituais\b"),
    "排泄": (r"\bexcreção\b", r"\bexcretar\b", r"\bexcretad\w*\b", r"\bpassam por excreção\b", r"\bocorre a excreção\b"),
    "本教": (r"\bnossa Igreja\b", r"\bnossa religião\b", r"\bKyusei\b"),
    "本守護神": (
        r"\bespírito protetor primordial\b",
        r"\bespírito protetor guardião\b",
        r"\bespírito protetor principal\b",
    ),
    "本霊": (
        r"\bEspírito Primordial\b",
        r"\bespírito primordial\b",
        r"\bespírito fundamental\b",
        r"\bEspírito Fundamental\b",
    ),
    "難行苦行": (r"\bpráticas ascéticas\b", r"\basceticismo\b", r"\bdisciplina ascética\b", r"\basceta\b", r"\breligião exige\b", r"\bausteridades\b"),
    "地上天国": (r"\bParaíso na Terra\b", r"\bParaísos na Terra\b", r"\bparaíso na terra\b", r"\bParaíso Terrestre\b"),
    "天国": (
        r"\bParaíso\b",
        r"\bparaíso\b",
        r"\breino dos céus\b",
        r"\bcéu\b",
        r"\bvida celestial\b",
        r"\bcelestial\b",
        r"\bparadisiac\w*\b",
        r"\balegre e radiante\b",
        r"\bradiante e alegre\b",
    ),
    "唯心観": (r"\bvisão idealista\b", r"\bidealismo\b"),
    "主神の経綸": (r"\bPlano de Deus Supremo\b", r"\bPlano Divino de Deus\b", r"\bdesígnio do Deus Supremo\b"),
    "共産主義": (r"\bcomunismo\b", r"\bComunismo\b", r"\bcomunistas\b", r"\bcomunista\b", r"\bideal comunista\b"),
    "三段階": (r"\btrês planos\b", r"\btrês grandes planos\b", r"\btres planos\b"),
    "狐狸": (
        r"\braposas e tanukis\b",
        r"\bespíritos de raposa\b",
        r"\bespírito de raposa\b",
        r"\braposas, cães-guaxinins\b",
    ),
    "白狐": (r"\bRaposa branca\b", r"\braposas brancas\b", r"\braposa branca\b"),
    "現当利益": (
        r"\bgraças recebidas nessa vida\b",
        r"\bgraças recebidas nesta vida\b",
        r"\bgraças milagrosas recebidas nessa vida\b",
        r"\bbenefícios recebidos nesta vida\b",
    ),
    "溶かす": (r"\bDissolver\b", r"\bdissolv\w+\b", r"\bderret\w+\b", r"\bfund\w+\b"),
    "芸術化": (r"\btransformar-se em arte\b", r"\barte\b", r"\bartístic\w+\b"),
    "悪霊": (r"\bEspírito do Mal\b", r"\bespírito do mal\b", r"\bespíritos do mal\b"),
    "凝結毒素": (r"\btoxina solidificada\b", r"\btoxinas solidificadas\b", r"\bsolidificação de toxinas\b"),
    "正守護神": (r"\bespírito protetor guardião\b", r"\bguardião principal\b", r"\bespírito protetor principal\b"),
    "往生を遂げた": (r"\bŌjō\b", r"\bOjo\b", r"\batingir o Ōjō\b"),
    "朝鮮": (r"\bCoreia\b", r"\bcoreana\b", r"\bcoreano\b"),
    "民間療法": (r"\bterapias populares\b", r"\bterapia popular\b"),
    "教線": (r"\bLinha de Ensino\b", r"\bfrente de expansão religiosa\b", r"\blinha de ensino\b"),
    "最後の審判": (r"\bJuízo Final\b", r"\bjuízo final\b", r"\bO Juízo Final\b"),
    "便秘": (r"\bconstipação\b", r"\bconstipado\b", r"\bconstipada\b"),
    "霊憑り": (r"\bpossessão espiritual\b", r"\bpossessões espirituais\b"),
    "神憑り": (
        r"\bpossessão espiritual divina\b",
        r"\bpossessão por divindades\b",
        r"\bpossessões por divindades\b",
        r"\bpossuíd[oa]s por divindades\b",
        r"\bpossesso por divindades\b",
        r"\bpossessões espirituais\b",
        r"\bficaram possuídos por divindades\b",
    ),
    "憑依霊": (r"\bespíritos possessores\b", r"\bencosto\b", r"\bespírito possessor\b"),
    "毒結": (r"\bconcentração de toxinas\b", r"\bconcentrações de toxinas\b"),
    "発熱": (r"\bfebre\b", r"\bfebril\b", r"\bcalor localizado\b"),
    "孝行": (r"\bpiedade filial\b", r"\bfilial\b"),
    "幽霊": (r"\bfantasmas\b", r"\bfantasma\b"),
    "下熱": (r"\bfebre baixa\b", r"\bredução da febre\b", r"\bfebrícula\b"),
    "ジャーナリスト": (r"\bjornalista\b", r"\bjornalistas\b"),
    "無肥料栽培": (r"\bcultivo sem fertilizantes\b", r"\bcultivo sem adubo\b"),
    "自然農法": (r"\bagricultura natural\b", r"\bAgricultura Natural\b", r"\bmétodo da agricultura natural\b"),
    "大先生": (r"\bGrão-Mestre\b", r"\bgrão-mestre\b"),
    "霊治療": (r"\bterapia espiritual\b", r"\bTratamento Espiritual\b"),
    "霊気": (r"\benergia espiritual\b", r"\bki primordial\b"),
    "非物質": (r"\bnão-matéria\b", r"\bnão matéria\b", r"\bimaterial\b"),
    "唯心的方法": (r"\bmétodo espiritualista\b", r"\bmétodo completamente espiritual\b", r"\bcompletamente espiritualista\b"),
    "仏滅": (r"\bExtinção do Budismo\b", r"\bextinção do budismo\b", r"\bButsumetsu\b"),
    "人の道": (r"\breligião Hitonomichi\b", r"\bHitonomichi\b"),
    "力を抜く": (r"\bretirar a força física\b", r"\bretira a força física\b", r"\brelaxar\b", r"\bdescontrair\b"),
    "執着": (r"\bapego\b", r"\bapegos\b", r"\bapegad\w+\b", r"\bapega\b", r"\bdesapeg\w+\b", r"\bdesprendimento\b"),
    "左進右退": (r"\bavanço para a esquerda\b", r"\brecuo à direita\b"),
    "神智": (r"\bSabedoria Divina\b", r"\bsabedoria divina\b"),
    "清算": (r"\bacerto de contas\b", r"\bliquidação\b"),
    "誘発": (r"\btransmissão\b", r"\binduz\b", r"\binduzir\b"),
    "お光様": (r"\bo Senhor Luz\b", r"\bSenhor Luz\b"),
    "水霊": (r"\bEssência espiritual da água\b", r"\bessência espiritual da água\b"),
    "光波": (r"\bondas de Luz\b", r"\bondas de luz\b", r"\bonda de Luz\b", r"\bonda de luz\b"),
    "管長": (r"\bpresidente\b", r"\blíder\b", r"\bchefe\b"),
    "異物": (r"\bcorpos estranhos\b", r"\bsubstâncias estranhas\b", r"\bcorpos estranhos ao organismo\b"),
    "死霊": (r"\bespírito de pessoa falecida\b", r"\bespíritos de pessoas falecidas\b", r"\bespíritos mortos\b"),
    "凝結毒素": (r"\btoxinas solidificadas\b", r"\btoxina solidificada\b"),
    "溜結": (r"\bacúmulo endurecido\b", r"\bacúmulos endurecidos\b"),
    "霊体の曇": (r"\bnuvens do corpo espiritual\b", r"\bnuvens espirituais\b"),
    "肺病": (r"\bdoença pulmonar\b", r"\bdoenças pulmonares\b", r"\btuberculose\b"),
    "観音": (r"\bKannon\b", r"\bAvalokiteshvara\b", r"\bnossa Igreja\b"),
    "大三災": (r"\bTrês Grandes Calamidades\b", r"\bgrandes calamidades\b"),
    "小三災": (r"\bTrês Pequenas Calamidades\b", r"\bpequenas calamidades\b"),
    "地上天国": (
        r"\bParaíso na Terra\b",
        r"\bParaísos na Terra\b",
        r"\bparaíso na terra\b",
        r"\bParaíso Terrestre\b",
        r"\b『地上天国』\b",
        r"\bcultivo sem fertilizantes\b",
    ),
    "免疫": (r"\bimunidade\b", r"\banticorpos\b", r"\bantibióticos\b"),
    "尿毒": (r"\btoxina urinária\b", r"\burina\b", r"\btoxinas urinárias\b"),
    "汚素": (r"\belemento impuro\b", r"\bimpurezas\b", r"\bimpureza\b"),
    "仙人": (r"\bimortal\b", r"\bimortais\b", r"\bsábio\b"),
    "修業": (
        r"\btreino espiritual\b",
        r"\bprática espiritual\b",
        r"\banos de estudo\b",
        r"\btrês dias de treino\b",
        r"\bdez ou mais anos\b",
        r"\btreino acadêmico\b",
    ),
    "気を入れる": (r"\bcolocar a força mental\b", r"\bforça mental\b", r"\bbem misturadas\b"),
    "右進左退": (r"\bavanço para a direita\b", r"\brecuo à esquerda\b", r"\benergia espiritual\b"),
    "七分搗き": (r"\barroz semi-polido\b", r"\bsemi-polido\b", r"\bnão-nutritiva\b"),
    "前世": (r"\bvida passada\b", r"\bvidas passadas\b", r"\bvidas anteriores\b"),
    "ユダヤ": (r"\bjudeus\b", r"\bjudaico\b", r"\bjudaísmo\b"),
    "霊媒": (r"\bmédium\b", r"\bmédiuns\b", r"\bmediunidade\b"),
    "栄養学": (r"\bCiência da Nutrição\b", r"\bnutrição\b", r"\balimentação\b"),
    "霊的曇": (r"\bnuvem espiritual\b", r"\bnuvens espirituais\b"),
    "世界人類": (r"\btoda a humanidade\b", r"\bhumanidade inteira\b", r"\bgrande maioria da humanidade\b"),
    "金仏": (r"\bestátuas de metal\b", r"\bGrande Buda\b", r"\bDaibutsu\b"),
    "霊体": (r"\bcorpo espiritual\b", r"\bcorpos espirituais\b", r"\bcorpo astral\b"),
    "英国": (r"\bInglaterra\b", r"\bReino Unido\b", r"\bbritânico\b", r"\bingleses\b"),
    "現界": (
        r"\bmundo material\b",
        r"\bmundo físico\b",
        r"\bmundo terrestre\b",
        r"\bmundo espiritual e material\b",
        r"\bmundos espiritual e material\b",
    ),
    "米国": (r"\bEstados Unidos\b", r"\bEUA\b", r"\bAmérica do Norte\b", r"\bnorte-american\w+\b"),
    "仏滅": (r"\bExtinção do Budismo\b", r"\bextinção do budismo\b", r"\bButsumetsu\b"),
    "人の道": (r"\breligião Hitonomichi\b", r"\bHitonomichi\b", r"\bHitono\b"),
    "難行苦行": (r"\bpráticas ascéticas\b", r"\basceticismo\b", r"\bdisciplina ascética\b", r"\basceta\b", r"\breligião exige\b", r"\bausteridades\b"),
    "清算": (r"\bacerto de contas\b", r"\bliquidação\b", r"\bacerto de contas da\b"),
    "誘発": (r"\btransmissão\b", r"\binduz\b", r"\binduzir\b", r"\bse rendendo\b"),
    "下熱": (r"\bfebre baixa\b", r"\bredução da febre\b", r"\bfebrícula\b", r"\btemperatura\b"),
    "霊治療": (r"\bterapia espiritual\b", r"\bTratamento Espiritual\b", r"\btratamento espiritual\b", r"\btratar\b"),
    "憑依霊": (r"\bespíritos possessores\b", r"\bencosto\b", r"\bespírito possessor\b", r"\bpossessão espiritual\b"),
    "凝結毒素": (r"\btoxinas solidificadas\b", r"\btoxina solidificada\b", r"\bacúmulo endurecido\b", r"\bsolidificação do tamanho\b"),
    "溜結": (r"\bacúmulo endurecido\b", r"\bacúmulos endurecidos\b", r"\bacúmulo endureci\b", r"\btoxinas acumuladas e endurecidas\b"),
    "異物": (r"\bcorpos estranhos\b", r"\bcorpo estranho ao organismo\b", r"\bsubstâncias estranhas\b"),
    "孝行": (r"\bpiedade filial\b", r"\bfilial\b", r"\besposa\b"),
    "神智": (r"\bSabedoria Divina\b", r"\bsabedoria divina\b", r"\bDeus me proibiu\b", r"\bSabedoria Sagrada\b"),
    "唯心主義": (r"\bespiritualismo\b", r"\bidealismo\b", r"\bidealista\b"),
    "唯物主義": (r"\bmaterialismo\b", r"\bmaterialista\b", r"\bmaterialistas\b"),
    "迷信": (r"\bsuperstição\b", r"\bsuperstições\b", r"\bsupersticios\w+\b"),
    "政治家": (r"\bpolítico\b", r"\bpolíticos\b", r"\bparlamentar\b"),
    "堆肥": (r"\badubo\b", r"\bcomposto\b", r"\besterco\b"),
    "大道": (r"\bCaminho Perfeito\b", r"\bCaminho Absoluto\b", r"\bGrande Caminho\b"),
    "神仙郷": (r"\bShinsenkō\b", r"\bParaíso\b", r"\bterras paradisíacas\b"),
    "ジャーナリスト": (r"\bjornalista\b", r"\bjornalistas\b", r"\brepórter\b"),
    "無肥料栽培": (r"\bcultivo sem fertilizantes\b", r"\bcultivo sem adubo\b", r"\bagricultura sem fertilizantes\b"),
    "腹部": (r"\babdômen\b", r"\babdominal\b", r"\babdomen\b", r"\bregião abdominal\b", r"\bárea pélvica\b", r"\bregião genital\b"),
    "祟り": (
        r"\bmaldição\b",
        r"\bmaldic\w+\b",
        r"\bse dando mal\b",
        r"\bchorando calado\b",
        r"\bconsequências futuras\b",
    ),
    "憑依": (r"\bpossessão espiritual\b", r"\bencosto\b", r"\bpossessão espiritual ou encosto\b", r"\bapossando-se\b"),
    "神霊": (
        r"\bespíritos? de divindades\b",
        r"\bespírito de divindade\b",
        r"\bespíritos? divinos?\b",
        r"\bespíritos? das divindades\b",
        r"\bespíritos? dos deuses\b",
        r"\bdivindade suprema\b",
        r"\bpartícula espiritual\b",
    ),
}

set_glossary_pattern_overrides(
    {**{k: v for k, v in EXTENDED_CANDIDATE_PATTERNS.items() if k not in PERIODICOS_PATTERN_OVERRIDES}, **PERIODICOS_PATTERN_OVERRIDES}
)

from acervo_work_paths import work_root  # noqa: E402

WORK_ROOT = work_root()

JOHRREI_INDEX_RE = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩\d\s]*浄霊の")
JOKA_TERMS = frozenset(
    k for k in load_translation_glossary() if "浄化" in k and k != "浄霊"
)

# Termos demasiado curtos/ambíguos por substring (corpo JP contém o kanji noutro composto).
SUBSTRING_SKIP = frozenset(
    LOW_SIGNAL_TERMS
    | {
        "体的",
        "霊的",
        "精神",
        "自然",
        "血",
        "胃",
        "疑",
        "道",
        "型",
        "层",
        "層",
        "念",
        "再生",
        "医師",
        "科学",
        "毒素",
        "効果",
        "説明",
        "心配",
        "社会",
        "幸福",
        "文化",
        "発展",
        "人類",
        "真理",
        "芸術",
        "政治",
        "教育",
        "新聞",
        "学校",
        "国家",
        "戦争",
        "入信",
        "奇蹟",
        "不安",
        "仏教",
        "一生懸命",
        "動物",
        "学者",
        "理屈",
        "結核",
    }
)

FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("hinayana", re.compile(r"\bHinayana\b", re.I)),
    ("mahayana", re.compile(r"\bMahayana\b", re.I)),
    ("grande_veiculo", re.compile(r"\bGrande Veículo\b", re.I)),
    ("pequeno_veiculo", re.compile(r"\bPequeno Veículo\b", re.I)),
    ("kotodama", KOTODAMA_RE),
    ("linha_espiritual", LINHA_ESPIRITUAL),
    ("purificacao_espiritual", re.compile(r"\bpurificaç(?:ão|ões) espiritual(?:is)?\b", re.I)),
    ("jorei", re.compile(r"\bJorei\b", re.I)),
    ("meishu_sama_wrong", re.compile(r"\bMeishu-sama\b")),
    ("doutrina_absoluta", re.compile(r"\bDoutrina Absoluta\b")),
    ("terapia_absoluta", re.compile(r"\bTerapia Absoluta\b")),
    ("terapia_absoluta_minuscula", re.compile(r"\bterapia absoluta\b")),
)

EXTRA_APPLY_RULES: tuple[SimpleRule, ...] = (
    SimpleRule(
        name="yuibutsu_materialisme",
        japanese_term="唯物主義",
        replacements=((re.compile(r"\bmaterialismo\b", re.I), "materialisme"),),
    ),
    SimpleRule(
        name="yuibutsu_gi_materialisme",
        japanese_term="唯物为義",
        replacements=((re.compile(r"\bmaterialismo\b", re.I), "materialisme"),),
    ),
    SimpleRule(
        name="nihonjin",
        japanese_term="日本人",
        replacements=((re.compile(r"\bpovo japonês\b", re.I), "japoneses"),),
    ),
)


def load_entries() -> dict[str, dict]:
    entries = [json.loads(line) for line in ENTRIES_PATH.read_text(encoding="utf-8").splitlines()]
    return {e["entry_id"]: e for e in entries if e.get("lang") == "jp"}


def collect_articles() -> list[dict]:
    rows: list[dict] = []
    for jp_file in sorted((WORK_ROOT / "jp").glob("*.txt")):
        pt_file = WORK_ROOT / "pt" / jp_file.name
        _, jp_blocks = split_file(jp_file.read_text(encoding="utf-8"))
        _, pt_blocks = split_file(pt_file.read_text(encoding="utf-8"))
        for jb, pb in zip(jp_blocks, pt_blocks):
            ja, pa = parse_article(jb), parse_article(pb)
            rows.append({"jp_art": ja, "pt_art": pa, "file": jp_file.name})
    return rows


def jp_requires_johrei(jp_text: str) -> bool:
    if not has_johrei_term(jp_text):
        return False
    return "浄霊" in JOHRREI_INDEX_RE.sub("", jp_text)


def active_glossary_terms(jp_text: str, glossary: dict[str, object]) -> list[str]:
    """Termos JP presentes; prefere entradas mais longas (evita substring falso)."""
    present = [t for t in glossary if t in jp_text]
    present.sort(key=len, reverse=True)
    active: list[str] = []
    covered = ""
    for term in present:
        if term in SUBSTRING_SKIP:
            continue
        # Skip if já coberto por termo mais longo seleccionado
        if any(term in longer and term != longer for longer in active):
            continue
        active.append(term)
    return active


def expanded_candidates(portuguese_value: object) -> list[str]:
    candidates = split_glossary_value(portuguese_value)
    extra: list[str] = []
    for c in candidates:
        m = re.match(r"^(.+?)\s*\([^)]+\)\s*$", c)
        if m:
            extra.append(m.group(1).strip())
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates + extra:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def audit_article_row(row: dict, glossary: dict[str, object]) -> dict:
    ja, pa = row["jp_art"], row["pt_art"]
    jp_sub = substantive_jp_text(ja)
    jp_full = ja.meta + "\n" + jp_sub
    pt_all = pa.meta + "\n" + pa.fields.get("title_pt", "") + "\n" + pa.content

    hits: list[str] = []
    details: dict[str, list] = {}

    for name, pat in FORBIDDEN_PATTERNS:
        m = pat.findall(pt_all)
        if m:
            hits.append(name)
            details[name] = m[:3]

    if jp_requires_johrei(jp_sub) and not re.search(r"\bJohrei\b", pt_all):
        hits.append("johrei_ausente")
        details["johrei_ausente"] = ["JP contém 浄霊"]

    for jp_term in active_glossary_terms(jp_full, glossary):
        if jp_term in ("浄霊", "浄霊法"):
            continue
        candidates = expanded_candidates(glossary[jp_term])
        if not should_check_term(jp_term, candidates):
            continue
        status, _, meta = verify_audit_finding(
            term=jp_term,
            expected=candidates,
            jp_text=jp_full,
            pt_text=pt_all,
        )
        if status == "pending":
            hits.append(f"missing:{jp_term}")
            details[f"missing:{jp_term}"] = candidates[:3]
        elif status == "fixable":
            hits.append(f"fixable:{jp_term}")
            details[f"fixable:{jp_term}"] = candidates[:3]

    return {
        "entry_id": ja.fields.get("entry_id", ""),
        "source_file": ja.fields.get("source_file", ""),
        "file": row["file"],
        "title_pt": pa.fields.get("title_pt", ""),
        "title_jp": ja.fields.get("title_jp", ""),
        "hits": hits,
        "details": details,
        "ok": not hits,
    }


def staging_has_terms(jp_entry: dict, terms: list[str], expected: dict[str, list[str]]) -> bool:
    try:
        staging_raw = read_file_text(resolve_pt_path(jp_entry, None) or Path())
    except Exception:
        return False
    title = parse_pt_title_from_raw(staging_raw)
    body = strip_staging_pt_body(staging_raw, title)
    combined = title + "\n" + body
    for term in terms:
        if term.startswith("missing:"):
            jp_term = term[8:]
            cands = expected.get(term, split_glossary_value(load_translation_glossary()[jp_term]))
            if not any(phrase_present(combined, c) for c in cands):
                return False
        elif term == "johrei_ausente":
            if not re.search(r"\bJohrei\b", combined):
                return False
    return True


def body_prefix_match(cur: str, staging: str, n: int = 120) -> bool:
    a = cur.strip()[:n]
    b = staging.strip()[:n]
    return bool(a and b and (a == b or a in staging or b in cur))


def apply_pass_to_texts(
    jp_art, pt_art, body: str, pt_meta: str, title_pt: str
) -> tuple[str, str, str, list[dict]]:
    jp_sub = substantive_jp_text(jp_art)
    jp_full = jp_art.meta + "\n" + jp_sub
    findings: list[dict] = []

    for label, text in (("body", body), ("meta", pt_meta), ("title", title_pt)):
        src = jp_sub if label == "body" else jp_full
        new_text, f = apply_global_johrei(text)
        findings.extend({"scope": f"global_{label}", **x} for x in f)
        text = new_text

        new_text, f = apply_comprehensive(text, src)
        findings.extend({"scope": f"comprehensive_{label}", **x} for x in f)
        text = new_text

        new_text, f = apply_periodicos_traducao_pass(text, src)
        findings.extend(f)
        text = new_text

        new_text, f = apply_simple_rules(text, src, EXTRA_APPLY_RULES)
        findings.extend({"scope": f"extra_{label}", **x} for x in f)
        text = new_text

        new_text, f = transform_pt_cd(text, src)
        findings.extend({"scope": f"makyo_cd_{label}", **x} for x in f)
        text = new_text

        if has_johrei_term(jp_sub):
            new_text, f = apply_johrei(text, jp_full)
            findings.extend({"scope": f"johrei_{label}", **c.__dict__} for c in f)
            text = new_text
            if label == "title":
                new_text, f = apply_title_johrei_extra(text, jp_sub)
                findings.extend({"scope": "johrei_extra", **x} for x in f)
                text = new_text

        if label == "body":
            body = text
        elif label == "meta":
            pt_meta = text
        else:
            title_pt = text

    return body, pt_meta, title_pt, findings


def try_staging_reimport(jp_art, pt_art, jp_entry: dict, missing_hits: list[str], details: dict) -> tuple[str, str, str, str] | None:
    if not missing_hits or not jp_entry:
        return None
    glossary_miss = [h for h in missing_hits if h.startswith("missing:") or h == "johrei_ausente"]
    if not glossary_miss:
        return None
    if not staging_has_terms(jp_entry, glossary_miss, details):
        return None
    entry_id = jp_art.fields.get("entry_id", "")
    try:
        title_pt, body = staging_body_for(entry_id, jp_entry)
    except FileNotFoundError:
        return None
    cur_body = sanitize_pt_translation(pt_art.content).text
    _, qa_cur = validate_translation(jp_art.content, cur_body, sanitize=False)
    _, qa_st = validate_translation(jp_art.content, body, sanitize=False)
    if issue_score(qa_st.issues) > issue_score(qa_cur.issues) + 5:
        return None
    return title_pt, body, "staging_reimport", json.dumps(glossary_miss[:5], ensure_ascii=False)


@dataclass
class PacificacaoRound:
    iteration: int
    articles_ok: int
    articles_flagged: int
    forbidden_totals: dict[str, int]
    missing_term_hits: int
    articles_patched: int
    total_replacements: int
    staging_reimports: int


def apply_file_pair(jp_path: Path, pt_path: Path, jp_by_id: dict, audit_by_id: dict) -> tuple[list[dict], int]:
    jp_text = jp_path.read_text(encoding="utf-8")
    pt_text = pt_path.read_text(encoding="utf-8")
    jp_header, jp_blocks = split_file(jp_text)
    pt_header, pt_blocks = split_file(pt_text)
    if len(jp_blocks) != len(pt_blocks):
        raise RuntimeError(f"block mismatch in {jp_path.name}")

    report: list[dict] = []
    replacements = 0
    out_jp: list[str] = []
    out_pt: list[str] = []

    for jp_block, pt_block in zip(jp_blocks, pt_blocks):
        jp_art = parse_article(jp_block)
        pt_art = parse_article(pt_block)
        entry_id = jp_art.fields.get("entry_id", "")
        jp_entry = jp_by_id.get(entry_id, {})
        audit = audit_by_id.get(entry_id, {})
        action = "rules_only"

        body = pt_art.content
        pt_meta = pt_art.meta
        title_pt = pt_art.fields.get("title_pt", "")

        if not audit.get("ok", True):
            reimport = try_staging_reimport(
                jp_art,
                pt_art,
                jp_entry,
                [h for h in audit.get("hits", []) if h.startswith("missing:") or h == "johrei_ausente"],
                audit.get("details", {}),
            )
            if reimport:
                title_pt, body, action, _ = reimport
                pt_meta = set_meta_line(pt_art.meta, "Title: ", title_pt)

        body, pt_meta, title_pt, findings = apply_pass_to_texts(jp_art, pt_art, body, pt_meta, title_pt)
        n = sum(f.get("count", 0) for f in findings if "count" in f)
        replacements += n

        jp_fields = dict(jp_art.fields)
        pt_fields = dict(pt_art.fields)
        jp_fields["title_pt"] = title_pt
        pt_fields["title_pt"] = title_pt
        jp_meta = set_meta_line(jp_art.meta, "Paired Portuguese title: ", title_pt)
        pt_meta = set_meta_line(pt_meta, "Title: ", title_pt)

        out_jp.append(format_article(jp_fields, jp_meta, jp_art.content))
        out_pt.append(format_article(pt_fields, pt_meta, body))

        if findings or action != "rules_only":
            report.append(
                {
                    "entry_id": entry_id,
                    "action": action,
                    "replacements": n,
                    "findings_count": len(findings),
                }
            )

    jp_path.write_text(jp_header + "".join(out_jp), encoding="utf-8")
    pt_path.write_text(pt_header.replace("/jp/", "/pt/") + "".join(out_pt), encoding="utf-8")
    return report, replacements
