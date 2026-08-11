import hashlib
import json
import pickle
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from translation_header_parser import enrich_entry_from_header, parse_translation_header  # noqa: E402
from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PT_DIR = PROJECT_ROOT / "textos_portugues"
JP_DIR = PROJECT_ROOT / "textos_japones"
PUBLICATION_SOURCES_DIR = PROJECT_ROOT / "data" / "publication_sources"
CLEAN_DIR = PROJECT_ROOT / "data" / "clean_corpus"
STAGING_DIR = PROJECT_ROOT / "experiments" / "rebuilt_large_indexes"
TARGET_DIR = PROJECT_ROOT / "experiments" / "uploaded_indexes"
MODEL_NAME = "intfloat/multilingual-e5-large"
SEGMENTACAO_MANUAL_DIR = PROJECT_ROOT / "reports" / "livros_trabalho" / "segmentacao_manual"


JA_TO_PT_TERMS = [
    ("革命的増産の自然農法解説", "Agricultura Natural Revolucionaria"),
    ("浄 霊法講座", "Curso de Johrei"),
    ("御光話録", "Gosuiji-roku"),
    ("御垂示録", "Gosuiji-roku"),
    ("御教え集", "Coletanea de Ensinamentos"),
    ("御教え", "Ensinamento"),
    ("御讃歌集", "Coletanea de Salmos"),
    ("信仰雑話", "Conversas sobre a Fe"),
    ("天国の福音書", "Evangelho do Reino dos Ceus"),
    ("天国の福音", "Evangelho do Reino dos Ceus"),
    ("アメリカを救う", "Salvando os Estados Unidos"),
    ("世界救世教奇蹟集", "Relatos de Milagres da Igreja Messianica Mundial"),
    ("世界救世教奇跡集", "Relatos de Milagres da Igreja Messianica Mundial"),
    ("世界救世教早わかり", "Guia Rapido da Igreja Messianica Mundial"),
    ("世界メシヤ教手引", "Manual da Igreja Messianica Mundial"),
    ("世界救世教教義解説", "Explicacao da Doutrina da Igreja Messianica Mundial"),
    ("世界救世教教義", "Doutrina da Igreja Messianica Mundial"),
    ("結核信仰療法", "Terapia de Fe para Tuberculose"),
    ("結核の革命的療法", "Terapia Revolucionaria da Tuberculose"),
    ("浄霊法講座", "Curso de Johrei"),
    ("自然農法解説", "Explicacao da Agricultura Natural"),
    ("観音講座", "Curso sobre Kannon"),
    ("御光話録（補）", "Gosuiji-roku Suplemento"),
    ("教えの光", "Luz dos Ensinamentos"),
    ("地上天国出来るまで", "Ate a Construcao do Paraiso Terrestre"),
    ("法難手記", "Memorias da Perseguicao Religiosa"),
    ("笑の泉", "Fonte do Riso"),
    ("一信者の告白", "Confissao de um Fiel"),
    ("新しき暴力", "Nova Violencia"),
    ("或る日の公判スケッチ", "Esboco de um Julgamento"),
    ("山と水", "Montanha e Agua"),
    ("明麿近詠集", "Poemas Recentes de Akemaro"),
    ("奇蹟物語", "Historias de Milagres"),
    ("霊界叢談", "Conversas sobre o Mundo Espiritual"),
    ("無肥料栽培法", "Metodo de Cultivo sem Fertilizantes"),
    ("結核と神霊療法", "Tuberculose e Terapia Espiritual"),
    ("基仏と観音教", "Cristo, Buda e a Fe Kannon"),
    ("怪物か聖者か", "Monstro ou Santo"),
    ("光への道", "Caminho para a Luz"),
    ("神示の健康法", "Metodo de Saude por Revelacao Divina"),
    ("神示の病理", "Patologia por Revelacao Divina"),
    ("自観説話集", "Coletanea de Narrativas Jikan"),
    ("自観隨談", "Dialogos Jikan"),
    ("自観叢書", "Colecao Jikan"),
    ("基督と自観師", "Cristo e Mestre Jikan"),
    ("世界の六大神秘家", "Os Seis Grandes Misticos do Mundo"),
    ("天国の花", "Flores do Paraiso"),
    ("明主様御言葉", "Palavras de Meishu-Sama"),
    ("水晶殿御遷座", "Transferencia ao Templo de Cristal"),
    ("ハワイ教会落成式に賜った御言葉", "Palavras na Cerimonia da Igreja do Havai"),
]

SOURCE_CATEGORY_RULES = [
    ("Gosuiji-roku", re.compile(r"御光話録|御垂示録|gosuiji", re.I)),
    ("Coletanea de Ensinamentos", re.compile(r"御教え集|colet[aâ]nea de ensinamentos", re.I)),
    ("Evangelho do Reino dos Ceus", re.compile(r"天国の福音|evangelho", re.I)),
    ("Eiko", re.compile(r"栄光|gl[oó]ria|eik[oō]", re.I)),
    ("Hikari", re.compile(r"光明|hikari|\bluz\b", re.I)),
    ("Tijotengoku", re.compile(r"地上天国|para[ií]so terrestre|para[ií]so na terra", re.I)),
    ("Jikan Sosho", re.compile(r"自観|jikan|autobserva|observa[cç][oõ]es", re.I)),
    ("Shinko Zatsuwa", re.compile(r"信仰雑話|conversas sobre (a )?f[eé]", re.I)),
    ("Kyusei", re.compile(r"救世|ky[uū]sei|salva[cç][aã]o", re.I)),
    ("Medicina e Johrei", re.compile(r"浄霊|johrei|medicina|tuberculose|結核", re.I)),
    ("Agricultura Natural", re.compile(r"自然農法|agricultura natural|cultivo", re.I)),
    ("Arte", re.compile(r"hakone art museum|ukiyo|arte|美術", re.I)),
]


def strip_extension(name: str) -> str:
    return name[:-4] if name.endswith(".txt") else name


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def ascii_slug(text: str, max_len=120) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "-", text.lower()).strip("-")
    text = re.sub(r"-+", "-", text)
    return (text[:max_len].strip("-") or "sem-titulo")


def clean_heading(text: str) -> str:
    text = normalize_spaces(text)
    text = re.sub(r"^\*+|\*+$", "", text).strip()
    text = text.strip("#-—–─: ")
    text = re.sub(r"^\d{3,6}\s*$", "", text)
    text = re.sub(r"^#\w+\s*", "", text)
    return normalize_spaces(text)


def has_japanese(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff]", text or ""))


def translate_filename_to_pt(filename: str) -> str:
    stem = strip_extension(filename)
    stem = stem.replace("未刊行", "Inedito")
    date = ""
    rest = stem
    match = re.match(r"^(\d{8}|\d{4}0000)[-,]?(.*)$", stem)
    if match:
        date, rest = match.groups()
    translated = rest
    replacements = {
        "補": "Suplemento",
        "地上天国と自然栽培の巻": "Paraiso Terrestre e Agricultura Natural",
        "海外入信者のために": "para adeptos do exterior",
        "薬理批判": "Critica da Farmacologia",
        "結核、喘息、心臓関係の症状について": "Tuberculose, Asma e Sintomas Cardiacos",
        "薬毒病について": "Sobre Doencas por Toxinas Medicamentosas",
        "婦人科": "Ginecologia",
        "胃・腸疾患": "Doencas do Estomago e Intestino",
        "頭　部": "Cabeca",
        "頭 部": "Cabeca",
        "眼・耳・鼻・咽喉・歯科": "Olhos, Ouvidos, Nariz, Garganta e Odontologia",
    }
    for source, target in replacements.items():
        translated = translated.replace(source, target)
    for ja, pt in sorted(JA_TO_PT_TERMS, key=lambda item: len(item[0]), reverse=True):
        translated = translated.replace(ja, pt)
    translated = translated.replace("『", "").replace("』", "")
    translated = translated.replace("（", " (").replace("）", ")")
    translated = translated.replace("号", "")
    translated = re.sub(r"第\s*(\d+)\s*篇", r" Volume \1 ", translated)
    translated = re.sub(r"[（(]\s*[一二三四五六七八九十]\s*[)）]", " ", translated)
    translated = re.sub(r"(Curso de Johrei)\s+\1", r"\1", translated)
    translated = re.sub(r"(Curso de Johrei)\s*nº\s*(\d+)", r"\1 nº \2", translated)
    translated = re.sub(r"(\d+)\s*$", r"nº \1", translated)
    translated = re.sub(r"([A-Za-zÀ-ÿ])n[oº]\s+(\d+)", r"\1 nº \2", translated)
    translated = unicodedata.normalize("NFKC", translated)
    translated = normalize_spaces(translated.strip("- ,"))
    if not translated:
        translated = rest or stem
    return normalize_spaces(f"{date} - {translated}" if date else translated)


def extract_date(filename: str, text: str) -> str:
    match = re.match(r"^(\d{4})(\d{2})(\d{2})", filename)
    if match:
        year, month, day = match.groups()
        if month != "00" and day != "00":
            return f"{year}-{month}-{day}"
        return year
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return ""


def first_content_title(text: str, fallback: str, lang: str) -> str:
    parsed = parse_translation_header(text)
    if parsed and parsed.display_title:
        return parsed.display_title
    for raw_line in text.splitlines()[:80]:
        raw_check = raw_line.strip()
        if raw_check in {"#E", "#S"} or raw_check.startswith("#K") or raw_check.startswith("#W"):
            continue
        line = clean_heading(raw_line)
        if not line:
            continue
        if len(line) > 160:
            continue
        if lang == "pt" and re.search(r"[\u3040-\u30ff\u3400-\u9fff]", line) and not re.search(r"[A-Za-zÀ-ÿ]", line):
            continue
        return line
    return fallback


def source_category(*values: str) -> str:
    haystack = " ".join(v or "" for v in values)
    for category, pattern in SOURCE_CATEGORY_RULES:
        if pattern.search(haystack):
            return category
    return "Outras Fontes"


TEACHING_MARKER_RE = re.compile(r"^#T\s+", re.MULTILINE)
PUBLICATION_METADATA_PREFIXES = (
    "Title:",
    "Publication source:",
    "Original publication",
    "Date:",
    "Language:",
    "Collection ID:",
    "Paired ",
    "Original path:",
    "Display ",
)


SPEAKER_LABEL_RE = re.compile(r"^(Interlocutor|Meishu-Sama):\s*", re.MULTILINE)


def _group_into_turn_units(paragraphs: list[str]) -> list[str]:
    """Agrupa parágrafos em unidades atômicas de corte (Fase 5, 2026-07-14).

    Cada unidade cobre de um rótulo 'Interlocutor:' até (mas sem incluir) o
    próximo 'Interlocutor:' -- ou seja, a pergunta e toda a resposta de
    Meishu-Sama que a segue (inclusive continuações sem rótulo próprio)
    nunca podem ser separadas em pedaços diferentes por split_chunks_by_size;
    o corte por tamanho só pode cair ENTRE unidades, nunca dentro de um par
    pergunta/resposta. Fora de um trecho de diálogo rotulado (a maioria do
    acervo não usa esses rótulos), cada parágrafo continua sendo sua própria
    unidade -- comportamento idêntico ao anterior, sem efeito nesses livros.
    """
    units: list[list[str]] = []
    in_dialogue = False
    expecting_answer = False
    for paragraph in paragraphs:
        is_question = paragraph.startswith("Interlocutor:")
        is_answer_label = paragraph.startswith("Meishu-Sama:")
        if is_question or is_answer_label:
            in_dialogue = True
        if is_question:
            units.append([paragraph])
            expecting_answer = True
        elif is_answer_label:
            # Só funde ao parágrafo anterior se ele for a pergunta que este
            # rótulo responde -- caso contrário (ex.: monólogo cujo primeiro
            # parágrafo rotulado vem logo após uma rubrica cênica sem
            # rótulo), abre unidade própria em vez de grudar num parágrafo
            # não-rotulado anterior sem relação de pergunta/resposta.
            if expecting_answer and units:
                units[-1].append(paragraph)
            else:
                units.append([paragraph])
            expecting_answer = False
        elif not in_dialogue or not units:
            units.append([paragraph])
        else:
            units[-1].append(paragraph)
    return ["\n\n".join(u) for u in units]


def split_chunks_by_size(text: str, max_chars=3200, overlap_chars=220):
    """Divide um único bloco por tamanho (unidades de turno/frases), com overlap interno.

    A unidade de empacotamento é o turno de diálogo (ver
    `_group_into_turn_units`), não o parágrafo cru -- isso garante que um
    corte por tamanho nunca caia entre um parágrafo 'Interlocutor:' e a
    resposta 'Meishu-Sama:' que o segue. Quando uma unidade sozinha (por
    exemplo uma fala muito longa) precisa ser dividida em várias frases por
    exceder max_chars, o rótulo do falante é repetido em CADA pedaço
    resultante -- sem isso, só o primeiro pedaço levaria o rótulo, e os
    pedaços seguintes (perfeitamente possíveis de aparecer isolados numa
    busca) ficariam sem identificação de quem fala.
    """
    raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    paragraphs = []
    for raw_paragraph in raw_paragraphs:
        # Em alguns trechos do corpus a quebra entre 'Interlocutor:' e a
        # resposta 'Meishu-Sama:' seguinte é uma única quebra de linha, sem
        # linha em branco -- o split acima funde os dois turnos num só
        # parágrafo bruto. Se não desmembrado aqui, esse parágrafo fica sem
        # rótulo reconhecível no meio (só no início), podendo ser cortado
        # por tamanho num ponto que separa pergunta de resposta sem que
        # nenhum dos dois pedaços resultantes carregue o rótulo correto.
        parts = re.split(r"\n(?=(?:Interlocutor|Meishu-Sama):)", raw_paragraph)
        paragraphs.extend(part.strip() for part in parts if part.strip())
    turn_units = _group_into_turn_units(paragraphs)
    chunks = []
    current = ""
    for turn_text in turn_units:
        label_match = SPEAKER_LABEL_RE.match(turn_text)
        active_label = label_match.group(0) if label_match else ""
        if len(turn_text) > max_chars:
            sentences = re.split(r"(?<=[.!?。！？])\s+", turn_text)
        else:
            sentences = [turn_text]
        for unit in sentences:
            if not unit:
                continue
            # Uma unidade de turno atomica pode, ela mesma, conter mais de um
            # falante (pergunta + resposta fundidas por _group_into_turn_units
            # quando excede max_chars e precisa ser dividida em frases). Se um
            # rotulo novo aparece no inicio desta frase, ele passa a ser o
            # falante ativo dali em diante -- sem isso, um pedaco que comece
            # bem dentro da resposta de Meishu-Sama continuava herdando o
            # rotulo "Interlocutor:" da pergunta que abriu a unidade inteira,
            # atribuindo a fala errada a quem a recuperasse isoladamente.
            sentence_label_match = SPEAKER_LABEL_RE.match(unit)
            if sentence_label_match:
                active_label = sentence_label_match.group(0)
            # Um novo chunk que comece no meio de uma fala longa (unit sem o
            # rotulo, porque nao e a primeira frase da unidade) precisa
            # levar o rotulo de volta -- senao esse pedaco fica sem
            # identificacao de quem fala se for recuperado isoladamente.
            if not current and active_label and not unit.startswith(active_label):
                unit = active_label + unit
            if current and len(current) + len(unit) + 2 > max_chars:
                # BUG REAL CONFIRMADO 2026-07-14 (御光話録5号): `active_label`
                # não serve para rotular o overlap -- quando uma unidade de
                # turno mesclada (Interlocutor:+Meishu-Sama:) é curta o
                # bastante para NÃO ser subdividida em frases (sentences =
                # [turn_text] inteiro), `active_label`/`sentence_label_match`
                # só enxergam o rótulo no INÍCIO da string inteira
                # ("Interlocutor:"), mesmo que a CAUDA de `current` (o que
                # está prestes a virar overlap) já pertença ao falante
                # seguinte ("Meishu-Sama:", que aparece no MEIO dessa mesma
                # string fundida). A fonte confiável é buscar, no `current`
                # ainda INTEIRO (antes de truncar para o overlap), o ÚLTIMO
                # rótulo que de fato aparece nele (em qualquer posição, não
                # só no início) -- só depois disso truncar para o overlap.
                # BUG REAL CONFIRMADO 2026-07-15 (御光話録14号): o rótulo
                # correto para o INÍCIO do overlap é o último rótulo que
                # aparece ANTES do ponto de corte (`cutoff`), não o último
                # rótulo em todo o `current` -- se a própria janela de
                # overlap contiver a TROCA de falante (um novo rótulo
                # aparecendo dentro dos últimos `overlap_chars`), o rótulo
                # antigo (o que realmente abre o overlap) já está presente
                # em algum lugar do texto truncado só por coincidência (o
                # rótulo novo, não o antigo), e a checagem antiga
                # (`tail_label not in current`) achava isso e pulava o
                # reparo -- deixando o trecho antes da troca sem nenhum
                # rótulo.
                cutoff = max(0, len(current) - overlap_chars)
                label_matches = list(SPEAKER_LABEL_RE.finditer(current))
                labels_before_cutoff = [m for m in label_matches if m.start() < cutoff]
                tail_label = labels_before_cutoff[-1].group(0) if labels_before_cutoff else ""
                # BUG REAL CONFIRMADO 2026-07-14 (御光話録（補）): o corte do
                # overlap por posição fixa (`[-overlap_chars:]`) pode cair
                # bem no MEIO da string literal de um rótulo anterior (ex.
                # corta "Interlocutor:" e sobra só "ocutor:" no início do
                # `current` truncado) -- um rótulo diferente do `tail_label`
                # (que é sempre o ÚLTIMO rótulo do current pré-truncamento),
                # então a checagem abaixo (`tail_label not in current`) não
                # detecta o problema, porque o tail_label real continua
                # presente mais adiante no texto truncado.
                # BUG REAL CONFIRMADO 2026-07-15 (御光話録14号, 2a rodada): a
                # correção anterior reparava esse fragmento casando por
                # SUFIXO TEXTUAL solto (ex. "r:", ":" isolados) -- qualquer
                # palavra comum do PT que termine em "r:" (pensar:, dizer:,
                # fazer:) casava por coincidência com o sufixo mais curto de
                # "Interlocutor:"/"Meishu-Sama:" e ganhava um rótulo
                # fabricado que não existe no texto original (achado real:
                # "...tendência de pensar: "Já que..." virou "Meishu-Sama:
                # Interlocutor: "Já que..."", rótulo inventado no meio de uma
                # frase comum). A fonte confiável é saber se o próprio
                # `cutoff` caiu DENTRO do span de um rótulo real já detectado
                # por `SPEAKER_LABEL_RE` em `current` (antes de truncar) --
                # só nesse caso existe de fato um rótulo cortado ao meio.
                truncated_match = next(
                    (m for m in label_matches if m.start() < cutoff < m.end()), None
                )
                chunks.append(current.strip())
                current = current[-overlap_chars:].strip()
                if truncated_match:
                    cut_len = cutoff - truncated_match.start()
                    fragment = truncated_match.group(0)[cut_len:].strip()
                    if fragment and current.startswith(fragment):
                        current = truncated_match.group(0).strip() + current[len(fragment):]
                # BUG REAL CONFIRMADO 2026-07-15 (御光話録（補）/4号/12号/13号/
                # 御垂示録1-4号/8号/9号/12号/13号/25号/28号, 御教え集6号, achado
                # corpus-wide): a checagem `not current.startswith(tail_label)`
                # só verifica igualdade com o rótulo ANTIGO -- se `current`
                # (após o corte) já começa, por coincidência de posição, com
                # um rótulo DIFERENTE e genuíno (a truncagem caiu bem no
                # limite entre um turno e o próximo, então o pedaço cortado já
                # abre com o rótulo real do turno seguinte), a checagem não
                # reconhece esse rótulo já presente e prepend o `tail_label`
                # de qualquer forma, produzindo 2 rótulos colados
                # ("Interlocutor: Meishu-Sama: ..."). A fonte confiável é
                # perguntar se `current` já começa com QUALQUER rótulo válido,
                # não apenas com o `tail_label` específico.
                if tail_label and not SPEAKER_LABEL_RE.match(current):
                    current = tail_label + current if current else ""
            current = f"{current}\n\n{unit}".strip() if current else unit
    if current:
        chunks.append(current.strip())
    return chunks


def split_teaching_units(text: str) -> list[str]:
    """Separa coletâneas em ensinamentos (#T). Arquivo inteiro = 1 unidade se não houver #T."""
    if not TEACHING_MARKER_RE.search(text or ""):
        return [text.strip()] if (text or "").strip() else []

    parts = re.split(r"(?=^#T\s+)", text, flags=re.MULTILINE)
    units: list[str] = []
    preamble = ""
    for part in parts:
        if not part.strip():
            continue
        if part.lstrip().startswith("#T"):
            if preamble.strip():
                units.append(preamble.strip())
                preamble = ""
            units.append(part.strip())
        else:
            preamble = f"{preamble}\n\n{part}".strip() if preamble else part.strip()
    if preamble.strip():
        units.append(preamble.strip())
    return units or ([text.strip()] if text.strip() else [])


# Determinação do usuário, 2026-07-14: a segmentação é SEMPRE pela divisão
# estrutural do autor. O corte por contagem de caractere foi autorizado
# exclusivamente para as três séries de palavra oral, porque uma sessão de um
# dia inteiro de diálogo não tem outra divisão natural além da data.
#
# BUG CORRIGIDO 2026-08-07: esta regra nunca chegou a ser implementada. O
# `profile` existe em todas as 137 specs e NUNCA era lido por este script --
# a exceção das 3 séries orais virava regra geral por omissão, e 1.077
# unidades de palavra escrita (artigos de periódico, experiências de fé,
# aulas, capítulos, poemas, hinos, depoimentos) eram partidas por tamanho em
# 50 obras. Achado pela regra G4 de scripts/varredura_padronizacao.py.
PERFIS_PALAVRA_ORAL = {"gokowa_roku_qa", "ochishiji_roku", "mioshie_shu"}


def pode_cortar_por_tamanho(profile: str | None) -> bool:
    """Só as 3 séries de palavra oral podem ser cortadas por contagem.

    `profile is None` significa arquivo SEM spec de segmentação -- não existe
    divisão do autor registrada para proteger, e tratar o livro inteiro como
    uma unidade daria chunks absurdos (medido: 134.407 caracteres em
    `自観叢書第6篇『怪物か聖者か』`, que é livro inteiro, não artigo). Nesses
    casos mantém o comportamento anterior. São os 4 arquivos de
    `textos_portugues/` fora do acervo curado de 137 obras -- três da série
    Jikan Sōsho escritos por terceiros e um manual de doutrina.
    """
    return profile is None or profile in PERFIS_PALAVRA_ORAL


def split_chunks(text: str, max_chars=3200, overlap_chars=220, *, cortar_por_tamanho=True):
    """Híbrido: nunca corta entre ensinamentos (#T); só subdivide por tamanho dentro de cada um.

    `cortar_por_tamanho=False` (palavra escrita) devolve a unidade autoral
    inteira, por mais longa que seja -- é a determinação de 14/07.
    """
    if not cortar_por_tamanho:
        unidades = [u.strip() for u in split_teaching_units(text) if u.strip()]
        return unidades or ([text.strip()] if text.strip() else [])
    all_chunks: list[str] = []
    for unit in split_teaching_units(text):
        all_chunks.extend(split_chunks_by_size(unit, max_chars=max_chars, overlap_chars=overlap_chars))
    return all_chunks


def strip_publication_metadata(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith(PUBLICATION_METADATA_PREFIXES):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def read_publication_file_body(path: Path) -> str:
    return clean_body(strip_publication_metadata(read_text(path)))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def clean_body(text: str) -> str:
    cleaned = []
    for line in text.splitlines():
        raw = line.rstrip()
        raw_check = raw.strip()
        # BUG REAL CONFIRMADO 2026-07-15: a checagem original rodava sobre
        # clean_heading(raw), mas clean_heading() já remove o prefixo "#"
        # (text.strip("#-—–─: ")) antes da checagem de tag rodar -- ou seja,
        # "#K...", "#E", "#S", "#W80" nunca batiam com startswith("#K")/etc.,
        # e essas linhas de metadado estrutural (incluindo citações de fonte
        # como "岡田茂吉全集...") vazavam para o texto limpo/indexado.
        # Checagem agora roda sobre a linha só com espaço removido, antes de
        # clean_heading() mexer nela.
        if (raw_check in {"#E", "#S"} or raw_check.startswith("#K")
                or raw_check.startswith("#W") or raw_check.startswith("#T")):
            continue
        # BUG REAL CONFIRMADO 2026-08-11: a linha divisória pura (só
        # "─"/"-"/"—" repetidos) checava contra `clean_heading(raw)`, que
        # aplica `.strip("#-—–─: ")` -- pra uma linha feita 100% desses
        # caracteres, isso zera a string inteira. `fullmatch` numa string
        # vazia nunca bate com "{5,}", então a linha nunca era reconhecida
        # como divisor e sobrevivia intacta (achado em 天国の福音書/信仰雑話,
        # 735/630 divisórias vazando pro texto limpo). Checa contra
        # `raw_check` (só rstrip/strip, sem clean_heading) em vez disso.
        if re.fullmatch(r"[─ー\-—–]{5,}", raw_check):
            # a divisória cumpria a função de separar título/citação/corpo
            # em blocos -- removê-la sem deixar rastro colava os três num
            # "\n" só, quando o resto do acervo usa "\n\n" entre eles
            # (mesmo padrão de 自観説話集, a referência citada em 04/08).
            # Uma linha vazia no lugar dela produz o "\n\n" de volta.
            cleaned.append("")
            continue
        cleaned.append(raw)
    text = "\n".join(cleaned)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def _load_spec_for(original_filename: str) -> dict | None:
    spec_path = SEGMENTACAO_MANUAL_DIR / f"{original_filename}.json"
    if not spec_path.exists():
        return None
    try:
        return json.loads(spec_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def article_entries_from_spec(path: Path, lang: str, paired_path: Path | None, spec: dict) -> list[dict] | None:
    """Gera 1 entrada por artigo usando as âncoras de segmentacao_manual/*.json
    (2026-07-14) -- em vez de tratar o livro inteiro como 1 bloco, corta pela
    própria divisão do autor (sessão/capítulo/item, o que a spec já registra),
    reaproveitando split_by_anchors (a mesma função que
    apply_manual_livros_segmentacao.py já usa e que está testada). Se a spec
    tiver qualquer âncora vazia ou não encontrada no corpo, retorna None --
    quem chama cai de volta no comportamento antigo (arquivo inteiro), nunca
    quebra o build por causa de uma spec incompleta.
    """
    articles = spec.get("articles", [])
    if len(articles) <= 1:
        return None
    anchor_field = "jp_anchor" if lang == "jp" else "pt_anchor"
    anchors = [a.get(anchor_field, "") for a in articles]
    if not all(anchors):
        return None
    text = clean_body(read_text(path))
    try:
        chunks = split_by_anchors(text, anchors, label=path.name)
    except ValueError:
        return None
    if len(chunks) != len(articles):
        return None

    original_filename = path.name
    translated_source = translate_filename_to_pt(original_filename)
    date = extract_date(original_filename, text)
    category = source_category(original_filename, translated_source, "", text[:500])
    base_id = hashlib.sha1(f"{lang}:{original_filename}".encode("utf-8")).hexdigest()[:16]
    title_field = "title_jp" if lang == "jp" else "title_pt"

    entries = []
    for i, (art, body) in enumerate(zip(articles, chunks), start=1):
        title = art.get(title_field) or first_content_title(body, translated_source, lang)
        entry = {
            "entry_id": f"{base_id}__art{i:03d}",
            "entry_type": "file",
            "lang": lang,
            "title": title,
            "display_source_name": translated_source,
            "display_source_name_pt": translated_source,
            "display_source_name_jp": strip_extension(original_filename),
            "source_category": category,
            "source_date": date,
            "original_filename": original_filename,
            "original_path": str(path.relative_to(PROJECT_ROOT)),
            "paired_original_filename": paired_path.name if paired_path else "",
            "has_parallel": bool(paired_path),
            "body": body,
            "cortar_por_tamanho": pode_cortar_por_tamanho(spec.get("profile")),
        }
        entries.append(enrich_entry_from_header(entry))
    return entries


def file_entry(path: Path, lang: str, paired_path: Path | None):
    text = clean_body(read_text(path))
    original_filename = path.name
    translated_source = translate_filename_to_pt(original_filename)
    date = extract_date(original_filename, text)
    title = first_content_title(text, translated_source, lang)
    if lang == "pt":
        public_source = translated_source
    else:
        public_source = translated_source
    category = source_category(original_filename, translated_source, title, text[:500])
    entry = {
        "entry_id": hashlib.sha1(f"{lang}:{original_filename}".encode("utf-8")).hexdigest()[:16],
        "entry_type": "file",
        "lang": lang,
        "title": title,
        "display_source_name": public_source,
        "display_source_name_pt": translated_source,
        "display_source_name_jp": strip_extension(original_filename),
        "source_category": category,
        "source_date": date,
        "original_filename": original_filename,
        "original_path": str(path.relative_to(PROJECT_ROOT)),
        "paired_original_filename": paired_path.name if paired_path else "",
        "has_parallel": bool(paired_path),
        "body": text,
        # Livro inteiro como uma entrada só: os `monolith` e os de artigo
        # único caem aqui (article_entries_from_spec devolve None para spec
        # com <= 1 artigo). O `profile` continua valendo -- não há divisão do
        # autor a respeitar, mas também não há autorização para cortar.
        "cortar_por_tamanho": pode_cortar_por_tamanho(
            (_load_spec_for(original_filename) or {}).get("profile")),
    }
    return enrich_entry_from_header(entry)


def _publication_body_entry(raw: dict, body: str, index: int, lang: str) -> dict:
    source = raw.get("source_category") or "Fonte Sem Periódico Identificado"
    title = raw.get("title") or "Sem titulo"
    if lang == "pt" and has_japanese(title):
        title = "Sem titulo"
    date = raw.get("source_date") or ""
    display_pt = source if title == "Sem titulo" else f"{source} - {title}"
    display_jp = f"{source} - {title}"
    clean_path = raw.get("clean_path", "")
    entry = {
        "entry_id": raw.get("entry_id") or f"publication-{lang}-{index:04d}",
        "entry_type": "publication_source",
        "lang": lang,
        "title": title,
        "display_source_name": display_pt,
        "display_source_name_pt": display_pt,
        "display_source_name_jp": display_jp,
        "source_category": source,
        "source_date": date,
        "original_filename": Path(clean_path).name if clean_path else "",
        "original_path": clean_path,
        "paired_original_filename": "",
        "has_parallel": True,
        "original_publication_reference": raw.get("original_publication_reference", ""),
        "body": body,
    }
    return enrich_entry_from_header(entry)


def publication_source_entries():
    path = PUBLICATION_SOURCES_DIR / "entries.jsonl"
    if not path.exists():
        return []
    entries = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = json.loads(line)
        lang = raw["lang"]
        clean_path = raw.get("clean_path", "")
        disk_path = PROJECT_ROOT / clean_path if clean_path else None
        if disk_path and disk_path.exists():
            body = read_publication_file_body(disk_path)
        else:
            body = raw.get("body", "")
        entries.append(_publication_body_entry(raw, body, index, lang))
    return entries


def collect_entries():
    entries = []
    for lang, directory, paired_directory in (("pt", PT_DIR, JP_DIR), ("jp", JP_DIR, PT_DIR)):
        for path in sorted(directory.glob("*.txt")):
            paired = paired_directory / path.name
            paired_path = paired if paired.exists() else None
            spec = _load_spec_for(path.name)
            article_entries = article_entries_from_spec(path, lang, paired_path, spec) if spec else None
            if article_entries:
                entries.extend(article_entries)
            else:
                entries.append(file_entry(path, lang, paired_path))
    entries.extend(publication_source_entries())
    return entries


def write_clean_corpus(entries):
    if CLEAN_DIR.exists():
        shutil.rmtree(CLEAN_DIR)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        lang_dir = CLEAN_DIR / entry["lang"] / ascii_slug(entry["source_category"])
        lang_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{entry['source_date'] or 'sem-data'}-{ascii_slug(entry['display_source_name_pt'])}-{entry['entry_id']}.txt"
        content = (
            f"Title: {entry['title']}\n"
            f"Display source: {entry['display_source_name']}\n"
            f"Display source PT: {entry['display_source_name_pt']}\n"
            f"Display source JP: {entry['display_source_name_jp']}\n"
            f"Category: {entry['source_category']}\n"
            f"Date: {entry['source_date']}\n"
            f"Language: {entry['lang']}\n"
            f"Original path: {entry['original_path']}\n"
            f"Has parallel: {entry['has_parallel']}\n"
        )
        if entry.get("header_type"):
            content += f"Header type: {entry['header_type']}\n"
        if entry.get("issue_number"):
            content += f"Issue number: {entry['issue_number']}\n"
        if entry.get("session_date"):
            content += f"Session date: {entry['session_date']}\n"
        if entry.get("publication_source"):
            content += f"Publication source: {entry['publication_source']}\n"
        content += f"\n{entry['body'].strip()}\n"
        (lang_dir / filename).write_text(content, encoding="utf-8")
        entry["clean_path"] = str((lang_dir / filename).relative_to(PROJECT_ROOT))
    with (CLEAN_DIR / "entries.jsonl").open("w", encoding="utf-8") as file:
        for entry in entries:
            slim = dict(entry)
            slim.pop("body", None)
            file.write(json.dumps(slim, ensure_ascii=False) + "\n")
    summary = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "total_entries": len(entries),
        "by_lang": dict(Counter(entry["lang"] for entry in entries)),
        "by_type": dict(Counter(entry["entry_type"] for entry in entries)),
        "by_category": dict(Counter(entry["source_category"] for entry in entries)),
        "missing_parallel": [entry["original_path"] for entry in entries if entry["entry_type"] == "file" and not entry["has_parallel"]],
    }
    (CLEAN_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def build_chunks(entries, lang):
    chunks = []
    metadata = []
    for entry in entries:
        if entry["lang"] != lang:
            continue
        cortar = entry.get("cortar_por_tamanho", True)
        for chunk_index, chunk in enumerate(
            split_chunks(entry["body"], cortar_por_tamanho=cortar), start=1
        ):
            if len(chunk.strip()) < 40:
                continue
            chunks.append(chunk)
            metadata.append(
                {
                    "fonte": entry["display_source_name"],
                    "titulo": entry["title"],
                    "conteudo": chunk,
                    "arquivo": entry["original_filename"],
                    "arquivo_original": entry["original_filename"],
                    "fonte_pt": entry["display_source_name_pt"],
                    "fonte_jp": entry["display_source_name_jp"],
                    "categoria": entry["source_category"],
                    "data": entry["source_date"],
                    "idioma": entry["lang"],
                    "entry_id": entry["entry_id"],
                    "entry_type": entry["entry_type"],
                    "clean_path": entry.get("clean_path", ""),
                    "chunk_index": chunk_index,
                    "header_type": entry.get("header_type", ""),
                    "obra": entry.get("work_name") or entry.get("publication_source", ""),
                    "numero_edicao": entry.get("issue_number", ""),
                    "data_sessao": entry.get("session_date", ""),
                }
            )
    return chunks, metadata


RE_FRASE = re.compile(r"(?<=[.!?。！？])\s+|\n{2,}")


def amostra_para_embedding(corpo: str, tokenizer, orcamento: int) -> str:
    """Representação do corpo que cabe na janela do modelo de embedding.

    O multilingual-e5-large trunca em 512 tokens (~2.100 caracteres em
    português). Um artigo escrito inteiro -- que desde 2026-08-07 é uma
    unidade só, por determinação do usuário -- passa disso na maioria dos
    casos: a mediana dos artigos de periódico é 3.704 caracteres e o maior
    tem 57.930. Truncar simplesmente deixaria o modelo ver só a abertura, e o
    que fosse tratado no meio ou no fim do artigo nunca seria alcançado pela
    busca semântica.

    Em vez de truncar, monta uma amostra: a abertura (onde o autor quase
    sempre anuncia o tema) mais frases distribuídas por igual ao longo do
    resto. A cobertura temática passa a ser do artigo inteiro. A busca
    literal (`buscar_termo`, grep no texto cru) continua alcançando qualquer
    frase exata, então a amostragem não cria ponto cego de recuperação --
    só troca precisão literal por cobertura, na perna onde isso é o certo.
    """
    def n_tokens(s: str) -> int:
        return len(tokenizer.encode(s, add_special_tokens=False))

    if n_tokens(corpo) <= orcamento:
        return corpo

    frases = [f.strip() for f in RE_FRASE.split(corpo) if f and f.strip()]
    if len(frases) <= 1:
        return corpo

    def corta_em(s: str, teto: int) -> str:
        """Corta a frase para caber em `teto` tokens, sem partir palavra."""
        if n_tokens(s) <= teto:
            return s
        proporcao = teto / max(1, n_tokens(s))
        cortada = s[: max(20, int(len(s) * proporcao))].rsplit(" ", 1)[0]
        while cortada and n_tokens(cortada) > teto:
            cortada = cortada[: int(len(cortada) * 0.85)].rsplit(" ", 1)[0]
        return cortada

    escolhidas: list[tuple[int, str]] = []
    usado = 0

    # Abertura: metade do orçamento. É onde o autor costuma anunciar o tema.
    teto_abertura = orcamento // 2
    i = 0
    while i < len(frases):
        custo = n_tokens(frases[i]) + 1
        if usado + custo > teto_abertura:
            break
        escolhidas.append((i, frases[i]))
        usado += custo
        i += 1
    if not escolhidas:  # a primeira frase sozinha já estoura
        return corta_em(frases[0], orcamento)

    # Resto: vagas de tamanho FIXO distribuídas por igual até o fim do artigo.
    # Preencher em ordem até o orçamento acabar faria a amostra parar no meio
    # -- medido: num artigo de 25.857 caracteres, cobria só os 3 primeiros
    # quintos. Reservar a vaga antes de preencher garante que a última frase
    # amostrada venha do fim do texto.
    restantes = list(range(i, len(frases)))
    if restantes:
        sobra = orcamento - usado
        vagas = max(1, min(len(restantes), sobra // 28))
        por_vaga = max(12, sobra // vagas)
        passo = len(restantes) / vagas
        for k in range(vagas):
            j = restantes[min(len(restantes) - 1, int(k * passo))]
            if any(idx == j for idx, _ in escolhidas):
                continue
            frag = corta_em(frases[j], por_vaga - 1)
            if not frag:
                continue
            custo = n_tokens(frag) + 1
            if usado + custo > orcamento:
                break
            escolhidas.append((j, frag))
            usado += custo

    escolhidas.sort()
    return " ".join(f for _, f in escolhidas)


def write_index(chunks, metadata, lang, model):
    tokenizer = model.tokenizer
    limite = model.max_seq_length or 512
    embedding_texts = []
    for chunk, meta in zip(chunks, metadata):
        cabecalho = (
            f"Fonte: {meta['fonte']}\n"
            f"Titulo: {meta['titulo']}\n"
            f"Categoria: {meta['categoria']}\n"
            + (f"Obra: {meta['obra']}\n" if meta.get("obra") else "")
            + (f"Edicao: {meta['numero_edicao']}\n" if meta.get("numero_edicao") else "")
            + (f"Data sessao: {meta['data_sessao']}\n" if meta.get("data_sessao") else "")
        )
        # 4 tokens de folga para os marcadores especiais do modelo
        orcamento = limite - len(tokenizer.encode(cabecalho, add_special_tokens=False)) - 4
        corpo = amostra_para_embedding(chunk, tokenizer, max(64, orcamento))
        embedding_texts.append(f"{cabecalho}\n{corpo}")
    embeddings = model.encode(embedding_texts, batch_size=32, show_progress_bar=True, convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    with (STAGING_DIR / f"chunks_{lang}.pkl").open("wb") as file:
        pickle.dump(chunks, file)
    with (STAGING_DIR / f"metadados_{lang}.pkl").open("wb") as file:
        pickle.dump(metadata, file)
    faiss.write_index(index, str(STAGING_DIR / f"indice_{lang}.faiss"))
    return {"lang": lang, "chunks": len(chunks), "dimension": embeddings.shape[1]}


def build_indexes(entries, langs=("pt", "jp")):
    # 2026-07-17: aceita reconstrucao parcial por idioma (--lang), para nao
    # regastar tempo reprocessando um idioma cujo corpus fonte nao mudou.
    # So limpa STAGING_DIR inteiro quando os dois idiomas serao refeitos;
    # em rebuild parcial, preserva os arquivos do idioma nao solicitado
    # (devem ja existir de um build anterior -- ver aviso em main()).
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    if set(langs) == {"pt", "jp"}:
        for old in STAGING_DIR.glob("*"):
            old.unlink() if old.is_file() else shutil.rmtree(old)
    else:
        for lang in langs:
            for name in (f"chunks_{lang}.pkl", f"metadados_{lang}.pkl", f"indice_{lang}.faiss"):
                path = STAGING_DIR / name
                if path.exists():
                    path.unlink()
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    report = {"model": MODEL_NAME, "indexes": []}
    for lang in langs:
        chunks, metadata = build_chunks(entries, lang)
        report["indexes"].append(write_index(chunks, metadata, lang, model))
    # Preserva no relatorio final os idiomas nao reprocessados nesta rodada,
    # se o build_report.json anterior existir (para o campo "indexes" sempre
    # refletir os dois idiomas, mesmo em rebuild parcial).
    prior_report_path = STAGING_DIR / "build_report.json"
    if set(langs) != {"pt", "jp"} and prior_report_path.exists():
        try:
            prior = json.loads(prior_report_path.read_text(encoding="utf-8"))
            done_langs = {idx["lang"] for idx in report["indexes"]}
            for idx in prior.get("indexes", []):
                if idx.get("lang") not in done_langs:
                    report["indexes"].append(idx)
        except Exception:
            pass
    (STAGING_DIR / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def install_indexes():
    backup_dir = TARGET_DIR.parent / f"uploaded_indexes_backup_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    if TARGET_DIR.exists() and any(TARGET_DIR.iterdir()):
        shutil.copytree(TARGET_DIR, backup_dir)
        shutil.rmtree(TARGET_DIR)
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("chunks_pt.pkl", "metadados_pt.pkl", "indice_pt.faiss", "chunks_jp.pkl", "metadados_jp.pkl", "indice_jp.faiss", "build_report.json"):
        shutil.copy2(STAGING_DIR / name, TARGET_DIR / name)
    return str(backup_dir.relative_to(PROJECT_ROOT)) if backup_dir.exists() else ""


def validate(entries):
    problems = defaultdict(list)
    for entry in entries:
        if entry["lang"] == "pt" and re.search(r"[\u3040-\u30ff\u3400-\u9fff]", entry["display_source_name"]):
            problems["pt_display_has_japanese"].append(entry["original_path"])
        if not entry["title"] or entry["title"] == "Sem titulo":
            problems["missing_title"].append(entry["original_path"])
        if not entry["body"].strip():
            problems["empty_body"].append(entry["original_path"])
    return {key: values[:50] for key, values in problems.items()}


def chunk_summary(entries):
    return {lang: len(build_chunks(entries, lang)[0]) for lang in ("pt", "jp")}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build clean e5-large Goshinsho indexes.")
    parser.add_argument("--install", action="store_true", help="Replace experiments/uploaded_indexes after a successful build.")
    parser.add_argument("--skip-index", action="store_true", help="Only rebuild clean corpus and metadata reports.")
    parser.add_argument(
        "--lang", choices=["pt", "jp", "both"], default="both",
        help="Reconstroi so um idioma (economiza tempo quando o outro corpus fonte nao mudou). "
             "Exige que o idioma NAO selecionado ja tenha chunks/indice/metadados em experiments/rebuilt_large_indexes/ "
             "de um build anterior -- o script para com erro se faltar.",
    )
    args = parser.parse_args()
    langs = ("pt", "jp") if args.lang == "both" else (args.lang,)
    if set(langs) != {"pt", "jp"}:
        other_lang = ("pt" if "pt" not in langs else "jp")
        missing = [
            name for name in (f"chunks_{other_lang}.pkl", f"metadados_{other_lang}.pkl", f"indice_{other_lang}.faiss")
            if not (STAGING_DIR / name).exists()
        ]
        if missing:
            raise SystemExit(
                f"--lang {args.lang} exige build anterior completo para '{other_lang}' em {STAGING_DIR} "
                f"(faltando: {missing}). Rode --lang both pelo menos uma vez antes."
            )

    entries = collect_entries()
    summary = write_clean_corpus(entries)
    validation = validate(entries)
    chunks = chunk_summary(entries)
    (CLEAN_DIR / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"clean_summary": summary, "chunk_summary": chunks, "validation": validation}, ensure_ascii=False, indent=2))
    if not args.skip_index:
        report = build_indexes(entries, langs=langs)
        print(json.dumps({"index_report": report}, ensure_ascii=False, indent=2))
        if args.install:
            backup = install_indexes()
            print(json.dumps({"installed": str(TARGET_DIR), "backup": backup}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
