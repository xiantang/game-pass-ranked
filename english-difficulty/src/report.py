"""Render the measurements as out/report.md."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"

# Registers worth naming in the summary table: they bracket the range a game
# can plausibly fall in, from instant-messaging English to Jacobean verse.
LANDMARKS = [
    ("chat/nps", "instant messaging"),
    ("brown/mystery", "genre fiction"),
    ("brown/fiction", "general fiction"),
    ("brown/news", "newspaper journalism"),
    ("gutenberg/carroll-alice", "children's classic"),
    ("gutenberg/austen-persuasion", "Austen"),
    ("brown/learned", "academic prose"),
    ("gutenberg/melville-moby_dick", "Moby-Dick"),
    ("gutenberg/milton-paradise", "Paradise Lost"),
    ("gutenberg/shakespeare-hamlet", "Shakespeare"),
    ("gutenberg/bible-kjv", "King James Bible"),
]


def _load(name: str) -> dict:
    path = OUT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _row(label: str, m: dict, blank_unreliable: bool = False) -> str:
    v, s = m["vocabulary"], m["sentence"]
    if blank_unreliable:
        # Everything this source was measured to get wrong. Blank, not zero:
        # a column that reads 45% low is worse than a column that is absent.
        return (f"| {label} | {v['coverage_2k']} | {v['coverage_5k']} | — | — | — | — | — |")
    return (f"| {label} | {v['coverage_2k']} | {v['coverage_5k']} | {v['cefr_c_plus_pct']} | "
            f"{v['cefr_unlisted_pct']} | {v['archaic_per_1k']} | {s['mean_length']} | "
            f"{s['subordinate_per_sentence']} |")


LOAD_HEADER = ("| game | words/hour | words/min spoken | corpus words | hours | "
               "ASR noise % |\n|---|---|---|---|---|---|")


def _load_row(slug: str, m: dict) -> str:
    """The listening-side load, which the caption timings do carry."""
    p = m.get("provenance", {})
    fmt = lambda k: p.get(k) if p.get(k) is not None else "—"
    return (f"| {slug} | {fmt('words_per_hour')} | {fmt('words_per_minute')} | "
            f"{fmt('words')} | {fmt('duration_hours')} | {fmt('asr_marker_pct')} |")


HEADER = ("| corpus | cov@2k % | cov@5k % | C1+C2 % | unlisted % | archaic/1k | "
          "sent. len | subord./sent |\n|---|---|---|---|---|---|---|---|")


def main() -> None:
    ladder = _load("ladder.json")
    games = _load("measurements.json")
    difficulty = _load("difficulty.json")

    lines = ["# Game English difficulty — measured report", ""]

    if not games:
        lines += [
            "> **No game corpus measured yet.** The reference scale below is built and",
            "> validated; drop transcripts into `corpus/raw/<slug>/` and re-run to fill in",
            "> the games. See `README.md` for what each game needs.",
            "",
        ]

    if ladder:
        lines += [
            "## The scale",
            "",
            "Reference registers, measured by the same pipeline on the same 20,000-token",
            "budget. A game's numbers mean something only against these.",
            "",
            HEADER,
        ]
        for key, label in LANDMARKS:
            if key in ladder:
                lines.append(_row(f"{label} (`{key}`)", ladder[key]))
        lines.append("")

    if games:
        lines += [
            "## Games", "",
            "Collected from automatic captions of no-commentary playthroughs. The",
            "blanked columns are the ones that source cannot carry: measured against a",
            "wiki corpus of the same game, sentence length came out 26% low and archaism",
            "45% low, because the automatic track has no punctuation for the parser to",
            "split on and speech recognition hears an archaic word as its modern",
            "neighbour. Coverage survives (+0.5%) and is what these rows are for.",
            "",
            HEADER,
        ]
        for slug, m in sorted(games.items()):
            blanked = "youtube-captions" in str(m.get("provenance", {}).get("source", ""))
            lines.append(_row(f"**{slug}**", m, blank_unreliable=blanked))
        lines.append("")
        if any("youtube-captions" in str(m.get("provenance", {}).get("source", ""))
               for m in games.values()):
            lines += [
                "### Load", "",
                "How fast the English arrives, which is a different question from how",
                "hard it is. Words per hour counts the whole playthrough, silence",
                "included; words per minute is measured over the gaps between captions,",
                "so it is the rate while someone is actually speaking.",
                "",
                LOAD_HEADER,
            ]
            for slug, m in sorted(games.items()):
                lines.append(_load_row(slug, m))
            lines.append("")

    if games and any(m.get("provenance", {}).get("words_per_hour") for m in games.values()):
        import calibrate

        lines += [
            "## Lookups per hour", "",
            "How often an unknown word stops you, per hour of play. It is the only",
            "composite here, and it needs no invented weight: unknown words per 1000",
            "tokens times thousands of words per hour multiply to a rate, with the",
            "units cancelling. Pick the column matching your own vocabulary.",
            "",
            "It carries vocabulary and volume only. Syntax and archaism are not in it,",
            "because the caption source cannot measure them — so a period-register game",
            "is understated here, not overstated.",
            "",
            "| game | unknown/1k @5k | words/hour | @3k | @5k | @8k |",
            "|---|---|---|---|---|---|",
        ]
        rows = []
        for slug, m in games.items():
            wph = m.get("provenance", {}).get("words_per_hour")
            if not wph:
                continue
            rates = [calibrate.unknown_per_1k(m, v) * wph / 1000
                     for v in (3000, 5000, 8000)]
            rows.append((slug, calibrate.unknown_per_1k(m, 5000), wph, rates))
        for slug, unk, wph, rates in sorted(rows, key=lambda r: r[3][1]):
            thin = " *" if (games[slug].get("provenance", {}).get("words") or 0) < 20000 else ""
            lines.append(f"| {slug}{thin} | {unk} | {wph} | {rates[0]:.0f} | "
                         f"**{rates[1]:.0f}** | {rates[2]:.0f} |")
        lines += [
            "",
            "`*` under 20,000 words of corpus, so that row is measured on a smaller",
            "sample than the budget the rest are cut to.",
            "",
        ]

    if difficulty:
        anchor = difficulty["anchor"]
        lines += [
            "## Difficulty, calibrated to you",
            "",
            f"Anchored on `{anchor}`, which you reported as comfortable. From its",
            f"coverage curve your working vocabulary is at least "
            f"**~{difficulty['inferred_vocabulary_size']:,} words** — the smallest",
            f"vocabulary that reads {difficulty['comfort_coverage']}% of it without stopping.",
            "",
            "`vocabulary` is the ratio of words per 1000 you are expected not to know.",
            "2.0x means twice as many lookups per hour, not 'twice as hard'.",
            "",
            "| game | vocabulary | unknown/1k | archaic | decode | reading | overall |",
            "|---|---|---|---|---|---|---|",
        ]
        fmt = lambda x: "—" if x is None else f"{x}x"
        for slug, row in sorted(difficulty["games"].items(),
                                key=lambda kv: kv[1].get("overall") or 0):
            mark = " *(anchor)*" if slug == anchor else ""
            lines.append(
                f"| {slug}{mark} | {fmt(row['vocabulary'])} | {row['unknown_per_1k']} | "
                f"{fmt(row['archaic_vs_anchor'])} | {fmt(row['decode'])} | "
                f"{fmt(row['reading'])} | **{fmt(row['overall'])}** |")
        lines += [
            "",
            "Listening is not in this table. Accent, speech rate and how much dialogue",
            "is voiced at all are not recoverable from a transcript; fill the `load`",
            "fields in `corpus/games.json` to score it.",
            "",
        ]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT / 'report.md'}")


if __name__ == "__main__":
    main()
