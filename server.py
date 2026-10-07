import json
import unicodedata
from pathlib import Path
import difflib

from mcp.server.mcpserver import MCPServer
from datetime import date

mcp = MCPServer("gujarati-lexicon", version="0.1.0", instructions=(
        "This server is a curated Gujarati dictionary. Always look Gujarati "
        "words up here before answering. If a word is not found, tell the "
        "user clearly; if you then answer from general knowledge, label it "
        "as not coming from the dictionary. Never invent idioms."
    ),)

# Load the dictionary once at startup.
# encoding="utf-8" is essential on Windows, or the Gujarati text breaks.
DATA_FILE = Path(__file__).parent / "words.json"

def normalize(text: str) -> str:
    # Gujarati can be typed in different Unicode forms; NFC makes them match.
    return unicodedata.normalize("NFC", text.strip())

# Common Gujarati endings, longest first so "માંથી" is tried before "થી".
SUFFIXES = ["માંથી", "માં", "થી", "નો", "ની", "નું", "ના", "ને", "એ", "ે", "ો"]


def _candidates(word: str) -> list[str]:
    """The word itself, then forms with up to two endings removed.

    Two levels handle stacked endings, e.g. આંખોમાં → આંખો → આંખ.
    """
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

WORDS = {
    normalize(entry["word"]): entry
    for entry in json.loads(DATA_FILE.read_text(encoding="utf-8"))
}

# ---------- helpers (shared by all tools) ----------

def _lookup(word: str) -> dict | None:
    for form in _candidates(normalize(word)):
        if form in WORDS:
            return WORDS[form]
    return None

def _not_found(word: str) -> dict:
    suggestions = difflib.get_close_matches(
        normalize(word), WORDS.keys(), n=3, cutoff=0.6
    )
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
    (e.g. 'પાણી'), not in romanized form.
    """
    entry = _lookup(word)
    if entry is None:
        return _not_found(word)
    return {
        "found": True,
        "word": entry["word"],
        "pos": entry["pos"],
        "meaning_gu": entry["meaning_gu"],
        "meaning_en": entry["meaning_en"],
        "example": entry["example"],
    }


@mcp.tool()
def synonyms(word: str) -> dict:
    """Get synonyms (સમાનાર્થી શબ્દો) for a Gujarati word.

    Use this when the user asks for similar words, alternatives, or another
    way to say a Gujarati word. Pass the word in Gujarati script.
    """
    entry = _lookup(word)
    if entry is None:
        return _not_found(word)
    return {"found": True, "word": entry["word"], "synonyms": entry["synonyms"]}


@mcp.tool()
def idioms(word: str) -> dict:
    """Find Gujarati idioms (રૂઢિપ્રયોગ) that contain a given word.

    Use this when the user asks for idioms, phrases, or sayings involving a
    Gujarati word. Searches across the whole dictionary, so it also finds
    idioms listed under other words. Pass the word in Gujarati script.
    """
    entry = _lookup(word)
    query = entry["word"] if entry else normalize(word)
    matches = [
        {"phrase": idiom["phrase"], "meaning": idiom["meaning"]}
        for entry in WORDS.values()
        for idiom in entry["idioms"]
        if query in normalize(idiom["phrase"])
    ]
    if not matches:
        return {
            "found": False,
            "word": word,
            "message": "No idioms found in the dictionary. Do not invent idioms.",
        }
    return {"found": True, "word": word, "idioms": matches}

# ---------- resource ----------

@mcp.resource(
    "lexicon://word-of-the-day",
    name="word_of_the_day",
    description="Today's Gujarati word with meaning, example, synonyms and idioms.",
    mime_type="application/json",
)
def word_of_the_day() -> str:
    entries = list(WORDS.values())
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

if __name__ == "__main__":
    mcp.run()  # stdio transport by default