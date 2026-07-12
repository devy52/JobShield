"""
Runs the full pipeline against tests/eval_sample.csv (30 labeled postings, 15
fraudulent / 15 real) and reports precision/recall/F1 -- a real accuracy number
for the pitch instead of relying on the live demo alone.

This burns real Fireworks credits: ~30 postings x a few calls each. Run this
ONCE you're confident in the pipeline (after test_pipeline_live.py looks good),
not while still debugging -- re-running repeatedly for no reason wastes budget.

Threshold used: risk_label in {"medium", "high"} counts as "flagged as risky."
"low" counts as "not flagged." This matches how a real user would react --
medium is already a caution signal, not a clean bill of health.

Usage: python -m scripts.run_eval
"""

import csv
import json

from dotenv import load_dotenv

load_dotenv()

from agent.pipeline import analyze_posting

BENCHMARK_EVAL_CSV_PATH = "tests/eval_sample.csv"
VALIDATION_EVAL_CSV_PATH = "tests/eval_modern.csv"
BENCHMARK_RESULTS_PATH = "eval_results_benchmark.json"
VALIDATION_RESULTS_PATH = "eval_results_validation.json"


def run(eval_csv_path, results_path):
    with open(eval_csv_path) as f:
        rows = list(csv.DictReader(f))

    results = []
    tp = fp = tn = fn = 0

    for i, row in enumerate(rows):
        actual_fraud = row["fraudulent"] == "1"
        text = row["text"]

        print(f"[{i + 1}/{len(rows)}] source_id={row.get('source_id', '?')} actual_fraud={actual_fraud} ...", end=" ")

        try:
            result = analyze_posting(text)
            verdict = result["verdict"]
            predicted_flagged = verdict["risk_label"] in ("medium", "high")
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"source_id": row.get("source_id"), "actual_fraud": actual_fraud, "error": str(e)})
            continue

        print(f"-> predicted={verdict['risk_score']}/{verdict['risk_label']}")

        if actual_fraud and predicted_flagged:
            tp += 1
        elif not actual_fraud and predicted_flagged:
            fp += 1
        elif not actual_fraud and not predicted_flagged:
            tn += 1
        else:
            fn += 1

        results.append(
            {
                "source_id": row.get("source_id"),
                "actual_fraud": actual_fraud,
                "predicted_score": verdict["risk_score"],
                "predicted_label": verdict["risk_label"],
                "predicted_flagged": predicted_flagged,
                "correct": actual_fraud == predicted_flagged,
            }
        )

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) else 0.0

    summary = {
        "n": len(rows),
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "accuracy": round(accuracy, 3),
    }

    with open(results_path, "w") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)

    print("\n" + "=" * 50)
    print(f"n={summary['n']}  TP={tp}  FP={fp}  TN={tn}  FN={fn}")
    print(f"Precision: {summary['precision']}  Recall: {summary['recall']}  F1: {summary['f1']}  Accuracy: {summary['accuracy']}")
    print(f"\nSaved full results to {results_path}")
    print("\nFor the pitch: quote precision/recall/accuracy, and be honest about FN/FP")
    print("counts if judges ask -- 'caught X of Y fraud cases, Z false positives on")
    print("Y legitimate postings' is a stronger, more credible claim than a bare percentage.")


if __name__ == "__main__":
    run(BENCHMARK_EVAL_CSV_PATH, BENCHMARK_RESULTS_PATH)
    run(VALIDATION_EVAL_CSV_PATH, VALIDATION_RESULTS_PATH)
