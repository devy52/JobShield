"""
Mocks both the Fireworks tool-calling loop and the underlying tool functions to
test run_agent_loop's control flow (tool dispatch, duplicate-call prevention,
domain_similarity chaining, loop termination) without network access or a real
API key. Safe to run anywhere, including sandboxed environments.

This does NOT confirm the live model makes good tool-calling decisions -- that
still needs a live run on your machine (tests/test_live.py).

Usage: python -m tests.test_orchestrator_mock
"""

import json
from unittest.mock import MagicMock, patch

import agent.orchestrator as orchestrator_module
from agent.schema import ExtractedPosting, UserContext


def _tool_call(call_id, name, arguments: dict):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    tc.model_dump.return_value = {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }
    return tc


def _response(content, tool_calls=None):
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def run():
    extracted = ExtractedPosting(
        company_name="Amazon",
        claimed_domain=None,
        claimed_email="careers@arnazon-jobs.com",
        claimed_email_domain="arnazon-jobs.com",
        salary_range="$45/hr",
        remote_flag=True,
        contact_channel="WhatsApp",
        red_flag_phrases=["no interview required"],
    )

    # Scripted turns: turn 1 calls 2 tools, turn 2 calls 1 more (+ a duplicate to
    # test dedup), turn 3 stops with a final summary.
    scripted_responses = [
        _response(
            None,
            tool_calls=[
                _tool_call("call_1", "whois_lookup", {"domain": "arnazon-jobs.com"}),
                _tool_call("call_2", "search_official_domain", {"company_name": "Amazon"}),
            ],
        ),
        _response(
            None,
            tool_calls=[
                _tool_call("call_3", "search_company_reviews", {"company_name": "Amazon"}),
                _tool_call("call_4", "whois_lookup", {"domain": "arnazon-jobs.com"}),  # duplicate on purpose
            ],
        ),
        _response(
            "Domain is unregistered and doesn't match search results for Amazon's real "
            "careers pages. Combined with WhatsApp-only contact, this looks high risk.",
            tool_calls=None,
        ),
    ]

    fake_tools = {
        "whois_lookup": MagicMock(
            return_value={"domain": "arnazon-jobs.com", "domain_not_registered": True, "lookup_failed": False}
        ),
        "search_official_domain": MagicMock(
            return_value={"candidate_domains": ["amazon.jobs", "hiring.amazon.com"]}
        ),
        "search_company_reviews": MagicMock(return_value={"results": []}),
        "search_social_presence": MagicMock(return_value={"linkedin_present": True}),
    }

    with patch.object(orchestrator_module, "TOOL_REGISTRY", fake_tools), patch.object(
        orchestrator_module, "get_fireworks_client"
    ) as mock_client_fn:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = scripted_responses
        mock_client_fn.return_value = mock_client

        result = orchestrator_module.run_agent_loop(extracted, UserContext())

    print("--- Result ---")
    print(json.dumps(result, indent=2))

    assert len(result["findings"]) == 3, f"expected 3 findings (dedup should drop the 4th call), got {len(result['findings'])}"
    assert result["domain_similarity"] is not None
    assert result["domain_similarity"]["typosquat_suspected"] is True
    assert fake_tools["whois_lookup"].call_count == 1, "whois_lookup should only run once despite 2 requests"
    assert fake_tools["search_official_domain"].call_count == 1
    assert fake_tools["search_company_reviews"].call_count == 1
    assert fake_tools["search_social_presence"].call_count == 0, "model never asked for this one"
    assert "high risk" in result["agent_notes"].lower()

    print("\n[PASS] agent loop dispatches tools correctly, dedups repeat calls,")
    print("       stops when the model stops, chains domain_similarity automatically,")
    print("       and never calls tools the model didn't ask for.")


if __name__ == "__main__":
    run()
