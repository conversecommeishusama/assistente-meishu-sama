import sys, json
from pathlib import Path
sys.path.insert(0, "scripts")
from apply_manual_livros_segmentacao import split_by_anchors, load_boundary_file, parse_article, split_file

NAMES = [
    "19550501-浄霊法講座（八）胃・腸疾患\xa0\xa0『浄霊法講座』8号",
    "19530600-A Story of Ukiyo-e",
    "19531015-御垂示録25号",
]

def load_body(path):
    text = Path(path).read_text(encoding="utf-8")
    art = parse_article(text)
    return art

for name in NAMES:
    spec_path = Path(f"reports/livros_trabalho/segmentacao_manual/{name}.txt.json")
    pt_path = Path(f"livros_publicacao_pt_revisado/{name}.txt")
    jp_path = Path(f"reports/livros_trabalho/jp/{name}.txt")
    spec = load_boundary_file(spec_path)
    arts = spec.get("articles", [])
    print("====", name, "n_articles_spec=", len(arts))

    pt_text = pt_path.read_text(encoding="utf-8")
    jp_text = jp_path.read_text(encoding="utf-8")

    pt_art = parse_article(pt_text)
    jp_art = parse_article(jp_text)

    pt_anchors = [a.get("pt_anchor","") for a in arts]
    jp_anchors = [a.get("jp_anchor","") for a in arts]

    try:
        pt_chunks = split_by_anchors(pt_art.content, pt_anchors, label="PT")
        print("  PT split OK:", len(pt_chunks), "chunks")
    except Exception as e:
        print("  PT split FAILED:", e)

    try:
        jp_chunks = split_by_anchors(jp_art.content, jp_anchors, label="JP")
        print("  JP split OK:", len(jp_chunks), "chunks")
    except Exception as e:
        print("  JP split FAILED:", e)
