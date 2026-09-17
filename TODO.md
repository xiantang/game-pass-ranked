# TODO

## Play time from IGDB

Goal: show how long each game takes, for the "时间紧，任务重，只玩精品" angle.
HowLongToBeat is out: no public API, and its search is deliberately protected
against scraping. IGDB (Twitch) has an official API with time-to-beat data.

1. **Credentials** (owner): create a Twitch app at https://dev.twitch.tv/console
   (2FA required, Confidential client). Put `IGDB_CLIENT_ID` / `IGDB_CLIENT_SECRET`
   in a git-ignored `.env`, and in GitHub secrets via `gh secret set`.
2. **Check coverage before building UI.** Match games by store ID through IGDB
   `external_games` (Xbox product ID, PS Store ID), falling back to title + year.
   Count how many games with a critic score of 80+ have time-to-beat data, then:
   - 70%+: card label, play-time filter and sort, and a 只玩精品 preset
     (critic 90+, user 8+, main story under 20h)
   - 40–70%: card label only, no filter
   - under 40%: drop IGDB and add an HLTB search link per game
3. Games with no end (roguelikes, sandboxes, racing: Hades, Balatro, Minecraft,
   Forza) must not be hidden by a play-time filter. Look at IGDB genres/themes for a
   "drop in anytime" tag instead.

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
