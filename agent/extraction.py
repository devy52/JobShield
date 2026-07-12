import json
import os

from agent.client import get_fireworks_client
from agent.schema import ExtractedPosting

from dotenv import load_dotenv
load_dotenv()

# Fast/cheap model for extraction -- verify the exact slug in your Fireworks
# console (Models tab) and set it in .env. This default is a placeholder.
EXTRACTION_MODEL = os.environ.get(
    "FIREWORKS_EXTRACTION_MODEL", "accounts/fireworks/models/deepseek-v4-flash"
)

SYSTEM_PROMPT = """You extract structured facts from a pasted job posting or recruiter message.
Return ONLY valid JSON matching this schema, no prose, no markdown code fences:
{
  "company_name": string or null,
  "claimed_domain": string or null,
  "claimed_email": string or null,
  "claimed_email_domain": string or null,
  "salary_range": string or null,
  "remote_flag": boolean,
  "contact_channel": string or null,
  "red_flag_phrases": [string, ...],
  "risk_flags": {
    "has_upfront_payment": boolean,
    "has_fake_check_or_reshipping": boolean,
    "has_no_interview_pressure": boolean,
    "has_unrealistic_pay": boolean
  }
}

STRICT RULES -- follow these exactly, they matter more than sounding complete:
1. claimed_domain and claimed_email_domain: only fill these in if a website or
   email address is LITERALLY WRITTEN in the text. Never invent, guess, or
   infer a domain from the company name alone, even if you're confident you
   know the company's real website. If no domain or email appears in the
   text, both fields must be null.
2. red_flag_phrases: each entry MUST be an exact verbatim substring copied
   from the input text -- not a paraphrase, summary, or category label. If
   you cannot find an exact quote in the text for a concern, leave it out
   rather than describing it in your own words. This list is for DISPLAY as
   quoted evidence, not for scoring -- it's fine if it's short or empty.
3. risk_flags -- this is what drives the actual risk score, so classify
   carefully using this rubric (each is independent, set true only if the
   text clearly supports it):
   - has_upfront_payment: any fee the applicant must pay -- registration,
     training, certification, background check, equipment purchased out of
     pocket. Reimbursement promises ("fully refunded on payday") still count.
   - has_fake_check_or_reshipping: posting involves the applicant receiving a
     check, e-check, or funds to purchase items, OR reshipping/forwarding
     packages. This applies regardless of exact wording -- "we'll send you a
     check to buy a laptop" and "we will send you an electronic check to
     purchase your Apple MacBook Pro" both count, even though they share no
     common substring.
   - has_no_interview_pressure: explicitly states or clearly implies no
     interview, immediate/instant hire, or a "fast-track" process that skips
     normal screening.
   - has_unrealistic_pay: pay is clearly disproportionate to the stated
     experience level or effort (e.g. high hourly pay for no-experience,
     minimal-effort work).
4. If a field isn't present in the text, use null (or an empty list for
   red_flag_phrases, or false for risk_flags). Do not fill gaps with
   plausible-sounding guesses.
"""


def extract_posting(raw_text: str) -> ExtractedPosting:
    client = get_fireworks_client()
    response = client.chat.completions.create(
        model=EXTRACTION_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        temperature=0,
    )
    content = response.choices[0].message.content.strip()

    # defensive cleanup in case the model wraps output in code fences anyway
    if content.startswith("```"):
        content = content.strip("`")
        if "\n" in content:
            content = content.split("\n", 1)[1]

    data = json.loads(content)
    return ExtractedPosting(**data)
