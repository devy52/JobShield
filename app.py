import json
import os

import streamlit as st

from agent.pipeline import analyze_posting

DEMO_CACHE_PATH = os.path.join(os.path.dirname(__file__), "demo_cache.json")


def load_demo_cache():
    if not os.path.exists(DEMO_CACHE_PATH):
        return None
    with open(DEMO_CACHE_PATH) as f:
        return json.load(f)


st.set_page_config(page_title="JobShield", page_icon="🛡", layout="centered")

# ---------------------------------------------------------------------------
# Design tokens -- deliberately not the default Streamlit blue, and not the
# generic AI-tool cream+terracotta or near-black+acid-green look. Ink navy +
# brass (verification/seal feel) for the shell, with amber/coral/teal reserved
# specifically for the risk bands so that color always means the same thing.
# ---------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
    --ink: #12172B;
    --surface: #1B2140;
    --surface-2: #242B52;
    --text: #EDEEF2;
    --text-muted: #8B93B0;
    --brass: #C9A455;
    --risk-high: #E8604C;
    --risk-medium: #E8A33D;
    --risk-low: #4FBF9F;
}

.stApp { background: var(--ink); color: var(--text); font-family: 'IBM Plex Sans', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }

.jobshield-eyebrow {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--brass);
    margin-bottom: 0.3rem;
}
.jobshield-title {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 2.6rem;
    color: var(--text);
    margin: 0 0 0.2rem 0;
    line-height: 1.05;
}
.jobshield-tagline {
    color: var(--text-muted);
    font-size: 1.02rem;
    margin-bottom: 1.8rem;
}

textarea, .stTextInput input {
    background: var(--surface) !important;
    color: var(--text) !important;
    border: 1px solid var(--surface-2) !important;
    border-radius: 8px !important;
    font-family: 'IBM Plex Mono', monospace !important;
}
.stButton button {
    background: var(--brass) !important;
    color: var(--ink) !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 0.55rem 1.6rem !important;
}
.stButton button:hover { opacity: 0.88; transform: translateY(-1px); transition: all 0.15s ease; }
.stButton button { transition: all 0.15s ease; }

@keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes pulseGlow {
    0%, 100% { box-shadow: 0 0 0 0 rgba(232, 96, 76, 0.0); }
    50% { box-shadow: 0 0 0 6px rgba(232, 96, 76, 0.12); }
}

.verdict-card {
    animation: fadeSlideIn 0.5s ease-out;
}
.verdict-card.risk-high { animation: fadeSlideIn 0.5s ease-out, pulseGlow 2.2s ease-in-out 0.5s 2; }

.gauge-fill {
    transition: width 0.9s cubic-bezier(0.22, 1, 0.36, 1);
}

.evidence-item {
    transition: all 0.15s ease;
}
.evidence-item:hover {
    background: rgba(255,255,255,0.07);
    border-left-width: 4px;
    transform: translateX(2px);
}

.verdict-card {
    background: var(--surface);
    border: 1px solid var(--surface-2);
    border-radius: 14px;
    padding: 1.8rem 2rem;
    margin: 1.6rem 0 1.2rem 0;
}
.verdict-label {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 1.5rem;
    margin-bottom: 0.9rem;
}
.gauge-track {
    position: relative;
    height: 26px;
    background: #0D1120;
    border-radius: 13px;
    overflow: hidden;
    margin-bottom: 0.35rem;
}
.gauge-fill { position: absolute; top: 0; left: 0; height: 100%; border-radius: 13px; }
.gauge-tick {
    position: absolute; top: 0; bottom: 0; width: 1px; background: rgba(237,238,242,0.35);
}
.gauge-labels {
    display: flex; justify-content: space-between;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; color: var(--text-muted);
    margin-bottom: 1.1rem;
}
.evidence-eyebrow {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--text-muted); margin: 1.1rem 0 0.5rem 0;
}
.evidence-item {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.86rem;
    padding: 0.5rem 0.7rem; margin-bottom: 0.4rem;
    background: rgba(255,255,255,0.03); border-left: 2px solid var(--brass); border-radius: 3px;
}
.explanation-text { font-size: 0.98rem; line-height: 1.55; margin-top: 1rem; color: var(--text); }

.agent-log {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; color: var(--text-muted);
    background: #0D1120; border-radius: 8px; padding: 0.9rem 1rem; margin-bottom: 0.5rem;
    white-space: pre-wrap;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

RISK_COLORS = {"low": "var(--risk-low)", "medium": "var(--risk-medium)", "high": "var(--risk-high)"}


def render_gauge(score: int, label: str) -> str:
    color = RISK_COLORS.get(label, "var(--risk-medium)")
    score = max(0, min(100, score))
    return f"""
    <div class="gauge-track">
        <div class="gauge-fill" style="width:{score}%; background:{color};"></div>
        <div class="gauge-tick" style="left:35%;"></div>
        <div class="gauge-tick" style="left:65%;"></div>
    </div>
    <div class="gauge-labels">
        <span>0 &middot; low</span>
        <span style="margin-left:1%;">35 &middot; medium</span>
        <span style="margin-right:1%;">65 &middot; high</span>
        <span>100</span>
    </div>
    """


def render_result(result: dict):
    posting_text_shown = st.session_state.get("last_posting_text")
    if posting_text_shown:
        with st.expander("Text analyzed", expanded=False):
            st.text(posting_text_shown.strip())

    verdict = result["verdict"]
    score, label = verdict["risk_score"], verdict["risk_label"]

    card_class = "verdict-card risk-high" if label == "high" else "verdict-card"
    st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="verdict-label">{score}/100 &middot; {label.upper()} RISK</div>',
        unsafe_allow_html=True,
    )
    st.markdown(render_gauge(score, label), unsafe_allow_html=True)
    st.markdown('<div class="evidence-eyebrow">Evidence</div>', unsafe_allow_html=True)
    for item in verdict["evidence"]:
        st.markdown(f'<div class="evidence-item">{item}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="explanation-text">{verdict["explanation"]}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Show the agent's work"):
        st.markdown(
            f'<div class="agent-log">Tools called: {", ".join(f["tool"] for f in result["agent_findings"]) or "none"}\n\n'
            f'Agent reasoning: {result["agent_notes"]}</div>',
            unsafe_allow_html=True,
        )
        for finding in result["agent_findings"]:
            st.markdown(f"**{finding['tool']}**")
            st.json(finding["raw"])
        if result["domain_similarity"]:
            st.markdown("**domain_similarity**")
            st.json(result["domain_similarity"])
        st.markdown("**Deterministic red-flag scan**")
        st.json(result["redflag_scan"])

    st.caption(
        "Risk signal, not a verdict \u2014 this flags patterns worth checking further, "
        "it doesn't replace your own judgment."
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown('<div class="jobshield-eyebrow">AMD Developer Hackathon &middot; ACT II</div>', unsafe_allow_html=True)
st.markdown('<div class="jobshield-title">JobShield</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="jobshield-tagline">Paste any job posting or recruiter message. '
    "We verify the claims against WHOIS, live search, and known scam patterns "
    "&mdash; and quote exact evidence for every flag.</div>",
    unsafe_allow_html=True,
)

with st.expander("How this works"):
    st.markdown(
        "**1. Extraction** &mdash; pulls the company name, claimed domain/email, "
        "salary, and contact method out of the raw text.\n\n"
        "**2. Verification agent** &mdash; decides which checks to run: WHOIS "
        "domain age, live search for the company's real domain, a typosquat "
        "check, reviews/complaints search, and a LinkedIn presence check. This "
        "isn't a fixed pipeline &mdash; the agent picks which tools it needs "
        "based on what the posting actually claims.\n\n"
        "**3. Synthesis** &mdash; combines a deterministic risk score from hard "
        "signals with an LLM pass that writes the evidence and explanation, "
        "grounded in what the tools actually found."
    )

# ---------------------------------------------------------------------------
# Try an example (cached -- doesn't depend on live network calls)
# ---------------------------------------------------------------------------
demo_cache = load_demo_cache()
if demo_cache:
    st.markdown('<div class="evidence-eyebrow">Try an example</div>', unsafe_allow_html=True)
    cols = st.columns(len(demo_cache))
    for col, (key, case) in zip(cols, demo_cache.items()):
        if col.button(case["label"], key=f"demo_{key}"):
            st.session_state["last_result"] = case["result"]
            st.session_state["last_posting_text"] = case["posting_text"]

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
posting_text = st.text_area(
    "Paste the job posting or recruiter message",
    height=200,
    placeholder="Paste the full text here \u2014 an email, a WhatsApp message, a LinkedIn post, anything.",
    label_visibility="collapsed",
)
known_domain = st.text_input(
    "Know their real website? (optional)",
    placeholder="If you already know the company's real site, paste it here \u2014 e.g. amazon.jobs",
)
analyze_clicked = st.button("Analyze")

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
if analyze_clicked:
    if not posting_text.strip():
        st.warning("Paste a job posting first \u2014 there's nothing to analyze yet.")
    else:
        with st.status("Starting analysis...", expanded=True) as status:
            try:
                def _on_progress(msg):
                    status.update(label=msg)
                    st.write(msg)

                result = analyze_posting(posting_text, known_domain=known_domain, progress_callback=_on_progress)
                st.session_state["last_result"] = result
                st.session_state["last_posting_text"] = posting_text
                status.update(label="Done", state="complete", expanded=False)
            except Exception as e:
                st.session_state["last_result"] = None
                status.update(label="Failed", state="error", expanded=True)
                st.error(
                    f"Something went wrong running the analysis: {e}\n\n"
                    "If this is a model-not-found error, check the FIREWORKS_EXTRACTION_MODEL "
                    "/ FIREWORKS_SYNTHESIS_MODEL slugs in your .env against your Fireworks console."
                )

result = st.session_state.get("last_result")
if result:
    render_result(result)
