import json
import os
from typing import Optional

from agent.client import get_fireworks_client
from agent.schema import ExtractedPosting, RiskVerdict


from dotenv import load_dotenv
load_dotenv()

# Default is a strong serverless model, NOT Gemma -- as of the last console
# check, no Gemma variant is on Fireworks' serverless tier (only reachable via
# on-demand deployment, ~$28-40 min). Swap in a Gemma slug here only if you
# find one serverless, or decide to eat the on-demand cost for the "Best Use
# of Gemma" bonus track. See .env.example / README for the full tradeoff.
SYNTHESIS_MODEL = os.environ.get("FIREWORKS_SYNTHESIS_MODEL", "accounts/fireworks/models/deepseek-v4-pro")

# risk_score/risk_label are computed entirely in code from compute_base_score,
# not asked of or accepted from the model. A prompted "adjust by at most 10
# points" bound turned out not to be reliably respected in practice -- observed
# live runs on a ~25-40 baseline (no domain claimed, so WHOIS/similarity never
# fire) came back scored as high as 71, meaning the model was freely overriding
# the number despite the instruction. The fix is enforcing this in code, not
# writing a stricter-sounding prompt and hoping. The LLM's job now is narrower
# and more reliable: write evidence + explanation grounded in what the tools
# actually found, nothing else.
SYSTEM_PROMPT = """You are writing the evidence and explanation for a job-posting
scam risk assessment. You'll be given extracted posting facts, a risk score that
has ALREADY been finalized by deterministic rules (you do not compute or change
it), and raw findings from verification tools (WHOIS, live search, reviews search,
social presence, domain similarity).

Return ONLY valid JSON matching this schema, no prose outside the JSON, no markdown
code fences:
{
  "evidence": [string, ...],
  "explanation": string
}

Rules:
- evidence: 3-6 short bullet points, each grounded in a specific fact from the tool
  findings or a verbatim entry from red_flag_phrases. Do not invent evidence that
  isn't backed by what you were given -- if there isn't much evidence, say fewer,
  honest things rather than padding the list. If the evidence is thin, say so
  rather than manufacturing bullets.
- explanation: 2-4 plain-English sentences a non-technical job seeker could
  understand, consistent with the given risk_label. Frame this as a risk signal,
  not a verdict -- e.g. "this posting shows strong signs of being fraudulent,"
  not "this is definitely a scam."
"""


def compute_base_score(
    extracted: ExtractedPosting,
    redflag_result: dict,
    similarity_result: Optional[dict],
    whois_result: Optional[dict],
) -> int:
    """
    Deterministic scoring rubric -- this is the ONLY thing that determines
    risk_score. Kept in code, not left to the LLM even partially, after prompted
    bounds on LLM score adjustment proved unreliable in practice.

    risk_flags (LLM-classified booleans) are the primary pattern signal, not
    scan_red_flags (exact-keyword regex, misses paraphrased scam language) or
    raw red_flag_phrases count (treats one devastating phrase the same as one
    minor one). Both of those still contribute, but capped low -- backup
    signals, not the main driver, to avoid triple-counting the same evidence.
    """
    score = 0

    if whois_result:
        if whois_result.get("domain_not_registered"):
            score += 40  # claimed domain doesn't exist at all -- stronger than "new"
        elif whois_result.get("newly_registered"):
            score += 30

    if similarity_result:
        if similarity_result.get("typosquat_suspected"):
            score += 25
        elif similarity_result.get("no_official_domain_found"):
            score += 20

    flags = extracted.risk_flags
    if flags.has_fake_check_or_reshipping:
        score += 30  # specific, high-confidence scam mechanic
    if flags.has_upfront_payment:
        score += 22
    if flags.has_no_interview_pressure:
        score += 15
    if flags.has_unrealistic_pay:
        score += 10

    # Backup signals, deliberately capped low now that risk_flags is primary
    score += min(len(extracted.red_flag_phrases) * 4, 12)
    score += min(redflag_result.get("total_hits", 0) * 3, 10)

    domain_claimed = extracted.claimed_domain or extracted.claimed_email_domain
    off_platform = any(
        x in (extracted.contact_channel or "").lower() for x in ("whatsapp", "telegram", "text")
    )
    if not domain_claimed and off_platform:
        score += 15

    return max(0, min(100, score))


def derive_risk_label(score: int) -> str:
    if score < 35:
        return "low"
    if score <= 65:
        return "medium"
    return "high"


def synthesize_risk(extracted: ExtractedPosting, redflag_result: dict, agent_result: dict) -> RiskVerdict:
    whois_result = next(
        (f["raw"] for f in agent_result["findings"] if f["tool"] == "whois_lookup"), None
    )
    similarity_result = agent_result.get("domain_similarity")

    base_score = compute_base_score(extracted, redflag_result, similarity_result, whois_result)
    risk_label = derive_risk_label(base_score)

    context = {
        "extracted_posting": extracted.model_dump(),
        "deterministic_red_flags": redflag_result,
        "risk_score": base_score,
        "risk_label": risk_label,
        "tool_findings": agent_result["findings"],
        "domain_similarity": similarity_result,
        "agent_notes": agent_result.get("agent_notes", ""),
    }

    client = get_fireworks_client()
    response = client.chat.completions.create(
        model=SYNTHESIS_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context, indent=2)},
        ],
        temperature=0,
    )
    content = response.choices[0].message.content.strip()

    if content.startswith("```"):
        content = content.strip("`")
        if "\n" in content:
            content = content.split("\n", 1)[1]

    data = json.loads(content)

    # risk_score/risk_label are NEVER taken from the model's output, even if it
    # includes them anyway -- always overwritten with the deterministic values.
    return RiskVerdict(
        risk_score=base_score,
        risk_label=risk_label,
        evidence=data.get("evidence", []),
        explanation=data.get("explanation", ""),
    )
