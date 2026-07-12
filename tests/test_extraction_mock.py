"""
Mocks the Fireworks/OpenAI response shape to test extract_posting's parsing
logic (JSON parsing, code-fence stripping, schema validation) without needing
network access or a real API key. Isolates "does my code work" from "does the
live model respond well" -- safe to run anywhere, including sandboxed environments.

This does NOT confirm the live Fireworks model extracts well from real text --
that still needs test_live.py, run on your machine with a real API key.

Usage: python -m tests.test_extraction_mock
"""

import json
from unittest.mock import MagicMock, patch

import agent.extraction as extraction_module
from agent.schema import ExtractedPosting


def _fake_response(content: str):
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


def _run_case(name: str, raw_content: str):
    with patch.object(extraction_module, "get_fireworks_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_response(raw_content)
        mock_client_fn.return_value = mock_client

        result = extraction_module.extract_posting("irrelevant -- response is mocked")
        assert isinstance(result, ExtractedPosting)
        print(f"[PASS] {name}")
        print(f"       {result.model_dump()}")


def run():
    clean_json = json.dumps(
        {
            "company_name": "Acme Corp",
            "claimed_domain": "acme.com",
            "claimed_email": None,
            "claimed_email_domain": None,
            "salary_range": "$100k-$130k",
            "remote_flag": True,
            "contact_channel": None,
            "red_flag_phrases": [],
        }
    )
    _run_case("clean JSON, no fences", clean_json)

    fenced_json = "```json\n" + clean_json + "\n```"
    _run_case("JSON wrapped in code fences (model ignored instructions)", fenced_json)

    minimal_json = json.dumps({"company_name": "Some Co", "remote_flag": False})
    _run_case("minimal JSON, missing optional fields (should default to null/[])", minimal_json)

    scam_shaped_json = json.dumps(
        {
            "company_name": "Amazon",
            "claimed_domain": None,
            "claimed_email": "careers@arnazon-jobs.com",
            "claimed_email_domain": "arnazon-jobs.com",
            "salary_range": "$45/hr",
            "remote_flag": True,
            "contact_channel": "WhatsApp",
            "red_flag_phrases": ["no interview required", "registration fee of $50"],
        }
    )
    _run_case("scam-shaped JSON with red flags populated", scam_shaped_json)

    print("\nAll parsing-logic cases passed.")
    print("Reminder: this proves extract_posting's code is correct, not that the")
    print("live model extracts well. Run test_live.py on your machine for that.")


if __name__ == "__main__":
    run()
