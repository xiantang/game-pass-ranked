# TODO

## Play time (HowLongToBeat)

Goal: show how long each game takes, for the "时间紧，任务重，只玩精品" angle.

Status (2026-10-23): card label shipped. `scripts/fetch-playtime.mjs` searches HLTB
through howlongtobeatpy (`scripts/hltb.py`) and caches matches in
`data/hltb-cache.json`. 97% of critic 80+ games (471/487) have a main-story time.
IGDB was tried first and dropped: most games had 1–3 reports and the numbers were
off (The Last of Us Remastered 6.7h, HLTB 14.7h).

- [ ] Play-time filter and sort, and a 只玩精品 preset (critic 90+, user 8+, main
  story under 20h). Coverage is high enough now.
- [ ] Games with no end (roguelikes, sandboxes, racing: Hades, Balatro, Minecraft,
  Forza) must not be hidden by a play-time filter. HLTB still gives them a "main"
  time, so tag them from Metacritic genres instead.
- [ ] Misses worth fixing by hand: Anno 1800, Diablo III Ultimate Evil Edition,
  Crash Team Racing Nitro-Fueled, Metro 2033 Redux, WipEout Omega Collection.
- [ ] howlongtobeatpy follows HLTB's private search call. When the weekly job
  prints "search failed", bump the pinned version in `requirements.txt`.

## Chinese names

- 宿命残响（ (Chained Echoes) is cut off by the mixed-name cleanup
- Two games are named 一般版
- 电车炫客: verify
- 雷曼：传奇 - 数码, 双人成行 - 数字版本: edition suffixes left over
- The Last of Us Part II 普通版 should be 最后生还者 第二部

## Site

- "只玩精品" one-click preset, and the slogan 时间紧，任务重，只玩精品 under the title
- Open Graph tags and a cover image, so shared links preview in WeChat / 小红书 / Reddit
- Visit stats (Cloudflare Web Analytics)
- Feedback link in the footer (GitHub Issues)
- US / EU catalogs, needed before posting to r/PlayStationPlus

## Promotion

- [x] 小红书: PS Plus Extra 90+ post
- [ ] 小红书: XGP post (critic 90+, user 8+), a few days after the first
- [ ] 小黑盒: XGP post, and share in the Xbox 凝聚力社区 group
- [ ] V2EX /go/create
- [ ] Hacker News Show HN (weekday, 8–10am Pacific)
- [ ] Reddit: modmail r/XboxGamePass; don't post until approved
