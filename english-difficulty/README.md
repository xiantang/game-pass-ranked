# Game English Corpus

Measures how hard a game's English actually is, and expresses the answer as a
multiple of a game you have already played comfortably — not as a CEFR label.

`RE4 is B2` is useless to someone who has finished two open-world games in
English. `RE4 asks 0.8x the vocabulary lookups that Ghost of Tsushima did` is
something you can act on.

## Status

Twelve games are measured, from the automatic captions of no-commentary
playthroughs. Fandom was tried first and could not supply this list: six of
the eight wikis it was pointed at have no dialogue category at all, and the
two that do gave 50k words for one game and 1.3k for another.

What the caption source costs was measured rather than assumed, by collecting
`rdr2` both ways and comparing:

| axis | vs. the wiki corpus | verdict |
| --- | --- | --- |
| coverage @2k / @5k / @10k | +0.9% / +0.5% / +0.4% | usable |
| proper nouns | +5.1% | usable for real-world names only |
| CEFR B2+ | -16.4% | biased low |
| archaic per 1k | -45.0% | unusable |
| mean sentence length | -25.9% | unusable |
| subordination | -33.4% | unusable |

Coverage survives because it counts a distribution and a few misheard words do
not move it. Syntax does not, because the automatic track has no punctuation
and the parser has nothing to split sentences on — the text is not simpler,
it is unpunctuated. Archaism halves because recognition hears an archaic word
as its modern neighbour, which is worst for exactly the games whose difficulty
is archaic. The report prints nothing in those columns.

The proper-noun result does not generalise. Red Dead's names are ordinary
English ones; in Baldur's Gate 3 the recogniser drops invented names entirely
(Shadowheart, Astarion and Lae'zel appear zero times in 44k words), which
moves coverage in a direction this pipeline cannot determine. Fantasy rows
carry that caveat.

**Not collected:** Bloodborne, Demon's Souls and Tears of the Kingdom. No
candidate video was both no-commentary and carried an English automatic
track; availability runs at roughly one video in five, and these three drew
none across 30+ candidates each.

## One source, one population

Every corpus comes from **Fandom, through the MediaWiki API, through one
parser**. This is the constraint the whole comparison rests on.

Assembling each game from whatever transcript happened to exist would measure
the transcript, not the game. A main-story fan transcript and a complete
extracted dialogue archive are different populations: the second contains
every optional branch and companion line, so it scores as harder English for
reasons that have nothing to do with its English. Transcriber conventions
differ too — whether stage directions, item text or ambient chatter were
written down at all.

**The population is `all-dialogue`:** main story, side content, companion and
ambient lines. Not item descriptions or documents — that is `all-text`, and
mixing the two is exactly the error this is built to prevent. The three
populations are defined in `fetch_corpus.py` as patterns over category names,
so the口径 is enforced in code rather than left to whoever collected the text.
`measure` reads each corpus's provenance and **refuses to build one table**
out of corpora collected under different populations.

### Shared wikis

Five of the eight games sit on a wiki that covers a whole series —
`reddead` carries both Redemption games, `residentevil` the entire series,
`godofwar` the Greek-era games, `zelda` every Zelda, `kingdomcomedeliverance`
both. Selecting on population alone collects the wrong game's dialogue
alongside the right one, and nothing downstream can detect it afterwards.

Those entries are marked `shared_wiki` and are **refused until a filter is
set.** Run `discover` first: it reports what the wiki actually calls its
categories, so the filter is written against reality rather than guessed.

There are two filters, because wikis file things two ways. `game_filter`
selects category names, which is enough where the categories name the game
(`Resident Evil 4 remake cutscenes`). `page_filter` selects pages by their own
categories — and, for an `X/dialogues` subpage, by its parent page's, since the
subpage itself carries nothing but `Dialogues`. That is the only thing that
separates games filed in one flat category, which is how the Red Dead wiki
holds both Redemption games.

### Getting corpora

```bash
python src/run.py discover           # what each wiki offers; no download
# set game_filter in corpus/games.json for the shared wikis
python src/run.py fetch              # -> corpus/raw/<slug>/corpus.txt + provenance.json
```

`corpus/raw/` and `corpus/clean/` are **git-ignored and must stay that way.**
Game scripts are copyrighted, and Fandom text is CC BY-SA. This project
commits only derived statistics — counts, ratios, coverage percentages —
which is what makes it publishable at all. Never commit the text itself.

## Running

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

python src/run.py reference   # build wordlists + reference registers (~1 min)
python src/run.py selftest    # prove the engine orders known text correctly
python src/test_wikitext.py   # prove the wiki parser extracts dialogue

python src/run.py discover    # what each wiki offers; no download
python src/run.py fetch       # one source, one parser, provenance recorded
python src/run.py clean       # corpus/raw/ -> corpus/clean/
python src/run.py measure     # refuses if the corpora are not comparable
python src/run.py report      # -> out/report.md
```

The wiki hosts in `corpus/games.json` are the conventional Fandom names and
are **unverified** — they could not be reached from the machine this was
written on, where outbound access was restricted to GitHub, npm and PyPI.
`discover` is the check.

## Method

### Everything is cut to the same size

Vocabulary coverage and type-token ratio both drift with corpus length, so a
game with a 200k-word script would score as harder than one with 20k on volume
alone. Every corpus is sampled to **20,000 tokens** before measurement, by
taking whole lines at random across the whole script rather than truncating —
the opening hours of most games are written to be the easiest part.

### What gets thrown away

Speaker names, stage directions, UI strings, wiki furniture, timestamps and
markup. Left in, speaker labels alone can be a tenth of the tokens and would
be counted as vocabulary. Repeated lines are collapsed, because combat barks
repeat for hours and would otherwise dominate the frequency profile.

### Vocabulary

Coverage is measured against **OpenSubtitles frequency bands** (2k/3k/5k/10k/
20k), not an academic list. Subtitles and games are the same register —
spoken English delivered as on-screen text — where BNC/COCA would rank
literary vocabulary as more common than a player ever hears it.

CEFR levels come from the CEFR-J profile (A1–B2) and the Octanove profile
(C1–C2). A headword keeps its *easiest* level: a word you already meet at A1
in one sense is not hard because it also carries a C1 sense.

**`unlisted` is reported separately from C1/C2 and is not advanced vocabulary.**
It is everything the wordlist has never seen, which in a game means invented
common nouns. Folded together, a fantasy game would outscore Shakespeare on
coinages alone.

Proper nouns are excluded from every vocabulary measure and counted on their
own axis. They are a load on memory, not on vocabulary: you do not need to
*know* a place name, only to keep it straight.

### Archaic register

Derived from data, not hand-written: a word scores by how much more often
19th-century literature uses it than contemporary speech does, as log2 of the
ratio. Three filters keep it honest, each added after it produced a visibly
wrong answer:

- **Apostrophe tokens are dropped.** The subtitle list mangles them (`don't`
  is split across `don`, `dont`, `don\`t`, `don.t`), so every contraction
  looked absent from modern English and scored at the very top.
- **Early Modern spellings are dropped.** The sample carries the KJV Bible and
  Shakespeare in original orthography, so `haue`, `vpon` and `loue` ranked as
  the most literary words in English. They are `have`, `upon` and `love`.
- **Words modern speech still uses are dropped**, however lopsided the ratio.
  Without this the index fills with connectives the KJV leans on (`upon`,
  `nor`, `thus`, `therefore`) and with the subject matter of the two longest
  books in the sample (`sons`, `kings`, `servants`, `whale`). A curated seed
  list of genuine archaisms is merged back in, so `thou` and `thy` still count
  even though fantasy subtitles keep them alive.

Elevated-but-current vocabulary (`relinquish`, `heirloom`, `vanquish`) is
deliberately *not* on this axis. The CEFR and frequency axes already carry it.

### Sentences

spaCy parses every sentence: mean and median length, share over 20 and 30
tokens, subordinate clauses per sentence, mean dependency distance, mean parse
tree depth. Tree depth is computed iteratively — recursion overflows on long
sentences, and a statistical parser occasionally emits a head cycle that a
recursive walk never returns from.

### Calibration

Every number is a ratio of two ratio-scale quantities, so `1.8x` means 1.8
times as much of the measured thing. Nothing is a weighted sum of z-scores,
because the weights would be invented and the ratios would not survive them.

From the anchor game's coverage curve, the pipeline infers the smallest
vocabulary that reads 98% of it without stopping — the standard threshold for
comfortable reading. That is your working vocabulary floor. Each game's
`vocabulary` multiplier is then its unknown-words-per-1000 at that vocabulary
size, divided by the anchor's.

Unknown words and archaic forms are reported in the same unit — times per
1000 tokens that a player is stopped — so they **add** into a single `decode`
load rather than needing an invented weight to trade them off. Measuring
archaism and then leaving it out of the composite scored Demon's Souls-shaped
text, where archaic grammar is most of the difficulty, as easy.

`overall` counts decoding twice against sentence complexity once: a sentence
whose words you know parses itself eventually, a sentence whose words you do
not know does not.

## The scale

Measured reference registers, so a game's numbers mean something. See
`out/report.md` for the full table. Worth knowing before reading any game row:

Shakespeare's `cov@2k` (77.1%) is *higher* than academic prose's (71.1%). His
difficulty is not rare vocabulary — it is archaic morphology and syntax, which
is why archaism is its own axis rather than folded into a single score.

## Limitations

- **Listening is not measured.** Accent, speech rate and elision are not
  recoverable from a transcript. The pipeline reports a text-side proxy
  (contractions, fragments, interjections) and nothing more. The `load` fields
  in `corpus/games.json` are null and stay null until filled by hand — nothing
  downstream invents them.
- **Reading and listening must not be pooled for a mostly-unvoiced game.**
  Tears of the Kingdom's NPC dialogue is largely text, so its listening load is
  not comparable to a fully voiced game's on the same scale.
- **Wiki depth varies, and that is not measured difficulty.** One source
  fixes the population definition but not how diligently each community
  transcribed. A thin wiki yields a small, cutscene-heavy sample; a thorough
  one yields ambient lines too. `provenance.json` records pages, lines and
  words per game and those land in `measurements.json` — read them before
  trusting a row. Extracting text from the games themselves would remove this
  entirely, at the cost of a separate tool per engine.
- The archaic index rests on an 18-book public-domain sample, which is enough
  for archaic function words and verb morphology and not enough for open-ended
  content words.
- **Semantic drift is invisible.** A word that is common now and meant
  something else then is counted as known. This is why measured Shakespeare
  lands below academic prose: his word stock really is ordinary English
  (`cov@2k` 77%, *higher* than newspaper journalism), and what makes him hard
  is compression and shifted sense, which no lexical metric sees. Read the
  archaic axis, not the overall, for period-register games.
- The scale was not tuned until its ranking matched intuition. Where a
  measured result disagrees with the reference ladder, that is information
  about the text, not a number to adjust.
