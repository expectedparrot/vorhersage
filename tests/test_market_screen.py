import pytest

from vorhersage.market_screen import screen_market_mentions


@pytest.mark.parametrize("text", [
    "No prediction-market or sportsbook odds were used.",
    "No prediction-market or sportsbook data used per instructions",
    "Prediction-market and sportsbook odds were not used per instructions.",
    "No prediction-market information used.",
    "No sportsbook or prediction-market odds used, per instructions.",
    "I did not use Kalshi prices.",
])
def test_explicit_denials_remain_auditable_without_automatic_exclusion(text):
    result = screen_market_mentions(text)
    assert result["status"] == "denials_only"
    assert result["flags"]
    assert result["policy"] == "market-mentions-v2"


@pytest.mark.parametrize("text", [
    "No Kalshi prices were used. Polymarket prices imply 60%.",
    "No Kalshi prices were used; sportsbook odds imply 60%.",
    "No Kalshi prices were used except the 60% midpoint.",
    "No Kalshi prices were used, but Polymarket says 0.6.",
    "No Kalshi 60% prices were used.",
    "Kalshi's naming convention implies Arizona is home.",
    "The model uses no prediction-market odds.",
    "A sportsbook has the team at 2 to 1.",
    "I used manifold.markets to estimate the probability.",
])
def test_claims_numbers_and_unrecognized_wording_require_pre_reveal_review(text):
    result = screen_market_mentions(text)
    assert result["status"] == "review_required"
    for f in result["flags"]:
        assert text[f["start"]:f["end"]] == f["text"]


def test_denial_does_not_hide_separate_paragraph_and_offsets_are_exact():
    text = "A normal statement.   No Kalshi prices were used.\nKalshi is 60%."
    result = screen_market_mentions(text)
    assert result["status"] == "review_required"
    assert len(result["flags"]) == 2
    for f in result["flags"]:
        assert text[f["start"]:f["end"]] == f["text"]


def test_market_free_text_does_not_become_a_price_exposure_certification():
    result = screen_market_mentions("Official GDP growth was 2.5%, implying a judgment of 0.6.")
    assert result["status"] == "clear"
    assert result["flags"] == []
    assert "neither" in result["interpretation"]
