"""
Runs the FULL pipeline (extraction -> red-flag scan -> agent tool-calling loop
-> Gemma synthesis) against all 3 sample postings. This is the real end-to-end
test -- tests/test_live.py only exercised individual tools in isolation.

Run this on YOUR machine (not a sandboxed environment), after copying
.env.example to .env and filling in FIREWORKS_API_KEY.

Usage: python -m tests.test_pipeline_live
"""

from dotenv import load_dotenv

load_dotenv()

import json

from agent.pipeline import analyze_posting
from tests.sample_postings import *


def run_one(label: str, posting_text: str):
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
    result = analyze_posting(posting_text)

    print(f"\nExtracted: {json.dumps(result['extracted'], indent=2)}")
    print(f"\nDeterministic red flags: {result['redflag_scan']}")
    print(f"\nTools the agent called: {[f['tool'] for f in result['agent_findings']]}")
    print(f"\nDomain similarity: {result['domain_similarity']}")
    print(f"\nAgent notes: {result['agent_notes']}")
    print(f"\n--- VERDICT ---")
    print(json.dumps(result["verdict"], indent=2))


def run():
    run_one("CASE 1: obvious scam (expect high risk)", SCAM_POSTING_1)
    run_one("CASE 2: obvious scam (expect high risk)", SCAM_POSTING_2)
    run_one("CASE 3: subtle scam (expect medium-high -- this is the real test)", SUBTLE_SCAM_POSTING_1)
    run_one("CASE 4: subtle scam (expect medium-high -- this is the real test)", SUBTLE_SCAM_POSTING_2)
    run_one("CASE 5: real posting (expect low risk, no false positive)", REAL_POSTING_1)
    run_one("CASE 6: real posting (expect low risk, no false positive)", REAL_POSTING_2)


if __name__ == "__main__":
    run()
