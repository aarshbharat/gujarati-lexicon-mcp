import pytest

from gujarati_lexicon_mcp.server import _find


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("આંખ", "આંખ"),
        ("આંખનો", "આંખ"),
        ("આંખોમાં", "આંખ"),
        ("ઘરમાં", "ઘર"),
        ("ઘરનું", "ઘર"),
        ("ઘરે", "ઘર"),       # Wiktionary inflection link
        ("પાણીમાં", "પાણી"),
        ("સૂરજ", "સૂરજ"),    # Wiktionary coverage
        ("અમે", "હું"),      # plural pronoun → base word
    ],
)
def test_find(word, expected):
    assert _find(word) == expected


def test_unknown_word_stays_unknown():
    assert _find("ઝઝઝઝ") is None