from server import _lookup

cases = {
    "આંખ": "આંખ",
    "આંખનો": "આંખ",
    "આંખોમાં": "આંખ",
    "ઘરમાં": "ઘર",
    "ઘરે": "ઘર",
    "પાણીમાં": "પાણી",
}

for word, expected in cases.items():
    entry = _lookup(word)
    got = entry["word"] if entry else None
    assert got == expected, f"{word!r}: expected {expected!r}, got {got!r}"

assert _lookup("સૂરજ") is None, "unknown word should stay unknown"
print("all lookup tests passed")