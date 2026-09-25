# Incentive Model — Stage 2.5

> **Pipeline position:** runs after reward/scoring decoding (Stage 2 / `reward-decoding.md`, `scoring-math.md`) and before the economics roll-up (`economics.md`) and verdict (`verdict-rubric.md`).
>
> **Job of this stage:** *model*, not merely *describe*, how a subnet pays. Stage 2 tells you **what code computes the reward**. Stage 2.5 turns that into a **predictive model**: given a miner's measurable behavior, what does it earn in alpha, in TAO, in USD — and can a *fresh* UID realistically climb to that, or is it structurally walled?
>
> **Truth-first contract.** Every numeric constant in this doc is a placeholder pattern. Mark each one **`VERIFY LIVE per netuid`** in your output and read the real value from chain/code (see `tooling-reference.md`). **Never fabricate a constant, a price, a pool depth, or an emission number.** If you cannot verify it, write `UNVERIFIED — could not read` and let it propagate to the verdict. A confident wrong number is worse than an honest gap.

This stage produces one artifact: an **Incentive Model** with seven parts. Parts 1–2 model the *scoring surface* (what the validator rewards). Parts 3–4 model the *payout surface* (what that reward is worth). Part 5 is the *permeability gate* (can a newcomer get there). Part 6 is the *live read checklist*. Part 7 is the *plain-English synthesis*.

---

## 1. Render scoring as math

The goal is a **formula**, not a paragraph. A paragraph hides the lever; a formula exposes it.

### 1a. Extract the function from code
From the validator code (located in Stage 2), isolate the exact computation that maps **one miner's response** to **a scalar score**, then to **a normalized weight**. Walk it in this order and name each variable as you go:

1. **Inputs** — what the validator measures per miner per evaluation. (e.g. a returned value, a latency, a loss, a similarity, a completion, an uptime sample.) Name each: `x₁, x₂, …`.
2. **Per-sample transform** — the raw scalar score from those inputs: `s = f(x₁, x₂, …)`. Capture exponents, clamps (`max(0, …)`), thresholds, and any reference/baseline term `b`.
3. **Aggregation** — how many samples, over what window, combined how (mean? EMA? min? sum?). Name the window `T` and the combiner.
4. **Ranking / selection** — does raw score map to reward directly, or via rank? Capture rank-cutoffs (top-k), tie-handling, and any winner-take-most curve.
5. **Normalization to weight** — how scores become the weight vector the validator sets on-chain: `wᵢ = sᵢ / Σⱼ sⱼ` (or softmax, or rank-bucketed). The weight — not the raw score — is what Yuma consensus turns into incentive.

Write the result as a single expression with a legend. Keep clamps and exponents explicit — they are usually the most important part.

### 1b. Worked-example template (fill in with REAL numbers)

Instantiate the formula with live measurements so the lever becomes obvious. Fill every `___`:

```
Scoring function (from code):   sᵢ = ___________________  (cite file:line)
Legend:                         xᵢ = ___,  baseline b = ___,  window T = ___
Reward mapping:                 rank → reward = ___________ ;  ties → ___

Subject miner:    returns X = ___ at latency Y = ___  →  raw score s = ___
Cohort median:    W = ___        (read from metagraph / live scoring sample)
Subject's rank:   ___ of ___ active UIDs   →  reward bucket = ___
Marginal alpha of X → X+1:       Δs = ___ ;  Δrank = ___ ;  Δreward = ___
Saturation point:                X beyond which Δreward ≈ 0:  ___
```

The **marginal** line is the whole point: it tells the operator whether a 1-unit improvement is worth anything, or whether the curve has already saturated / is rank-gated so only crossing a competitor matters.

### 1c. Illustrative format example (DO NOT specialize the doc to this)
> *Example only — to show the shape of a filled template. This subnet is one possible target, not the subject.*
>
> A subnet scores `score = max(0, baseline_loss − val_loss) ** 1.2`; the **top-3 miners** earn reward weights `2.25 / 1.5 / 1.0`; **ties resolve to 0**. Legend: `val_loss` = the miner's reported validation loss; `baseline_loss` = a fixed reference; exponent `1.2` rewards margin super-linearly.
>
> Filled: a miner at `val_loss = 2.10` vs `baseline_loss = 2.40` scores `(0.30)**1.2 ≈ 0.236`. If cohort median score is `0.18` and that lands the miner at **rank 4**, reward = **0** (outside top-3). Marginal: dropping `val_loss` by `0.05` raises score to `(0.35)**1.2 ≈ 0.282` — *worthless unless it crosses rank 3*. This exposes that the real lever is **rank-crossing**, not raw margin, and that the **ties→0** rule makes any duplicated/copied output catastrophic.

Use this only as a pattern. Re-derive the formula from the target's own code every time.

---

## 2. Dominant lever + zero-score cliffs

### 2a. Isolate the single dominant lever
Of all inputs `x₁…xₙ`, **which one variable, if moved, moves the reward the most?** Determine it from the formula's structure, not intuition:
- Highest exponent / steepest term usually dominates.
- A **rank cutoff** often dominates everything: below the cutoff, *all* continuous improvement pays zero. When a cutoff exists, the dominant lever is "cross competitor N", and the continuous inputs are secondary.
- A **min()** combiner means the *worst* sample is the lever (one bad response tanks the aggregate).

State the dominant lever in one sentence: *"On this subnet, earnings are driven primarily by ___, because ___."*

### 2b. Enumerate zero-score cliffs
List every condition that produces **reward = 0** despite effort, and every condition that **deregisters** the UID. Read these from code + hyperparameters; do not assume:

| Cliff | Trigger (from code / chain) | Recoverable? |
|---|---|---|
| Clamp-to-zero | score term hits `max(0, …)` floor (e.g. worse than baseline) | yes — improve input |
| Outside reward bucket | rank > top-k cutoff | yes — but requires crossing a competitor |
| Tie / duplicate | identical output to another miner; copy detection | sometimes — depends on detector |
| Stale / no response | missed evaluation window, timeout, malformed payload | yes — fix uptime |
| Weight-copier penalty | validator down-weights detected free-riders | varies |
| **Deregistration** | UID pruned for lowest incentive after immunity; failed liveness | **no — must re-register and pay burn again** |

The deregistration row is decision-critical: it sets the **clock** the permeability gate in Part 5 races against.

### 2c. Classify deterministic vs stochastic
- **Deterministic:** same inputs → same score every epoch (most loss/latency/similarity scorers). Operator can optimize directly; outcomes are predictable.
- **Stochastic:** scoring samples random tasks/prompts/seeds, or validators sample a subset of miners per epoch, or reward has noise. Then earnings are a **distribution**, not a point — model expected value *and* variance, and warn that a single good epoch is not signal.

State which one applies and why. A stochastic scorer with high variance plus a short immunity window is a hostile combination for newcomers (you may be deregistered on bad luck before your true skill is measured).

---

## 3. dTAO economics (2026 — verify live)

> The 2024 "price-based emission" mental model is **OBSOLETE**. As of 2026, emission is **flow-based** ("Taoflow"). Model it that way.

### 3a. Taoflow: emission follows net TAO flow, not price
Per-subnet emission is driven by an **EMA of net TAO flow** into the subnet's pool (stake/buy inflow minus unstake/sell outflow), **not** by alpha price level. Consequences to model:
- **Negative net flow → emission trends toward 0.** A subnet bleeding TAO can stop paying *regardless of how good the tech is or how high alpha once was.* Check the flow EMA / recent stake-flow direction live.
- A subnet with a flat price but **steady positive inflow** can out-earn a higher-priced subnet that is in outflow.
- This is the **single most important macro input** and it is dynamic — re-read it close to decision time. Mark `VERIFY LIVE per netuid`.

### 3b. The 41 / 41 / 18 split
Per-subnet alpha emission is split (verify live — governance can change it):
- **~41% to miners**, **~41% to validators (+ their delegators)**, **~18% to the subnet owner.**

For a *miner* operator, only the **~41% miner share** is the addressable pool. Use it — not total emission — as the numerator when sizing miner earnings. (If analyzing a validator path, the math differs; this doc models the miner.)

### 3c. Alpha → TAO → USD, WITH slippage
Emission is paid in the subnet's **alpha** token. Converting to spendable TAO/USD goes through the subnet's **constant-product AMM** (alpha↔TAO), so **realized value ≠ alpha_amount × spot_price.** Model the slippage explicitly:

```
Constant product:   alpha_reserve × tao_reserve = k   (read both reserves live)
Spot price:         P_spot = tao_reserve / alpha_reserve
Sell Δalpha, get:   ΔTAO = tao_reserve − k / (alpha_reserve + Δalpha)
Effective price:    P_eff = ΔTAO / Δalpha   (< P_spot; gap grows with Δalpha / thin pool)
USD:                value_usd = ΔTAO × TAO_USD   (TAO_USD: VERIFY LIVE)
```

**Why a high-emission subnet can still be near-worthless:** if the alpha/TAO **pool is thin**, daily miner emission is large *in alpha* but selling it craters `P_eff` (high slippage), so realized TAO is small. If **net flow is negative** (3a), emission is also shrinking. Either condition independently can make nominal APR illusory. Always quote earnings at the **effective** price for a realistic daily sell size, and state pool depth + flow direction next to it.

### 3d. Daily-earnings formula (miner)
```
daily_alpha   = incentiveᵢ × (alpha_to_miners_per_epoch) × epochs_per_day
              # incentiveᵢ ∈ [0,1] = this UID's normalized share of the miner pool
              # alpha_to_miners_per_epoch = per-epoch subnet emission × ~0.41 (3b) — VERIFY
              # epochs_per_day ≈ 20  (see Part 4) — VERIFY
daily_tao     = AMM_sell(daily_alpha)         # apply slippage from 3c, not spot
daily_usd     = daily_tao × TAO_USD           # VERIFY LIVE
```
Report `daily_usd` **net of exit slippage**, and annotate every factor `VERIFY LIVE`. Show the spot-vs-effective gap so the reader sees the slippage tax. If net flow is negative, add a one-line caveat that the emission term is decaying.

---

## 4. Emission mechanics (verify live)

Read these from chain; the defaults below are *patterns to verify*, not facts:

- **Tempo** — epoch length, **~360 blocks** default. Weights set / emission distributed once per tempo. `VERIFY LIVE`.
- **Epochs per day** — **~20** at ~12s blocks (`86400 / (12 × 360) ≈ 20`). Derive from the *live* tempo and block time, don't hardcode.
- **Immunity period** — new UIDs are protected from deregistration for **~4096 blocks** default, **but read live** — owners can change it per subnet. This is the newcomer's runway (feeds Part 5).
- **Dec-2025 halving** — base block emission halved to **0.5 TAO/block**; factor the current value into per-epoch emission. `VERIFY LIVE` (further halvings possible).
- **Registration cost — continuous dynamic burn.** Registration is priced by a **continuous burn curve** governed by `BurnHalfLife` / `BurnIncreaseMult` (cost rises with recent registration rate, decays over time toward `min_burn`). **The old "difficulty doubles each registration" heuristic is DEPRECATED — do not use it.** Read the **current burn cost** live right before sizing payback; it is volatile.

For each: state the live value, the source command, and how it feeds the model (immunity → runway; tempo/epochs → emission cadence; burn → entry cost / payback period).

---

## 5. Permeability / cohort gate — the decision-critical part

A subnet can have excellent economics (Parts 1–4) and still be **uninvestable for a newcomer** because a fresh UID cannot reach the paying cohort before its immunity expires. This part decides whether the verdict is allowed to say "opportunity" at all.

Model the **race**: *time-to-first-meaningful-emission* vs *immunity window*.

### 5a. Immunity window vs time-to-first-emission
- **Runway** = immunity_period (blocks) → days (Part 4).
- **Time-to-climb** = how long until a competent fresh UID earns non-trivial incentive. Drivers: Yuma consensus convergence, **bond maturation**, validator coverage of the new UID, and the scoring window `T`.
- If **time-to-climb > runway**, the UID is likely deregistered (and loses its burn) before it ever earns. That is a structural wall.

### 5b. Bond wall, YC3, and liquid alpha
Validator **bonds** create inertia: validators accrue bonds toward established miners, and a new miner's weight is dampened until validators build bonds to it. This is the primary newcomer wall.
- **YC3 / `yuma3_enabled`** and **liquid alpha (`liquid_alpha_enabled`)**, *where enabled*, **lower the bond wall** — they let weight/bonds adjust faster, improving permeability. Check both per netuid. **Only credit this benefit where the flags are actually ON.** Where they are OFF, assume strong bond inertia and a higher wall.
- **Bond inertia** (when YC3/liquid-alpha off): model multi-day-to-weeks lag before a new UID's true score is reflected in incentive.

### 5c. Validator stake-threshold & concentration
- **Stake-threshold querying:** some validators only query / weight miners above a threshold, or only a top subset — a fresh UID may be **invisible** to most stake until it crosses it. Determine the effective threshold and how much stake actually evaluates newcomers.
- **Winner-take-most concentration:** read the incentive distribution from the metagraph. If the top few UIDs hold the overwhelming majority of incentive and turnover is near-zero, the cohort is **walled** — newcomers churn through immunity without displacing incumbents.

### 5d. Verdict cap (HARD RULE)
Combine the above into a permeability call: **PERMEABLE** (fresh UID can realistically climb within runway) or **WALLED** (cannot).

> **If the subnet is structurally WALLED, the Stage verdict is capped at "CHEAP TEST" and may NEVER be "SERIOUS OPPORTUNITY", no matter how attractive Parts 1–4 are.** Great economics behind a wall a newcomer cannot cross is not an opportunity for that newcomer. State the wall mechanism explicitly (bond inertia / concentration / stake-threshold invisibility / runway < time-to-climb) so the cap is auditable. Pass this cap to `verdict-rubric.md`.

---

## 6. Live hyperparameter checklist (read per netuid)

Read every row live before modeling; record value **and** source. Commands use `btcli` / the SDK — see `tooling-reference.md` for exact invocation, auth, and SDK equivalents. Treat all of these as `VERIFY LIVE per netuid`.

| Parameter | Why it matters | Where (see `tooling-reference.md`) |
|---|---|---|
| `tempo` | epoch length → epochs/day, emission cadence (Part 4) | `btcli subnet hyperparameters --netuid N` / SDK `subnet_hyperparameters` |
| `immunity_period` | newcomer runway (Part 5a) | subnet hyperparameters |
| `yuma3_enabled` | lowers bond wall where ON (Part 5b) | subnet hyperparameters |
| `liquid_alpha_enabled` | lowers bond wall where ON (Part 5b) | subnet hyperparameters |
| `commit_reveal` (enabled + interval) | weight commit/reveal delay → scoring latency, copy-resistance | subnet hyperparameters |
| `min_burn` / `max_burn` | bounds on registration cost (Part 4) | subnet hyperparameters |
| **current burn cost** | actual entry price now → payback (Part 4); volatile | `btcli subnet list` / `subnet info` (recycle/burn) |
| UID **count / cap** (`max_uids`, current n) | competition density; is there even a slot? | metagraph / `btcli subnet metagraph --netuid N` |
| incentive distribution | concentration / winner-take-most (Part 5c) | metagraph incentive column |
| net TAO flow / pool reserves | Taoflow emission + slippage (Part 3) | subnet info / pool reserves; flow EMA |

If a parameter cannot be read, record `UNVERIFIED` and surface it — do not silently default.

---

## 7. Plain-English synthesis (required output)

End the Incentive Model with **one paragraph** an operator can act on, in plain English. It must answer: *"This is exactly how you earn here."* Include, in words:
1. the **dominant lever** and the **marginal payoff** of improving it (Parts 1–2);
2. what scores **zero / deregisters** you (Part 2b) and whether scoring is deterministic or a gamble (Part 2c);
3. the **realistic daily USD** net of slippage, with pool-depth and net-flow caveats (Parts 3–4);
4. the **permeability call** and, if WALLED, the explicit statement that the verdict is capped at CHEAP TEST and why (Part 5).

Keep every number tagged `VERIFY LIVE` or `UNVERIFIED` as appropriate. The paragraph is the bridge from this stage's math to the `verdict-rubric.md` decision — it should let a reader who skips the formulas still understand the earning path and its single biggest risk.
