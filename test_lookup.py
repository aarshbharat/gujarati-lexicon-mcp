from server import _find

cases = {
    "આંખ": "આંખ",
    "આંખનો": "આંખ",
    "આંખોમાં": "આંખ",
    "ઘરમાં": "ઘર",
    "ઘરે": "ઘર",
    "પાણીમાં": "પાણી",
    "સૂરજ": "સૂરજ",  # was missing before; Wiktionary covers it now
}

for word, expected in cases.items():
    got = _find(word)
    assert got == expected, f"{word!r}: expected {expected!r}, got {got!r}"

assert _find("ઝઝઝઝ") is None, "nonsense should stay unknown"
print("all lookup tests passed")