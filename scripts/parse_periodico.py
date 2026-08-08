"""Parser tolerante para os arquivos de trabalho de periódico
(=== ARTIGO === com metadata1 [+ '---' + metadata2 opcional] + conteúdo)."""
from pathlib import Path

KNOWN_KEYS = {"entry_id", "paired_id", "source_file", "sort_date", "title_jp", "title_pt"}


def parse_meta1(block_lines):
    """Consome linhas 'key: value' reconhecidas no início do bloco.
    Retorna (meta_dict, indice_da_proxima_linha_nao_consumida)."""
    meta = {}
    i = 0
    while i < len(block_lines):
        line = block_lines[i]
        if line.strip() == "---":
            return meta, i + 1, True
        if not line.strip():
            return meta, i, False
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            if k in KNOWN_KEYS:
                meta[k] = v.strip()
                i += 1
                continue
        # linha não reconhecida (ex.: title_jp/title_pt multi-linha por engano) -- aborta
        return meta, i, False
    return meta, i, False


def skip_meta2(lines, start):
    """Depois de '---', há um bloco de metadados redundante (Title:/Publication
    source:/.../Paired...) terminando na primeira linha em branco. Pula até lá."""
    i = start
    while i < len(lines) and lines[i].strip():
        i += 1
    # i aponta pra linha em branco (ou fim)
    return i + 1


def parse_file(path):
    t = Path(path).read_text(encoding="utf-8")
    header, *blocks_raw = t.split("=== ARTIGO ===")
    articles = []
    anomalies = []
    for idx, b in enumerate(blocks_raw):
        b_stripped = b.lstrip("\n")
        lines = b_stripped.split("\n")
        meta, next_i, had_dashes = parse_meta1(lines)
        if had_dashes:
            content_start = skip_meta2(lines, next_i)
        else:
            # pula linha em branco isolada, se houver
            content_start = next_i
            while content_start < len(lines) and not lines[content_start].strip():
                content_start += 1
            anomalies.append((idx, "sem_bloco_meta2_redundante"))
        content = "\n".join(lines[content_start:]).strip("\n")
        missing = KNOWN_KEYS - set(meta.keys())
        if missing:
            anomalies.append((idx, f"campos_ausentes:{missing}"))
        articles.append({"meta": meta, "content": content.strip()})
    return articles, anomalies
