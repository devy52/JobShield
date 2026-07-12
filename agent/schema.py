from typing import List, Optional
from pydantic import BaseModel, Field


class RiskFlags(BaseModel):
    """
    Boolean classification of known scam patterns, filled in by the same
    extraction call as ExtractedPosting. Exists because two deterministic
    signals proved too narrow on their own: scan_red_flags only catches exact
    keyword matches (missed "We will send you an electronic check to purchase
    your Apple MacBook Pro" entirely -- not a literal match for any configured
    phrase), and counting red_flag_phrases treats one devastating pattern the
    same as one minor one. Booleans are a narrower, more reliable ask of an
    LLM than a freely-chosen score -- same reasoning as why synthesis no
    longer sets risk_score directly.
    """

    has_upfront_payment: bool = Field(
        False, description="Posting asks the applicant to pay any fee -- registration, training, certification, equipment"
    )
    has_fake_check_or_reshipping: bool = Field(
        False,
        description="Posting involves receiving a check/funds to purchase items, or reshipping/forwarding packages -- classic fake-check scam mechanics",
    )
    has_no_interview_pressure: bool = Field(
        False, description="Posting states or implies hiring with no interview, immediate/instant hire, or a fast-track process bypassing normal screening"
    )
    has_unrealistic_pay: bool = Field(
        False, description="Pay is clearly disproportionate to the stated experience level or effort required"
    )


class ExtractedPosting(BaseModel):
    """Structured facts pulled from a raw pasted job posting / recruiter message."""

    company_name: Optional[str] = Field(None, description="Company name as stated in the posting")
    claimed_domain: Optional[str] = Field(None, description="Company website domain mentioned in the posting, if any")
    claimed_email: Optional[str] = Field(None, description="Contact email address mentioned in the posting, if any")
    claimed_email_domain: Optional[str] = Field(None, description="Domain portion of the contact email")
    salary_range: Optional[str] = Field(None, description="Stated salary or pay range")
    remote_flag: bool = Field(False, description="Whether the posting claims to be remote")
    contact_channel: Optional[str] = Field(
        None, description="How the poster wants to be contacted, e.g. WhatsApp, Telegram, personal email"
    )
    red_flag_phrases: List[str] = Field(
        default_factory=list,
        description="Suspicious phrases pulled verbatim from the posting (e.g. requests for upfront payment) -- for EVIDENCE display, not primarily for scoring",
    )
    risk_flags: RiskFlags = Field(default_factory=RiskFlags, description="Boolean scam-pattern classification -- for SCORING")


class UserContext(BaseModel):
    """
    Optional info the user already knows and supplies directly, rather than
    something extracted from the posting text. Feeds into domain_similarity
    as a trusted candidate alongside whatever live search turns up.
    """

    known_domain: Optional[str] = Field(
        None, description="Company website the user believes is real, from their own prior knowledge"
    )


class ToolFinding(BaseModel):
    tool: str
    summary: str
    raw: dict


class RiskVerdict(BaseModel):
    risk_score: int = Field(..., ge=0, le=100)
    risk_label: str  # "low" | "medium" | "high"
    evidence: List[str]
    explanation: str
