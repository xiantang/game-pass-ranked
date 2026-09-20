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

| corpus | cov@2k % | cov@5k % | C1+C2 % | unlisted % | archaic/1k | sent. len | subord./sent |
|---|---|---|---|---|---|---|---|
| **rdr2** | 93.75 | 96.98 | 0.29 | 6.19 | 0.4 | 7.38 | 0.637 |
| **re4-remake** | 90.96 | 95.29 | 0.2 | 6.09 | 1.78 | 6.82 | 0.436 |

