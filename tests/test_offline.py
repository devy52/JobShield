"""
Runs the two pieces that are pure logic and need no network access.
Safe to run anywhere, including sandboxed environments.

Usage: python -m tests.test_offline
"""

from tools.redflag_tool import scan_red_flags
from tools.similarity_tool import domain_similarity, merge_domain_candidates
from tests.sample_postings import SCAM_POSTING, SUBTLE_SCAM_POSTING, REAL_POSTING


def run():
    print("=== Red flag scan: SCAM_POSTING ===")
    print(scan_red_flags(SCAM_POSTING))

    print("\n=== Red flag scan: SUBTLE_SCAM_POSTING ===")
    print(scan_red_flags(SUBTLE_SCAM_POSTING))

    print("\n=== Red flag scan: REAL_POSTING (should be mostly empty) ===")
    print(scan_red_flags(REAL_POSTING))

    print("\n=== Domain similarity: arnazon-jobs.com vs [amazon.com] (expect typosquat) ===")
    print(domain_similarity("arnazon-jobs.com", ["amazon.com"]))

    print("\n=== Domain similarity: acme.com vs [acme.com] (expect exact match) ===")
    print(domain_similarity("acme.com", ["acme.com"]))

    print("\n=== Domain similarity: flextest.co vs [] (expect no match found) ===")
    print(domain_similarity("flextest.co", []))

    print("\n=== merge_domain_candidates: user says 'amazon.com', search found nothing ===")
    print(merge_domain_candidates("https://www.amazon.com/", []))

    print("\n=== merge_domain_candidates: user says nothing, search found acme.com ===")
    print(merge_domain_candidates("", ["acme.com"]))

    print("\n=== merge_domain_candidates: user + search both present, no duplicates ===")
    print(merge_domain_candidates("acme.com", ["acme.com", "acme-careers.net"]))


if __name__ == "__main__":
    run()
