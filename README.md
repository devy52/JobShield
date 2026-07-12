# JobShield

An AI agent that analyzes a pasted job posting or recruiter message and flags
scam risk, with exact evidence for each red flag -- domain age, whether the
company's claimed domain matches its real one, and known scam-pattern phrases.
Built for AMD Developer Hackathon: ACT II (Unicorn Track).

Works on any pasted text, not just listings on one platform -- covering the
off-platform pivot (WhatsApp/Telegram/personal email) that platform-native
moderation can't reach.

## Status: Day 2 complete (pending your live verification)

**Day 1 -- tools layer**
- [x] Extraction schema + Fireworks extraction call, verified via mocked responses
- [x] WHOIS domain-age tool (+ distinguishes "not registered" from generic failure)
- [x] Live search tool (official domain lookup)
- [x] Domain similarity / typosquat tool (tldextract-based, subdomain-safe)
- [x] Deterministic red-flag ruleset
- [x] User-supplied "known domain" input, reviews search, social presence check
- [x] Eval sample for benchmarking (`tests/eval_sample.csv`) -- 30 labeled postings,
      run the finished pipeline against this on Day 3 and report precision/recall

**Day 2 -- agent, synthesis, UI, container**
- [x] Tool-calling agent loop (`agent/orchestrator.py`) -- orchestrator model decides
      which of 4 verification tools to call, deduplicates repeat calls, chains
      domain_similarity automatically once search results are in. Verified via
      `tests/test_orchestrator_mock.py` (scripted multi-turn tool-calling, no network)
- [x] Risk synthesis (`agent/synthesis.py`) -- deterministic baseline score
      from hard signals (`compute_base_score`) + an LLM layered on top for evidence
      bullets and plain-English explanation. (Originally allowed the model a
      bounded +/-10 point score adjustment; superseded on Day 3 -- see changelog
      below, scoring is now fully code-controlled with no model input at all.)
      Verified via `tests/test_synthesis_mock.py` (rubric sanity checks + mocked
      LLM response parsing)
- [x] Full pipeline (`agent/pipeline.py`) -- extraction -> red-flag scan -> agent
      loop -> synthesis, one function for the UI to call
- [x] Streamlit UI (`app.py`) -- paste box, optional known-domain input, risk
      gauge with labeled 35/65 thresholds, evidence list, "show agent's work"
      panel. Boot-tested (returns HTTP 200, no errors) but NOT live-tested against
      real Fireworks calls yet
- [x] Dockerfile + .dockerignore -- NOT build-tested (no Docker available in my
      sandbox, and no Docker Hub access even if there were) -- you need to verify
      `docker build` actually works

**Day 3 -- demo cases, eval, pitch**
- [x] `scripts/generate_demo_cache.py` -- pre-computes results for the 3 sample
      postings and saves to `demo_cache.json`, so the live demo's "Try an
      example" buttons never depend on WHOIS/search/Fireworks succeeding live.
      NOT YET RUN -- needs your Fireworks key, run this once the pipeline is
      confirmed good
- [x] `app.py` updated -- "How this works" section, "Try an example" buttons
      (load from cache, gracefully absent if `demo_cache.json` doesn't exist
      yet), shows the analyzed text alongside any result (live or cached).
      Boot-tested clean both with and without the cache file present
- [x] `scripts/run_eval.py` -- runs the full pipeline against the 30-posting
      eval sample, computes precision/recall/F1/accuracy, saves to
      `eval_results.json`. NOT YET RUN -- burns real credits (~30 postings x
      a few calls each), run once, not repeatedly
- [x] `PITCH.md` -- judge-facing submission narrative (stats, differentiation,
      architecture, roadmap, honest limitations), separate from this
      developer-facing README. Has a placeholder for eval numbers -- fill in
      after running `scripts/run_eval.py`
- [ ] Backup demo video -- not something I can produce; script/record this
      once demo_cache.json is generated and the UI is confirmed working
- [ ] Deploy to Streamlit Community Cloud -- needs your GitHub + Streamlit account
- [ ] Docker build -- still not verified end-to-end (see Day 2 section above)
- [ ] Submit

## What YOU still need to verify (can't be done from my sandbox)

1. `python -m tests.test_pipeline_live` -- the real end-to-end test, runs all 3
   sample postings through extraction -> agent loop -> synthesis for real
2. `streamlit run app.py` -- click through the UI with a real posting
3. `docker build -t jobshield .` then `docker run -p 8501:8501 --env-file .env jobshield`
   -- confirm the container actually builds and serves. Note: `.env` is
   deliberately excluded from the image (see `.dockerignore`) -- pass secrets at
   `docker run` time, don't bake them in

## Fixed after live testing surfaced a scoring accuracy gap (Day 3, submission day)

Sophisticated scam postings using paraphrased language ("We will send you an
electronic check to purchase your Apple MacBook Pro") scored only medium risk,
despite the agent's own narrative reasoning calling them "near-certain scams."
Root cause: `scan_red_flags`' exact-keyword matching missed this phrasing
entirely, and raw `red_flag_phrases` count doesn't reflect severity (one
devastating pattern scored the same as one minor one).

Fixed by adding `RiskFlags` (`agent/schema.py`) -- 4 booleans classified by
the same extraction call, using a strict per-category rubric instead of exact
keyword matching. These are now the primary scoring signal in
`compute_base_score`; `scan_red_flags` and raw phrase count still contribute
but capped low, as backup signals rather than the main driver. Regression
test added in `tests/test_synthesis_mock.py` using the exact posting that
scored wrong live (47/medium -> now 82/high with risk_flags set).

## Fixed after live testing surfaced score instability (Day 3)

Running the same posting text repeatedly produced wildly different scores
(e.g. the subtle-scam case: 71, then 49, then 71). Root-caused to two things:

1. **The LLM wasn't reliably respecting the prompted "adjust by at most 10
   points" bound.** The math didn't add up otherwise -- with no domain claimed,
   WHOIS/similarity never fire, so the deterministic baseline for the subtle
   case should max out around 40, yet live runs hit 71. Fixed by removing the
   model's ability to set `risk_score`/`risk_label` at all: `compute_base_score`
   is now the *only* source of the score, and `synthesize_risk` overwrites
   whatever the model returns for those fields even if it includes them anyway
   (see the regression test in `tests/test_synthesis_mock.py` that mocks
   exactly this misbehavior and confirms it's ignored). The LLM's job is now
   narrower: evidence + explanation only, grounded in the already-final score.
2. `temperature=0.2` on the synthesis call added unnecessary variance for a
   task that should be reproducible -- changed to `0`.

**Not fixed, and can't fully be:** live search/WHOIS results genuinely differ
call-to-call for companies with little real web footprint (this is why the
rock-stable case was "Amazon" and the unstable ones were fictional test
companies with nothing consistent for search to find). This is inherent to
doing *live* verification rather than checking against a static list --
documented honestly in `PITCH.md` rather than hidden. `demo_cache.json` locks
in one snapshot so this doesn't surface during the actual demo.

## Fixed after first live test run (Day 1, afternoon/evening)

Your first `test_live.py` run surfaced 4 real bugs, fixed:
1. WHOIS lookups on unregistered domains were buried under a generic
   `lookup_failed` with a wall of legal text -- now surfaced distinctly as
   `domain_not_registered: True`, a stronger signal than "newly registered."
2. Domain similarity mis-parsed subdomains (`hiring.amazon.com` read as
   `hiring`, not `amazon`) -- now uses `tldextract` for correct parsing.
3. Extraction was hallucinating a `claimed_domain` when the posting never
   stated one -- prompt now explicitly forbids inferring a domain from the
   company name alone.
4. `red_flag_phrases` wasn't staying verbatim (paraphrased "cash it" as
   "check-cashing") -- prompt now requires exact substrings only.

Also swapped the `REAL_POSTING` sample off "Acme Corp" (collides with the
fictional Acme Corporation in search results).

**Known limitation, not fixed (carry into the pitch's honest caveats, not
a blocker):** search/reviews/social-presence results aren't filtered for
relevance to the *specific* company -- a generic or common company name can
surface loosely-related results. Worth a sentence in the demo script rather
than solving algorithmically this close to deadline.

## Cost management (limited Fireworks credits)

- **The real dividing line is serverless vs. on-demand, not model size.**
  Serverless = pay-per-token, scales to ~$0 when idle. On-demand = dedicated
  GPU deployment, billed hourly whether you're using it or not (shows as a
  min/max cost estimate in the console). MoE architecture doesn't dodge this:
  fewer active params per token helps compute cost, but the full parameter
  set still has to sit in GPU memory, so MoE models often land on the
  expensive on-demand tier anyway.
- Confirmed against the actual serverless list in the console (2026-07-09):
  no Gemma model is serverless at all -- only reachable via on-demand
  deployment (~$28-40 min, confirmed). Re-check with a direct "gemma" search
  in the console before ruling it out entirely -- this list may not be exhaustive.
- Extraction + orchestrator: `deepseek-v4-flash` -- cheapest confirmed
  serverless model that also has function-calling support. Note some cheap
  serverless models (e.g. `gpt-oss-20b`) do NOT support function calling and
  will break the orchestrator's tool-calling loop -- check for that tag
  specifically, not just the price.
- Synthesis: must be Gemma for the "Best Use of Gemma" bonus track, but
  defaults to `deepseek-v4-pro` (NOT Gemma) since none is serverless. This is
  a genuine tradeoff, not a technical constraint: synthesis is a single
  bounded call, not a loop, so cost is a non-issue here (~$0.005/call even at
  this model's list price) *unless* you specifically want the Gemma bonus
  badge, in which case budget for the on-demand cost deliberately.
- If chasing the Gemma bonus and on-demand is unavoidable: deploy right
  before you need it, run live tests + eval + demo in one concentrated
  session, then undeploy immediately. Don't leave it deployed idle -- that's
  what burns the "min" cost even with no traffic.
- The agent loop resends the full conversation on every tool-calling turn, so
  iteration COUNT matters more than per-token price for the serverless models
  -- `MAX_TOOL_ITERATIONS` in `agent/orchestrator.py` is capped at 4 for this reason.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in FIREWORKS_API_KEY, verify model slugs
```

## Running tests

```bash
# No network needed -- pure logic + mocked LLM/tool responses
python -m tests.test_offline
python -m tests.test_extraction_mock
python -m tests.test_orchestrator_mock
python -m tests.test_synthesis_mock

# Needs FIREWORKS_API_KEY + real network access (not sandboxed)
python -m tests.test_live            # individual tools in isolation
python -m tests.test_pipeline_live   # full pipeline, all 3 sample postings

# The actual app
streamlit run app.py
```

## Architecture

1. **Extraction** (fast model via Fireworks) -- pulls company name, claimed
   domain/email, salary, remote flag, contact channel from raw text. Strict
   prompt rules against hallucinating fields not literally present in the text.
2. **Agent loop** (`agent/orchestrator.py`) -- orchestrator model decides which
   verification tools to call: WHOIS, live search, reviews search, social
   presence. `domain_similarity` runs automatically afterward on whatever
   search turned up (deterministic, not left to the model).
3. **Synthesis** (Fireworks, model-agnostic) -- deterministic baseline score from
   hard signals, an LLM writes the evidence bullets and explanation on top;
   scoring is fully code-controlled regardless of what the model returns. No
   Gemma variant is serverless on Fireworks as of this build (confirmed via
   direct console search) -- defaults to `deepseek-v4-pro`. Not competing for
   the "Best Use of Gemma" bonus track; architecture would support a one-line
   model swap if a serverless Gemma option becomes available.
4. **UI** (Streamlit) -- paste box -> risk gauge + evidence + explanation +
   transparent "agent's work" panel.
