# Bittensor subnet — canonical knowledge

## ⚠️ 2026 dTAO-era update (verified 2026-05-30 — read live before acting)

> **Why this section exists:** parts of the body below predate dTAO (Feb 2025) and Taoflow (Nov 2025). Where the old text states a now-superseded fact, an inline `> ⚠️ SUPERSEDED 2026` flag points back here. **Every number here is a default / commonly-observed value — re-read live with `btcli sudo get --netuid N` / `btcli subnet hyperparameters --netuid N` / taostats before relying on it.**

**dTAO (Dynamic TAO), launched 2025-02-13/14** replaced the old root-validator-voting emission model with a market mechanism. Each subnet now has its own **alpha (α) token** and an on-chain **constant-product AMM pool** (TAO reserve + alpha reserve). **Staking into a subnet = a swap** (TAO in → alpha out along the curve); `price(α) = TAO_reserve / alpha_reserve`. A miner earns **alpha, not TAO** — realized USD = `alpha_earned × alpha_price(τ) × TAO_price(USD)`, and large alpha→TAO sells incur **slippage** on thin pools, so a high-emission subnet with a cheap alpha or a shallow pool can be near-worthless. ([dTAO overview](https://docs.learnbittensor.org/dynamic-tao/); [emissions](https://docs.learnbittensor.org/learn/emissions))

**Flow-based "Taoflow" emissions (Nov 2025)** govern how the per-block TAO is split **across** subnets: a subnet's share ∝ an **EMA of its net TAO staking flow** (staked minus unstaked), `share(i) = z_i^p / Σ z_j^p` with `z_i = max(S_i − L, 0)`, linear `p = 1`, EMA ~30-day half-life. **Sustained negative net flow → 0 emission** (and 0 alpha injection / 0 APY for holders). This **SUPERSEDES both** the original dTAO price-based allocation **and** the legacy root-validator-voting model. ([emissions](https://docs.learnbittensor.org/learn/emissions); [Opentensor X](https://x.com/opentensor/status/1999071691243429968); [CoinDesk](https://coindesk.cc/bittensor-activates-dynamic-tao-restructuring-emission-model-around-real-time-staking-flows-53434.html); [Messari](https://messari.io/newsletter/unqualified-opinions/bittensor-s-taoflow-a-smarter-real-time-emissions-model))

**Within a subnet**, each block's emission is split **41% miners / 41% validators+stakers / 18% owner** (applies to the **alpha** emission). **Tempo ~360 blocks** (~72 min); Yuma Consensus runs and alpha is distributed at tempo end → **~20 epochs/day** (7,200 blocks/day ÷ 360). ([arxiv 2507.02951](https://arxiv.org/html/2507.02951v1); [taostats](https://docs.taostats.io/docs/distribution-of-alpha-in-a-subnet); [emissions](https://docs.learnbittensor.org/learn/emissions))

**First TAO halving Dec 2025 → 0.5 TAO/block (~3,600 TAO/day)** network-wide (sources cite Dec 14–15; supply-threshold-triggered, so ±1 day). Pre-halving was 1 TAO/block (~7,200/day) — **any pre-Dec-2025 yield figure overstates current rewards ~2×.** ([emissions](https://docs.learnbittensor.org/learn/emissions); [DLNews](https://www.dlnews.com/articles/defi/bittensor-halving-seen-to-boost-tao-price-and-starve-zombie-subnets/); [Grayscale](https://research.grayscale.com/reports/bittensor-on-the-eve-of-the-first-halving))

**Continuous dynamic burn registration:** UID registration cost is now **continuous**, governed by `BurnHalfLife` + `BurnIncreaseMult` (bounded by `MinBurn` ≈ 0.0005 τ / `MaxBurn` ≈ 100 τ defaults). Each registration **bumps the burn up**, then it **decays back down** over time. The OLD interval-difficulty heuristic ("each registration doubles cost / halves over ~4 days"; `adjustment_interval` 360 / `target_regs_per_interval` 1) is **DEPRECATED and inert for neuron registration** — read the live cost via `btcli sudo get --netuid N`. ([subnet hyperparameters](https://docs.learnbittensor.org/subnets/subnet-hyperparameters))

**UID slots & immunity:** `max_allowed_uids` = **256** (≤64 validator / ≤192 miner slots); deregistration evicts the **non-immune UID with the lowest pruning score** (pruning score = recent emissions) once slots are full. **Immunity period default ~4096 blocks** (older docs); live values seen 5,000–7,000 blocks (≈ a few hours at 12 s/block) — **read live per netuid, do not hardcode.** ([deregistration](https://docs.learnbittensor.org/subnets/subnet-deregistration); [subnet hyperparameters](https://docs.learnbittensor.org/subnets/subnet-hyperparameters); [taostats subnet-params](https://docs.taostats.io/docs/subnet-parameters))

**TAO weight = 0.18:** a validator's effective stake-weight in a subnet = `alpha_stake + 0.18 × tao_stake` (root/TAO stake is deliberately discounted vs native alpha; governance-adjustable). Yuma Consensus uses this **alpha-denominated effective stake** when computing the stake-weighted median (κ ≈ 0.5). ([validators](https://docs.learnbittensor.org/validators); [subnetalpha/docs](https://subnetalpha.ai/dtao/))

**YC3 / liquid alpha (newcomer-relevant):** `yuma3_enabled` is a **per-subnet opt-in, default off**; with liquid alpha (`liquid_alpha_enabled`, default off; `alpha_low`/`alpha_high` ≈ 0.7/0.9) it makes the bond EMA variable and **lowers the new-miner bond wall where enabled**. **Commit-reveal** (v3/v4 Drand timelock; `commit_reveal_weights_enabled` default off, opt-in) mitigates weight-copying but adds a recognition-lag for good newcomers. ([consensus-based weights](https://docs.learnbittensor.org/subnets/consensus-based-weights); [commit-reveal](https://docs.learnbittensor.org/concepts/commit-reveal))

> **Pointers:** For the verified btcli/SDK/API command surface see `tooling-reference.md`; for scoring/economics modeling see `incentive-model.md`.

---

This file is the operator-grade cheat sheet for what a Bittensor subnet repo *typically* looks like, what each file *typically* does, and how mining/validation/scoring/weight-setting actually wire together. Use it as a map; verify against the specific repo you're auditing.

## How a Bittensor subnet works (in 90 seconds)

A subnet is an independent network running on top of the Bittensor metagraph. Each subnet has:

- A **netuid** (e.g. 1, 8, 19) — its slot on Bittensor mainnet (or testnet).
- Two neuron types: **miners** (produce work) and **validators** (judge work).
- A **protocol** — the request/response schema, defined as a subclass of `bittensor.Synapse`.
- A **reward function** — validator-side code that scores miner outputs.
- **Weight setting** — validators periodically commit a weight vector over miner UIDs; on-chain consensus aggregates these into the **incentive** distribution that determines miner emissions.
- **Emissions** — TAO emitted to the subnet each block, split between miners (incentive), validators (dividends), and the subnet owner (owner cut).
  > ⚠️ SUPERSEDED 2026: see the dTAO-era update above — participants now receive **alpha tokens, not TAO**; the per-block emission is split 41% miners / 41% validators+stakers / 18% owner, and a subnet's *cross-subnet* share is set by **Taoflow** (EMA of net TAO flow), not by root-validator votes.

The miner's job is to **maximize the weight assigned by validators**. Whatever the reward function in `reward.py` (or its equivalent) scores high is what earns. README claims about "decentralization" or "fairness" do not pay; the reward function pays.

## Standard subnet repo layout

Most subnets descend from the OpenTensor `bittensor-subnet-template` and look like this (paths vary):

```
<repo>/
├── neurons/
│   ├── miner.py              # miner entrypoint; subclasses BaseMinerNeuron
│   └── validator.py          # validator entrypoint; subclasses BaseValidatorNeuron
├── <subnet_name>/            # e.g. "template", "vision", "prompting"
│   ├── __init__.py
│   ├── protocol.py           # bt.Synapse subclasses — the wire format
│   ├── base/
│   │   ├── miner.py          # BaseMinerNeuron — axon serving, blacklist, priority
│   │   ├── validator.py      # BaseValidatorNeuron — query loop, set_weights cadence
│   │   └── neuron.py         # shared init: wallet, subtensor, metagraph
│   ├── validator/
│   │   ├── forward.py        # validator forward() — task gen + query + score
│   │   ├── reward.py         # the reward function (THE FILE THAT MATTERS MOST)
│   │   └── ...
│   ├── miner/
│   │   └── ...               # optional helper logic
│   └── utils/
│       ├── uids.py           # miner-UID selection logic
│       ├── config.py         # CLI flag wiring
│       └── ...
├── scripts/
│   ├── start_miner.sh
│   ├── start_validator.sh
│   └── check_compatibility.sh
├── docs/
├── tests/
├── README.md
├── requirements.txt
├── setup.py / pyproject.toml
├── .env.example or template
├── docker-compose.yml        # if present
└── Dockerfile                # if present
```

Some subnets diverge heavily (Go binaries, Rust workers, multi-language services, queue-based architectures). Treat the structure above as a *prior*, not a rule.

## Where the truth lives (priority reading order)

When auditing, read in this order — earlier files dominate the operator picture:

1. **`reward.py` / `validator/reward.py` / anything called from `validator.forward()` to score** — this is the single most important file in the repo. If you only read one file, read this. Every miner strategy is downstream of what this function rewards.
2. **`protocol.py`** — defines the request/response contract. Tells you what the miner must produce and what fields the validator will inspect.
3. **`neurons/validator.py` + `validator/forward.py`** — the validator's main loop. Tells you where tasks come from (synthetic? scraped? external API?), how miners are selected for queries, what timing/concurrency looks like, and how scores are aggregated.
4. **`neurons/miner.py`** — the template miner's `forward()` and `blacklist()` / `priority()`. Tells you what a default miner does and how it can be replaced.
5. **`base/validator.py`** — `set_weights()` logic, weight normalization, EMA / momentum / running average of scores.
6. **`config.py` / CLI flags** — what's tunable, what's hard-coded.
7. **External-service tells** in imports — `openai`, `anthropic`, `huggingface_hub`, `wandb`, `redis`, `boto3`, scraping libs, paid APIs.
8. **`README.md` / `docs/`** — read LAST. Use it only to confirm/refute what the code already told you.

## Reward function patterns (what to grep for)

Common scoring patterns and what they imply for miners:

- **Cosine similarity** (`F.cosine_similarity`, `np.dot(a,b)/(...)`) — embeddings/text matching. Miners that produce outputs close to a reference vector win. Hidden reference = a moat for whoever made it.
- **Exact / regex match** — deterministic task. Cloning the validator's task generator wins.
- **BLEU / ROUGE / BERTScore** — generation quality. Better LLM wins (subject to budget).
- **L1 / L2 / MSE on logits or embeddings** — model-output matching. Often "match this teacher model" — top miners distill the teacher.
- **Time-decay / latency multiplier** — fast responders win. Infra/locality matters.
- **Binary accept/reject + reputation EMA** — gates plus running average. Consistency matters more than peaks.
- **Cross-validator deviation penalty** — outputs that disagree with the median get penalized. Encourages mimicry; can entrench incumbents.
- **External oracle / paid API call inside the validator** — validator pays for ground truth. Whoever controls the oracle controls the subnet. Major centralization tell.

When you find the reward function, write down (a) what signal it computes, (b) what input it needs (where does ground truth come from?), (c) what range it outputs, (d) what zeros it.

## Weight-setting & emission cadence

- Validators call `subtensor.set_weights(uids, weights)` every `tempo` blocks (typically 360 blocks = ~72 minutes on mainnet, but configurable).
- The on-chain Yuma consensus aggregates validator weights weighted by their **stake**. Low-stake validators have little voice; if a few high-stake validators dominate, *their* reward function tuning is what pays.
  > ⚠️ SUPERSEDED 2026: see the dTAO-era update above — "stake" here is now the **alpha-denominated effective stake** (`alpha_stake + 0.18 × tao_stake`, TAO weight 0.18), not raw TAO. The median is taken at κ ≈ 0.5.
- Look for: how is `weights` computed from `scores`? Softmax? Top-k mask? Linear normalize? Many subnets zero out everything below some percentile — be very aware of those cliffs.
- Look at `set_weights` cadence and EMA decay: a high-decay EMA (`alpha=0.9`) means recent performance dominates; a low-decay EMA (`alpha=0.1`) means historical performance is sticky and newcomers struggle.

## Common red flags (centralization / gameability)

These show up in the code and almost always matter:

- **Hard-coded validator hotkeys** in miner blacklist (`if hotkey not in ALLOWED_VALIDATORS`) — miner only serves a known set; project gates participation.
- **Project-owned API as ground truth** — validator calls `https://api.<project>.ai/score`. Project can change scoring without redeploying validators.
- **Encrypted / opaque payloads** — synapse fields are JWE/ciphertext blobs decrypted only by project-issued keys.
- **License gates** — miner code requires a per-user key issued by the project Discord.
- **Off-chain leaderboard that influences weights** — validators read external rankings instead of computing locally.
- **Stake-weighted validator monopoly** — one or two hotkeys hold >50% validator stake; their weight vector is the only one that matters.
- **Frozen template + dominant top hotkeys for weeks** — strong signal of insider mining or a moat newcomers can't cross.

## Common positive signals

- Reward function is fully local (no external API call) and deterministic.
- Protocol is open, simple, no encryption.
- README links to a public dashboard with per-miner score breakdown.
- Recent issues from non-team contributors getting merged.
- Multiple independent validators with comparable stake.
- Newcomers visibly climbing the leaderboard within weeks of registration.

## Infra reality

What a subnet *typically* needs from a miner:

- **CPU-only inference / API-proxy miners** — $10–50/mo VPS works (e.g. text completion, scraping, oracles).
- **Small-model GPU miners** (≤7B params, fp16) — single consumer GPU (3090/4090) or rented A40 / L4 — ~$0.30–0.80/hr cloud.
- **Large-model GPU miners** (70B+, training, multi-modal) — A100/H100 territory, $1.50–8/hr cloud or owned hardware. Most solo operators cannot compete here.
- **Always-on requirement** — yes for all of them. A subnet validator that misses a few queries deregs miners with low recent-EMA.
- **Public IP / open port** — almost always required. The axon binds an external IP; NAT'd home setups need port forwarding or a tunnel (e.g. ngrok, cloudflared, tailscale funnel) and that is fragile.

## Registration cost

Registration is the **burn cost**: TAO required to obtain a UID on the subnet. It floats based on demand. Mainnet ranges historically: 0.01 TAO to 10+ TAO. Check TaoStats for the live number. Many newcomers fail because they read an old README that quoted a tiny burn.
> ⚠️ SUPERSEDED 2026: see the dTAO-era update above — burn pricing is now **continuous** (`BurnHalfLife` + `BurnIncreaseMult`, bounded by `MinBurn`/`MaxBurn`), NOT interval-difficulty. The legacy "doubles each reg / halves over ~4 days" heuristic is deprecated; read the live cost via `btcli sudo get --netuid N`. Note `btcli subnet burn-cost` returns the **new-subnet creation** cost, not the per-UID registration cost.

## Wallet / hotkey basics

- `coldkey` — held offline, owns stake and signs registrations.
- `hotkey` — held on the mining server, signs blocks and serves the axon. **A hotkey is a UID — losing it loses your registration.**
- Multiple hotkeys can register on the same subnet under one coldkey, but each costs a separate burn.

## What "earning" really means

Three things you need to be alive on chain:

1. **Registered** (hotkey has a UID) — costs burn TAO once.
2. **Responding to queries** (axon serves, returns non-error responses within the time budget) — keeps you eligible.
3. **Scoring > peers on the validator's reward function** — earns incentive.

A miner can be (1)+(2) for days while earning literally zero because (3) fails. Beginners frequently mistake "axon alive, no errors" for "mining successfully". The validator log / leaderboard tells the truth.

## Hardware reality by subnet type (from Cody's BITTENSOR.md)

### GPU-required subnets (NVIDIA GPU mandatory)

| Type | Examples | Min GPU | Notes |
|------|----------|---------|-------|
| LLM Inference | SN1, SN4, SN64 | RTX 3090 (24GB) | Larger models need A100 (80GB) |
| Image Generation | SN5 | RTX 3090 (24GB) | Stable Diffusion, FLUX |
| Fine-tuning | SN37 | RTX 3090+ | Training runs need VRAM |
| ML Compute | SN19 | A10+ | General ML inference |
| Audio/Speech | SN16 | RTX 3060+ | Whisper, TTS |
| Video | SN17 | A100 | Very VRAM intensive |

**GPU VPS pricing reference** (verify current rates before quoting):
- RunPod — A100/H100, ~$1–3/hr for A100
- Vast.ai — marketplace pricing, often cheapest
- Lambda Cloud — A100/H100, ~$1.10/hr for A100
- AWS p3/p4 — expensive, reliable
- Hetzner / OVH — budget EU dedicated GPU

### CPU-friendly subnets (no GPU)

| Type | Examples | Min Specs | Notes |
|------|----------|-----------|-------|
| Data scraping | SN13, SN3 | 4 vCPU, 8GB RAM | Network I/O heavy |
| Search/indexing | SN22 (Desearch) | 4 vCPU, 16GB RAM | Fast storage matters |
| Blockchain data | SN15 | 2 vCPU, 4GB RAM | Light compute |
| VPN / Networking | SN65 (TPN) | 2 vCPU, 2GB RAM | Bandwidth matters |
| Storage | SN21 | 2 vCPU, 8GB RAM + disk | Disk-heavy |
| Oracle / Data feeds | Various | 2 vCPU, 4GB RAM | API-based |

**CPU VPS pricing reference**:
- Hetzner — best EU value (CX31: 4 vCPU/8GB ~$8/mo)
- Contabo — very cheap, decent specs
- DigitalOcean — reliable, $12–24/mo
- Vultr — good global coverage
- AWS Lightsail — cheap entry

### Hybrid

Some subnets accept CPU miners with reduced score; GPU strictly improves. SN22 (search) is the canonical example — CPU works, GPU helps embedding models.

## The 7-factor mineability framework

When weighing a subnet, score it against these seven factors:

1. **Registration cost** (lower = better entry)
   - Cheap: < 0.1 TAO
   - Moderate: 0.1 – 1 TAO
   - Expensive: > 1 TAO
   - Very expensive: > 10 TAO (top subnets)

2. **Miner slot fill (k/n)** from `btcli`
   - Open: k/n < 50%
   - Competitive: 50–80%
   - Saturated: > 90% (high dereg risk if you score low)

3. **Emission rate per miner**
   - High emission + few miners → opportunity
   - Low emission + many miners → trap
   - Rough math: `daily_subnet_emission_to_miners / active_miners`

4. **Hardware cost vs earnings**
   - CPU subnet on $10/mo VPS earning 0.5 TAO/day → great ROI
   - GPU subnet on $3/hr A100 earning 0.1 TAO/day → losing money

5. **Incentive distribution** (run `btcli subnet metagraph --netuid N`)
   > ⚠️ SUPERSEDED 2026: on current btcli (9.21.x) the metagraph viewer verb is **`btcli subnet show --netuid N`** — `metagraph` is not a verb. Verify on the target box (version-dependent). See `tooling-reference.md`.
   - Top 5 take 80%+ → hard to compete as newcomer
   - Spread evenly → easier to climb

6. **Code quality & docs** — clear README, miner setup guide, active commits, issues being merged. Dead repo = avoid.

7. **Community activity** — active validators, miner troubleshooting in Discord, recent project tweets. Silence = risk.

## Mining profitability quick math

```
Daily TAO per miner ≈ subnet_daily_miner_emission × your_incentive_share
Daily USD          = daily_TAO × TAO_price
Daily cost         = server_cost_per_day
Profit             = Daily USD − Daily cost

Example A (winning):
  Subnet emits 100 TAO/day to miners; you hold 1% incentive = 1 TAO/day
  TAO @ $400 → $400/day revenue
  A100 on RunPod = $72/day cost
  Profit = +$328/day

Example B (losing):
  Same subnet, 0.01% incentive = 0.01 TAO/day = $4/day revenue
  A100 cost $72/day
  Profit = −$68/day
```

The difference between Example A and Example B is two orders of magnitude on incentive share. That gap is what the rest of this skill exists to predict.

## btcli reference (operator-grade)

Always prefix with `PATH=$HOME/.local/bin:$PATH` on a VPS install.
> ⚠️ SUPERSEDED 2026: see `tooling-reference.md` for the machine-verified command surface (btcli 9.21.x). Key deltas: the metagraph viewer is **`btcli subnet show --netuid N`** (no `metagraph` verb); `burn-cost` is the **new-subnet creation** cost, not the per-UID reg cost (read that via `btcli sudo get --netuid N`); `--json-output` is available for parsing. Verify verbs on the target box before scripting.

```bash
# All subnets with key metrics (Price = registration burn)
btcli subnet list --network finney

# Single subnet info
btcli subnet info --netuid <N> --network finney

# Full metagraph (every UID with stake / incentive / emission)
btcli subnet metagraph --netuid <N> --network finney

# Wallet balance
btcli wallet balance --wallet.name <name> --network finney

# Register on a subnet (burns TAO)
btcli subnet register \
  --netuid <N> \
  --wallet.name <name> \
  --hotkey.name <hotkey> \
  --network finney
```

Two scripts in `$SKILL_DIR/scripts/` wrap these for analysis:
- `subnet-scanner.py [<netuid>]` — parses `btcli` output to JSON (local)
- `subnet-research.py report <netuid>` — full live intel via Taostats + Desearch + GitHub (remote APIs)

## Common mining failure modes

| Symptom | Likely cause | First fix |
|---------|--------------|-----------|
| "Not registered" | Failed registration or got deregged | Re-register; check immunity expired |
| Zero incentive, axon alive | Responses don't match validator scoring | Re-read reward.py; check task format |
| Deregistered within hours | Scored below dereg threshold | Improve miner or pick less-saturated subnet |
| Registration cost too high | Demand spike | Wait for cost to drop; consider a different subnet |
| Miner crashes on boot | Dependency conflict | Use exact Python version from repo; pin deps |
| Can't connect to subtensor | Network/endpoint issue | Try a specific endpoint instead of default `finney` |

## Staking as a passive alternative

If active mining isn't viable, staking TAO to an existing validator earns a share of their dividends with no hardware. Lower risk, lower reward.

```bash
btcli stake add --wallet.name <name> --hotkey.name <validator_hotkey> --amount <TAO>
```

Worth mentioning in the report when the verdict is `AVOID` for mining but the subnet itself still emits to validators that pay dividends.

## Post-halving constants (lock these in)

The post-halving constants matter for every emission calculation. Hardcoded in `scripts/subnet-research.py`:

```
BLOCK_REWARD_TAO       = 0.5            # post-halving (Dec 12, 2025)
BLOCKS_PER_DAY         = 7200
DAILY_NETWORK_EMISSION = 3,600 TAO/day
```
> ⚠️ SUPERSEDED 2026: see the dTAO-era update above — the values are correct, but the first halving date is more reliably cited as **Dec 14–15, 2025** (supply-threshold-triggered, ±1 day by source). The 0.5 TAO/block (~3,600/day) figure is the **network-wide** TAO mint; a subnet's actual TAO share is set by Taoflow, and participants receive alpha, not TAO.

If a report claims the network emits more than ~3,600 TAO/day, the math is wrong.

## Glossary

- **netuid** — subnet ID number.
- **UID** — a miner or validator's slot inside a subnet.
- **incentive** — share of TAO emission going to a miner UID, computed from validator weights.
- **dividends** — share going to a validator UID.
- **emission** — total TAO per block paid into the subnet.
  > ⚠️ SUPERSEDED 2026: see the dTAO-era update above — what's paid to participants each block is **alpha**, not TAO; the per-block TAO injected into the subnet's pool is `Δτ̄ × Taoflow_share(i)`.
- **tempo** — block interval at which weights are settled and emissions paid.
- **stake** — TAO bonded to a hotkey; validators need stake to have weight influence.
  > ⚠️ SUPERSEDED 2026: see the dTAO-era update above — effective stake-weight is now `alpha_stake + 0.18 × tao_stake` (alpha-denominated), not raw TAO.
- **dereg** — when a UID is recycled because immunity expired and incentive was too low; miner loses the slot.
- **immunity** — newly registered UIDs are protected from dereg for an immunity period (often ~hours).
  > ⚠️ SUPERSEDED 2026: see the dTAO-era update above — default ~4096 blocks per older docs, but 5,000–7,000 seen live; per-subnet and time-varying, so **read it live per netuid** (`btcli subnet hyperparameters --netuid N`).
- **alpha (α)** — a subnet's own token (one per subnet, dTAO). Miners/validators/owner are paid in alpha; realize value by swapping alpha→TAO through the subnet's AMM pool (subject to slippage).
- **Taoflow** — the Nov-2025 cross-subnet emission model: a subnet's TAO share ∝ an EMA of its net TAO staking flow; sustained net outflow → 0 emission.
- **axon** — the miner's serving endpoint (HTTP).
- **dendrite** — the validator's client that queries axons.
- **metagraph** — the live snapshot of all UIDs, stakes, and scores on a subnet.
