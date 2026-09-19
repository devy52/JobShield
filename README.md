# JobShield

An AI agent that analyzes a pasted job posting or recruiter message and flags
scam risk, with exact evidence for each red flag: domain age, whether the
company's claimed domain matches its real one, and known scam-pattern phrases.
Built for AMD Developer Hackathon: ACT II (Unicorn Track).

Works on any pasted text, not just listings on one platform, covering the
off-platform pivot (WhatsApp/Telegram/personal email) that platform-native
moderation can't reach.

**Live:** https://job-shield.streamlit.app/
(The "Try an example" buttons load cached results. Live analysis of pasted
text needs a working Fireworks API key. It's given but credits might run out.)

## Evaluation results

Run with `python -m scripts.run_eval` on the 30-posting labeled sample
(`tests/eval_sample.csv`). Full per-posting output: `eval_results.json`.

| Metric    | Score |
|-----------|-------|
| Precision | 0.929 |
| Recall    | 0.867 |
| F1        | 0.897 |
| Accuracy  | 0.900 |

Confusion matrix: 13 true positives, 14 true negatives, 1 false positive,
2 false negatives. "Flagged" means a medium or high risk label.

**Limitations:** n=30 is a small sample, so treat these numbers as indicative,
not definitive. Live WHOIS/search results can vary between calls for companies
with a thin web footprint (see "Score instability" below).

## Status

**Day 1: tools layer**
- [x] Extraction schema + Fireworks extraction call
- [x] WHOIS domain-age tool (distinguishes "not registered" from generic failure)
- [x] Live search tool (official domain lookup)
- [x] Domain similarity / typosquat tool (tldextract-based, subdomain-safe)
- [x] Deterministic red-flag ruleset
- [x] User-supplied "known domain" input, reviews search, social presence check
- [x] 30-posting labeled eval sample (`tests/eval_sample.csv`)

**Day 2: agent, synthesis, UI, container**
- [x] Tool-calling agent loop (`agent/orchestrator.py`): the orchestrator model
  decides which of 4 verification tools to call, deduplicates repeat calls,
  and chains domain_similarity automatically once search results are in.
  Tested via `tests/test_orchestrator_mock.py`.
- [x] Risk synthesis (`agent/synthesis.py`): deterministic score from hard
  signals (`compute_base_score`), with an LLM writing evidence bullets and the
  explanation. Scoring is fully code-controlled (see "Score instability").
- [x] Full pipeline (`agent/pipeline.py`): extraction, red-flag scan, agent
  loop, synthesis
- [x] Streamlit UI (`app.py`): paste box, optional known-domain input, risk
  gauge with 35/65 thresholds, evidence list, "show agent's work" panel
- [x] Dockerfile + .dockerignore

**Day 3: demo cases, eval, pitch, deploy**
- [x] `scripts/generate_demo_cache.py` and `demo_cache.json`: pre-computed
  results so the "Try an example" buttons never depend on live WHOIS/search/API
- [x] `scripts/run_eval.py` run; results in `eval_results.json`
- [x] `PITCH.md`
- [x] Deployed to Streamlit Community Cloud
- [ ] Docker build not yet verified end-to-end
- [ ] Backup demo video
- [ ] Submit

## Fixed after live testing surfaced a scoring accuracy gap

Sophisticated scam postings using paraphrased language ("We will send you an
electronic check to purchase your Apple MacBook Pro") scored only medium risk,
despite the agent's own narrative reasoning calling them "near-certain scams."
Root cause: `scan_red_flags`' exact-keyword matching missed this phrasing
entirely, and raw `red_flag_phrases` count doesn't reflect severity.

Fixed by adding `RiskFlags` (`agent/schema.py`): 4 booleans classified by the
same extraction call, using a strict per-category rubric instead of exact
keyword matching. These are now the primary scoring signal in
`compute_base_score`; `scan_red_flags` and raw phrase count still contribute
but capped low, as backup signals. Regression test added in
`tests/test_synthesis_mock.py` using the exact posting that scored wrong live
(47/medium, now 82/high).

## Score instability (fixed)

Running the same posting repeatedly produced wildly different scores (e.g. 71,
then 49, then 71). Two causes:

1. **The LLM wasn't reliably respecting the prompted "adjust by at most 10
   points" bound.** Fixed by removing the model's ability to set
   `risk_score`/`risk_label` at all: `compute_base_score` is now the *only*
   source of the score, and `synthesize_risk` overwrites whatever the model
   returns for those fields (regression test in `tests/test_synthesis_mock.py`
   mocks exactly this misbehavior). The LLM now writes evidence and
   explanation only, grounded in the already-final score.
2. `temperature=0.2` on the synthesis call added unnecessary variance. Changed
   to `0`.

**Not fixed, and can't fully be:** live search/WHOIS results genuinely differ
call-to-call for companies with little real web footprint. This is inherent to
live verification rather than checking against a static list. It is documented
in `PITCH.md`, and `demo_cache.json` locks in one snapshot for demos.

## Fixed after first live test run

1. WHOIS lookups on unregistered domains were buried under a generic
   `lookup_failed`; now surfaced as `domain_not_registered: True`, a stronger
   signal than "newly registered."
2. Domain similarity mis-parsed subdomains (`hiring.amazon.com` read as
   `hiring`); now uses `tldextract`.
3. Extraction hallucinated a `claimed_domain` when the posting never stated
   one; the prompt now forbids inferring a domain from the company name alone.
4. `red_flag_phrases` weren't staying verbatim; the prompt now requires exact
   substrings only.

**Known limitation:** search/reviews/social-presence results aren't filtered
for relevance to the specific company, so a common company name can surface
loosely related results.

## Cost management (limited Fireworks credits)

- The real dividing line is serverless vs. on-demand, not model size.
  Serverless is pay-per-token and scales to ~$0 when idle. On-demand is a
  dedicated GPU billed hourly whether you use it or not.
- Extraction + orchestrator: `deepseek-v4-flash`, the cheapest confirmed
  serverless model with function-calling support. Some cheap models (e.g.
  `gpt-oss-20b`) lack function calling and break the tool-calling loop.
- Synthesis: `deepseek-v4-pro`. No Gemma model was serverless on Fireworks at
  build time (checked 2026-07-09), so this project is not competing for the
  "Best Use of Gemma" bonus. The architecture supports a one-line model swap.
- The agent loop resends the full conversation each tool-calling turn, so
  `MAX_TOOL_ITERATIONS` in `agent/orchestrator.py` is capped at 4.

## Setup

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # fill in FIREWORKS_API_KEY, verify model slugs

Never commit `.env`. It is listed in `.gitignore`.

## Running tests

    # No network needed: pure logic + mocked LLM/tool responses
    python -m tests.test_offline
    python -m tests.test_extraction_mock
    python -m tests.test_orchestrator_mock
    python -m tests.test_synthesis_mock

    # Needs FIREWORKS_API_KEY + real network access
    python -m tests.test_live
    python -m tests.test_pipeline_live

    # Evaluation (burns API credits; run once)
    python -m scripts.run_eval

    # The app
    streamlit run app.py

## Architecture

1. **Extraction** (fast model via Fireworks): pulls company name, claimed
   domain/email, salary, remote flag, contact channel, and risk flags from raw
   text. Strict prompt rules against hallucinating fields.
2. **Agent loop** (`agent/orchestrator.py`): the orchestrator model decides
   which verification tools to call (WHOIS, live search, reviews search, social
   presence). `domain_similarity` runs automatically afterward.
3. **Synthesis** (Fireworks): deterministic score from hard signals, with an
   LLM writing the evidence bullets and explanation on top. Scoring is fully
   code-controlled regardless of what the model returns.
4. **UI** (Streamlit): paste box, risk gauge, evidence, explanation, and a
   transparent "agent's work" panel.
