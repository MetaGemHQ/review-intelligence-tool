"""Comparison-table matrix runner.

Runs every (model, prompt technique) cell N times over a single fixed topic,
records each run to evaluation_runs via the normal service path, and writes two
artifacts: a per-run CSV and an aggregated Markdown table.

Usage:
    python matrix_runner.py [topic_id] [runs_per_cell]
Defaults: topic_id=4 (Volkswagen, US Trustpilot), runs_per_cell=3.
"""

import csv
import sys
from itertools import combinations

from dotenv import load_dotenv

load_dotenv()

from services import evaluation_service as es
from services import prompts

# Three model families. The OpenAI + Gemini models run on free tiers; the
# Claude models draw on prepaid Anthropic credits (a few cents per full matrix).
# Heavier Gemini tiers (2.5-flash, 2.0-flash, 2.5-pro) stay out: quota-limited
# on the free tier.
MODELS = [
    "gpt-4o-mini",
    "gemini-2.5-flash-lite",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
]
TECHNIQUES = list(prompts.TECHNIQUES)


def _theme_set(themes):
    return {t.strip().lower() for t in themes if t and t.strip()}


def _avg_pairwise_jaccard(theme_sets):
    sets = [s for s in theme_sets if s]
    if len(sets) < 2:
        return None
    scores = []
    for a, b in combinations(sets, 2):
        union = a | b
        scores.append(len(a & b) / len(union) if union else 1.0)
    return sum(scores) / len(scores)


def _mean(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def main():
    topic_id = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    runs_per_cell = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    per_run_csv = f"data/comparison_runs_topic{topic_id}.csv"
    table_md = f"comparison_table_topic{topic_id}.md"

    per_run = []
    for model in MODELS:
        for technique in TECHNIQUES:
            for idx in range(1, runs_per_cell + 1):
                row = {
                    "model": model,
                    "technique": technique,
                    "run": idx,
                    "status": "ok",
                    "sentiment": None,
                    "rating": None,
                    "n_themes": None,
                    "themes": "",
                    "input_tokens": None,
                    "output_tokens": None,
                    "latency_ms": None,
                    "cost_usd": None,
                    "error": "",
                }
                try:
                    r = es.run_evaluation(topic_id, model=model, technique=technique)
                    ev = r["evaluation"]
                    row.update(
                        sentiment=ev["overall_sentiment"],
                        rating=ev["rating"],
                        n_themes=len(ev["key_themes"]),
                        themes="; ".join(ev["key_themes"]),
                        input_tokens=r["input_tokens"],
                        output_tokens=r["output_tokens"],
                        latency_ms=r["latency_ms"],
                        cost_usd=r["total_cost"],
                    )
                except Exception as e:
                    row["status"] = "fail"
                    row["error"] = f"{type(e).__name__}: {e}"[:300]
                per_run.append(row)
                print(
                    f"{model:<18} {technique:<16} run {idx}/{runs_per_cell} "
                    f"-> {row['status']} {row['sentiment']} r{row['rating']} "
                    f"{row['latency_ms']}ms",
                    flush=True,
                )

    with open(per_run_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_run[0].keys()))
        writer.writeheader()
        writer.writerows(per_run)

    lines = [
        f"# Model x Prompt-Technique Comparison (topic {topic_id})",
        "",
        f"{runs_per_cell} runs per cell. Cost is total USD across the cell's runs.",
        "",
        "| Model | Technique | Valid | Mean latency (ms) | Mean cost/run (USD) | Ratings | Sentiments | Theme stability |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for model in MODELS:
        for technique in TECHNIQUES:
            cell = [
                r for r in per_run if r["model"] == model and r["technique"] == technique
            ]
            ok = [r for r in cell if r["status"] == "ok"]
            valid = f"{len(ok)}/{len(cell)}"
            mean_lat = _mean([r["latency_ms"] for r in ok])
            mean_cost = _mean([r["cost_usd"] for r in ok])
            ratings = ", ".join(str(r["rating"]) for r in ok) or "-"
            sentiments = ", ".join(sorted({r["sentiment"] for r in ok})) or "-"
            stability = _avg_pairwise_jaccard([_theme_set(r["themes"].split("; ")) for r in ok])
            lines.append(
                f"| {model} | {technique} | {valid} | "
                f"{round(mean_lat) if mean_lat is not None else '-'} | "
                f"{round(mean_cost, 6) if mean_cost is not None else '-'} | "
                f"{ratings} | {sentiments} | "
                f"{round(stability, 2) if stability is not None else '-'} |"
            )

    total_cost = sum(r["cost_usd"] or 0 for r in per_run)
    fails = sum(1 for r in per_run if r["status"] == "fail")
    lines += ["", f"Total runs: {len(per_run)} | failures: {fails} | total cost: ${total_cost:.4f}"]

    with open(table_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nWrote {per_run_csv} and {table_md}")
    print(f"Total cost: ${total_cost:.4f} | failures: {fails}")


if __name__ == "__main__":
    main()
