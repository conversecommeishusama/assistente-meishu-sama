#!/usr/bin/env python3
"""Ajuste CONSOLIDADO do glossário de tradução — 2026-10-08.

Consolida em um único trabalho:
  - 6 questões levantadas pelo usuário (2026-10-08)
  - 1.190 achados da revisão do Claude sobre `kowa_full.txt` (88 lotes)

Decisões do usuário:
  - MEDIDAS: converter SEMPRE para o sistema métrico ocidental (sem unidade JP)
  - DEMAIS: seguir as recomendações do relatório
    `docs/DECISOES_GLOSSARIO_CONSOLIDADO_20261008.md`

Uso:
    .venv/bin/python scripts/aplicar_ajuste_glossario_20261008.py [--dry-run]
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GLOSSARIO = RAIZ / "glossario_traducao.json"
REGRAS = RAIZ / "glossario_regras.json"

# --------------------------------------------------------------------------
# 1) ENTRADAS NOVAS
# --------------------------------------------------------------------------
# Convenção de valor:  `forma principal — nota explicativa`
#   - o bloqueio determinístico exige "forma principal"
#   - o texto após " — " é só orientação para o tradutor
#   - o conteúdo entre parênteses é variante ACEITA (mas não exigida)
NOVAS: dict[str, str] = {
    # ---- A. MEDIDAS (bloco de regra; o usuário decidiu SEMPRE métrico) ----
    "【MEDIDAS — CONVERTER SEMPRE PARA O SISTEMA MÉTRICO】": (
        "NUNCA transliterar unidade japonesa (nada de shaku/sun/ken/tsubo/ri/"
        "shō/gō) e NUNCA manter a unidade japonesa no texto. Converter sempre: "
        "尺≈30,3 cm · 寸≈3,03 cm · 分≈3,03 mm · 間≈1,82 m · 丈≈3,03 m · "
        "尋≈1,82 m · 町≈109 m · 里≈3,93 km · 坪≈3,31 m² · 升≈1,80 L · "
        "斗≈18,0 L · 合≈180 mL · 勺≈18 mL · 貫≈3,75 kg · 匁≈3,75 g — "
        "ex.: 三尺→'cerca de 90 cm'; 一尺五寸→'cerca de 45 cm'; "
        "二、三十間→'de 36 a 54 m'; 一〇里四方→'uns 39 km de lado'"
    ),
    # ---- B. VERTICAL/HORIZONTAL (erro real: latitude/longitude) ----
    "経（緯と対で使われた場合）": (
        "vertical — SOMENTE quando em par com 緯 (経と緯 / 経緯 / 経の文化 / "
        "緯の文化) ou no sentido doutrinário de eixo espiritual. NUNCA traduzir "
        "como latitude/longitude. Atenção: em 経済 / 経典 / 経験 / 経綸 / "
        "観音経 o kanji é OUTRO sentido — não aplicar esta regra"
    ),
    "緯（経と対で使われた場合）": (
        "horizontal — SOMENTE quando em par com 経. NUNCA latitude/longitude "
        "nem 'trama' solta. Ex.: 緯の文化→Cultura Horizontal"
    ),
    "縦": (
        "vertical — eixo espiritual/estrutural. NUNCA 'comprimento', "
        "'longitudinal' nem 'latitude'. Par obrigatório: 横→horizontal "
        "(não 'largura'). Ex.: 霊界は縦横の三段階→'o mundo espiritual tem três "
        "níveis verticais e horizontais'"
    ),
    "横": (
        "horizontal — NUNCA 'largura' nem 'longitude' quando em par com 縦"
    ),
    "経緯": (
        "o vertical e o horizontal — NUNCA 'latitude e longitude'. Também "
        "aceito 'a urdidura e a trama' quando a imagem têxtil for explícita"
    ),
    "経と緯": (
        "o vertical e o horizontal (urdidura e trama) — o par representa "
        "masculino/feminino, espírito/matéria, Oriente/Ocidente"
    ),
    "経緯を結ぶ": (
        "unir o vertical e o horizontal — imagem da cruz (十) que une os dois "
        "eixos; também 'atar a urdidura à trama'"
    ),
    # ---- C. MENTE / CORAÇÃO ----
    "心（霊・心・魂の区別）": (
        "mente / consciência — reservar 'coração' para contextos de AFETO "
        "(真心, 心配, 観音心). Em contexto técnico (霊・心・魂) usar sempre "
        "'mente' ou 'consciência', nunca 'coração'"
    ),
    "気持ち": (
        "intenção interior / disposição — evitar 'coração' (reservado a 心)"
    ),
    # ---- D. POSSESSÃO / ESPÍRITOS ----
    "とっつく": (
        "grudar-se / agarrar-se — variante informal de 取り憑く; nunca "
        "'ficar possesso'"
    ),
    "取っ付く": (
        "grudar-se / agarrar-se — variante informal de 取り憑く; nunca "
        "'ficar possesso'"
    ),
    "生き霊": (
        "espírito de pessoa viva — mesma forma fixada de 生霊 (variante gráfica)"
    ),
    "狐霊": (
        "espírito-raposa — forma fixada, distinta de 狐狸 ('raposa e texugo')"
    ),
    "神懸り": (
        "possessão espiritual — sem especificar 'por divindades' (o contexto "
        "pode incluir espíritos de raposa)"
    ),
    "憑る": (
        "possuir / encostar-se — NUNCA 'ficar possesso' (em português "
        "'possesso' significa 'raivoso', não 'possuído')"
    ),
    "憑く": (
        "possuir / encostar-se — NUNCA 'ficar possesso'"
    ),
    # ---- E. CULTO / SUFRÁGIO ----
    "祭る": (
        "consagrar — quando o objeto for altar/imagem (観音様を祭ってない家→"
        "'casa que não tem Kannon consagrado'). Para divindade usar 'cultuar'; "
        "para espírito/ancestral usar 'sufragar'"
    ),
    "供養": (
        "prestar sufrágio — oferecer orações em benefício do espírito (kuyō); "
        "NUNCA 'cultuar' quando o objeto for espírito/ancestral"
    ),
    "お供え": (
        "oferenda — forma fixada; o verbo é 'oferecer' (água/comida/flores)"
    ),
    "お供えを上げる": (
        "oferecer a oferenda — usar 'oferecer', nunca 'recitar'"
    ),
    "位牌": (
        "tabuleta mortuária (ihai) — na 1ª menção de cada artigo a forma "
        "completa; depois apenas 'tabuleta' ou 'ihai'"
    ),
    "御霊紙": (
        "Papel Sagrado (Goreishi) — na 1ª menção de cada artigo a forma "
        "completa; depois 'Goreishi'"
    ),
    # ---- F. PLANO DIVINO ----
    # (revisão de 経綸, ver REVISOES)
    # ---- G. HIERARQUIA ESPIRITUAL ----
    "霊統": (
        "linhagem espiritual — par de 血統→'linhagem sanguínea'"
    ),
    "身魂": (
        "ser espiritual — traço próprio de 身魂, para diferenciar de 魂 "
        "('alma'). Aceito 'corpo e alma' quando o contexto for explicativo"
    ),
    "霊動": (
        "movimento espiritual — aceito 'manifestação espiritual (reitō)'"
    ),
    "中幽界": (
        "Mundo Intermediário — MESMA tradução de 中有界 (são o mesmo nível); "
        "八衢 é o nome técnico do estágio dentro dele"
    ),
    # ---- H. IMAGEM SAGRADA ----
    "御書体": (
        "Imagem da Luz Divina (caligrafia sagrada) — forma caligráfica, "
        "distinta da forma pictórica (お姿)"
    ),
    "御掛軸": (
        "Imagem da Luz Divina — quando consagrado; variante de 御軸"
    ),
    # ---- I. ORAÇÕES ----
    "【ORAÇÕES — REGRA DE USO】": (
        "Diante do 御軸 (Imagem da Luz Divina): norito + Zengen-Sandji. "
        "Diante do 仏壇 (altar budista): APENAS Zengen-Sandji (as duas últimas "
        "frases, no uso cotidiano). O verbo de recitação é 'recitar' "
        "(奏上/上げる); reservar 'oferecer' para お供え/玉串"
    ),
    "天津祝詞": (
        "Amatsu Norito (Norito Celestial) — na 1ª menção de cada artigo a "
        "forma completa; depois apenas 'Norito'"
    ),
    "御讃歌": (
        "Salmo — consistente com 御讃歌集→'Coletânea de Salmos'"
    ),
    # ---- J. TERMOS DOUTRINÁRIOS ----
    "散花結実": (
        "A flor cai, o fruto amadurece (sanka-kekijitsu) — expressão fixa; "
        "na 1ª menção de cada artigo com a transliteração"
    ),
    "木龍": (
        "dragão da árvore — mesma família de 地龍→'dragão da terra'; aceito "
        "'espírito-dragão da madeira'"
    ),
    "御神徳": (
        "Virtude Divina — distinto de 御利益 ('benefício/graça material')"
    ),
    # ---- Z. CAUDA LONGA ----
    "時所位": (
        "Jishoi (tempo, local e posição) — na 1ª menção de cada artigo; "
        "depois apenas 'Jishoi'"
    ),
    "地所位": (
        "posição no mundo — aparece sempre ligado a mundo/Paraíso da Luz "
        "(光明世界における地所位); distinto de 時所位 (posição dinâmica)"
    ),
    "相応の理": (
        "princípio da correspondência — forma fixada"
    ),
    "三隣亡": (
        "Santanbō (três vizinhos arruinados) — na 1ª menção de cada artigo"
    ),
    "大将軍": (
        "Daijōgun (a divindade dos oito pontos) — na 1ª menção de cada artigo"
    ),
    "家相": (
        "geomancia da casa (kasō) — na 1ª menção de cada artigo"
    ),
    "癩病": (
        "lepra — termo histórico; usar 'lepra' sem carga pejorativa, sem "
        "eufemismo e sem atualizar para outro nome de doença"
    ),
    "伊都能売": (
        "Izunome — quando usado conceitualmente (sem 大御神), na 1ª menção de "
        "cada artigo com nota de 'estado de perfeição espiritual'"
    ),
}

# --------------------------------------------------------------------------
# 2) ENTRADAS REVISADAS
# --------------------------------------------------------------------------
REVISOES: dict[str, str] = {
    # Erro real: 経緯 não é latitude/longitude
    "経綸": (
        "Plano Divino — quando o sujeito for Deus/主神. Com sujeito "
        "humano/coletivo usar 'grande obra' ou 'grande empreendimento'"
    ),
    "大経綸": "grande Plano Divino — ver regra de sujeito em 経綸",
    # 心: não achatar a distinção doutrinária
    "心魂": (
        "mente — em contexto técnico (distinção 霊・心・魂). Aceito "
        "'consciência' ou 'psique'; evitar 'alma' (reservado a 魂)"
    ),
    # D: proibir "possesso"
    "憑依": (
        "possessão espiritual — aceito 'encosto'; NUNCA 'possesso' (em "
        "português significa 'raivoso', não 'possuído')"
    ),
    # E: objeto decide o verbo
    "祀る": (
        "sufragar — quando o objeto for espírito/ancestral/falecido "
        "(ajudar a subir ao céu). Com divindade usar 'cultuar'; com altar/"
        "imagem usar 'consagrar'"
    ),
    # 6A: o usuário escolheu 'oferenda' — preservando o nome do rito
    "玉串": (
        "Oferenda de Gratidão (tamagushi) — ramo de sakaki com tiras de papel "
        "(shide), oferecido nas cerimônias como expressão de gratidão"
    ),
    # J
    "型": (
        "modelo — em uso genérico. Quando for manifestação profética "
        "(prefiguração de um fato futuro) usar 'padrão profético' ou "
        "'prefiguração'"
    ),
    "大乗": (
        "Daijo (o Grande Veículo) — na 1ª menção de cada artigo com a glosa; "
        "depois apenas 'Daijo'"
    ),
    "副霊": (
        "Espírito Secundário — NÃO confundir com 副守護神 ('espírito protetor "
        "secundário'): 副霊 é aspecto da alma humana; 副守護神 é espírito "
        "protetor"
    ),
    "副守護神": (
        "espírito protetor secundário — NÃO confundir com 副霊 ('Espírito "
        "Secundário', aspecto da alma humana)"
    ),
    "正守護神": (
        "espírito protetor guardião — as três formas fixadas são: 正守護神→"
        "'espírito protetor guardião', 主守護神→'espírito protetor "
        "primordial', 副守護神→'espírito protetor secundário'"
    ),
    "智慧証覚": (
        "Chieshōkaku (Inteligência da Percepção Verdadeira) — na 1ª menção de "
        "cada artigo a forma completa; depois apenas 'Chieshōkaku'"
    ),
    "八衢": (
        "Yachimata — estágio intermediário entre o inferno (地獄) e o mundo "
        "dos deuses; usar a MESMA tradução-base de 中幽界/中有界 ('Mundo "
        "Intermediário') com 'Yachimata' entre parênteses na 1ª menção"
    ),
    "中有界": (
        "Mundo Intermediário — MESMA tradução de 中幽界; 八衢 (Yachimata) é "
        "o nome técnico do estágio dentro dele"
    ),
    # H: diferenciar consagrado × caligrafia
    "御軸": (
        "Imagem da Luz Divina — quando consagrada (com 光明如来). Se for "
        "apenas o rolo com a caligrafia, sem consagração, usar 'caligrafia "
        "sagrada'"
    ),
    "御額": (
        "placa caligráfica — obra emoldurada de veneração secundária ao "
        "御神体; não confundir com a Imagem da Luz Divina"
    ),
    # Z
    "御利益": (
        "benefício material — distinguir de 御神徳 ('Virtude Divina'). Onde a "
        "repetição ficar redundante, usar 'graça'"
    ),
    "死霊": (
        "espírito do falecido — com とっつく/取り憑く, 'o espírito do falecido "
        "se gruda / toma posse'"
    ),
    # 念: o valor antigo ('vontade/pensamento') é GENÉRICO demais — o achado
    # mostrou que em contexto devocional 念 é 'invocação/prece interior'.
    "念": (
        "invocação / prece interior — em contexto devocional; em 念じる usar "
        "'orar/implorar'; em 一念 'um só pensamento'. NUNCA 'pensamento' "
        "genérico quando o texto trata de prece"
    ),
}

# --------------------------------------------------------------------------
# 3) TERMOS DE 1 KANJI — orientação para o tradutor, SEM exigência na trava
# --------------------------------------------------------------------------
# (o kanji tem sentidos contextuais; forçar a forma do glossário causava erro
#  real: 国利民福に対しはなだ熱が乏しい → "pouquíssima FEBRE" em vez de
#  "pouco ARDOR")
UM_KANJI_GUIA: dict[str, str] = {
    "熱": "ardor/calor — 'febre' apenas em contexto clínico (発熱/熱がある)",
    "想": "pensar em / imaginar — não confundir com 念 (prece)",
}
NAO_VERIFICAR = [
    "熱", "想", "我", "血", "道", "魂", "疑", "層", "俵", "儂", "咳",
    "曇", "棒", "痔", "癌", "胃", "艮", "祭",
    "心（霊・心・魂の区別）", "念", "型",
    "経（緯と対で使われた場合）", "緯（経と対で使われた場合）",
    "縦", "横",
    "【MEDIDAS — CONVERTER SEMPRE PARA O SISTEMA MÉTRICO】",
    "【ORAÇÕES — REGRA DE USO】",
]

# --------------------------------------------------------------------------
# 4) TRAVAS NEGATIVAS (proibição) — regras do arquivo de regras
# --------------------------------------------------------------------------
PROIBICOES = [
    {
        "proibido_pt": ["possesso", "possessos", "possessa", "possessas"],
        "gatilho_jp": [],
        "motivo": (
            "Em português 'possesso' significa 'raivoso/irritado', não "
            "'possuído por espírito'. Usar 'possuído', 'sob possessão "
            "espiritual' ou 'encostado'."
        ),
        "gravidade": "erro",
    },
    {
        "proibido_pt": ["latitude", "longitude", "latitudes", "longitudes"],
        "gatilho_jp": ["経緯", "経", "緯", "縦", "横"],
        "motivo": (
            "経緯 / 経 / 緯 não são coordenadas geográficas: no sentido de "
            "Meishu-Sama são os eixos VERTICAL e HORIZONTAL (urdidura e trama; "
            "Oriente/Ocidente; espírito/matéria). Usar 'vertical e horizontal'."
        ),
        "gravidade": "erro",
    },
    {
        "proibido_pt": ["shaku", "sun", "ken", "chō", "cho", "ri", "tsubo",
                        "shō", "sho", "gō", "go", "kan", "monme", "hiro",
                        "jō", "jo"],
        "gatilho_jp": ["尺", "寸", "間", "丈", "尋", "町", "里", "坪", "升",
                       "斗", "合", "勺", "貫", "匁"],
        "motivo": (
            "Decisão do projeto: medidas japonesas devem ser SEMPRE "
            "convertidas ao sistema métrico ocidental (cm/m/km/m²/L/kg), sem "
            "transliteração da unidade."
        ),
        "gravidade": "medida",
    },
]

# Idiomatismos em que numeral + kanji NÃO é medida (falsos positivos de 分)
MEDIDAS_EXCECOES = [
    "十分", "自分", "半分", "多分", "充分", "五分五分", "何分", "充分",
    "十分の一", "大部分",
]

# --------------------------------------------------------------------------
# 5) MEDIDAS — tabela de conversão (usada pela auditoria e pelo prompt)
# --------------------------------------------------------------------------
MEDIDAS = {
    "尺": {"fator": 0.30303, "unidade": "m", "exemplo": "三尺 → cerca de 90 cm"},
    "寸": {"fator": 0.030303, "unidade": "m", "exemplo": "一寸 → cerca de 3 cm"},
    "分": {"fator": 0.0030303, "unidade": "m", "exemplo": "一寸八分 → cerca de 5,4 cm"},
    "間": {"fator": 1.8182, "unidade": "m", "exemplo": "二、三十間 → de 36 a 54 m"},
    "丈": {"fator": 3.0303, "unidade": "m", "exemplo": "一丈 → cerca de 3 m"},
    "尋": {"fator": 1.8182, "unidade": "m", "exemplo": "一尋 → cerca de 1,8 m"},
    "町": {"fator": 109.09, "unidade": "m", "exemplo": "一町 → cerca de 109 m"},
    "里": {"fator": 3927.27, "unidade": "m", "exemplo": "一〇里四方 → uns 39 km de lado"},
    "坪": {"fator": 3.3058, "unidade": "m²", "exemplo": "七千五百坪 → cerca de 24.800 m²"},
    "升": {"fator": 1.8039, "unidade": "L", "exemplo": "一升 → cerca de 1,8 L"},
    "斗": {"fator": 18.039, "unidade": "L", "exemplo": "二斗三升 → cerca de 41 L"},
    "合": {"fator": 0.18039, "unidade": "L", "exemplo": "五、六合 → cerca de 1 L"},
    "勺": {"fator": 0.018039, "unidade": "L", "exemplo": "二合五勺 → cerca de 450 mL"},
    "貫": {"fator": 3.75, "unidade": "kg", "exemplo": "一貫 → cerca de 3,75 kg"},
    "匁": {"fator": 0.00375, "unidade": "kg", "exemplo": "一匁 → cerca de 3,75 g"},
}

# --------------------------------------------------------------------------
# 6) PRIMEIRA OCORRÊNCIA POR ARTIGO
# --------------------------------------------------------------------------
PRIMEIRA_OCORRENCIA = {
    "時所位": {"completa": "Jishoi (tempo, local e posição)", "curta": "Jishoi"},
    "位牌": {"completa": "tabuleta mortuária (ihai)", "curta": "tabuleta"},
    "御霊紙": {"completa": "Papel Sagrado (Goreishi)", "curta": "Goreishi"},
    "天津祝詞": {"completa": "Amatsu Norito (Norito Celestial)", "curta": "Norito"},
    "智慧証覚": {"completa": "Chieshōkaku (Inteligência da Percepção Verdadeira)",
                 "curta": "Chieshōkaku"},
    "言霊": {"completa": "espírito da palavra", "curta": "espírito da palavra"},
    "大乗": {"completa": "Daijo (o Grande Veículo)", "curta": "Daijo"},
    "散花結実": {"completa": "A flor cai, o fruto amadurece (sanka-kekijitsu)",
                 "curta": "A flor cai, o fruto amadurece"},
    "三隣亡": {"completa": "Santanbō (três vizinhos arruinados)", "curta": "Santanbō"},
    "大将軍": {"completa": "Daijōgun (a divindade dos oito pontos)", "curta": "Daijōgun"},
    "家相": {"completa": "geomancia da casa (kasō)", "curta": "geomancia da casa"},
    "伊都能売": {"completa": "Izunome", "curta": "Izunome"},
}


def main() -> int:
    dry = "--dry-run" in sys.argv
    glossario: dict = json.loads(GLOSSARIO.read_text(encoding="utf-8"))
    antes = len(glossario)

    novas_de_fato = [k for k in NOVAS if k not in glossario]
    ja_existem = [k for k in NOVAS if k in glossario]
    revisadas = [k for k in REVISOES if k in glossario]
    revisar_ausentes = [k for k in REVISOES if k not in glossario]

    print(f"glossario_traducao.json: {antes} entradas")
    print(f"  novas a inserir ......... {len(novas_de_fato)}")
    if ja_existem:
        print(f"  ⚠️  já existiam (sobrescrever): {ja_existem}")
    print(f"  revisões de existentes .. {len(revisadas)}")
    if revisar_ausentes:
        print(f"  ⚠️  revisões sem entrada (serão CRIADAS): {revisar_ausentes}")

    if dry:
        print("\n(--dry-run: nada foi gravado)")
        return 0

    # backup
    ts = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    bkp = GLOSSARIO.with_suffix(f".json.bak_ajuste_consolidado_{ts}")
    shutil.copy2(GLOSSARIO, bkp)
    print(f"\nbackup: {bkp.name}")

    # aplica
    glossario.update(NOVAS)
    glossario.update(UM_KANJI_GUIA)
    glossario.update(REVISOES)

    GLOSSARIO.write_text(
        json.dumps(glossario, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"gravado: {len(glossario)} entradas (+{len(glossario) - antes})")

    # regras
    regras = {
        "versao": "2026-10-08",
        "origem": (
            "docs/DECISOES_GLOSSARIO_CONSOLIDADO_20261008.md — 1.190 achados "
            "do Claude (kowa_full.txt, 88 lotes) + 6 questões do usuário"
        ),
        "decisoes_usuario": {
            "medidas": "converter SEMPRE para o sistema métrico ocidental",
            "demais": "seguir as recomendações do relatório de decisões",
        },
        "proibicoes": PROIBICOES,
        "medidas": MEDIDAS,
        "medidas_excecoes": MEDIDAS_EXCECOES,
        "primeira_ocorrencia": PRIMEIRA_OCORRENCIA,
        "nao_verificar": sorted(set(NAO_VERIFICAR)),
    }
    if REGRAS.exists():
        bkp2 = REGRAS.with_suffix(f".json.bak_{ts}")
        shutil.copy2(REGRAS, bkp2)
        print(f"backup: {bkp2.name}")
    REGRAS.write_text(
        json.dumps(regras, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"gravado: {REGRAS.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
