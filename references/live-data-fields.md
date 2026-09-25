# Live-data field rules

When `scripts/subnet-research.py report <netuid>` runs, it emits a JSON blob with fields drawn from Taostats, GitHub, and Desearch. Some fields are accurate and operator-relevant. Some look useful but are wrong, internal, or misleading. This file is the source of truth on what to use.

These rules come from Cody's hard-won experience — they have been miscited before, and the failure mode every time is over-confident numbers in a report that look authoritative but aren't.

---

## Fields to USE in reports

### Subnet identity
- `identity.subnet_name` — display name
- `identity.description`, `identity.summary` — what it claims to do
- `identity.github_repo` — primary code source
- `identity.website`, `identity.discord`, `identity.twitter` — operator channels
- `identity.tags` — surface-level categorization

### Subnet state (live)
- `subnet_info.active_miners` — **the** real active miner count
- `subnet_info.active_validators` — real validator count
- `subnet_info.max_neurons` — total UID slots (usually 256)
- `subnet_info.registration_cost_tao` — current miner burn cost (NOT "subnet registration")
- `subnet_info.tempo` — block interval for weight settlement
- `subnet_info.registration_allowed` — whether new miners can register *right now*

### Economics
- `tao_price_usd` — current TAO/USD for cost translation
- `metagraph.daily_emission_tao` — total subnet daily emission
- `metagraph.miner_daily_emission_tao` — miner share of daily emission
- `metagraph.validator_daily_emission_tao` — validator share
- `metagraph.owner_daily_emission_tao` — owner cut
- `metagraph.avg_miner_daily_tao` — average per-miner daily TAO
- `metagraph.top_miner_daily_tao` — top miner's daily TAO (the ceiling)
- `metagraph.bottom_miner_daily_tao` — bottom earning miner (the floor)
- `metagraph.top_3_miners` — UID, daily_tao, incentive, partial hotkey — **always include this table**

### Profitability (derived inside the script)
- `profitability.avg_daily_usd_per_miner`
- `profitability.top_daily_usd`
- `profitability.days_to_roi` — registration burn / avg miner daily TAO
- `profitability.competition_ratio` — active_miners / total_miner_emission (lower = better)

### Code health
- `github.stars`, `github.forks`, `github.open_issues`
- `github.last_commit`, `github.days_since_last_commit` — >60 days = dead-repo signal
- `github.contributors` — small number + team-only = centralization signal
- `github.recent_commits[]` — last 5 commit messages and authors
- `github.readme` — first 8000 chars; use to verify mining setup claims

### Community pulse
- `x_sentiment.tweets[]` — recent X posts mentioning the project
- `project_tweets[]` — the project's own recent tweets (cadence + tone signal)
- `web_research` — Desearch web hits (guides, articles)
- `website_content` — first 5000 chars of crawled project site

---

## Fields to NEVER show in reports

These look useful but are either raw, internal, or wrong-for-the-claim. Do not put them in the operator-facing output.

- `emission` (raw per-block emission) — confusing, not human-readable
- `projected_emission` — internal fraction, not a forecast
- `metagraph.tao_pool` raw rao integers — too big, no operator value
- `metagraph.alpha_pool`, `metagraph.alpha_rewards` — alpha-token internals
- `metagraph.tao_in_pool` raw rao — divide by 1e9 if you must, and call it pool size
- `subnet_info.active_keys` or `subnet_info.max_neurons` **as a miner count** — these are not miner counts (active_keys ≈ everything that touched the subnet recently; max_neurons is the slot cap)
- `incentive_burn` — internal accounting, not the registration cost a miner pays
- EMA TAO inflow values — internal smoothing
- Anything with the suffix `_rao` shown unconverted

---

## Fields that need conversion before display

- All `_rao` integers → divide by `1e9` to get TAO, then format to 4–6 decimal places
- `incentive` floats from metagraph → display as percent of the subnet's total miner incentive (`incentive_share = neuron_incentive / sum(all_miner_incentives)`)
- `daily_*_alpha_as_tao` → already in rao; divide by 1e9 for TAO
- ISO timestamps → display in WAT (UTC+1) when reporting to Dx; otherwise UTC with explicit `Z`

---

## Classification rules (miner vs validator)

The script classifies neurons by **scoreable signal**, not by `validator_permit`:

```
miner     := neuron with incentive > 0
validator := neuron with dividends > 0
```

A neuron can have both (some miners hold validator_permit). When citing counts, use `subnet_info.active_miners` and `subnet_info.active_validators` from Taostats — those numbers are what the live network reports.

The script's own `metagraph.miners` / `metagraph.validators` are derived from the same definition and should match closely. If they diverge significantly, note that as a known unknown and prefer `subnet_info.*`.

---

## Failure handling

`scripts/subnet-research.py` writes diagnostic messages to **stderr** when an API call fails:

```
[taostats] /api/subnet/identity/v1 rate limited, waiting 5s...
[desearch] project tweets error: ...
```

Captured stderr should be quoted verbatim in **Commands and live checks run** when a section is downgraded to "Unknown — could not verify."

The script never raises on a partial result — missing fields just don't appear in the JSON. **Always check for key existence before citing**, never `report["metagraph"]["avg_miner_daily_tao"]` without a guard.

---

## Hard rules

1. **Every number in the report comes from the JSON.** No estimating, no rounding from memory, no "probably around X".
2. **Never copy numbers from a subnet's GitHub README into the live-stats table.** READMEs are stale. The JSON wins.
3. **Never show raw JSON to the user.** Always format into tables + prose. The JSON is your source, not your output.
4. **The Top 3 Miners table is mandatory** when `metagraph.top_3_miners` is present. Concentration is the single most important signal a reader can act on.
5. **TAO price changes hourly.** Quote it with a timestamp from `report.generated_at`.

---

## Cross-check with TaoStats web

When the script is unavailable (no API keys, rate-limited, network down), fall back to `https://taostats.io/subnets/<netuid>` via WebFetch and pull:

- Registration cost
- Active miners / validators
- Recent emission chart
- Top hotkey concentration

State the fallback explicitly in **Commands and live checks run**, and mark the affected fields with their source URL so the audit trail stays intact.
