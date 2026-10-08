"""Convert the kaikki.org Gujarati dump into data/wiktionary.json.

Source: Wiktionary via kaikki.org, licensed CC BY-SA.
Run from the project root:
    uv run python scripts/build_wiktionary.py
"""
import json
import unicodedata
from collections import defaultdict
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "kaikki-gujarati.jsonl"
OUT = ROOT / "src" / "gujarati_lexicon_mcp" / "data" / "wiktionary.json"

SKIP_POS = {"character", "punct", "symbol", "prefix", "suffix"}
MAX_SENSES = 5  # keep tool responses short for the LLM


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text.strip())


def romanization(item: dict) -> str | None:
    for form in item.get("forms", []):
        if "romanization" in form.get("tags", []):
            return form["form"]
    return None


def collect_synonyms(source: dict, into: set) -> None:
    for syn in source.get("synonyms", []):
        if syn.get("word"):
            into.add(nfc(syn["word"]))


def new_entry() -> dict:
    return {"transliteration": None, "senses": [], "synonyms": set(), "lemmas": set(), "form_notes": []}

GLOSS_FORM_OF = re.compile(r"^[^()]* of ([\u0A80-\u0AFF]+)(?: \([^)]*\))?$")

# Headwords must be in Gujarati script (ZWNJ/ZWJ, spaces, hyphens allowed).
GUJARATI_ONLY = re.compile(r"[\u0A80-\u0AFF\u200c\u200d \-]+")


def base_word(sense: dict) -> str | None:
    """Return the base word if this sense only says 'X form of <word>'."""
    ref = sense.get("form_of") or sense.get("alt_of")
    if ref and ref[0].get("word"):
        return nfc(ref[0]["word"])               # structured link (preferred)
    glosses = sense.get("glosses") or []
    if glosses:
        match = GLOSS_FORM_OF.match(glosses[-1])
        if match:
            return nfc(match.group(1))           # fallback: read the text
    return None

def main() -> None:
    words = defaultdict(new_entry)
    skipped = 0

    with RAW.open(encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            if item.get("lang_code") != "gu" or item.get("pos") in SKIP_POS:
                skipped += 1
                continue

            word = nfc(item["word"])
            if not GUJARATI_ONLY.fullmatch(word):   # skip Perso-Arabic script etc.
                skipped += 1
                continue
            entry = words[word]                      # group all lines by word          # group all lines by word
            entry["transliteration"] = entry["transliteration"] or romanization(item)
            collect_synonyms(item, entry["synonyms"])

            for sense in item.get("senses", []):
                # Inflected forms and alternative spellings point to a base word,
                # e.g. ઘરે is "locative singular of ઘર". Record the link instead
                # of storing "...of ઘર" as if it were a meaning.
                lemma = base_word(sense)
                if lemma:
                    entry["lemmas"].add(lemma)
                    if sense.get("glosses"):
                        entry["form_notes"].append(sense["glosses"][-1])
                    continue

                glosses = sense.get("glosses")
                if not glosses:
                    continue
                collect_synonyms(sense, entry["synonyms"])
                example = (sense.get("examples") or [{}])[0]
                clean = {
                    "pos": item["pos"],
                    "meaning_en": "; ".join(glosses),
                    "example": example.get("text"),
                    "example_en": example.get("english") or example.get("translation"),
                }
                entry["senses"].append({k: v for k, v in clean.items() if v})

    output = []
    for word, e in sorted(words.items()):
        if not e["senses"] and not e["lemmas"]:
            continue

        record = {
            "word": word,
            "transliteration": e["transliteration"],
            "senses": e["senses"][:MAX_SENSES],
            "synonyms": sorted(e["synonyms"]),
        }
        if not e["senses"]:                      # a pure inflected form
            record["lemma"] = sorted(e["lemmas"])[0]
            if e["form_notes"]:
                record["form_note"] = e["form_notes"][0]
        output.append(record)

    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=1), encoding="utf-8")
    redirects = sum("lemma" in r for r in output)
    print(f"{len(output)} words ({redirects} inflected forms) -> "
          f"{OUT.relative_to(ROOT)} ({skipped} lines skipped)")


if __name__ == "__main__":
    main()