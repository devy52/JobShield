import re
from urllib.parse import urlparse

from ddgs import DDGS  # pip install ddgs


def search_official_domain(company_name: str, max_results: int = 5) -> dict:
    """
    Search for a company's official careers/website domain.

    NOTE: hits DuckDuckGo over HTTPS -- run this locally, not in a
    sandboxed/proxied environment that only allows a fixed domain list.
    """
    company_name = (company_name or "").strip()
    if not company_name:
        return {"query": None, "candidate_domains": [], "search_failed": True, "error": "empty company name"}

    query = f"{company_name} official careers page"
    domains = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                url = r.get("href") or r.get("url")
                if not url:
                    continue
                netloc = urlparse(url).netloc.lower()
                netloc = re.sub(r"^www\.", "", netloc)
                if netloc and netloc not in domains:
                    domains.append(netloc)
        return {"query": query, "candidate_domains": domains, "search_failed": False}
    except Exception as e:
        return {"query": query, "candidate_domains": [], "search_failed": True, "error": str(e)}


def search_company_reviews(company_name: str, max_results: int = 5) -> dict:
    """
    Surfaces public complaint/review snippets mentioning this company alongside
    'scam'. Returns raw snippets for the synthesis step to reason over -- this
    tool does not itself judge sentiment, it just gathers what's out there.
    """
    company_name = (company_name or "").strip()
    if not company_name:
        return {"query": None, "results": [], "search_failed": True, "error": "empty company name"}

    query = f"{company_name} reviews scam complaints"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        snippets = [
            {"title": r.get("title"), "url": r.get("href") or r.get("url"), "snippet": r.get("body")}
            for r in results
        ]
        return {"query": query, "results": snippets, "search_failed": False}
    except Exception as e:
        return {"query": query, "results": [], "search_failed": True, "error": str(e)}


def search_social_presence(company_name: str, max_results: int = 5) -> dict:
    """
    SHALLOW PRESENCE CHECK ONLY -- confirms whether a LinkedIn company page turns
    up in search results for this company name. This does NOT verify account age,
    follower count, or whether the page is genuine. Treat a hit as a weak positive
    signal and an absence as a mild red flag -- nothing stronger than that. Say so
    explicitly wherever this result is surfaced (UI, pitch, README).
    """
    company_name = (company_name or "").strip()
    if not company_name:
        return {"query": None, "linkedin_present": False, "linkedin_urls": [], "search_failed": True, "error": "empty company name"}

    query = f"{company_name} LinkedIn company page"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        linkedin_urls = [
            (r.get("href") or r.get("url"))
            for r in results
            if "linkedin.com" in (r.get("href") or r.get("url") or "").lower()
        ]
        return {
            "query": query,
            "linkedin_present": len(linkedin_urls) > 0,
            "linkedin_urls": linkedin_urls,
            "search_failed": False,
        }
    except Exception as e:
        return {"query": query, "linkedin_present": False, "linkedin_urls": [], "search_failed": True, "error": str(e)}
