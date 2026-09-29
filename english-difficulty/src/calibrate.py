"""Turn raw measurements into difficulty multipliers against a personal anchor.

The output is deliberately not a CEFR label. "RE4 is B2" tells a player who
already finished two open-world games in English nothing they can act on.
"RE4 asks 0.8x the vocabulary lookups that Ghost of Tsushima did" does.

Every multiplier here is a ratio of two ratio-scale quantities, so 1.8x means
1.8 times as much of the thing being measured. Nothing is a weighted sum of
z-scores, because the weights would be invented and the ratios would not
survive them.
"""
from __future__ import annotations

import math

# Coverage a reader needs for comfortable, uninterrupted comprehension. The
# 98% figure is the standard finding for reading without a dictionary; below
# ~95% comprehension degrades sharply.
COMFORT_COVERAGE = 98.0

BAND_KEYS = [("coverage_2k", 2000), ("coverage_3k", 3000),
             ("coverage_5k", 5000), ("coverage_10k", 10000),
             ("coverage_20k", 20000)]

# What each axis is built from. Every entry is ratio-scale with a true zero,
# so dividing two of them is meaningful.
READING_FACTORS = [
    ("sentence", "mean_length"),
    ("sentence", "subordinate_per_sentence"),
    ("sentence", "mean_dependency_distance"),
]
LISTENING_TEXT_FACTORS = [
    ("register", "contractions_per_1k"),
    ("register", "fragment_pct"),
    ("register", "interjections_per_1k"),
]
LOAD_TEXT_FACTORS = [
    ("proper_nouns", "distinct_per_1k"),
]


def coverage_at(metrics: dict, vocab_size: float) -> float:
    """Coverage at an arbitrary vocabulary size, interpolated between bands.

    Vocabulary growth is roughly linear in log(size), so the interpolation is
    done on the logarithm rather than on the raw band counts.
    """
    vocab = metrics["vocabulary"]
    points = [(size, vocab[key]) for key, size in BAND_KEYS if key in vocab]
    if not points:
        raise ValueError("no coverage bands in metrics")
    if vocab_size <= points[0][0]:
        return points[0][1]
    if vocab_size >= points[-1][0]:
        return points[-1][1]
    for (s0, c0), (s1, c1) in zip(points, points[1:]):
        if s0 <= vocab_size <= s1:
            span = math.log(s1) - math.log(s0)
            t = 0.0 if span == 0 else (math.log(vocab_size) - math.log(s0)) / span
            return c0 + t * (c1 - c0)
    return points[-1][1]


def infer_vocab_size(anchor: dict, comfort: float = COMFORT_COVERAGE) -> float:
    """Estimate the player's working vocabulary from a game they found easy.

    If a game felt comfortable, the player knew enough of its words to read it
    without stopping. The smallest vocabulary that reaches the comfort
    threshold on that game is the floor of what they have.
    """
    vocab = anchor["vocabulary"]
    points = [(size, vocab[key]) for key, size in BAND_KEYS if key in vocab]
    for (s0, c0), (s1, c1) in zip(points, points[1:]):
        if c0 < comfort <= c1:
            span = c1 - c0
            t = 0.0 if span == 0 else (comfort - c0) / span
            return math.exp(math.log(s0) + t * (math.log(s1) - math.log(s0)))
    if points[0][1] >= comfort:
        return float(points[0][0])
    return float(points[-1][0])


def unknown_per_1k(metrics: dict, vocab_size: float) -> float:
    """Words per 1000 the player is expected not to know."""
    return round(10.0 * (100.0 - coverage_at(metrics, vocab_size)), 2)


def _ratio(game: dict, anchor: dict, path: tuple[str, str]) -> float | None:
    section, key = path
    a = anchor.get(section, {}).get(key)
    g = game.get(section, {}).get(key)
    if a in (None, 0) or g is None:
        return None
    return g / a


def _geomean(values: list[float]) -> float | None:
    values = [v for v in values if v is not None and v > 0]
    if not values:
        return None
    return math.exp(sum(math.log(v) for v in values) / len(values))


def axis_multipliers(game: dict, anchor: dict, vocab_size: float) -> dict:
    anchor_unknown = unknown_per_1k(anchor, vocab_size)
    game_unknown = unknown_per_1k(game, vocab_size)
    vocabulary = (game_unknown / anchor_unknown) if anchor_unknown > 0 else None

    a_arch = anchor["vocabulary"]["archaic_per_1k"]
    g_arch = game["vocabulary"]["archaic_per_1k"]
    archaic_ratio = None if a_arch == 0 else g_arch / a_arch

    # Unknown words and archaic forms are the same unit — times per 1000 tokens
    # that a player is stopped — so they add rather than needing a weight
    # invented to trade them off. Measuring archaism and then leaving it out of
    # the composite scored Demon's Souls-shaped text, where archaic grammar is
    # the whole difficulty, as easy.
    anchor_decode = anchor_unknown + a_arch
    game_decode = game_unknown + g_arch
    decode = (game_decode / anchor_decode) if anchor_decode > 0 else None

    return {
        "vocabulary": round(vocabulary, 2) if vocabulary else None,
        "unknown_per_1k": game_unknown,
        "decode": round(decode, 2) if decode else None,
        "decode_per_1k": round(game_decode, 2),
        "reading": round(_geomean([_ratio(game, anchor, p) for p in READING_FACTORS]) or 0, 2) or None,
        "listening_text_proxy": round(
            _geomean([_ratio(game, anchor, p) for p in LISTENING_TEXT_FACTORS]) or 0, 2) or None,
        "name_load": round(
            _geomean([_ratio(game, anchor, p) for p in LOAD_TEXT_FACTORS]) or 0, 2) or None,
        "archaic_vs_anchor": round(archaic_ratio, 2) if archaic_ratio is not None else None,
    }


def overall(axes: dict) -> float | None:
    """One number, dominated by decoding because comprehension is.

    Decoding load counts double against sentence complexity: a sentence whose
    words you know parses itself eventually, a sentence whose words you do not
    know does not.
    """
    parts = []
    if axes.get("decode"):
        parts += [axes["decode"]] * 2
    if axes.get("reading"):
        parts.append(axes["reading"])
    value = _geomean(parts)
    return round(value, 2) if value else None


def calibrate(measurements: dict, anchor_slug: str, comfort: float = COMFORT_COVERAGE) -> dict:
    if anchor_slug not in measurements:
        raise KeyError(f"anchor {anchor_slug!r} has no measurements")
    anchor = measurements[anchor_slug]
    vocab_size = infer_vocab_size(anchor, comfort)

    rows = {}
    for slug, metrics in measurements.items():
        axes = axis_multipliers(metrics, anchor, vocab_size)
        rows[slug] = {**axes, "overall": overall(axes)}

    return {
        "anchor": anchor_slug,
        "comfort_coverage": comfort,
        "inferred_vocabulary_size": int(round(vocab_size)),
        "games": rows,
    }
