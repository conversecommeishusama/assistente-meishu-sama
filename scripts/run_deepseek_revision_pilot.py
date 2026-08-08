#!/usr/bin/env python3
"""DeepSeek revision pilot: JP+PT paragraph review with automated QA metrics."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text  # noqa: E402
from audit_translation_glossary import GLOSSARY_TRADUCAO_PATH, load_translation_glossary  # noqa: E402
from paragraph_glossary import align_paragraphs  # noqa: E402

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review" / "pilot"
PROTOCOL_PATH = PROJECT_ROOT / "protocolo_revisao.txt"
GLOSSARY_PATH = GLOSSARY_TRADUCAO_PATH
MODEL = "deepseek-chat"
BATCH_SIZE = 4

KOTODAMA_NESTED = re.compile(r"Kotodama\s*\(\s*Kotodama", re.I)
BAD_CAPITALIZATION = re.compile(r"\.\s+(quando|por isso)\b", re.I)
BAD_GRAMMAR = re.compile(
    r"essas nuvens espirituais é |o que é essas nuvens|linha espiritual",
    re.I,
)
LINHA_ESPIRITUAL = re.compile(r"\blinha espiritual\b", re.I)


@dataclass
class QualityScore:
    total_checks: int = 0
    passed: int = 0
    issues: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.passed / self.total_checks if self.total_checks else 1.0


def load_env_api_key() -> str:
    try:
        from goshinsho.config import Config

        if Config.DEEPSEEK_API_KEY:
            return Config.DEEPSEEK_API_KEY
    except Exception:
        pass
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("DEEPSEEK_API_KEY não configurada.")


def load_glossary() -> dict:
    return load_translation_glossary()


def select_glossary_entries(jp_text: str, pt_text: str, glossary: dict, max_entries: int = 40) -> list[tuple[str, object]]:
    haystack = f"{jp_text}\n{pt_text}"
    selected: list[tuple[str, object]] = []
    for japanese, portuguese in glossary.items():
        if japanese in haystack:
            selected.append((japanese, portuguese))
        if len(selected) >= max_entries:
            break
    return selected


def format_glossary_block(entries: list[tuple[str, object]]) -> str:
    lines = ["### GLOSSÁRIO RELEVANTE (obrigatório quando o termo JP aparecer):"]
    for japanese, portuguese in entries:
        if isinstance(portuguese, list):
            preview = ", ".join(str(item) for item in portuguese[:3])
            lines.append(f"- {japanese} -> {preview}")
        else:
            lines.append(f"- {japanese} -> {portuguese}")
    return "\n".join(lines)


def build_revision_prompt(batch: list, protocol: str, glossary_block: str) -> str:
    blocks = []
    for item in batch:
        blocks.append(
            f"### PARÁGRAFO {item['index']}\n"
            f"JP:\n{item['jp']}\n\n"
            f"PT (atual):\n{item['pt']}"
        )
    return f"""{protocol}

{glossary_block}

Revise os parágrafos abaixo conforme o protocolo. Compare JP com PT.

{chr(10).join(blocks)}
"""


def parse_revision_response(content: str) -> dict | None:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def call_deepseek(client, prompt: str) -> tuple[str, dict]:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=8000,
    )
    usage = {}
    if response.usage:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }
    return response.choices[0].message.content or "", usage


def assess_paragraph_quality(pt: str, jp: str, glossary: dict) -> QualityScore:
    score = QualityScore()
    checks = [
        ("sem_kotodama_aninhado", not KOTODAMA_NESTED.search(pt)),
        ("sem_linha_espiritual", not LINHA_ESPIRITUAL.search(pt)),
        ("capitalizacao_pos_ponto", not BAD_CAPITALIZATION.search(pt)),
        ("gramatica_nuvens", not BAD_GRAMMAR.search(pt)),
    ]
    for japanese, portuguese in glossary.items():
        if japanese not in jp:
            continue
        values = portuguese if isinstance(portuguese, list) else [portuguese]
        if japanese == "霊線" and LINHA_ESPIRITUAL.search(pt):
            checks.append((f"glossario_{japanese}", False))
        elif japanese == "言霊" and KOTODAMA_NESTED.search(pt):
            checks.append((f"glossario_{japanese}", False))
    for name, ok in checks:
        score.total_checks += 1
        if ok:
            score.passed += 1
        else:
            score.issues.append(name)
    return score


def pick_pilot_pairs(pairs: list, sample_size: int, seed_paths: list[str] | None = None) -> list:
    if seed_paths:
        by_path = {
            str(permanent_pt_path(p.pt).relative_to(PROJECT_ROOT)): p for p in pairs
        }
        selected = [by_path[path] for path in seed_paths if path in by_path]
        if len(selected) >= sample_size:
            return selected[:sample_size]

    sized = []
    for pair in pairs:
        try:
            jp = read_entry_text(pair.jp)
            pt = permanent_pt_path(pair.pt).read_text(encoding="utf-8")
            sized.append((len(jp) + len(pt), pair))
        except Exception:
            continue
    sized.sort(key=lambda item: item[0])
    if sample_size <= 3:
        indices = [0, len(sized) // 2, len(sized) - 1]
    else:
        step = max(1, len(sized) // sample_size)
        indices = list(range(0, len(sized), step))[:sample_size]
    return [sized[i][1] for i in indices]


def revise_text_with_deepseek(
    client,
    jp_text: str,
    pt_text: str,
    protocol: str,
    glossary: dict,
    *,
    max_paragraphs: int | None = None,
) -> tuple[str, list[dict], dict]:
    pairs = align_paragraphs(jp_text, pt_text)
    if max_paragraphs:
        pairs = pairs[:max_paragraphs]

    glossary_entries = select_glossary_entries(jp_text, pt_text, glossary)
    glossary_block = format_glossary_block(glossary_entries)

    revised_by_index: dict[int, str] = {}
    all_batches: list[dict] = []
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for start in range(0, len(pairs), BATCH_SIZE):
        batch_pairs = pairs[start : start + BATCH_SIZE]
        batch = [{"index": p.index, "jp": p.jp, "pt": p.pt} for p in batch_pairs]
        prompt = build_revision_prompt(batch, protocol, glossary_block)
        raw, usage = call_deepseek(client, prompt)
        for key in usage_total:
            usage_total[key] += usage.get(key, 0)

        parsed = parse_revision_response(raw)
        batch_record = {
            "start_index": batch_pairs[0].index,
            "usage": usage,
            "raw_preview": raw[:500],
            "parsed_ok": parsed is not None,
        }

        if parsed and "paragraphs" in parsed:
            for item in parsed["paragraphs"]:
                idx = int(item.get("index", -1))
                revised = item.get("revised_pt", "")
                if idx >= 0 and revised:
                    revised_by_index[idx] = revised
            batch_record["changes"] = [
                {
                    "index": item.get("index"),
                    "changed": item.get("changed"),
                    "changes": item.get("changes", []),
                }
                for item in parsed.get("paragraphs", [])
            ]
        else:
            batch_record["error"] = "json_parse_failed"
            for p in batch_pairs:
                revised_by_index[p.index] = p.pt

        all_batches.append(batch_record)
        time.sleep(0.3)

    revised_paras = []
    for p in pairs:
        revised_paras.append(revised_by_index.get(p.index, p.pt))

    return "\n\n".join(revised_paras), all_batches, usage_total


def evaluate_text(jp_text: str, pt_before: str, pt_after: str, glossary: dict) -> dict:
    pairs = align_paragraphs(jp_text, pt_before)
    before_scores = [assess_paragraph_quality(p.pt, p.jp, glossary) for p in pairs]
    after_pairs = align_paragraphs(jp_text, pt_after)
    after_scores = [assess_paragraph_quality(p.pt, p.jp, glossary) for p in pairs[: len(after_pairs)]]

    before_rate = sum(s.rate for s in before_scores) / len(before_scores) if before_scores else 1.0
    after_rate = sum(s.rate for s in after_scores) / len(after_scores) if after_scores else 1.0

    changed_paras = sum(
        1 for i, p in enumerate(pairs) if i < len(after_pairs) and p.pt.strip() != after_pairs[i].pt.strip()
    )

    return {
        "paragraphs": len(pairs),
        "quality_before": round(before_rate * 100, 1),
        "quality_after": round(after_rate * 100, 1),
        "quality_delta": round((after_rate - before_rate) * 100, 1),
        "paragraphs_changed": changed_paras,
        "issues_before": sum(len(s.issues) for s in before_scores),
        "issues_after": sum(len(s.issues) for s in after_scores),
        "length_ratio": round(len(pt_after) / max(len(pt_before), 1), 4),
    }


def estimate_corpus_cost(pairs: list, avg_usage_per_text: dict, strategy: str) -> dict:
    total_chars = 0
    for pair in pairs:
        try:
            jp = read_entry_text(pair.jp)
            pt = permanent_pt_path(pair.pt).read_text(encoding="utf-8")
            total_chars += len(jp) + len(pt)
        except Exception:
            continue

    multipliers = {
        "file": 1.0,
        "paragraph": 11.5,
        "hybrid_15pct": 1.8,
        "two_pass": 1.6,
    }
    mult = multipliers.get(strategy, 1.0)
    texts = len(pairs)
    prompt_per_text = avg_usage_per_text.get("prompt_tokens", 5000) * mult
    completion_per_text = avg_usage_per_text.get("completion_tokens", 1500) * mult
    total_prompt = prompt_per_text * texts
    total_completion = completion_per_text * texts

    flash_in = 0.14 * 0.4 + 0.0028 * 0.6
    flash_out = 0.28
    return {
        "strategy": strategy,
        "texts": texts,
        "total_chars": total_chars,
        "est_prompt_tokens": int(total_prompt),
        "est_completion_tokens": int(total_completion),
        "est_usd_flash": round((total_prompt / 1e6) * flash_in + (total_completion / 1e6) * flash_out, 2),
        "est_brl_flash": round(((total_prompt / 1e6) * flash_in + (total_completion / 1e6) * flash_out) * 5.8, 0),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DeepSeek revision pilot with QA metrics.")
    parser.add_argument("--sample", type=int, default=12, help="Number of texts in pilot.")
    parser.add_argument("--max-paragraphs", type=int, default=8, help="Max paragraphs per text in pilot.")
    parser.add_argument("--paths", nargs="*", help="Specific pt paths (relative to project root).")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()
    pairs = pair_entries(load_entries())

    seed_paths = args.paths or [
        "data/publication_sources/pt/eiko/16-de-janeiro-de-1952-forca-absoluta-publication-pt-0256.txt",
        "data/publication_sources/pt/hikari/13-de-agosto-de-1949-os-tres-grandes-desastres-e-os-tres-pequenos-desastres-publication-pt-0300.txt",
        "data/publication_sources/pt/guia-rapido-da-igreja-messianica-mundial/20-de-novembro-de-1950-seguir-a-razao-publication-pt-0141.txt",
    ]
    if args.paths:
        by_path = {
            str(permanent_pt_path(p.pt).relative_to(PROJECT_ROOT)): p for p in pairs
        }
        pilot_pairs = [by_path[path] for path in args.paths if path in by_path]
    else:
        pilot_pairs = pick_pilot_pairs(pairs, args.sample, seed_paths)

    from openai import OpenAI

    client = OpenAI(api_key=load_env_api_key(), base_url="https://api.deepseek.com/v1")

    results = []
    usage_accum = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for pair in pilot_pairs:
        pt_path = permanent_pt_path(pair.pt)
        jp_text = read_entry_text(pair.jp)
        pt_before = pt_path.read_text(encoding="utf-8")

        pt_after, batches, usage = revise_text_with_deepseek(
            client,
            jp_text,
            pt_before,
            protocol,
            glossary,
            max_paragraphs=args.max_paragraphs,
        )
        for key in usage_accum:
            usage_accum[key] += usage.get(key, 0)

        metrics = evaluate_text(jp_text, pt_before, pt_after, glossary)
        rel_path = str(pt_path.relative_to(PROJECT_ROOT))
        result = {
            "pt_path": rel_path,
            "title": pair.pt.get("title") or pair.pt.get("display_source_name_pt"),
            "batches": batches,
            "usage": usage,
            **metrics,
        }
        results.append(result)

        out_file = args.output_dir / "revised" / rel_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(pt_after, encoding="utf-8")

        audit_file = args.output_dir / "audit" / (Path(rel_path).stem + ".md")
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        audit_file.write_text(
            f"# {result['title']}\n\n"
            f"**Arquivo:** `{rel_path}`\n\n"
            f"| Métrica | Antes | Depois |\n"
            f"|---------|------:|-------:|\n"
            f"| Qualidade automática | {metrics['quality_before']}% | {metrics['quality_after']}% |\n"
            f"| Problemas detectados | {metrics['issues_before']} | {metrics['issues_after']} |\n"
            f"| Parágrafos alterados | — | {metrics['paragraphs_changed']}/{metrics['paragraphs']} |\n\n"
            f"## Amostra (primeiros 2 parágrafos)\n\n"
            f"### Antes\n\n{pt_before[:1200]}...\n\n"
            f"### Depois\n\n{pt_after[:1200]}...\n",
            encoding="utf-8",
        )
        print(f"done: {rel_path} Q {metrics['quality_before']}% -> {metrics['quality_after']}%")

    avg_usage = {
        "prompt_tokens": usage_accum["prompt_tokens"] / max(len(results), 1),
        "completion_tokens": usage_accum["completion_tokens"] / max(len(results), 1),
    }

    avg_quality_before = sum(r["quality_before"] for r in results) / len(results)
    avg_quality_after = sum(r["quality_after"] for r in results) / len(results)
    parse_failures = sum(1 for r in results for b in r["batches"] if not b.get("parsed_ok"))

    cost_scenarios = [
        estimate_corpus_cost(pairs, avg_usage, "file"),
        estimate_corpus_cost(pairs, avg_usage, "paragraph"),
        estimate_corpus_cost(pairs, avg_usage, "hybrid_15pct"),
        estimate_corpus_cost(pairs, avg_usage, "two_pass"),
    ]

    pilot_summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "sample_size": len(results),
        "max_paragraphs_per_text": args.max_paragraphs,
        "usage_total": usage_accum,
        "usage_avg_per_text": avg_usage,
        "avg_quality_before_pct": round(avg_quality_before, 1),
        "avg_quality_after_pct": round(avg_quality_after, 1),
        "parse_failures": parse_failures,
        "results": results,
        "cost_scenarios": cost_scenarios,
    }

    json_path = args.output_dir / "pilot_summary.json"
    json_path.write_text(json.dumps(pilot_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"summary={json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
