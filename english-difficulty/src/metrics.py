"""Measure one body of English text on the axes that make a game hard to play.

Nothing here knows about games specifically: it takes cleaned text and returns
numbers. `calibrate.py` turns those numbers into difficulty multipliers.
"""
from __future__ import annotations

import json
import random
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "reference"

# Comparing corpora of different sizes is the easiest way to get a wrong answer:
# vocabulary coverage and type-token ratio both drift with length, so a game with
# a 200k-word script would look "harder" than one with 20k purely on size. Every
# corpus is cut to the same token budget before measurement.
SAMPLE_TOKENS = 20_000
MATTR_WINDOW = 500

SUBORDINATE_DEPS = {"advcl", "ccomp", "xcomp", "relcl", "acl", "csubj", "csubjpass", "pcomp"}
CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}
CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2", "unlisted"]

# Only ever tested against tokens already missing from both the frequency list
# and the dictionary, where an -eth or -st ending is an archaic verb rather
# than `most` or `first`.
ARCHAIC_MORPHOLOGY = re.compile(r"^[a-z']+(?:eth|'?st)$")


@dataclass
class Reference:
    ranks: dict[str, int]
    bands: list[int]
    cefr: dict[str, str]
    archaic: dict[str, float]
    dictionary: set[str]

    @classmethod
    def load(cls) -> "Reference":
        freq = json.loads((REF / "frequency.json").read_text())
        return cls(
            ranks=freq["ranks"],
            bands=freq["bands"],
            cefr=json.loads((REF / "cefr.json").read_text()),
            archaic=json.loads((REF / "archaic.json").read_text()),
            dictionary=set(json.loads((REF / "dictionary.json").read_text())),
        )

    def rank(self, lemma: str, surface: str) -> int | None:
        return self.ranks.get(lemma) or self.ranks.get(surface)

    def level(self, lemma: str, surface: str) -> str:
        return self.cefr.get(lemma) or self.cefr.get(surface) or "unlisted"

    def is_english(self, lemma: str, surface: str) -> bool:
        """Whether a token is a word at all, as opposed to noise.

        Coverage counts what a player has to *learn*. A transcript's typos, a
        chat log's `brb`, and a setting's invented names are not vocabulary,
        and counting them as unknown words makes a messy dump score as harder
        English. A genuinely rare word (`relinquish`) is in the dictionary and
        still counts; a colloquial one (`gonna`) is in the frequency list.
        """
        if (lemma in self.ranks or surface in self.ranks
                or lemma in self.dictionary or surface in self.dictionary):
            return True
        # Archaic forms are vocabulary the player still has to decode, but
        # `hath`, `doth` and `mayest` are in neither a modern frequency list
        # nor a modern dictionary. Without this, filtering noise also filtered
        # out most of what makes Early Modern English hard, and Shakespeare
        # measured as easier than newspaper prose.
        if lemma in self.archaic or surface in self.archaic:
            return True
        return bool(ARCHAIC_MORPHOLOGY.match(surface))


def load_nlp():
    import spacy

    nlp = spacy.load("en_core_web_sm", exclude=["ner"])
    nlp.max_length = 4_000_000
    return nlp


def take_sample(lines: list[str], budget: int = SAMPLE_TOKENS, seed: int = 20260920) -> list[str]:
    """Cut a corpus down to a fixed token budget.

    Sampling whole lines at random rather than truncating keeps the sample
    spread across the whole script instead of over-weighting its opening hours,
    which in most games are written to be the easiest part.
    """
    if not lines:
        return []
    rough = sum(len(line.split()) for line in lines)
    if rough <= budget:
        return list(lines)
    order = list(range(len(lines)))
    random.Random(seed).shuffle(order)
    picked, total = [], 0
    for idx in order:
        picked.append(idx)
        total += len(lines[idx].split())
        if total >= budget:
            break
    return [lines[i] for i in sorted(picked)]


def _tree_depth(token, cache: dict) -> int:
    """How far a token sits below its sentence root.

    Walks up iteratively. Recursion overflows Python's stack on a long
    sentence, and a statistical parse occasionally emits a head cycle, which
    a naive recursive walk never returns from.
    """
    chain, seen = [], set()
    cur = token
    while cur.head is not cur and cur.i not in cache and cur.i not in seen:
        seen.add(cur.i)
        chain.append(cur)
        cur = cur.head
    depth = cache.get(cur.i, 0)
    for tok in reversed(chain):
        depth += 1
        cache[tok.i] = depth
    return cache.get(token.i, depth)


def analyse(lines: list[str], nlp, ref: Reference, sample: bool = True) -> dict:
    """Return every raw measurement for one corpus."""
    used = take_sample(lines) if sample else list(lines)
    text = "\n".join(used)
    if not text.strip():
        raise ValueError("empty corpus")

    doc = nlp(text)

    words = [t for t in doc if t.is_alpha]
    if not words:
        raise ValueError("no alphabetic tokens")

    # Proper nouns are a load on memory, not on vocabulary: a player does not
    # need to "know" Sucker Punch's place names, only to keep them straight.
    # They are counted separately and excluded from every vocabulary measure.
    candidates = [t for t in words if t.pos_ != "PROPN"]
    propn = [t for t in words if t.pos_ == "PROPN"]
    vocab = [t for t in candidates
             if ref.is_english(t.lemma_.lower(), t.text.lower())]
    kept = {t.i for t in vocab}
    noise = [t for t in candidates if t.i not in kept]
    if not vocab:
        raise ValueError("no recognisable English vocabulary")

    banded = {b: 0 for b in ref.bands}
    beyond = 0
    for t in vocab:
        r = ref.rank(t.lemma_.lower(), t.text.lower())
        if r is None:
            beyond += 1
            continue
        for b in ref.bands:
            if r <= b:
                banded[b] += 1
    n_vocab = len(vocab)
    cumulative = {}
    running = 0
    for b in ref.bands:
        running = banded[b]
        cumulative[f"coverage_{b // 1000}k"] = round(100 * running / n_vocab, 2)

    content = [t for t in vocab if t.pos_ in CONTENT_POS]
    levels = {k: 0 for k in CEFR_ORDER}
    for t in content:
        levels[ref.level(t.lemma_.lower(), t.text.lower())] += 1
    n_content = max(len(content), 1)
    cefr_pct = {k: round(100 * v / n_content, 2) for k, v in levels.items()}

    archaic_hits = [
        ref.archaic[t.lemma_.lower()]
        for t in vocab
        if t.lemma_.lower() in ref.archaic
    ]

    sents = [s for s in doc.sents if any(t.is_alpha for t in s)]
    lengths = [len([t for t in s if t.is_alpha]) for s in sents]
    n_sents = max(len(sents), 1)

    subordinate = sum(1 for t in doc if t.dep_ in SUBORDINATE_DEPS)
    depths, distances = [], []
    for s in sents:
        cache: dict = {}
        depths.append(max((_tree_depth(t, cache) for t in s), default=0))
        distances += [abs(t.i - t.head.i) for t in s if t.head is not t]

    finite = {"VBD", "VBP", "VBZ", "MD"}
    fragments = sum(
        1 for s in sents
        if not any(t.tag_ in finite for t in s) and len([t for t in s if t.is_alpha]) > 1
    )

    lowered = text.lower()
    contractions = len(re.findall(r"\b\w+'(?:s|t|re|ve|ll|d|m)\b", lowered))
    pronouns = sum(1 for t in words if t.lemma_.lower() in {"i", "you", "we"})
    interjections = sum(1 for t in doc if t.pos_ == "INTJ")
    questions = sum(1 for s in sents if s.text.strip().endswith("?"))

    forms = [t.text.lower() for t in words]
    mattr = None
    if len(forms) >= MATTR_WINDOW:
        ratios = [
            len(set(forms[i:i + MATTR_WINDOW])) / MATTR_WINDOW
            for i in range(0, len(forms) - MATTR_WINDOW, 50)
        ]
        mattr = round(statistics.fmean(ratios), 4)

    per_1k = lambda n: round(1000 * n / len(words), 2)

    return {
        "volume": {
            "lines_total": len(lines),
            "lines_sampled": len(used),
            "tokens": len(words),
            "types": len(set(forms)),
            "sentences": len(sents),
        },
        "vocabulary": {
            **cumulative,
            "beyond_top_band_pct": round(100 * beyond / n_vocab, 2),
            "cefr_pct": cefr_pct,
            # Two different things, kept apart on purpose. `unlisted` is not
            # advanced vocabulary: it is everything the wordlist has never
            # seen, which in a game means invented common nouns (an estus, a
            # tarnished) and in chat means typos. Folding it into C-level
            # would score a fantasy game as harder than Shakespeare on
            # coinages alone.
            "cefr_b2_plus_pct": round(
                sum(cefr_pct[k] for k in ("B2", "C1", "C2", "unlisted")), 2),
            "cefr_c_plus_pct": round(sum(cefr_pct[k] for k in ("C1", "C2")), 2),
            "cefr_unlisted_pct": cefr_pct["unlisted"],
            "archaic_per_1k": per_1k(len(archaic_hits)),
            # Tokens that are not English words: coinages, typos, chat
            # shorthand. Excluded from coverage above, reported here because a
            # setting with heavy invented terminology is still a real load.
            "coinage_per_1k": per_1k(len(noise)),
            "archaic_mean_score": round(statistics.fmean(archaic_hits), 2) if archaic_hits else 0.0,
            "mattr": mattr,
        },
        "proper_nouns": {
            "pct_of_tokens": round(100 * len(propn) / len(words), 2),
            "distinct_per_1k": per_1k(len({t.text.lower() for t in propn})),
        },
        "sentence": {
            "mean_length": round(statistics.fmean(lengths), 2) if lengths else 0,
            "median_length": statistics.median(lengths) if lengths else 0,
            "over_20_pct": round(100 * sum(1 for x in lengths if x > 20) / n_sents, 2),
            "over_30_pct": round(100 * sum(1 for x in lengths if x > 30) / n_sents, 2),
            "subordinate_per_sentence": round(subordinate / n_sents, 3),
            "mean_tree_depth": round(statistics.fmean(depths), 2) if depths else 0,
            "mean_dependency_distance": round(statistics.fmean(distances), 2) if distances else 0,
        },
        "register": {
            "contractions_per_1k": per_1k(contractions),
            "first_second_person_per_1k": per_1k(pronouns),
            "interjections_per_1k": per_1k(interjections),
            "question_pct": round(100 * questions / n_sents, 2),
            "fragment_pct": round(100 * fragments / n_sents, 2),
        },
    }
