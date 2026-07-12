"""
Exercises every network-dependent piece -- Fireworks extraction, WHOIS, live
search, reviews search, social presence check -- AND chains domain_similarity
on top so you see the full picture per posting, not just isolated tool output.

Run this on YOUR machine (not a sandboxed environment), after copying
.env.example to .env and filling in FIREWORKS_API_KEY.

Usage: python -m tests.test_live
"""

from dotenv import load_dotenv

load_dotenv()

from agent.extraction import extract_posting
from tools.whois_tool import whois_lookup
from tools.search_tool import search_official_domain, search_company_reviews, search_social_presence
from tools.similarity_tool import domain_similarity, merge_domain_candidates
from tools.redflag_tool import scan_red_flags
from tests.sample_postings import SCAM_POSTING, SUBTLE_SCAM_POSTING, REAL_POSTING


def run_one(label: str, posting_text: str, user_known_domain: str = ""):
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")

    print("\n--- Extraction (Fireworks) ---")
    extracted = extract_posting(posting_text)
    print(extracted.model_dump_json(indent=2))

    print("\n--- Deterministic red-flag scan ---")
    print(scan_red_flags(posting_text))

    domain_to_check = extracted.claimed_email_domain or extracted.claimed_domain
    if domain_to_check:
        print(f"\n--- WHOIS: {domain_to_check} ---")
        print(whois_lookup(domain_to_check))
    else:
        print("\n(no domain extracted -- nothing to WHOIS-check, this itself is worth noting)")

    search_result = {"candidate_domains": []}
    if extracted.company_name:
        print(f"\n--- Search: {extracted.company_name} ---")
        search_result = search_official_domain(extracted.company_name)
        print(search_result)

        print(f"\n--- Reviews/complaints search: {extracted.company_name} ---")
        print(search_company_reviews(extracted.company_name))

        print(f"\n--- Social presence check: {extracted.company_name} ---")
        print(search_social_presence(extracted.company_name))

    if domain_to_check:
        candidates = merge_domain_candidates(user_known_domain, search_result.get("candidate_domains", []))
        print(f"\n--- Domain similarity: {domain_to_check} vs {candidates} ---")
        print(domain_similarity(domain_to_check, candidates))


def run():
    run_one("CASE 1: obvious scam", SCAM_POSTING)
    run_one("CASE 2: subtle scam", SUBTLE_SCAM_POSTING)
    run_one("CASE 3: real posting", REAL_POSTING)


if __name__ == "__main__":
    run()
