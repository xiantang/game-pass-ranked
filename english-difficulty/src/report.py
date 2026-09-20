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


def _row(label: str, m: dict) -> str:
    v, s = m["vocabulary"], m["sentence"]
    return (f"| {label} | {v['coverage_2k']} | {v['coverage_5k']} | {v['cefr_c_plus_pct']} | "
            f"{v['cefr_unlisted_pct']} | {v['archaic_per_1k']} | {s['mean_length']} | "
            f"{s['subordinate_per_sentence']} |")


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
        lines += ["## Games", "", HEADER]
        for slug, m in sorted(games.items()):
            lines.append(_row(f"**{slug}**", m))
        lines.append("")

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
