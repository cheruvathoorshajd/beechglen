"""Test doubles shared by the flow, API and agent tests."""

from __future__ import annotations

from app.contracts import CallIn, ExtractedClaim, Extraction


def claim(subject: str, attribute: str, value: str, quote: str, first_hand: bool = True) -> ExtractedClaim:
    return ExtractedClaim(subject=subject, attribute=attribute, value=value, quote=quote, first_hand=first_hand)


class FakeExtractor:
    """Maps a transcript to a prepared extraction; unknown transcripts raise."""

    def __init__(self) -> None:
        self.by_transcript: dict[str, Extraction] = {}

    def add(self, transcript: str, **fields) -> str:
        self.by_transcript[transcript] = Extraction(**fields)
        return transcript

    def __call__(self, call: CallIn) -> Extraction:
        return self.by_transcript[call.transcript]


class FakeToolCaller:
    """Records requests and replays canned tool inputs (None = failure)."""

    def __init__(self, *results) -> None:
        self.results = list(results)
        self.requests: list[dict] = []

    def __call__(self, **kwargs):
        self.requests.append(kwargs)
        if not self.results:
            return None
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
