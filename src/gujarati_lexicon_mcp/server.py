import difflib
import json
import unicodedata
from datetime import date
from pathlib import Path

from mcp.server.mcpserver import MCPServer

mcp = MCPServer(
    "gujarati-lexicon",
    version="0.2.0",
    instructions=(
        "This server is a Gujarati dictionary combining two sources: a "
        "hand-checked dictionary (Gujarati meanings, idioms) and Wiktionary "
        "(English meanings, broad coverage). Prefer curated meanings when both "
        "exist. Always look Gujarati words up here before answering. If a word "
        "is not found, tell the user clearly; if you then answer from general "
        "knowledge, label it as not coming from the dictionary. Never invent idioms."
    ),
)

DATA_DIR = Path(__file__).parent / "data"
WIKTIONARY_ATTRIBUTION = "Wiktionary (en.wiktionary.org) via kaikki.org, CC BY-SA"

# Common Gujarati endings, longest first so "માંથી" is tried before "થી".
SUFFIXES = ["માંથી", "માં", "થી", "નો", "ની", "નું", "ના", "ને", "એ", "ે", "ો"]


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text.strip())


def _load(filename: str) -> dict[str, dict]:
    entries = json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
    return {normalize(e["word"]): e for e in entries}


CURATED = _load("curated.json")        # hand-checked: Gujarati meanings, idioms
WIKTIONARY = _load("wiktionary.json")  # broad coverage: English meanings
HEADWORDS = sorted(CURATED.keys() | WIKTIONARY.keys())
HEADWORD_SET = set(HEADWORDS)


# ---------- lookup helpers ----------

def _candidates(word: str) -> list[str]:
    """The word itself, then forms with up to two endings removed."""
    forms = [word]
    frontier = [word]
    for _ in range(2):
        frontier = [
            f[: -len(s)]
            for f in frontier
            for s in SUFFIXES
            if f.endswith(s) and len(f) > len(s)
        ]
        forms.extend(frontier)
    return forms


    """If the headword is only an inflected form, return its base word."""
    wiki = WIKTIONARY.get(headword)
    if wiki and not wiki["senses"] and wiki.get("lemma") in HEADWORD_SET:
        return wiki["lemma"]
    return headword


def _find(word: str) -> str | None:
    """Return the dictionary headword for a word (or its inflected form)."""
    for form in _candidates(normalize(word)):
        if form in HEADWORD_SET:
            return _resolve(form)
    return None

def _resolve(headword: str) -> str:
    """If the headword is only an inflected form, return its base word."""
    wiki = WIKTIONARY.get(headword)
    if wiki and not wiki["senses"] and wiki.get("lemma") in HEADWORD_SET:
        return wiki["lemma"]
    return headword


def _not_found(word: str) -> dict:
    suggestions = difflib.get_close_matches(normalize(word), HEADWORDS, n=3, cutoff=0.6)
    return {
        "found": False,
        "word": word,
        "suggestions": suggestions,
        "message": "This word is not in the dictionary. If you answer from "
                   "general knowledge, state clearly that it is not from the "
                   "dictionary. If suggestions exist, ask whether the user "
                   "meant one of them.",
    }


# ---------- tools ----------

@mcp.tool()
def define(word: str) -> dict:
    """Look up the meaning of a Gujarati word in the dictionary.

    Use this whenever the user asks what a Gujarati word means, its part of
    speech, or how it is used in a sentence. Pass the word in Gujarati script
    (e.g. 'પાણી'), not in romanized form. Inflected forms (e.g. 'આંખોમાં')
    are matched to their base word.
    """
    headword = _find(word)
    if headword is None:
        return _not_found(word)

    result: dict = {"found": True, "word": headword}
    if normalize(word) != headword:
        result["matched_from"] = word  # the input was an inflected form
        form_entry = WIKTIONARY.get(normalize(word))
        if form_entry and form_entry.get("form_note"):
            result["form_note"] = form_entry["form_note"]  # e.g. "plural of હું"

    curated = CURATED.get(headword)
    if curated:
        result["curated"] = {
            "pos": curated["pos"],
            "meaning_gu": curated["meaning_gu"],
            "meaning_en": curated["meaning_en"],
            "example": curated["example"],
        }

    wiki = WIKTIONARY.get(headword)
    if wiki:
        if wiki.get("transliteration"):
            result["transliteration"] = wiki["transliteration"]
        result["wiktionary_senses"] = wiki["senses"]
        result["wiktionary_attribution"] = WIKTIONARY_ATTRIBUTION

    return result


@mcp.tool()
def synonyms(word: str) -> dict:
    """Get synonyms (સમાનાર્થી શબ્દો) for a Gujarati word.

    Use this when the user asks for similar words, alternatives, or another
    way to say a Gujarati word. Pass the word in Gujarati script.
    """
    headword = _find(word)
    if headword is None:
        return _not_found(word)

    curated = CURATED.get(headword, {}).get("synonyms", [])
    wiki = WIKTIONARY.get(headword, {}).get("synonyms", [])
    merged = list(dict.fromkeys(curated + wiki))  # curated first, no duplicates

    if not merged:
        return {"found": True, "word": headword, "synonyms": [],
                "message": "No synonyms recorded for this word."}

    result = {"found": True, "word": headword, "synonyms": merged}
    if wiki:
        result["note"] = "Wiktionary synonyms may belong to different senses of the word."
        result["wiktionary_attribution"] = WIKTIONARY_ATTRIBUTION
    return result


@mcp.tool()
def idioms(word: str) -> dict:
    """Find Gujarati idioms (રૂઢિપ્રયોગ) that contain a given word.

    Use this when the user asks for idioms, phrases, or sayings involving a
    Gujarati word. Searches across the whole dictionary, so it also finds
    idioms listed under other words. Pass the word in Gujarati script.
    """
    query = _find(word) or normalize(word)
    matches = [
        {"phrase": idiom["phrase"], "meaning": idiom["meaning"]}
        for entry in CURATED.values()
        for idiom in entry.get("idioms", [])
        if query in normalize(idiom["phrase"])
    ]
    if not matches:
        return {"found": False, "word": word,
                "message": "No idioms found in the dictionary. Do not invent idioms."}
    return {"found": True, "word": word, "idioms": matches}


# ---------- resource ----------

@mcp.resource(
    "lexicon://word-of-the-day",
    name="word_of_the_day",
    description="Today's Gujarati word with meaning, example, synonyms and idioms.",
    mime_type="application/json",
)
def word_of_the_day() -> str:
    entries = list(CURATED.values())  # curated only: best quality
    entry = entries[date.today().toordinal() % len(entries)]
    return json.dumps(entry, ensure_ascii=False, indent=2)


# ---------- prompt ----------

@mcp.prompt()
def explain_passage(passage: str) -> str:
    """Explain a Gujarati passage word by word using the dictionary."""
    return (
        "Explain the following Gujarati passage for a learner.\n"
        "1. For each important word, call the `define` tool.\n"
        "2. If a phrase looks like an idiom, call the `idioms` tool.\n"
        "3. Give a simple English translation of the whole passage.\n"
        "4. Mark clearly which meanings came from the dictionary and "
        "which did not.\n\n"
        f"Passage:\n{passage}"
    )


def main() -> None:
    """Entry point for the `gujarati-lexicon-mcp` command."""
    mcp.run()


if __name__ == "__main__":
    main()