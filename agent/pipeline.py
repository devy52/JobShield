from typing import Callable, Optional

from agent.extraction import extract_posting
from agent.orchestrator import run_agent_loop
from agent.schema import RiskVerdict, UserContext
from agent.synthesis import synthesize_risk
from tools.redflag_tool import scan_red_flags


def analyze_posting(
    raw_text: str, known_domain: str = "", progress_callback: Optional[Callable[[str], None]] = None
) -> dict:
    """
    End-to-end pipeline: extract structured facts -> deterministic red-flag scan
    (always runs, no network) -> agent loop decides which verification tools to
    call -> LLM synthesizes everything into a final risk verdict (scoring is
    fully deterministic; the model only writes evidence/explanation text).

    progress_callback, if given, is called with a short status string at each
    real stage boundary -- optional and purely additive, existing callers are
    unaffected. Exists so the UI can show genuine pipeline progress instead of
    a generic spinner, without faking status text that doesn't reflect what's
    actually happening.

    Returns a dict with every intermediate stage included, not just the final
    verdict -- the UI's "show agent's work" panel depends on this for transparency.
    """
    def _notify(msg: str):
        if progress_callback:
            progress_callback(msg)

    user_context = UserContext(known_domain=known_domain) if known_domain else UserContext()

    _notify("Reading the posting and pulling out the key claims...")
    extracted = extract_posting(raw_text)
    redflag_result = scan_red_flags(raw_text)

    _notify("Checking WHOIS, live search, and reviews for what it can verify...")
    agent_result = run_agent_loop(extracted, user_context)

    _notify("Weighing the evidence and writing the explanation...")
    verdict: RiskVerdict = synthesize_risk(extracted, redflag_result, agent_result)

    return {
        "extracted": extracted.model_dump(),
        "redflag_scan": redflag_result,
        "agent_findings": agent_result["findings"],
        "domain_similarity": agent_result["domain_similarity"],
        "agent_notes": agent_result["agent_notes"],
        "verdict": verdict.model_dump(),
    }
