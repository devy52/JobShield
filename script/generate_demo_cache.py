"""
Pre-computes analyze_posting() results for the 3 demo cases and saves them to
demo_cache.json. Run this ONCE, locally, once you're confident the pipeline
produces good output -- the app then loads from this cache for the "Try an
example" buttons, so your live demo never depends on WHOIS/search/Fireworks
calls succeeding in front of judges.

Re-run this any time you change the prompts, rubric, or tools -- the cache
goes stale otherwise and will show outdated verdicts.

Usage: python -m scripts.generate_demo_cache
"""

import json

from dotenv import load_dotenv

load_dotenv()

from agent.pipeline import analyze_posting
from tests.sample_postings import *

CASES = {
    "obvious_scam_1": {
        "label": "Obvious scam",
        "text": SCAM_POSTING_1,
    },
    "obvious_scam_2": {
        "label": "Obvious scam",
        "text": SCAM_POSTING_2,
    },
    "subtle_scam_1": {
        "label": "Subtle scam",
        "text": SUBTLE_SCAM_POSTING_1,
    },
    "subtle_scam_2": {
        "label": "Subtle scam",
        "text": SUBTLE_SCAM_POSTING_2,
    },
    "real_posting_1": {
        "label": "Real posting",
        "text": REAL_POSTING_1,
    },
    "real_posting_2": {
        "label": "Real posting",
        "text": REAL_POSTING_2,
    },
}


def run():
    cache = {}
    for key, case in CASES.items():
        print(f"Running: {case['label']}...")
        result = analyze_posting(case["text"])
        cache[key] = {
            "label": case["label"],
            "posting_text": case["text"],
            "result": result,
        }
        score = result["verdict"]["risk_score"]
        label = result["verdict"]["risk_label"]
        print(f"  -> {score}/100, {label}")

    with open("demo_cache.json", "w") as f:
        json.dump(cache, f, indent=2)

    print("\nSaved to demo_cache.json")
    print("Sanity check before trusting this for the demo:")
    print("  - obvious_scam should be HIGH risk")
    print("  - subtle_scam should be MEDIUM or HIGH risk (this is the real test)")
    print("  - real_posting should be LOW risk, no false positive")


if __name__ == "__main__":
    run()
