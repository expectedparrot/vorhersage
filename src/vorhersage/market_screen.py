"""Versioned lexical audit of forecast prose, not a detector of price exposure.

Only complete, narrowly specified denials are classified automatically. Other
mentions require a recorded review before targets are revealed. Source evidence
must still pass its own stricter URL/content boundary.
"""
import re

POLICY = "market-mentions-v2"
MENTION = re.compile(r"\b(?:kalshi|polymarket|predictit|manifold\.markets|prediction[ -]markets?|sportsbooks?|betting odds)\b", re.I)
_MARKET = r"(?:kalshi|polymarket|predictit|prediction[ -]markets?|sportsbooks?)"
_SUBJECT = _MARKET + r"(?:\s+(?:or|and)\s+" + _MARKET + r")*(?:\s+(?:odds|prices|data|information))?"
_SUFFIX = r"(?:,?\s+(?:per instructions|in this (?:forecast|estimate|assessment)))?"
_DENIAL = re.compile(
    r"(?:No\s+" + _SUBJECT + r"\s+(?:were\s+|was\s+|have been\s+|has been\s+)?(?:used|consulted|accessed)"
    r"|" + _SUBJECT + r"\s+(?:were|was|have been|has been)\s+not\s+(?:used|consulted|accessed)"
    r"|I\s+(?:did not|have not)\s+(?:use|consult|access)\s+" + _SUBJECT + r")"
    + _SUFFIX + r"[.!?]?", re.I)


def screen_market_mentions(text):
    """Return review flags; a clean result is not certification of non-exposure.

    Full-clause matching prevents a denial from clearing a separate affirmative
    claim. Numerical quotes, qualifications, and unrecognized wording always
    remain reviewable. Offsets refer to the original supplied text.
    """
    if not isinstance(text, str):
        raise ValueError("Forecast prose must be a string.")
    flags = []
    for part in re.finditer(r"[^\n;]+(?:;|\n|$)", text):
        # Split on sentence punctuation followed by whitespace, not domain dots.
        start = part.start()
        for sentence in re.split(r"(?<=[.!?])\s+", part.group()):
            clause = sentence.strip().rstrip(";").strip()
            matches = list(MENTION.finditer(sentence))
            if matches:
                denial = bool(_DENIAL.fullmatch(clause))
                flags.append({"start": start, "end": start + len(sentence),
                              "text": sentence, "mentions": [m.group() for m in matches],
                              "classification": "explicit_denial" if denial else "review_required"})
            start += len(sentence)
            # Recover the original offset even when the separator has >1 space.
            while start < part.end() and text[start].isspace():
                start += 1
    return {"policy": POLICY,
            "status": "review_required" if any(f["classification"] == "review_required" for f in flags)
                      else "denials_only" if flags else "clear",
            "flags": flags,
            "interpretation": "Lexical triage only; neither denials nor absence of keywords establish that prices were unavailable."}
