import json
import os
from typing import Callable, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

from agent.client import get_fireworks_client
from agent.schema import ExtractedPosting, ToolFinding, UserContext
from tools.search_tool import search_official_domain, search_company_reviews, search_social_presence
from tools.similarity_tool import domain_similarity, merge_domain_candidates
from tools.whois_tool import whois_lookup

# Cheap/fast model for orchestration -- verify this slug in your Fireworks console.
ORCHESTRATOR_MODEL = os.environ.get(
    "FIREWORKS_ORCHESTRATOR_MODEL",
    os.environ.get("FIREWORKS_EXTRACTION_MODEL", "accounts/fireworks/models/deepseek-v4-flash"),
)


MAX_TOOL_ITERATIONS = 4

# domain_similarity/merge_domain_candidates are deliberately NOT exposed to the
# model -- they're deterministic post-processing on whatever search turns up,
# not something requiring judgment. Same reasoning for scan_red_flags, which
# runs upfront in the pipeline rather than as an agent-callable tool.
TOOL_REGISTRY: Dict[str, Callable] = {
    "whois_lookup": whois_lookup,
    "search_official_domain": search_official_domain,
    "search_company_reviews": search_company_reviews,
    "search_social_presence": search_social_presence,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "whois_lookup",
            "description": "Look up domain registration info: age, registrar, or whether it's registered at all. Use for any domain claimed in the posting or contact email.",
            "parameters": {
                "type": "object",
                "properties": {"domain": {"type": "string", "description": "Domain to check, e.g. example.com"}},
                "required": ["domain"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_official_domain",
            "description": "Search the web for the company's real, official website or careers page domain.",
            "parameters": {
                "type": "object",
                "properties": {"company_name": {"type": "string"}},
                "required": ["company_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_company_reviews",
            "description": "Search for public reviews or complaints mentioning this company alongside 'scam'.",
            "parameters": {
                "type": "object",
                "properties": {"company_name": {"type": "string"}},
                "required": ["company_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_social_presence",
            "description": "Shallow check for whether a LinkedIn company page shows up for this company name. Presence/absence only -- not verification of authenticity.",
            "parameters": {
                "type": "object",
                "properties": {"company_name": {"type": "string"}},
                "required": ["company_name"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are a verification agent investigating whether a job posting is legitimate.
You've been given structured facts already extracted from the posting. Decide which
verification tools to call to check the claims -- you don't have to call all of them,
and you can call more than one per turn. Typical approach: if a domain or email was
claimed, check its WHOIS registration; if a company name is present, search for its
official domain to compare against what was claimed; use the reviews/complaints
search and social presence check for extra signal, especially if the domain checks
are inconclusive. Do not call the same tool with the same arguments more than once.
Once you've gathered enough evidence, respond with a short plain-text summary of
what you found and why -- no JSON needed here, a separate step turns this into a
final risk score.
"""


def run_agent_loop(extracted: ExtractedPosting, user_context: Optional[UserContext] = None) -> dict:
    """
    Runs a tool-calling loop where the orchestrator model decides which verification
    tools to call based on the extracted posting. domain_similarity is then run
    automatically afterward on whatever search_official_domain turned up, merged
    with any user-supplied known_domain -- that step is deterministic, not left to
    the model's judgment.
    """
    user_context = user_context or UserContext()
    client = get_fireworks_client()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Extracted posting facts:\n{extracted.model_dump_json(indent=2)}"},
    ]

    findings: List[ToolFinding] = []
    search_candidates: List[str] = []
    called_signatures = set()
    final_notes = ""

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.chat.completions.create(
            model=ORCHESTRATOR_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0,
        )
        message = response.choices[0].message
        final_notes = message.content or final_notes

        if not message.tool_calls:
            messages.append({"role": "assistant", "content": message.content or ""})
            break

        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [tc.model_dump() for tc in message.tool_calls],
            }
        )

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            signature = (name, json.dumps(args, sort_keys=True))
            if name not in TOOL_REGISTRY:
                result = {"error": f"unknown tool {name}"}
            elif signature in called_signatures:
                result = {"skipped": True, "reason": "already called with these arguments"}
            else:
                called_signatures.add(signature)
                result = TOOL_REGISTRY[name](**args)
                if name == "search_official_domain":
                    search_candidates.extend(result.get("candidate_domains", []))
                findings.append(ToolFinding(tool=name, summary=json.dumps(args), raw=result))

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )
    else:
        # loop exhausted MAX_TOOL_ITERATIONS without the model stopping on its own
        final_notes = final_notes or "(agent hit max tool-call iterations)"

    domain_to_check = extracted.claimed_email_domain or extracted.claimed_domain
    similarity_result = None
    if domain_to_check:
        candidates = merge_domain_candidates(user_context.known_domain, search_candidates)
        similarity_result = domain_similarity(domain_to_check, candidates)

    return {
        "findings": [f.model_dump() for f in findings],
        "domain_similarity": similarity_result,
        "agent_notes": final_notes,
    }
