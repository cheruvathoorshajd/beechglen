"""Quote grounding (README -> "2. Verify")."""

from __future__ import annotations

from app.contracts import ExtractedClaim, Extraction
from app.pipeline.verify import ground, quote_status

ENGLISH = "I'm the clerk. A man in a white jacket and jeans took the cash from the register. He ran toward Hynes station."
SPANISH = "Estoy en la tienda de Mass Ave y Boylston. Vi al hombre con una chaqueta blanca. Corrió hacia la estación."
PORTUGUESE = "Teve um acidente entre um SUV branco e uma picape vermelha."


def test_exact_quote_is_verified_despite_case_and_punctuation():
    assert quote_status("white jacket and jeans", ENGLISH) == "verified"
    assert quote_status("A man in a WHITE jacket, and jeans", ENGLISH) == "verified"


def test_partial_quote_is_pending():
    # 4 of 5 tokens appear (80%), but not as one contiguous run.
    assert quote_status("white jacket took the knife", ENGLISH) == "pending_verification"


def test_hallucinated_quote_is_rejected():
    assert quote_status("he had a red baseball cap", ENGLISH) == "rejected"
    assert quote_status("", ENGLISH) == "rejected"


def test_word_fragments_are_not_exact_matches():
    assert quote_status("ite jacket", ENGLISH) == "rejected"


def test_spanish_quote_with_accents_is_verified():
    assert quote_status("chaqueta blanca", SPANISH) == "verified"
    assert quote_status("Corrió hacia la estación", SPANISH) == "verified"


def test_accents_are_kept_so_an_unaccented_paraphrase_does_not_match():
    assert quote_status("Corrio hacia la estacion", SPANISH) == "rejected"


def test_portuguese_quote_is_verified():
    assert quote_status("SUV branco", PORTUGUESE) == "verified"


def test_ground_returns_one_status_per_claim_in_order():
    claims = [
        ExtractedClaim(subject="suspect", attribute="upper_clothing_color", value="white", quote="chaqueta blanca"),
        ExtractedClaim(subject="suspect", attribute="weapon", value="gun", quote="tenía una pistola"),
        ExtractedClaim(subject="suspect", attribute="direction_of_travel", value="station", quote="hacia la estación"),
    ]
    assert ground(Extraction(claims=claims), SPANISH) == ["verified", "rejected", "verified"]
