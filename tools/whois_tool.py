from datetime import datetime, timezone

import whois  # pip install python-whois

# Substrings WHOIS servers use to say "this domain has no registration record" --
# python-whois surfaces these as an exception message rather than a clean signal,
# so we have to pattern-match the (huge, boilerplate-laden) error text ourselves.
_NOT_FOUND_MARKERS = (
    "no match for",
    "not found",
    "no data found",
    "no entries found",
    "domain not found",
    "status: free",
)


def whois_lookup(domain: str) -> dict:
    """
    Look up WHOIS registration info for a domain. Flags domains registered
    recently, and separately flags domains with NO registration record at
    all -- an even stronger scam signal than a newly-registered domain, since
    it usually means the poster's claimed domain doesn't exist or was made up.

    NOTE: this makes a raw WHOIS protocol call (not HTTP), so it needs
    unrestricted outbound network access -- run it locally, not in a
    sandboxed/proxied environment.
    """
    domain = (domain or "").strip().lower()
    if not domain:
        return {"domain": domain, "lookup_failed": True, "domain_not_registered": False, "error": "empty domain"}

    try:
        w = whois.whois(domain)
        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]

        if not creation_date:
            # Some registries return an empty/near-empty record instead of
            # raising when there's no match -- treat that as unregistered too.
            return {
                "domain": domain,
                "lookup_failed": False,
                "domain_not_registered": True,
                "registrar": None,
                "creation_date": None,
                "age_days": None,
                "newly_registered": None,
            }

        if creation_date.tzinfo is None:
            creation_date = creation_date.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - creation_date).days

        return {
            "domain": domain,
            "registrar": w.registrar,
            "creation_date": str(creation_date),
            "age_days": age_days,
            "newly_registered": age_days < 180,
            "lookup_failed": False,
            "domain_not_registered": False,
        }
    except Exception as e:
        error_text = str(e).lower()
        not_registered = any(marker in error_text for marker in _NOT_FOUND_MARKERS)
        return {
            "domain": domain,
            "lookup_failed": not not_registered,
            "domain_not_registered": not_registered,
            # raw WHOIS "not found" responses include a wall of registry legal
            # boilerplate -- truncate before this goes anywhere near the LLM prompt
            "error": str(e)[:200],
        }
