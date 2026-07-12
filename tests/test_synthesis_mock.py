"""
Three things tested here:
1. compute_base_score / derive_risk_label -- pure logic, no network, safe anywhere.
2. synthesize_risk -- mocks a well-behaved LLM response (evidence + explanation
   only) and verifies risk_score/risk_label come from the deterministic rubric,
   not the model.
3. synthesize_risk override test -- mocks a MISBEHAVING response where the model
   sneaks a risk_score/risk_label into its JSON anyway (simulating exactly the
   failure mode observed in live testing, where the model didn't respect the
   old "adjust by at most 10 points" instruction). Confirms the code ignores
   it either way.

Does NOT confirm the live model writes good evidence/explanations -- that needs
a live run on your machine.

Usage: python -m tests.test_synthesis_mock
"""

import json
from unittest.mock import MagicMock, patch

import agent.synthesis as synthesis_module
from agent.schema import ExtractedPosting, RiskVerdict
from agent.synthesis import compute_base_score, derive_risk_label


def _fake_response(content: str):
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


def test_scoring_rubric():
    print("=== compute_base_score / derive_risk_label cases ===")

    scam_extracted = ExtractedPosting(
        company_name="Amazon",
        claimed_email_domain="arnazon-jobs.com",
        contact_channel="WhatsApp",
        red_flag_phrases=["no interview required", "registration fee of $50", "respond within 24 hours"],
    )
    scam_redflags = {"total_hits": 4}
    scam_similarity = {"typosquat_suspected": True, "no_official_domain_found": False}
    scam_whois = {"domain_not_registered": True}
    scam_score = compute_base_score(scam_extracted, scam_redflags, scam_similarity, scam_whois)
    print(f"Obvious scam score: {scam_score} (expect high, >=80) -> label={derive_risk_label(scam_score)}")
    assert scam_score >= 80
    assert derive_risk_label(scam_score) == "high"

    real_extracted = ExtractedPosting(company_name="Meridian Ledger Systems", claimed_domain="meridianledger.com", red_flag_phrases=[])
    real_redflags = {"total_hits": 0}
    real_similarity = {"typosquat_suspected": False, "no_official_domain_found": False}
    real_whois = {"domain_not_registered": False, "newly_registered": False}
    real_score = compute_base_score(real_extracted, real_redflags, real_similarity, real_whois)
    print(f"Clean real posting score: {real_score} (expect low, <=10) -> label={derive_risk_label(real_score)}")
    assert real_score <= 10
    assert derive_risk_label(real_score) == "low"

    subtle_extracted = ExtractedPosting(
        company_name="FlexTest Solutions",
        claimed_domain=None,
        claimed_email_domain=None,
        contact_channel="Telegram @flextest_hr",
        red_flag_phrases=["cash it"],
    )
    subtle_redflags = {"total_hits": 0}
    subtle_score = compute_base_score(subtle_extracted, subtle_redflags, None, None)
    print(f"Subtle scam score: {subtle_score} (expect moderate, 15-40) -> label={derive_risk_label(subtle_score)}")
    assert 15 <= subtle_score <= 40

    # Regression test for the real bug found in live testing: a sophisticated
    # fake-check scam with NO domain claimed and phrasing that scan_red_flags'
    # literal keyword matching misses entirely ("We will send you an electronic
    # check..." doesn't match any configured keyword substring). Before
    # risk_flags existed, this scored 47/medium despite the agent's own
    # narrative calling it a "near-certain scam." risk_flags should catch it
    # even when the keyword scanner and phrase-count can't.
    from agent.schema import RiskFlags

    sophisticated_extracted = ExtractedPosting(
        company_name="GlobalTech Innovations Ltd.",
        contact_channel="Telegram, WhatsApp",
        red_flag_phrases=[
            "IMMEDIATE HIRE",
            "NO EXPERIENCE REQUIRED!",
            "We will send you an electronic check to purchase your Apple MacBook Pro",
        ],
        risk_flags=RiskFlags(has_fake_check_or_reshipping=True, has_no_interview_pressure=True, has_unrealistic_pay=True),
    )
    sophisticated_score = compute_base_score(sophisticated_extracted, {"total_hits": 0}, None, None)
    print(f"Sophisticated fake-check scam (0 keyword hits, relies on risk_flags): {sophisticated_score} "
          f"(expect high, >65) -> label={derive_risk_label(sophisticated_score)}")
    assert sophisticated_score > 65, f"risk_flags should push this to high even with 0 scan_red_flags hits, got {sophisticated_score}"
    assert derive_risk_label(sophisticated_score) == "high"

    print("[PASS] scoring rubric and label derivation behave sensibly\n")


SCAM_CONTEXT = dict(
    extracted=ExtractedPosting(
        company_name="Amazon",
        claimed_email_domain="arnazon-jobs.com",
        contact_channel="WhatsApp",
        red_flag_phrases=["no interview required", "registration fee of $50"],
    ),
    redflag_result={"total_hits": 3, "categories_triggered": ["upfront_payment", "no_interview"]},
    agent_result={
        "findings": [{"tool": "whois_lookup", "summary": "{}", "raw": {"domain_not_registered": True}}],
        "domain_similarity": {"typosquat_suspected": True, "best_match": "amazon.jobs"},
        "agent_notes": "High risk: unregistered domain, typosquat, upfront fee requested.",
    },
)
# Expected deterministic score for the context above: 40 (unregistered) + 25
# (typosquat) + 16 (2 red flags x8) + 15 (3 hits x5) = 96 -> "high"
EXPECTED_SCORE = compute_base_score(SCAM_CONTEXT["extracted"], SCAM_CONTEXT["redflag_result"], SCAM_CONTEXT["agent_result"]["domain_similarity"], {"domain_not_registered": True})
EXPECTED_LABEL = derive_risk_label(EXPECTED_SCORE)


def test_synthesis_well_behaved_response():
    print("=== synthesize_risk with a well-behaved response (evidence + explanation only) ===")

    fake_json = json.dumps(
        {
            "evidence": [
                "Claimed domain arnazon-jobs.com is not registered",
                "Domain closely resembles amazon.jobs, a likely typosquat",
                "Posting requests a 'registration fee of $50' before starting",
            ],
            "explanation": "This posting shows strong signs of being fraudulent.",
        }
    )

    with patch.object(synthesis_module, "get_fireworks_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_response(fake_json)
        mock_client_fn.return_value = mock_client

        verdict = synthesis_module.synthesize_risk(SCAM_CONTEXT["extracted"], SCAM_CONTEXT["redflag_result"], SCAM_CONTEXT["agent_result"])

    assert isinstance(verdict, RiskVerdict)
    assert verdict.risk_score == EXPECTED_SCORE, f"expected {EXPECTED_SCORE}, got {verdict.risk_score}"
    assert verdict.risk_label == EXPECTED_LABEL
    assert len(verdict.evidence) == 3
    print(f"[PASS] score={verdict.risk_score} (deterministic), label={verdict.risk_label}, "
          f"{len(verdict.evidence)} evidence bullets from the model\n")


def test_synthesis_ignores_model_score_override():
    print("=== synthesize_risk when the model sneaks in its own risk_score anyway ===")
    print("(this is the exact failure mode seen in live testing -- a model returning")
    print(" its own number despite instructions not to)")

    misbehaving_json = json.dumps(
        {
            "risk_score": 12,  # model ignoring instructions and inventing its own low score
            "risk_label": "low",
            "evidence": ["Some evidence the model made up anyway"],
            "explanation": "The model thinks this is fine, but the code should not listen to it.",
        }
    )

    with patch.object(synthesis_module, "get_fireworks_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_response(misbehaving_json)
        mock_client_fn.return_value = mock_client

        verdict = synthesis_module.synthesize_risk(SCAM_CONTEXT["extracted"], SCAM_CONTEXT["redflag_result"], SCAM_CONTEXT["agent_result"])

    assert verdict.risk_score == EXPECTED_SCORE, (
        f"BUG: model's score leaked through. Expected deterministic {EXPECTED_SCORE}, got {verdict.risk_score}"
    )
    assert verdict.risk_label == EXPECTED_LABEL, "BUG: model's label leaked through"
    print(f"[PASS] model tried to override with score=12/low, code correctly kept "
          f"score={verdict.risk_score}/{verdict.risk_label} regardless\n")


def run():
    test_scoring_rubric()
    test_synthesis_well_behaved_response()
    test_synthesis_ignores_model_score_override()
    print("All synthesis tests passed.")
    print("Reminder: this proves the rubric and score-clamping are correct, not that")
    print("the live model writes good evidence/explanations -- that needs a live run.")


if __name__ == "__main__":
    run()
