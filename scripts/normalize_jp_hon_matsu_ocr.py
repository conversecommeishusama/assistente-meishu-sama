#!/usr/bin/env python3
"""Corrige erros OCR 末↔本 no acervo japonês (publication_sources + periodicos_trabalho).

Hipótese: extração PDF leu 本 (hon) como 末 (matsu). Ordem das substituições importa.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import source_roots, work_root  # noqa: E402
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "translation_review"

# (old, new, rule_id) — mais específico primeiro
JP_OCR_REPLACEMENTS: tuple[tuple[str, str, str], ...] = (
    # passagem 1–2 (já aplicada; mantida para idempotência)
    ("大末教", "大本教", "daihonkyo"),
    ("日末医術", "日本医術", "nihon_iryo"),
    ("日末農法", "日本農法", "nihon_noho"),
    ("日末住血吸虫", "日本住血吸虫", "nihon_schisto"),
    ("日末観音", "日本観音", "nihon_kannon"),
    ("在日末", "在日本", "zainihon"),
    ("日末人", "日本人", "nihonjin"),
    ("日末画", "日本画", "nihonga"),
    ("日末文化", "日本文化", "nihon_bunka"),
    ("日末", "日本", "nihon"),
    ("末教刉", "本教刊", "honkyo_kan"),
    ("末医術", "本医術", "hon_iryo"),
    ("末療法", "本療法", "hon_ryoho"),
    ("末教", "本教", "honkyo"),
    ("御末人", "御本人", "gohonjin"),
    ("基末", "基本", "kihon"),
    # 末当→本当: regex em transform_jp (não em 末当地)
    ("末文", "本文", "honbun"),
    ("末来", "未来", "mirai"),
    ("末著", "本著", "honcho"),
    ("末誌", "本誌", "honshi"),
    ("末紙", "本紙", "honshi_paper"),
    ("末体", "本体", "hontai"),
    ("御末尊", "御本尊", "gohonzon"),
    # passagem 3 — tier 1 (auditoria 2026-06-22)
    ("資末为義", "資本主義", "shihon_shugi"),
    ("資末家", "資本家", "shihon_ka"),
    ("大資末", "大資本", "dai_shihon"),
    ("資末", "資本", "shihon"),
    ("全部末人扊記", "全部本人扊記", "zenbu_honjin"),
    ("本教仮末部", "本教仮本部", "honkyo_kari_honbu"),
    ("大成会末部", "大成会本部", "taiseikai_honbu"),
    ("一度末法", "一度本法", "ichido_honpo"),
    ("他力末願", "他力本願", "tariki_hongan"),
    ("一大末願", "一大本願", "ichidai_hongan"),
    ("大末信徒", "大本信徒", "daihon_shinto"),
    ("いまの大末", "いまの大本", "ima_no_daihon"),
    ("末農法宠", "本農法宠", "hon_noho_cho"),
    ("末農法", "本農法", "hon_noho"),
    ("末栽培者", "本栽培者", "hon_saibai_sha"),
    ("末栽培", "本栽培", "hon_saibai"),
    ("土未来", "土本来", "do_honrai"),
    ("末守護神", "本守護神", "hon_shugoshin"),
    ("末美術館", "本美術館", "hon_bijutsukan"),
    ("末格的活", "本格的活", "honkakuteki_katsu"),
    ("末格的", "本格的", "honkakuteki"),
    ("末質的", "本質的", "honshitsuteki"),
    ("末質", "本質", "honshitsu"),
    ("ご末人", "ご本人", "go_honjin"),
    ("部末人", "部本人", "bu_honjin"),
    ("末人", "本人", "honjin"),
    ("末物", "本物", "honmono"),
    ("仮末部", "仮本部", "kari_honbu"),
    ("末部", "本部", "honbu"),
    ("末社", "本社", "honsha"),
    ("末館", "本館", "honkan"),
    ("末堂", "本堂", "hondo"),
    ("末舞台", "本舞台", "hon_butai"),
    ("末年度", "本年度", "hon_nendo"),
    ("末年", "本年", "hon_nen"),
    ("末道", "本道", "hon_do"),
    ("末論", "本論", "honron"),
    ("末山", "本山", "honzan"),
    ("末願", "本願", "hongan"),
    ("末元", "本元", "hongen"),
    ("末原", "本原", "hon_gen"),
    ("末源", "本源", "hongen_moto"),
    ("末能的", "本能的", "hono_teki"),
    ("末能", "本能", "hono"),
    ("末性", "本性", "honsho"),
    ("末心", "本心", "honshin"),
    ("末意", "本意", "hon_i"),
    ("当利益末位", "当利益本位", "to_rieki_hon_i"),
    ("興味末位", "興味本位", "kyomi_hon_i"),
    ("自力末位", "自力本位", "jiriki_hon_i"),
    ("利益末位", "利益本位", "rieki_hon_i"),
    ("国家末位", "国家本位", "kokka_hon_i"),
    ("力末位", "力本位", "chikara_hon_i"),
    ("益末位", "益本位", "eki_hon_i"),
    ("味末位", "味本位", "mi_hon_i"),
    ("末位", "本位", "hon_i"),
    ("末分", "本分", "honbun_bun"),
    ("末領", "本領", "honryo"),
    ("末義", "本義", "hongi"),
    ("末尊", "本尊", "honzon"),
    ("末然", "本然", "honnen"),
    ("末数発展", "本数発展", "honsu_hatten"),
    ("末数", "本数", "honsu"),
    ("末施術", "本施術", "hon_sejutsu"),
    ("末職", "本職", "honshoku"),
    ("末吊", "本吊", "hon_cho"),
    ("末欄", "本欄", "hon_ran"),
    ("末稿", "本稿", "honko"),
    ("末筊", "本筊", "hon_byo"),
    # 末書→本書 tratado em transform_jp (regex: não dentro de 始末書)
    ("末所緑町", "本所緑町", "honjo_midori"),
    ("末所", "本所", "honjo"),
    ("末拠", "本拠", "honkyo_base"),
    ("末場", "本場", "honba"),
    ("末国", "本国", "hon_koku"),
    ("末郷", "本郷", "hongo"),
    ("末霊", "本霊", "hon_rei"),
    ("末能为義", "本能为義", "hono_gi"),
    ("末家", "本家", "honke"),
    ("末田植", "田植", "taue"),
    ("末田", "本田", "honda_field"),
    ("宮末武蔵", "宮本武蔵", "miyamoto_musashi"),
    ("橋末関雪", "橋本関雪", "hashimoto_kansetsu"),
    ("橋末徹馬", "橋本徹馬", "hashimoto_tetsuma"),
    ("橋末厚相", "橋本厚相", "hashimoto_atsuo"),
    ("橋末凝胤", "橋本凝胤", "hashimoto_gyo_in"),
    ("岡末米蔵", "岡本米蔵", "okamoto_yonezo"),
    ("末阿弥光", "本阿弥光", "honami_ko"),
    ("末阿弥", "本阿弥", "honami"),
    ("脚末", "脚本", "kyakuhon"),
    ("重桜亓十末", "重桜七十本", "ju_hon"),
    ("躑躅数十末", "躑躅数十本", "su_hon"),
    ("老木百末", "老木百本", "hyaku_hon"),
    ("野桜百末", "野桜百本", "yama_zakura"),
    ("桜亓十末", "桜七十本", "sakura_ju"),
    ("一日数末打", "一日数本打", "ichinichi"),
    ("三末植", "三本植", "san_hon_ue"),
    ("三十末", "三十本", "san_ju_hon"),
    ("四十末", "四十本", "yon_ju_hon"),
    ("百末", "百本", "hyaku_hon_counter"),
    ("数末", "数本", "su_hon_counter"),
    ("何末", "何本", "nan_hon"),
    ("四末", "四本", "yon_hon"),
    ("二末", "二本", "ni_hon"),
    ("一末", "一本", "ichi_hon"),
    ("見末", "見本", "mihon"),
    # passagem 3b — residual confirmado vs textos_japones
    ("桜一千末", "桜一千本", "sakura_sen_hon"),
    ("二千末", "二千本", "ni_sen_hon"),
    ("末妻", "本妻", "hon_sai"),
    ("熊末", "熊本", "kumamoto"),
    ("末屋", "本屋", "hon_ya"),
)

# OCR simplificado 为 (為) → 主 em compostos; após regras 末/本 específicas
JP_ZH_OCR_REPLACEMENTS: tuple[tuple[str, str, str], ...] = (
    ("民为为義", "民主主義", "minshu_shugi"),
    ("社会为義", "社会主義", "shakai_shugi"),
    ("共産为義", "共産主義", "kyosan_shugi"),
    ("唯物为義", "唯物主義", "yuibutsu_shugi"),
    ("資本为義", "資本主義", "shihon_shugi_alt"),
    ("为義", "主義", "shugi"),
    ("造物为", "造物主", "zoso_shu"),
    ("为飝", "主食", "shushoku"),
    ("为神", "主神", "shujin"),
    ("为なる", "主なる", "shunaru"),
)

def jp_roots_for_segment() -> tuple[Path, ...]:
    seg_id = os.environ.get("ACERVO_SEGMENT", "periodicos")
    if seg_id == "livros_acervo":
        jp_src, _ = source_roots("livros_acervo")
        return (jp_src, work_root("livros_acervo") / "jp")
    if seg_id == "periodicos":
        return (
            PROJECT_ROOT / "data" / "publication_sources" / "jp",
            PROJECT_ROOT / "reports" / "periodicos_trabalho" / "jp",
        )
    roots: list[Path] = []
    jp_src, _ = source_roots(seg_id)
    if jp_src.is_dir():
        roots.append(jp_src)
    pub_jp = PROJECT_ROOT / "data" / "publication_sources" / "jp"
    if pub_jp.is_dir() and pub_jp not in roots:
        roots.append(pub_jp)
    work_jp = work_root(seg_id) / "jp"
    if work_jp.is_dir() and work_jp not in roots:
        roots.append(work_jp)
    return tuple(roots)


def collect_jp_files() -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for root in jp_roots_for_segment():
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.txt")):
            if path not in seen:
                seen.add(path)
                out.append(path)
    return out


_HONSHO_OCR_RE = re.compile(r"(?<!始)末書")
_HONTO_OCR_RE = re.compile(r"末当(?!地)")


def transform_jp(text: str) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    new = text
    honsho_count = len(_HONSHO_OCR_RE.findall(new))
    if honsho_count:
        new = _HONSHO_OCR_RE.sub("本書", new)
        findings.append({"rule": "honsho", "pattern": "(?<!始)末書", "replacement": "本書", "count": honsho_count})
    honto_count = len(_HONTO_OCR_RE.findall(new))
    if honto_count:
        new = _HONTO_OCR_RE.sub("本当", new)
        findings.append({"rule": "honto", "pattern": "末当(?!地)", "replacement": "本当", "count": honto_count})
    for old, new_str, rule in (*JP_OCR_REPLACEMENTS, *JP_ZH_OCR_REPLACEMENTS):
        count = new.count(old)
        if count:
            new = new.replace(old, new_str)
            findings.append({"rule": rule, "pattern": old, "replacement": new_str, "count": count})
    return new, findings


def normalize_entries_jsonl(apply: bool) -> dict:
    """Atualiza body/title em entries.jsonl com kanji corrigidos."""
    if os.environ.get("ACERVO_SEGMENT", "periodicos") == "livros_acervo":
        return {"entries_changed": 0, "skipped": "livros_acervo segment"}
    path = PROJECT_ROOT / "data" / "publication_sources" / "entries.jsonl"
    if not path.is_file():
        return {"entries_changed": 0}
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = 0
    out_lines: list[str] = []
    for line in lines:
        if not line.strip():
            out_lines.append(line)
            continue
        row = json.loads(line)
        row_changed = False
        for key in ("title", "body", "display_source_name", "display_source_name_jp", "paired_title_jp"):
            val = row.get(key)
            if isinstance(val, str):
                new_val, findings = transform_jp(val)
                if findings:
                    row[key] = new_val
                    row_changed = True
        if row_changed:
            changed += 1
        out_lines.append(json.dumps(row, ensure_ascii=False))
    if apply and changed:
        path.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
    return {"entries_changed": changed}


def collect_work_pt_metadata_files() -> list[Path]:
    root = work_root() / "pt"
    if not root.is_dir():
        return []
    return sorted(root.glob("*.txt"))


def normalize_work_pt_title_jp(apply: bool) -> dict:
    """Corrige title_jp: nos blocos PT de trabalho (metadados colados ao JP antigo)."""
    changed_files = 0
    replacements = 0
    for pt_path in collect_work_pt_metadata_files():
        text = pt_path.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        out: list[str] = []
        file_changed = False
        for line in lines:
            if line.startswith("title_jp:"):
                val = line[len("title_jp:") :].rstrip("\n")
                new_val, findings = transform_jp(val)
                if findings:
                    file_changed = True
                    replacements += sum(f["count"] for f in findings)
                    out.append(f"title_jp:{new_val}\n")
                    continue
            out.append(line)
        if file_changed:
            changed_files += 1
            if apply:
                pt_path.write_text("".join(out), encoding="utf-8")
    return {"work_pt_title_jp_files": changed_files, "work_pt_title_jp_replacements": replacements}


def normalize_periodicos_pt_title_jp(apply: bool) -> dict:
    """Compat: delega para normalize_work_pt_title_jp."""
    result = normalize_work_pt_title_jp(apply)
    return {
        "periodicos_pt_title_jp_files": result["work_pt_title_jp_files"],
        "periodicos_pt_title_jp_replacements": result["work_pt_title_jp_replacements"],
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Normalize JP 末→本 OCR errors in publication_sources.")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    planned: list[dict] = []

    for jp_path in collect_jp_files():
        text = jp_path.read_text(encoding="utf-8")
        new_text, findings = transform_jp(text)
        if not findings or new_text == text:
            continue
        planned.append(
            {
                "jp_path": str(jp_path.relative_to(PROJECT_ROOT)),
                "findings": findings,
                "_new": new_text,
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "jp_hon_matsu_ocr_normalize.jsonl"
    with report_path.open("w", encoding="utf-8") as f:
        for row in planned:
            public = {k: v for k, v in row.items() if not k.startswith("_")}
            f.write(json.dumps(public, ensure_ascii=False) + "\n")

    backup_path = None
    if args.apply and planned:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"jp_hon_matsu_ocr_{ts}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for row in planned:
                tar.add(PROJECT_ROOT / row["jp_path"], arcname=row["jp_path"])
        for row in planned:
            (PROJECT_ROOT / row["jp_path"]).write_text(row["_new"], encoding="utf-8")

    rule_counts: Counter[str] = Counter()
    for row in planned:
        for finding in row["findings"]:
            rule_counts[finding["rule"]] += finding["count"]

    entries = normalize_entries_jsonl(args.apply)
    work_pt = normalize_work_pt_title_jp(args.apply)

    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "segment": os.environ.get("ACERVO_SEGMENT", "periodicos"),
        "jp_roots": [str(p.relative_to(PROJECT_ROOT)) for p in jp_roots_for_segment() if p.is_dir()],
        "files_scanned": len(collect_jp_files()),
        "files_changed": len(planned),
        "replacements": sum(rule_counts.values()),
        "rules": dict(rule_counts),
        "entries_jsonl": entries,
        "work_pt_title_jp": work_pt,
        "periodicos_pt_title_jp": {
            "periodicos_pt_title_jp_files": work_pt["work_pt_title_jp_files"],
            "periodicos_pt_title_jp_replacements": work_pt["work_pt_title_jp_replacements"],
        },
        "report": str(report_path),
        "backup": str(backup_path) if backup_path else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
