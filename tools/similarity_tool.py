import difflib
import re
from typing import List

import tldextract


def _registrable_domain(domain: str) -> str:
    """
    Correctly isolate domain+suffix (e.g. 'hiring.amazon.com' -> 'amazon.com',
    'amazon.jobs' -> 'amazon.jobs'), stripping subdomains. A naive split on
    the first '.' misreads subdomains as the brand name -- e.g. it would read
    'hiring.amazon.com' as 'hiring', not 'amazon'.
    """
    if not domain:
        return ""
    ext = tldextract.extract(domain)
    if ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    return ext.domain


def _core_label(domain: str) -> str:
    """
    Isolate just the brand-name label, on top of _registrable_domain, e.g.
    'arnazon-jobs.com' -> 'arnazon-jobs' -> 'arnazon'. Strips common suffixes
    appended directly to the brand name itself (as opposed to subdomains,
    which _registrable_domain already handles).
    """
    if not domain:
        return ""
    ext = tldextract.extract(domain)
    label = ext.domain
    label = re.sub(r"-(jobs?|careers?|hr|recruit(ing)?|inc|corp|team|official)$", "", label)
    return label


def merge_domain_candidates(user_known_domain: str, search_candidates: List[str]) -> List[str]:
    """
    Combine a user-supplied 'I know their real site is X' domain with domains
    found via live search, de-duplicated, user-supplied domain listed first
    since it's the more trusted signal when present.
    """
    merged: List[str] = []

    if user_known_domain:
        cleaned = user_known_domain.lower().strip()
        cleaned = re.sub(r"^https?://", "", cleaned)
        cleaned = re.sub(r"^www\.", "", cleaned)
        cleaned = cleaned.split("/")[0]
        if cleaned:
            merged.append(cleaned)

    for d in search_candidates or []:
        d_norm = (d or "").lower().strip()
        if d_norm and d_norm not in merged:
            merged.append(d_norm)

    return merged


def domain_similarity(claimed: str, candidates: List[str]) -> dict:
    """
    Compare a claimed domain against candidate domains (e.g. from search_official_domain
    or merge_domain_candidates) and flag likely typosquats. Pure string logic -- no
    network needed, safe to run anywhere.

    Checks three signals: the registrable domain (subdomain-safe), the brand-name
    core label (suffix-stripped), and flags a typosquat if either is a close-but-
    not-exact match to any candidate.
    """
    claimed = (claimed or "").lower().strip()
    claimed_reg = _registrable_domain(claimed)
    claimed_core = _core_label(claimed)
    best = {"match": None, "ratio": 0.0, "core_ratio": 0.0}

    for c in candidates:
        c_norm = (c or "").lower().strip()
        if not c_norm:
            continue
        c_reg = _registrable_domain(c_norm)
        ratio = difflib.SequenceMatcher(None, claimed_reg, c_reg).ratio()
        core_ratio = difflib.SequenceMatcher(None, claimed_core, _core_label(c_norm)).ratio()
        # rank candidates by whichever signal is stronger
        if max(ratio, core_ratio) > max(best["ratio"], best["core_ratio"]):
            best = {"match": c_norm, "ratio": ratio, "core_ratio": core_ratio}

    exact_match = best["match"] is not None and _registrable_domain(best["match"]) == claimed_reg and claimed_reg != ""
    typosquat_suspected = (not exact_match) and (
        0.75 <= best["ratio"] < 1.0 or 0.75 <= best["core_ratio"] < 1.0
    )
    no_official_domain_found = best["match"] is None

    return {
        "claimed_domain": claimed,
        "best_match": best["match"],
        "similarity_ratio": round(best["ratio"], 3),
        "core_label_ratio": round(best["core_ratio"], 3),
        "exact_match": exact_match,
        "typosquat_suspected": typosquat_suspected,
        "no_official_domain_found": no_official_domain_found,
    }
