# Bittensor Tooling Reference (subnet-scout)

> **Date authored:** 2026-05-30 (dTAO era).
>
> ⚠️ **RE-VERIFY BEFORE RELYING ON THIS.** Tool versions, command surfaces, and
> API auth formats drift fast in Bittensor. This file is a snapshot. Before you
> build against any concrete fact below, re-run the live probe it cites
> (`--help`, `--version`, `docs.taostats.io/llms.txt`, etc.). The truth-first
> rule: **read live, do not hardcode.**

## Verification tags

| Tag | Meaning |
|-----|---------|
| `[VERIFIED-LOCAL]` | Confirmed on THIS machine via shell this session |
| `[VERIFIED-WEB]` | Confirmed from a live URL this session |
| `[UNVERIFIED]` | From docs / prior knowledge — confirm with `--help` or OpenAPI |
| `[UNKNOWN]` | Could not be determined |

## Version reality (CONFIRMED THIS MACHINE)

| Component | This machine | PyPI latest (2026-05-28) | How verified |
|-----------|--------------|---------------------------|--------------|
| **btcli (bittensor-cli)** | **9.21.1** `[VERIFIED-LOCAL]` | 9.22.0 `[VERIFIED-WEB]` | `btcli --version`, `uv tool list` |
| **bittensor SDK** | **NOT importable anywhere** (only uv-cached wheels 10.3.1/10.3.2 on disk) `[VERIFIED-LOCAL]` | 10.4.0 `[VERIFIED-WEB]` | `import bittensor` → `ModuleNotFoundError` |
| system `python3` (3.14.5) | no `bittensor` importable `[VERIFIED-LOCAL]` | — | `ModuleNotFoundError` |
| btcli tool venv python | ships `bittensor_cli` only; **no SDK** `[VERIFIED-LOCAL]` | — | `import bittensor` fails in that venv too |

Canonical docs (both redirect): btcli `https://docs.bittensor.com/btcli` → `https://docs.learnbittensor.org/btcli` `[VERIFIED-WEB]`; SDK API `https://docs.learnbittensor.org/python-api/html/autoapi/index.html` `[VERIFIED-WEB]`.

---

## 1. btcli — the real command surface (v9.21.1)

Modern btcli is **noun-verb**: you MUST enter the group (or alias) first. The
pre-"Revolution" flat verbs (`btcli overview`, `btcli register`) are gone —
migrate any group-less commands from old scripts. `[VERIFIED-WEB]`

Config lives at `~/.bittensor/config.yml` (`network`, `wallet_name`,
`wallet_hotkey`, `wallet_path`, `safe_staking`, `rate_tolerance`, …); CLI flags
override per-invocation. `[VERIFIED-WEB]`

### 1.1 Wallet `[VERIFIED-LOCAL]`

```bash
btcli wallet create                # coldkey + hotkey(s)
btcli wallet new-coldkey           # coldkey only (holds TAO; high-value)
btcli wallet new-hotkey            # hotkey only
btcli wallet list                  # all wallets + hotkeys at configured path
btcli wallet overview              # registered accounts across subnets (stake/emission)
btcli wallet balance               # free + staked coldkey balances
btcli wallet transfer              # send TAO wallet→wallet
btcli wallet swap-hotkey / swap-coldkey / regen-coldkey / regen-hotkey
btcli wallet sign / verify         # prove key ownership
```

> **Naming note:** the verbs are hyphenated (`new-coldkey`, `new-hotkey`), not
> underscored. Confirm spelling against `btcli wallet --help` on your box —
> older docs and some scripts use `new_coldkey`/`new_hotkey`. `[VERIFIED-LOCAL]`

### 1.2 Subnet `[VERIFIED-LOCAL]`

```bash
btcli subnet list                          # all subnets + details (alias: btcli s list)
btcli subnet list --json-out               # JSON output  [VERIFIED-WEB]
btcli subnet show --netuid 102             # *** THE METAGRAPH VIEWER ***
btcli subnet hyperparameters --netuid 102  # per-subnet hyperparameters
btcli subnet price --netuid 102            # historical price, past 24h
btcli subnet register --netuid 102 \       # recycle/burn registration (THE dTAO path)
    --wallet.name my_cold --wallet.hotkey my_hot
btcli subnet burn-cost                      # TAO to CREATE a new subnet (NOT per-UID reg cost)
btcli subnet create / start
```

> **CRITICAL naming facts (differ from older docs):** `[VERIFIED-LOCAL]`
> - The metagraph viewer is **`btcli subnet show --netuid N`** (help text:
>   "Inspect the metagraph for a subnet"). There is **NO `btcli subnet
>   metagraph` verb** in 9.21.1 — `btcli s metagraph` from old docs is stale.
> - **`burn-cost` is the NEW-SUBNET creation cost**, NOT the per-UID
>   registration cost. The per-UID recycle/registration cost is read from the
>   recycle amount / hyperparameters (`btcli sudo get`) / the metagraph
>   (`btcli subnet show`) — never from `burn-cost`. Do not conflate them.
> - **No `pow-register` subnet verb** in 9.21.1 — `btcli subnet register` is the
>   only neuron-registration path and it recycles (burns) TAO. PoW survives only
>   as `btcli wallet faucet` (testnet). SDK equivalent is still
>   `subtensor.burned_register` (§3.3).

**Safe-mode price guard (registration):** `btcli subnet register` has a
price-tolerance / confirmation guard **on by default** — it prompts before
spending if the recycle cost moved. For automation, the bypass flags are
`--unsafe` and `--no_prompt` (confirm exact spelling via `btcli subnet register
--help`; some builds use `--no-prompt`). `[UNVERIFIED exact flag spelling]`
**Wrap this guard with your own budget/USD/payback cap — do not reinvent it.**

### 1.3 Sudo / hyperparameters `[VERIFIED-LOCAL: group; UNVERIFIED: exact verb]`

```bash
btcli sudo get --netuid 102        # read hyperparameters (also: btcli subnet hyperparameters --netuid 102)
btcli sudo set --netuid 102 ...    # subnet-owner only
```

Hyperparameters to **read live, never hardcode** (owners change them): `tempo`,
`immunity_period` (commonly-cited default 4096 blocks ≈ 13.7h but
subnet-configurable — read per netuid), `yuma3_enabled` (YC3, default False,
per-subnet opt-in), `liquid_alpha`, `min_burn` / `max_burn`,
`commit_reveal_weights_enabled`, `bonds_penalty`, `alpha_sigmoid_steepness`,
`bonds_moving_avg`. `[UNVERIFIED defaults — treat all as "read via sudo get"]`

> Verify whether `sudo get` vs `subnet hyperparameters` is the right verb on
> your build; both surface hyperparameters in 9.21.x. For SN102 specifically,
> check `commit_reveal_weights_enabled` before assuming a plain `set_weights`
> validator path. `[UNKNOWN for SN102]`

### 1.4 Stake (dTAO alpha) `[VERIFIED-LOCAL]`

```bash
btcli stake add    --netuid 102 --amount 1.0 --wallet.name my_cold --wallet.hotkey my_hot
btcli stake remove --netuid 102 --amount 1.0 ...
btcli stake list   --wallet.name my_cold          # stake across ALL subnets
btcli stake move / transfer / swap                # keep coldkey ownership
```

dTAO: stake is per-subnet **alpha**, priced by that subnet's TAO/alpha pool.
`--netuid` is **required** on stake / register / show ops. `[VERIFIED-LOCAL]`

### 1.5 JSON output

`--json-out` is confirmed for `btcli subnet list` `[VERIFIED-WEB]`. The exact
flag name varies by command/version (`--json-out` vs `--json-output`) — **probe
it per command** (`btcli <cmd> --help | grep -i json`) before parsing. `[UNVERIFIED]`

### 1.6 Axon (miner) `[VERIFIED-LOCAL: group exists]`

`btcli axon` is a real top-level group ("Axon serving commands"). Inspect
`btcli axon --help` for serve verbs for your miner deployment.

---

## 2. Portable btcli resolution (NEVER hardcode an absolute path)

This machine installs btcli as a **uv tool**: `~/.local/bin/btcli` is a symlink
into `~/.local/share/uv/tools/bittensor-cli/`. `shutil.which("btcli")` resolves
it directly. uv content-addressed cache paths (`~/.cache/uv/archive-<hash>/…`)
**change on every reinstall — never hardcode them.** `[VERIFIED-LOCAL]`

> A known prior bug in this skill hardcoded `/home/ubuntu/.local/bin/btcli`,
> which is dead on macOS. Always resolve dynamically.

```python
import shutil, subprocess, sys

def resolve_btcli() -> list[str]:
    """argv prefix that runs btcli, portably.
    Order: PATH shim -> $BTCLI_PATH -> ~/.local/bin -> uv tool run -> python -m."""
    import os
    exe = shutil.which("btcli")                       # works here (~/.local/bin/btcli)
    if exe:
        return [exe]
    env = os.environ.get("BTCLI_PATH")
    if env and os.path.exists(env):
        return [env]
    home = os.path.expanduser("~/.local/bin/btcli")
    if os.path.exists(home):
        return [home]
    uv = shutil.which("uv")                            # /opt/homebrew/bin/uv here
    if uv:
        return [uv, "tool", "run", "bittensor-cli", "--"]   # or [uv, "run", "btcli"]
    return [sys.executable, "-m", "bittensor_cli"]     # [UNVERIFIED: confirm __main__ entrypoint]

argv = resolve_btcli() + ["subnet", "show", "--netuid", "102"]
out = subprocess.run(argv, check=True, capture_output=True, text=True).stdout
```

Resolution order to honor: `shutil.which("btcli")` → `$BTCLI_PATH` →
`~/.local/bin/btcli` → `uv tool run btcli` → `python -m bittensor_cli`.
Cleanest cross-machine setup: `uv tool install bittensor-cli`. `[VERIFIED-LOCAL]`

---

## 3. bittensor Python SDK (v10.x)

> **KEY REALITY — the SDK is NOT importable in the default environment here.**
> System `python3` lacks it; btcli's tool venv ships only `bittensor_cli` (no
> `import bittensor`). The only SDK on disk is uv-cached wheels (10.3.1/10.3.2),
> not installed into any PATH-reachable env. `[VERIFIED-LOCAL]`
>
> **Therefore a tool must EITHER:**
> 1. **Create its own SDK env:** `uv venv .venv && uv pip install --python
>    .venv/bin/python bittensor` (uv reuses the cached 10.3.2 wheel → fast), then
>    resolve *its own* interpreter (not btcli's) for `import bittensor`; **OR**
> 2. **Avoid the SDK entirely** and parse `btcli ... --json-out` via
>    `resolve_btcli()` (§2). For on-chain reads this needs no SDK env. `[VERIFIED-LOCAL]`

> Everything below is `[UNVERIFIED — verify against the installed SDK version]`.
> v10 dropped lowercase factory aliases in favor of **PascalCase imports**
> (`from bittensor import Subtensor, AsyncSubtensor, …`) per its MIGRATION_GUIDE
> — confirm against `bittensor.__version__` before relying on either form.

### 3.1 Connect

```python
import bittensor as bt
sub = bt.Subtensor(network="finney")        # PascalCase (v10);  bt.subtensor(...) on older
async_sub = bt.AsyncSubtensor(network="finney")
```

`Subtensor` = thin layer over Substrate: query chain data, manage stake/liquidity,
register neurons, submit weights. `[VERIFIED-WEB doc text]`

### 3.2 Metagraph

```python
mg = sub.metagraph(netuid=102, lite=False)  # lite=False → full tensors
mg.sync(subtensor=sub)
```

Fields (confirm presence/dtype via `dir(mg)` on YOUR build):

| Field | Meaning |
|-------|---------|
| `mg.uids` / `mg.hotkeys` / `mg.coldkeys` | UIDs and ss58 keys per UID |
| `mg.axons` | axon endpoints (ip/port) per UID |
| `mg.S` | stake per UID (dTAO: alpha — confirm units) |
| `mg.I` | incentive |
| `mg.E` | emission |
| `mg.R` | rank |
| `mg.C` / `mg.consensus` | consensus |
| `mg.T` / `mg.trust` | trust |
| `mg.D` / `mg.dividends` | dividends |
| `mg.validator_permit` / `mg.active` / `mg.last_update` | permit / activity / last-weight block |
| `mg.n` / `mg.block` | neuron count / synced block |

`[UNVERIFIED — confirm exact attr presence via dir(mg)]`

### 3.3 Registration / serve / weights

```python
ok = sub.burned_register(wallet=w, netuid=102,             # recycles TAO (dTAO path)
                         wait_for_inclusion=True, wait_for_finalization=True)
# burned_register honors a recycle-cost tolerance (commonly ~0.5%) — verify on your build.

sub.serve_axon(netuid=102, axon=axon)                       # [UNVERIFIED signature]

sub.set_weights(wallet=w, netuid=102, uids=uids, weights=weights,
                version_key=__version_as_int__)             # commit_reveal subnets use
                                                            # commit_weights / reveal_weights instead
```

**dTAO economics helpers:** the SDK exposes alpha↔TAO conversion with slippage
(stake/unstake price impact against the subnet pool). Confirm helper names on
your installed version. `[UNVERIFIED]`

**v10 multi-mechanism:** newer methods accept a `mechid` parameter (per-subnet
mechanism id). Flag and verify against the installed-version docs before use.
`[UNVERIFIED]`

---

## 4. Taostats API

- **Base URL:** `https://api.taostats.io` `[UNVERIFIED — confirm host in OpenAPI]`
- **Docs / agent index:** `https://docs.taostats.io/` ; `https://docs.taostats.io/llms.txt` (Markdown + OpenAPI) `[VERIFIED-WEB]`
- **Key:** required; create org + project at `taostats.io/pro`. `[VERIFIED-WEB]`
- **Auth header:** uses an **`Authorization`** header. The literal form — claimed
  elsewhere as `tao-xxxxx:yyyyy` — is **UNCONFIRMED**. Verify raw-vs-`Bearer` and
  the exact `tao-:` shape against `docs.taostats.io/llms.txt` or one endpoint's
  "try it" example **before hardcoding.** `[UNVERIFIED]`
- **Rate limit:** free tier ≈ **5 calls/min** `[VERIFIED-WEB community-cited]`;
  exact tier caps are on the pricing page. `[UNKNOWN exact numbers]`
- **TypeScript SDK** available. `[VERIFIED-WEB]`

Key endpoints (resolve literal versioned paths from `llms.txt` — they look like
`/api/<area>/latest/v1`):

| Need | Path / reference |
|------|------------------|
| dTAO pool / alpha price | `/api/dtao/pool/latest/v1` `[VERIFIED-WEB]` |
| Metagraph / neurons | "Get Metagraph" endpoint `[VERIFIED-WEB name]` |
| All subnets | "Get Subnets" |
| TAO price | "Get tao Price" |
| Subnet emission | "Get tao emission" |
| Validator yield / account / staking | delegation / account endpoints |

```python
import requests
H = {"accept": "application/json", "Authorization": "<TAOSTATS_API_KEY>"}  # [UNVERIFIED: raw vs Bearer]
r = requests.get("https://api.taostats.io/api/dtao/pool/latest/v1",
                 params={"netuid": 102}, headers=H, timeout=30)
r.raise_for_status(); data = r.json()
```

> **Action before building:** fetch `https://docs.taostats.io/llms.txt` once;
> grep for `metagraph`, `pool`, `price`, `emission`; pin literal paths and the
> exact auth header form.

---

## 5. Desearch API `[VERIFIED-WEB]`

- **Base URL:** `https://api.desearch.ai`
- **Auth header:** **`Authorization: dt_<key>`** — RAW key, **not** `Bearer`.
  Keys are prefixed `dt_`.
- **Get a key:** Desearch Console `https://console.desearch.ai/` → API Keys.
- **Content type:** `application/json`.
- **Optional SDK:** `desearch-py` (note: an **undeclared dependency** in prior
  skill code — if you `import desearch_py`, add it to `requirements.txt`).

| Need | Method | Path |
|------|--------|------|
| AI search (multi-source synthesis) | POST | `/desearch/ai/search` |
| X / Twitter search | POST | `/twitter` |

`/desearch/ai/search` body: `prompt` (str), `tools` (array — `"web"`,
`"twitter"`, `"reddit"`, `"arxiv"`, `"hackernews"`, `"wikipedia"`, `"youtube"`),
`model` (`"NOVA"` / `"ORBIT"` / `"HORIZON"`), `date_filter`, `streaming`.

```python
import requests
H = {"Authorization": "dt_<DESEARCH_API_KEY>", "Content-Type": "application/json"}
r = requests.post("https://api.desearch.ai/desearch/ai/search",
                  json={"prompt": "Bittensor subnet 102",
                        "tools": ["twitter", "web"], "model": "NOVA"},
                  headers=H, timeout=60)
r.raise_for_status(); data = r.json()
```

---

## 6. Which source for which data

| Data you need | Best source | Why |
|---------------|-------------|-----|
| Metagraph (uids/stake/incentive/emission/permits) | **Chain via SDK** (`mg = sub.metagraph(netuid)`) or `btcli subnet show --netuid N` | **Ground truth**, always current, no API key |
| Registration recycle cost / hyperparameters | **Chain** (`btcli sudo get` / `subnet hyperparameters`) | Read live; owners change them |
| Weights / consensus / dividends | **Chain via SDK** | Ground truth |
| TAO price / dTAO alpha pool price / historical series | **Taostats** (`/api/dtao/pool/latest/v1`, price endpoints) | dTAO pool pricing + history for ROI math |
| Emission time series, validator yield rankings | **Taostats** | Pre-aggregated analytics |
| Social / narrative signal (X, web, Reddit) | **Desearch** (`/desearch/ai/search`, `/twitter`) | The only social source here |
| New-subnet creation cost | `btcli subnet burn-cost` | NOT per-UID registration cost |

**Rule of thumb:** chain/SDK = ground truth (no key, authoritative); Taostats =
price / dTAO pool / historical (ROI math); Desearch = social only. When chain
and a third-party API disagree, **the chain wins.**

---

## 7. Open items to re-verify before relying on this

1. SDK metagraph attr presence on the target build — `dir(mg)`. `[UNVERIFIED]`
2. SN102 `commit_reveal_weights_enabled` — `btcli subnet hyperparameters --netuid 102`. `[UNKNOWN]`
3. Taostats literal versioned paths + auth header form (raw vs Bearer / `tao-:` shape) + numeric rate caps — `docs.taostats.io/llms.txt`. `[UNVERIFIED]`
4. Exact `--json-out` vs `--json-output` flag per command — `btcli <cmd> --help`. `[UNVERIFIED]`
5. `python -m bittensor_cli` module entrypoint validity (last-resort fallback). `[UNVERIFIED]`
6. v10 PascalCase-only imports + `mechid` param + alpha↔TAO slippage helper names — installed-version MIGRATION_GUIDE. `[UNVERIFIED]`
7. `btcli subnet register` automation bypass flag spelling (`--no_prompt` vs `--no-prompt`, `--unsafe`) — `btcli subnet register --help`. `[UNVERIFIED]`
