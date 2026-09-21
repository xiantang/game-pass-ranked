# Game English difficulty — measured report

## The scale

Reference registers, measured by the same pipeline on the same 20,000-token
budget. A game's numbers mean something only against these.

| corpus | cov@2k % | cov@5k % | C1+C2 % | unlisted % | archaic/1k | sent. len | subord./sent |
|---|---|---|---|---|---|---|---|
| instant messaging (`chat/nps`) | 85.07 | 90.51 | 0.28 | 21.8 | 0.11 | 13.11 | 1.369 |
| genre fiction (`brown/mystery`) | 86.81 | 92.56 | 1.09 | 8.74 | 1.83 | 13.37 | 1.091 |
| general fiction (`brown/fiction`) | 84.35 | 90.72 | 1.14 | 11.38 | 2.58 | 14.54 | 1.09 |
| newspaper journalism (`brown/news`) | 78.6 | 88.52 | 1.25 | 10.37 | 0.81 | 21.29 | 1.389 |
| children's classic (`gutenberg/carroll-alice`) | 90.81 | 94.52 | 0.58 | 5.03 | 4.44 | 19.46 | 2.222 |
| Austen (`gutenberg/austen-persuasion`) | 87.29 | 92.1 | 1.51 | 6.95 | 10.68 | 24.99 | 2.375 |
| academic prose (`brown/learned`) | 71.23 | 82.4 | 2.2 | 15.87 | 1.59 | 23.12 | 1.489 |
| Moby-Dick (`gutenberg/melville-moby_dick`) | 78.03 | 85.5 | 2.1 | 18.38 | 14.49 | 24.84 | 1.903 |
| Paradise Lost (`gutenberg/milton-paradise`) | 73.51 | 83.3 | 2.41 | 20.31 | 35.72 | 33.08 | 2.974 |
| Shakespeare (`gutenberg/shakespeare-hamlet`) | 85.71 | 90.12 | 1.2 | 20.57 | 27.46 | 13.08 | 0.967 |
| King James Bible (`gutenberg/bible-kjv`) | 82.76 | 89.64 | 1.59 | 18.95 | 50.75 | 26.27 | 1.937 |

## Games

Collected from automatic captions of no-commentary playthroughs. The
blanked columns are the ones that source cannot carry: measured against a
wiki corpus of the same game, sentence length came out 26% low and archaism
45% low, because the automatic track has no punctuation for the parser to
split on and speech recognition hears an archaic word as its modern
neighbour. Coverage survives (+0.5%) and is what these rows are for.

| corpus | cov@2k % | cov@5k % | C1+C2 % | unlisted % | archaic/1k | sent. len | subord./sent |
|---|---|---|---|---|---|---|---|
| **bg3** | 88.16 | 93.91 | — | — | — | — | — |
| **clair-obscur-33** | 91.7 | 95.18 | — | — | — | — | — |
| **cyberpunk-2077** | 89.34 | 94.25 | — | — | — | — | — |
| **ghost-of-tsushima** | 92.23 | 96.51 | — | — | — | — | — |
| **god-of-war-2018** | 92.82 | 96.45 | — | — | — | — | — |
| **jedi-survivor** | 91.83 | 95.61 | — | — | — | — | — |
| **kcd2** | 92.65 | 96.15 | — | — | — | — | — |
| **persona-5-royal** | 90.04 | 94.93 | — | — | — | — | — |
| **rdr2** | 94.61 | 97.48 | — | — | — | — | — |
| **re2-remake** | 90.04 | 95.88 | — | — | — | — | — |
| **re4-remake** | 93.6 | 97.0 | — | — | — | — | — |
| **spider-man-2** | 92.02 | 96.22 | — | — | — | — | — |
| **tlou-remastered** | 95.51 | 97.79 | — | — | — | — | — |
| **uncharted-4** | 93.67 | 96.93 | — | — | — | — | — |

### Load

How fast the English arrives, which is a different question from how
hard it is. Words per hour counts the whole playthrough, silence
included; words per minute is measured over the gaps between captions,
so it is the rate while someone is actually speaking.

| game | words/hour | words/min spoken | corpus words | hours | ASR noise % |
|---|---|---|---|---|---|
| bg3 | 2315 | 95.7 | 43549 | 18.81 | 2.42 |
| clair-obscur-33 | 1607 | 74.9 | 38560 | 24.0 | 0.04 |
| cyberpunk-2077 | 3132 | 109.8 | 16443 | 5.25 | 0.46 |
| ghost-of-tsushima | 2876 | 111.1 | 24391 | 8.48 | 3.83 |
| god-of-war-2018 | 2861 | 120.0 | 29310 | 10.24 | 1.45 |
| jedi-survivor | 1903 | 100.0 | 22760 | 11.96 | 2.03 |
| kcd2 | 5126 | 150.0 | 184415 | 35.98 | 1.16 |
| persona-5-royal | 4980 | 121.0 | 21652 | 4.35 | 0.6 |
| rdr2 | 4816 | 139.5 | 172106 | 35.74 | 1.04 |
| re2-remake | 639 | 45.2 | 2476 | 3.87 | 18.2 |
| re4-remake | 1280 | 51.7 | 11611 | 9.07 | 0.21 |
| spider-man-2 | 3516 | 122.0 | 63272 | 18.0 | 0.94 |
| tlou-remastered | 2826 | 104.2 | 28442 | 10.07 | 1.1 |
| uncharted-4 | 4006 | 122.2 | 38167 | 9.53 | 1.64 |

## Lookups per hour

How often an unknown word stops you, per hour of play. It is the only
composite here, and it needs no invented weight: unknown words per 1000
tokens times thousands of words per hour multiply to a rate, with the
units cancelling. Pick the column matching your own vocabulary.

It carries vocabulary and volume only. Syntax and archaism are not in it,
because the caption source cannot measure them — so a period-register game
is understated here, not overstated.

| game | unknown/1k @5k | words/hour | @3k | @5k | @8k |
|---|---|---|---|---|---|
| re2-remake * | 41.2 | 639 | 50 | **26** | 14 |
| re4-remake * | 30.0 | 1280 | 60 | **38** | 26 |
| tlou-remastered | 22.1 | 2826 | 96 | **62** | 41 |
| clair-obscur-33 | 48.2 | 1607 | 104 | **77** | 52 |
| jedi-survivor | 43.9 | 1903 | 114 | **84** | 57 |
| ghost-of-tsushima | 34.9 | 2876 | 157 | **100** | 64 |
| god-of-war-2018 | 35.5 | 2861 | 150 | **102** | 69 |
| rdr2 | 25.2 | 4816 | 184 | **121** | 79 |
| uncharted-4 | 30.7 | 4006 | 180 | **123** | 81 |
| spider-man-2 | 37.8 | 3516 | 210 | **133** | 88 |
| bg3 | 60.9 | 2315 | 207 | **141** | 102 |
| cyberpunk-2077 * | 57.5 | 3132 | 266 | **180** | 121 |
| kcd2 | 38.5 | 5126 | 291 | **197** | 132 |
| persona-5-royal | 50.7 | 4980 | 370 | **252** | 162 |

`*` under 20,000 words of corpus, so that row is measured on a smaller
sample than the budget the rest are cut to.

