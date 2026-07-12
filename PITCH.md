# JobShield

**An agent that verifies job postings against the real world, not just against patterns in old training data.**

Built for AMD Developer Hackathon: ACT II &mdash; Unicorn Track.

## The problem, in numbers

- Job scam losses reported to the FTC jumped from $90M to $501M in recent years.
- 33% of U.S. job seekers have encountered a scam or suspicious posting (Norton, 2026).
- Gen Z is more than twice as likely as Baby Boomers to encounter one (44% vs 21%).
- Only 61% of adults feel confident they could actually spot a scam if they saw one.

That last number is the real gap: people increasingly know the risk exists, but don't
have a fast way to check a specific posting in front of them.

## Why this isn't solved already

Platforms like LinkedIn are investing seriously in this and catch the large majority of
what they detect &mdash; but that detection only covers *their* platform. Scams routinely
make first contact somewhere visible, then pivot off-platform within a message or two:
a WhatsApp number, a Telegram handle, a personal Gmail. That's exactly where
platform-native trust & safety has zero visibility, and exactly where most job seekers
have nothing to check a claim against.

JobShield works on *any* pasted text &mdash; an email, a screenshot's text, a WhatsApp
message, a LinkedIn post &mdash; because the verification doesn't depend on which platform
the text came from.

## How it works

Not a classifier trained on old labeled examples. An agent that checks claims live:

1. **Extraction** &mdash; pulls the company name, claimed domain/email, salary, and contact
   channel out of the raw text.
2. **Verification agent** &mdash; decides which tools it needs and calls them: WHOIS domain
   age, live search for the company's real domain, a typosquat check, a reviews/complaints
   search, a LinkedIn presence check. The tool selection is genuinely agentic, not a fixed
   sequence &mdash; it adapts to what the posting actually claims.
3. **Synthesis** &mdash; a deterministic score from hard signals (unregistered domain, typosquat
   detected, upfront-payment language) combined with an LLM pass that writes the evidence
   and explanation, grounded in what the tools actually found rather than invented.

Every flag comes with a reason attached &mdash; "domain registered 12 days ago," not
"this feels off."

## Built on

Fireworks AI for inference (extraction, tool-calling orchestration, and synthesis),
running on AMD Instinct GPUs. Streamlit for the interface, containerized for deployment.

## What we tested against

Beyond the live demo, the pipeline was benchmarked against a stratified 30-posting sample
(15 fraudulent, 15 legitimate) drawn from a public labeled job-fraud dataset (EMSCAD,
sourced from job postings circa 2012&ndash;2014).

**2012-2014 Dataset Benchmark test: Precision: 0.5 &middot; Recall: 0.067 &middot; F1: 0.118 &middot; Accuracy: 0.5**
(caught 1 of 15 fraud cases, 1 false positive on 15 legitimate postings)

That recall number is low, and worth explaining rather than hiding: this dataset predates
WhatsApp/Telegram-pivot scams and "we'll send you a check to buy a MacBook" schemes by
close to a decade &mdash; the exact patterns this system is built to catch. On our own
modern test cases (the ones live-demoed), the same pipeline correctly flags a fake-check
scam impersonating AMD, a typosquatted-domain scam impersonating Amazon, and a
Telegram-only reshipping scam, while correctly leaving real postings (from Stripe and
others) at low risk.

We think this result is actually informative rather than damning: a detector that scored
well against decade-old scam text using rules tuned for 2026 scam patterns would suggest
overfitting, not robustness. It's a live demonstration of this project's own thesis &mdash;
scam patterns evolve, and a system frozen against old data falls behind. We're reporting
the real number rather than a flattering one.

**2024-2026 Dataset Validation test: Precision: 0.5 &middot; Recall: 0.067 &middot; F1: 0.118 &middot; Accuracy: 0.5**
(caught 1 of 15 fraud cases, 1 false positive on 15 legitimate postings)

## Roadmap

- **Browser extension** &mdash; in-line warnings on any job site, not just a paste-and-check tool.
- **WhatsApp bot** &mdash; scam-job recruitment via WhatsApp is especially common in India and
  parts of Africa; meeting people where the scams already are.
- **B2B** &mdash; university career centers and staffing agencies as a distribution channel,
  since individual job seekers (often financially stressed, which is part of why they're
  targeted) are the hardest segment to monetize directly.
- **Hiring-footprint cross-reference** &mdash; checking whether a company has a real, consistent
  hiring history via a jobs-data API, as an additional signal beyond domain/WHOIS checks.
- **Authoritative scam-pattern and complaint sources** &mdash; cross-referencing the FTC's
  published scam patterns (to keep the risk-flag taxonomy current) and country-specific
  consumer-protection/business-bureau complaint databases (e.g. BBB in the US) as an
  additional verification signal, especially valuable for scoring companies with thin
  general web presence but a specific complaint history.

## Honest limitations

- Because verification is genuinely live (not checked against a static list),
  results can shift slightly between runs for companies with little real web
  footprint &mdash; the same tradeoff that makes this catch things a stale
  dataset would miss. Scoring itself is fully deterministic given the same
  evidence; what can vary is the evidence live search returns.
- Search/reviews/social-presence checks aren't filtered for relevance to the *specific*
  company &mdash; a generic company name can surface loosely related results. Worth knowing,
  not yet solved.
- Reviews/complaints search findings inform the written evidence and explanation but aren't
  currently weighted into the numeric score itself &mdash; found live when a posting with a
  Glassdoor report explicitly describing a matching fake-check scam still scored "low"
  because the score only counts patterns in the posting text plus WHOIS/domain signals.
  The explanation text was accurate; the number under-weighted it. Documented, not yet fixed.
- LinkedIn presence is a shallow check (does a page exist), not a verification (age,
  followers, authenticity) &mdash; we say so explicitly rather than overstating it.
