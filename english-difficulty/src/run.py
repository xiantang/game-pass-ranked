"""Command line entry point for the game English corpus.

    python src/run.py reference   # build the wordlists and reference registers
    python src/run.py clean       # corpus/raw/<slug>/ -> corpus/clean/<slug>.txt
    python src/run.py ladder      # measure the reference registers
    python src/run.py measure     # measure every cleaned game corpus
    python src/run.py report      # write out/report.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import calibrate  # noqa: E402
import clean as cleaner  # noqa: E402
import metrics as M  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
REF = ROOT / "reference"


def _load_games_config() -> dict:
    path = ROOT / "corpus" / "games.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def cmd_reference(_args) -> None:
    import fetch_reference

    fetch_reference.main()


def cmd_clean(_args) -> None:
    config = _load_games_config()
    slugs = sorted(config.get("games", {}))
    if not slugs:
        slugs = sorted({p.stem if p.is_file() else p.name
                        for p in (ROOT / "corpus" / "raw").glob("*")})
    if not slugs:
        print("no raw corpora in corpus/raw/ — see README.md", file=sys.stderr)
        return
    for slug in slugs:
        lines = cleaner.clean_game(slug)
        if not lines:
            print(f"  {slug}: no raw text found, skipped", file=sys.stderr)
            continue
        path = cleaner.write_clean(slug, lines)
        words = sum(len(x.split()) for x in lines)
        print(f"  {slug}: {len(lines)} lines, ~{words} words -> {path.name}", file=sys.stderr)


def _measure_many(named: dict[str, list[str]], sample: bool) -> dict:
    ref = M.Reference.load()
    nlp = M.load_nlp()
    out = {}
    for name, lines in sorted(named.items()):
        try:
            out[name] = M.analyse(lines, nlp, ref, sample=sample)
            v = out[name]["vocabulary"]
            print(f"  {name}: cov5k={v['coverage_5k']}% B2+={v['cefr_b2_plus_pct']}% "
                  f"archaic/1k={v['archaic_per_1k']}", file=sys.stderr)
        except ValueError as exc:
            print(f"  {name}: skipped ({exc})", file=sys.stderr)
    return out


def cmd_ladder(_args) -> None:
    ladder_dir = REF / "ladder"
    if not ladder_dir.exists():
        print("run `reference` first", file=sys.stderr)
        return
    named = {}
    for path in sorted(ladder_dir.glob("*.txt")):
        key = path.stem.replace("__", "/")
        named[key] = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    print(f"measuring {len(named)} reference registers", file=sys.stderr)
    result = _measure_many(named, sample=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ladder.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"wrote {OUT / 'ladder.json'}", file=sys.stderr)


def cmd_measure(args) -> None:
    clean_dir = ROOT / "corpus" / "clean"
    named = {}
    for path in sorted(clean_dir.glob("*.txt")):
        named[path.stem] = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    if not named:
        print("no cleaned corpora — run `clean` first (and see README.md on "
              "how to obtain the raw transcripts)", file=sys.stderr)
        return
    print(f"measuring {len(named)} game corpora", file=sys.stderr)
    result = _measure_many(named, sample=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "measurements.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    config = _load_games_config()
    anchor = args.anchor or config.get("anchor")
    if anchor and anchor in result:
        table = calibrate.calibrate(result, anchor)
        (OUT / "difficulty.json").write_text(json.dumps(table, indent=2), encoding="utf-8")
        print(f"anchored on {anchor}; vocabulary estimate "
              f"{table['inferred_vocabulary_size']} words", file=sys.stderr)
    elif anchor:
        print(f"anchor {anchor!r} has no corpus yet — measurements written, "
              f"difficulty table not", file=sys.stderr)


# Registers standing in for games, so the whole chain can be verified without
# any game corpus present. Ordered from easiest to hardest by construction.
SELFTEST_CASES = [
    ("chat/nps", "instant messaging"),
    ("gutenberg/carroll-alice", "children's classic"),
    ("brown/fiction", "general fiction"),
    ("brown/learned", "academic prose"),
    ("gutenberg/melville-moby_dick", "Moby-Dick"),
    ("gutenberg/shakespeare-hamlet", "Shakespeare"),
]
SELFTEST_ANCHOR = "gutenberg/carroll-alice"


def cmd_selftest(_args) -> None:
    """Run the full measure-and-calibrate path over known-ordered text.

    If the engine is sound, difficulty must rise from children's fiction to
    Shakespeare. This is the only end-to-end check that needs no game corpus.
    """
    ladder_dir = REF / "ladder"
    if not ladder_dir.exists():
        print("run `reference` first", file=sys.stderr)
        raise SystemExit(1)

    named = {}
    for key, _label in SELFTEST_CASES:
        path = ladder_dir / (key.replace("/", "__") + ".txt")
        if path.exists():
            named[key] = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    measured = _measure_many(named, sample=True)
    table = calibrate.calibrate(measured, SELFTEST_ANCHOR)

    print(f"\nanchor {SELFTEST_ANCHOR}, "
          f"inferred vocabulary {table['inferred_vocabulary_size']:,}\n", file=sys.stderr)
    print(f"{'register':<34}{'vocab':>8}{'unk/1k':>9}{'read':>8}{'archaic':>9}{'overall':>9}",
          file=sys.stderr)
    order = []
    for key, label in SELFTEST_CASES:
        row = table["games"].get(key)
        if not row:
            continue
        order.append((label, row["overall"]))
        fmt = lambda x: "—" if x is None else f"{x:.2f}"
        print(f"{label:<34}{fmt(row['vocabulary']):>8}{row['unknown_per_1k']:>9}"
              f"{fmt(row['reading']):>8}{fmt(row['archaic_vs_anchor']):>9}"
              f"{fmt(row['overall']):>9}", file=sys.stderr)

    failures = []
    got = {label: score for label, score in order}
    if got.get("Shakespeare", 0) <= got.get("children's classic", 0):
        failures.append("Shakespeare must outscore the children's classic")
    # Deliberately strict. "Harder than Alice" was true even when a filter
    # bug had stripped Early Modern verb forms out of Shakespeare's
    # vocabulary and scored him below newspaper prose.
    vocab = {label: table["games"][key]["vocabulary"]
             for key, label in SELFTEST_CASES if key in table["games"]}
    if (vocab.get("Shakespeare") or 0) <= (vocab.get("general fiction") or 0):
        failures.append("Shakespeare's vocabulary must outscore general fiction's")
    if (vocab.get("instant messaging") or 0) >= (vocab.get("academic prose") or 0):
        failures.append("instant messaging must not outscore academic prose")
    if got.get("academic prose", 0) <= got.get("general fiction", 0):
        failures.append("academic prose must outscore general fiction")
    arch = {label: table["games"][key]["archaic_vs_anchor"]
            for key, label in SELFTEST_CASES if key in table["games"]}
    if (arch.get("Shakespeare") or 0) <= (arch.get("instant messaging") or 0):
        failures.append("Shakespeare must be more archaic than instant messaging")

    print("", file=sys.stderr)
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        raise SystemExit(1)
    print("selftest passed", file=sys.stderr)


def cmd_report(_args) -> None:
    import report

    report.main()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("reference").set_defaults(fn=cmd_reference)
    sub.add_parser("clean").set_defaults(fn=cmd_clean)
    sub.add_parser("ladder").set_defaults(fn=cmd_ladder)
    measure = sub.add_parser("measure")
    measure.add_argument("--anchor", help="slug of the game to calibrate against")
    measure.set_defaults(fn=cmd_measure)
    sub.add_parser("selftest").set_defaults(fn=cmd_selftest)
    sub.add_parser("report").set_defaults(fn=cmd_report)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
