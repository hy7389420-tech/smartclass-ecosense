import re

BANNED_TERMS = (
    "skipped",
    "skip",
    "bunked",
    "bunk",
    "intentionally",
    "lazy",
    "bored",
    "distracted",
    "attentive",
    "attention score",
    "emotion",
)


def assert_neutral_text(text: str) -> str:
    for term in BANNED_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE):
            raise ValueError(f"Generated text contains a prohibited term: {term}.")
    return text
