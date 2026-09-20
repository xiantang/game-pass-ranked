# Game English difficulty — measured report

> **No game corpus measured yet.** The reference scale below is built and
> validated; drop transcripts into `corpus/raw/<slug>/` and re-run to fill in
> the games. See `README.md` for what each game needs.

## The scale

Reference registers, measured by the same pipeline on the same 20,000-token
budget. A game's numbers mean something only against these.

| corpus | cov@2k % | cov@5k % | C1+C2 % | unlisted % | archaic/1k | sent. len | subord./sent |
|---|---|---|---|---|---|---|---|
| instant messaging (`chat/nps`) | 82.36 | 87.68 | 0.21 | 26.14 | 0.06 | 13.48 | 1.385 |
| genre fiction (`brown/mystery`) | 86.77 | 92.49 | 1.11 | 8.77 | 1.89 | 13.14 | 1.057 |
| general fiction (`brown/fiction`) | 84.28 | 90.71 | 1.16 | 11.43 | 2.58 | 14.41 | 1.081 |
| newspaper journalism (`brown/news`) | 78.49 | 88.44 | 1.25 | 10.57 | 0.87 | 20.82 | 1.369 |
| children's classic (`gutenberg/carroll-alice`) | 90.73 | 94.41 | 0.51 | 5.24 | 4.59 | 21.25 | 2.501 |
| Austen (`gutenberg/austen-persuasion`) | 87.28 | 92.09 | 1.54 | 7.05 | 10.58 | 25.05 | 2.388 |
| academic prose (`brown/learned`) | 71.07 | 82.23 | 2.15 | 16.15 | 1.53 | 22.79 | 1.465 |
| Moby-Dick (`gutenberg/melville-moby_dick`) | 77.94 | 85.38 | 2.04 | 18.69 | 14.89 | 25.31 | 1.904 |
| Paradise Lost (`gutenberg/milton-paradise`) | 73.02 | 82.89 | 2.43 | 20.63 | 36.67 | 28.03 | 2.307 |
| Shakespeare (`gutenberg/shakespeare-hamlet`) | 77.14 | 81.15 | 1.01 | 38.04 | 27.41 | 12.21 | 0.822 |
| King James Bible (`gutenberg/bible-kjv`) | 82.48 | 89.52 | 1.57 | 19.15 | 53.14 | 26.38 | 1.89 |

