"""Quote grounding: the hallucination guard (README -> "2. Verify").

Every extracted claim must cite a verbatim span of the transcript. Quote and
transcript are normalized the same way (Unicode casefold, punctuation
stripped, whitespace collapsed, accents kept), so the check works for Spanish
and Portuguese callers without letting an unaccented paraphrase pass.

| Check                                               | Status               |
|-----------------------------------------------------|----------------------|
| Quote is an exact (whole-word) run of the transcript | verified             |
| At least 80% of quote tokens appear in the transcript | pending_verification |
| Otherwise                                           | rejected             |

Fail-open: a partial match still flows through, at reduced weight, with a
marker; only an unsupported claim is excluded.
"""

from __future__ import annotations

from app.contracts import ClaimStatus, Extraction
from app.text import contains_exact, token_coverage

#: Share of quote tokens that must appear for ``pending_verification``.
PENDING_MIN_COVERAGE = 0.80


def quote_status(quote: str, transcript: str) -> ClaimStatus:
    """Grounding status of one quote against its transcript."""
    if contains_exact(transcript, quote):
        return "verified"
    if token_coverage(quote, transcript) >= PENDING_MIN_COVERAGE:
        return "pending_verification"
    return "rejected"


def ground(extraction: Extraction, transcript: str) -> list[ClaimStatus]:
    """One status per claim, in the same order as ``extraction.claims``."""
    return [quote_status(claim.quote, transcript) for claim in extraction.claims]
