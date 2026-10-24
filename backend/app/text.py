"""Text normalization shared by the quote guard and the location resolver.

Normalization rules (README -> "2. Verify"):

* Unicode casefold, so case never matters.
* Punctuation stripped, replaced by a space so words never fuse together.
* Whitespace collapsed.
* **Accents kept.** Stripping them would let a quote in Spanish or Portuguese
  match a transcript it does not actually appear in.
"""

from __future__ import annotations

import unicodedata


def normalize(text: str) -> str:
    """Casefold, drop punctuation, collapse whitespace, keep accents."""
    folded = unicodedata.normalize("NFC", text).casefold()
    cleaned = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in folded)
    return " ".join(cleaned.split())


def tokens(text: str) -> list[str]:
    """Normalized whitespace-separated tokens."""
    normalized = normalize(text)
    return normalized.split() if normalized else []


def contains_exact(haystack: str, needle: str) -> bool:
    """True when ``needle`` is a contiguous run of whole words in ``haystack``.

    Both sides are normalized first, so punctuation and casing differences do
    not break an otherwise verbatim quote. Matching on word boundaries keeps a
    fragment such as "ite jacket" from passing as a quote of "white jacket".
    """
    normalized_needle = normalize(needle)
    if not normalized_needle:
        return False
    return f" {normalized_needle} " in f" {normalize(haystack)} "


def token_coverage(needle: str, haystack: str) -> float:
    """Fraction of ``needle``'s tokens that also appear in ``haystack``.

    Multiset-aware: a quote repeating a word twice needs that word twice in the
    transcript to score fully.
    """
    needle_tokens = tokens(needle)
    if not needle_tokens:
        return 0.0

    remaining: dict[str, int] = {}
    for token in tokens(haystack):
        remaining[token] = remaining.get(token, 0) + 1

    matched = 0
    for token in needle_tokens:
        if remaining.get(token, 0) > 0:
            remaining[token] -= 1
            matched += 1
    return matched / len(needle_tokens)


def first_words(text: str, limit: int) -> str:
    """First ``limit`` whitespace-separated words of ``text``, trimmed."""
    words = text.split()
    return " ".join(words[:limit]).strip()


def sha256_of(text: str) -> str:
    """Stable SHA-256 hex digest, used as the extraction cache key."""
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()
