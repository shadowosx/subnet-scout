# Live data sources

Where to fetch live state for a subnet, what each source gives you, and how to handle failure.

Every numeric claim in the final report must trace to one of these. If none of them yielded a number for a given claim, the claim either gets removed or moves to **Known unknowns**.

---

## TaoStats (taostats.io)

Primary public source for subnet economics.

- **Subnet page** — `https://taostats.io/subnets/<netuid>`
  - Current registration burn (in TAO)
  - Active miner count, active validator count
  - Subnet emission rate
  - Owner cut
  - Subnet age / first registered block
- **Miner / validator table** — concentration view; sort by incentive descending to see the top hotkeys
- **Hotkey page** — `https://taostats.io/hotkey/<ss58>` — historical incentive, registrations, coldkey link
- **Coldkey page** — `https://taostats.io/coldkey/<ss58>` — all hotkeys under one coldkey; useful for spotting clusters
- **Subnet emissions over time** — visible on the subnet page; look for cliffs / pumps

Fetch via `WebFetch`. If rate-limited, retry once with a backoff or accept a partial pull — do not fabricate.

What to extract for the report:
- Live burn cost (in TAO + USD at current rate if quotable)
- Active miner count
- Top 5 hotkey share of incentive (concentration metric)
- Validator stake distribution (top 3 validator stake share)
- Recent (last 30 days) churn in top 20: how many hotkeys are new?

## Subnet's own dashboard

Many subnets host a leaderboard / explorer. Common patterns:
- `dashboard.<project>.ai`
- `<project>.tao.bot`
- `<project>.com/leaderboard`

These usually show per-miner score breakdowns more granular than TaoStats. If linked from the repo README, **always inspect it** — they often reveal the moat (e.g. "miners must publish to HuggingFace" — leaderboard scrapes HF).

If the dashboard is behind a login or only on Discord, mark it as a centralization tell.

## OpenTensor Foundation registry

`https://github.com/opentensor/bittensor-subnets` — community-maintained index of subnets and their repos. Useful when the user gave you a netuid but not a repo URL.

## btcli (only if user authorizes)

If user has `btcli` installed and wants you to drive it:

```bash
btcli subnet metagraph --netuid <N>
btcli subnet list
btcli wallet overview --wallet.name <name>
```

The metagraph dump gives you exact UID-by-UID stake, incentive, last-update — more granular than TaoStats. **Never** run wallet commands without explicit confirmation; they expose addresses and require the user's coldkey path.

## GitHub signals (use the `gh` CLI or WebFetch)

For the target repo:
- `gh repo view <owner/repo>` — stars, last push, license
- `git log --since="60 days ago" --oneline` (in cloned repo) — recent activity
- `git log --since="60 days ago" --format="%an" | sort | uniq -c` — committer concentration; team-only commits is a project-health signal
- Open issues count, recent merged PRs, who's merging — non-team merges signal a healthy maintainer culture

## Discord / X / official docs site

If the README links these, treat as **soft** context. Do not infer drama or "the team is shady" from any post without verifiable evidence (a deleted commit, a public statement). Operator reports should not include rumor.

What the docs site CAN tell you cleanly:
- Official stance on subnet purpose
- Roadmap claims (use for the gap table)
- Operator guides (helpful for the Stage 6 plan)

## CoinGecko / CMC (TAO price)

To convert TAO ↔ USD for the cost section:
- `https://www.coingecko.com/en/coins/bittensor`

Quote the price with a timestamp; TAO is volatile.

---

## Failure handling

For every source, on failure:
1. State the failure mode (rate limit / 404 / login wall / timeout) in **Commands and live checks run**.
2. Mark the dependent claim as "Unknown — could not verify" or list it in **Known unknowns**.
3. Do not pad with assumed defaults. If burn cost is unverified, do not assume "probably around 1 TAO".

A report with two or three "Unknown — could not verify" entries is honest. A report with zero is suspicious.
