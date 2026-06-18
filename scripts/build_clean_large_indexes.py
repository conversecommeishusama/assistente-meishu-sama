import hashlib
import json
import pickle
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PT_DIR = PROJECT_ROOT / "textos_portugues"
JP_DIR = PROJECT_ROOT / "textos_japones"
PUBLICATION_SOURCES_DIR = PROJECT_ROOT / "data" / "publication_sources"
CLEAN_DIR = PROJECT_ROOT / "data" / "clean_corpus"
STAGING_DIR = PROJECT_ROOT / "experiments" / "rebuilt_large_indexes"
TARGET_DIR = PROJECT_ROOT / "experiments" / "uploaded_indexes"
MODEL_NAME = "intfloat/multilingual-e5-large"


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
    for line in text.splitlines()[:80]:
        line = clean_heading(line)
        if not line:
            continue
        if line in {"#E", "#S"} or line.startswith("#K") or line.startswith("#W"):
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


def split_chunks(text: str, max_chars=3200, overlap_chars=220):
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    chunks = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            sentences = re.split(r"(?<=[.!?。！？])\s+", paragraph)
        else:
            sentences = [paragraph]
        for unit in sentences:
            if not unit:
                continue
            if current and len(current) + len(unit) + 2 > max_chars:
                chunks.append(current.strip())
                current = current[-overlap_chars:].strip()
            current = f"{current}\n\n{unit}".strip() if current else unit
    if current:
        chunks.append(current.strip())
    return chunks


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def clean_body(text: str) -> str:
    cleaned = []
    for line in text.splitlines():
        raw = line.rstrip()
        stripped = clean_heading(raw)
        if stripped in {"#E", "#S"} or stripped.startswith("#K") or stripped.startswith("#W"):
            continue
        if re.fullmatch(r"[─ー\-—–]{5,}", stripped):
            continue
        cleaned.append(raw)
    text = "\n".join(cleaned)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


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
    return {
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
    }


def publication_source_entries():
    path = PUBLICATION_SOURCES_DIR / "entries.jsonl"
    if not path.exists():
        return []
    entries = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = json.loads(line)
        lang = raw["lang"]
        source = raw.get("source_category") or "Fonte Sem Periódico Identificado"
        title = raw.get("title") or "Sem titulo"
        if lang == "pt" and has_japanese(title):
            title = "Sem titulo"
        date = raw.get("source_date") or ""
        display_pt = source if title == "Sem titulo" else f"{source} - {title}"
        display_jp = f"{source} - {title}"
        entries.append(
            {
                "entry_id": raw.get("entry_id") or f"publication-{lang}-{index:04d}",
                "entry_type": "publication_source",
                "lang": lang,
                "title": title,
                "display_source_name": display_pt,
                "display_source_name_pt": display_pt,
                "display_source_name_jp": display_jp,
                "source_category": source,
                "source_date": date,
                "original_filename": Path(raw.get("clean_path", "")).name,
                "original_path": raw.get("clean_path", ""),
                "paired_original_filename": "",
                "has_parallel": True,
                "original_publication_reference": raw.get("original_publication_reference", ""),
                "body": raw.get("body", ""),
            }
        )
    return entries


def collect_entries():
    entries = []
    for lang, directory, paired_directory in (("pt", PT_DIR, JP_DIR), ("jp", JP_DIR, PT_DIR)):
        for path in sorted(directory.glob("*.txt")):
            paired = paired_directory / path.name
            entries.append(file_entry(path, lang, paired if paired.exists() else None))
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
            f"Has parallel: {entry['has_parallel']}\n\n"
            f"{entry['body'].strip()}\n"
        )
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
        for chunk_index, chunk in enumerate(split_chunks(entry["body"]), start=1):
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
                }
            )
    return chunks, metadata


def write_index(chunks, metadata, lang, model):
    embedding_texts = [
        f"Fonte: {meta['fonte']}\nTitulo: {meta['titulo']}\nCategoria: {meta['categoria']}\n\n{chunk}"
        for chunk, meta in zip(chunks, metadata)
    ]
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


def build_indexes(entries):
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    report = {"model": MODEL_NAME, "indexes": []}
    for lang in ("pt", "jp"):
        chunks, metadata = build_chunks(entries, lang)
        report["indexes"].append(write_index(chunks, metadata, lang, model))
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
    args = parser.parse_args()

    entries = collect_entries()
    summary = write_clean_corpus(entries)
    validation = validate(entries)
    chunks = chunk_summary(entries)
    (CLEAN_DIR / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"clean_summary": summary, "chunk_summary": chunks, "validation": validation}, ensure_ascii=False, indent=2))
    if not args.skip_index:
        report = build_indexes(entries)
        print(json.dumps({"index_report": report}, ensure_ascii=False, indent=2))
        if args.install:
            backup = install_indexes()
            print(json.dumps({"installed": str(TARGET_DIR), "backup": backup}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
