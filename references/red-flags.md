# Red flags — concrete gameability / centralization / insider tells

Treat this list as a checklist. Each red flag is a *concrete, code-or-data-observable* signal. If you can point to one, write it up; if you can't, don't speculate it exists.

The presence of any single red flag does not auto-AVOID. The pattern of multiple red flags does.

---

## Code-level red flags

### 1. Hard-coded validator allow-list in the miner
```python
ALLOWED_VALIDATORS = {"5G...", "5F..."}
if synapse.dendrite.hotkey not in ALLOWED_VALIDATORS:
    return blacklist
```
What it means: the project chooses who can query miners. Independent validators are locked out, so consensus is gated.

### 2. Validator calls a project-owned API for ground truth
```python
score = requests.post("https://api.<project>.ai/score", ...).json()["score"]
```
What it means: scoring is centralized. The project can change scoring without redeploying validators. Possible silent rug.

### 3. Encrypted / opaque protocol payload
```python
class Task(bt.Synapse):
    ciphertext: bytes
    nonce: bytes
```
What it means: miners can only decrypt with a project-issued key. Project gates participation.

### 4. License key gate
```python
if not validate_license(os.environ["PROJECT_LICENSE"]): exit(1)
```
What it means: same as above — participation is project-gated.

### 5. Reward function that rewards mimicry of a single source
```python
reward = cosine_similarity(miner_output, oracle_model(task))
```
If `oracle_model` is a specific closed-source model only the project can call cheaply, the moat is the oracle's cost.

### 6. Cross-validator deviation penalty
```python
score -= abs(my_score - median(other_validator_scores))
```
Encourages mimicry of the dominant validator. Newcomer validators get suppressed; entrenches incumbents.

### 7. Hard-coded "official miner registry"
```python
OFFICIAL_MINERS = [...]
if uid in OFFICIAL_MINERS: reward *= 1.5
```
Explicit favoritism. Rare but it has happened.

### 8. Reward function not in the repo
The validator imports `from <subnet>.scoring import score_response` but `scoring.py` is not in the repo, or it's a stub that calls out to a private package. Major code-vs-marketing gap.

### 9. Latency multiplier with extreme exponent
```python
reward *= exp(-10 * latency_seconds)
```
A sharp latency curve means co-located miners win regardless of quality. Tells you network topology matters more than work product.

### 10. Validator that scores from a HuggingFace leaderboard
Validator fetches `https://huggingface.co/api/datasets/<project>/leaderboard` and reads ranks. Off-chain scoring; project controls the dataset.

---

## On-chain / economic red flags

### 11. Top hotkeys cluster under one coldkey
Pull the top 10 hotkeys from TaoStats, look up each `coldkey`. If 5+ resolve to one or two coldkeys, you're looking at coordinated mining (could be the project, could be one big operator — either way it's concentration).

### 12. Frozen top with no churn
If the top 10 hotkeys have been the same for 30+ days, either the moat is durable (could be legit) or newcomers are being suppressed (often not). Cross-check with code red flags — if 11 + frozen top, very likely insider lock.

### 13. Validator stake monopoly
One or two hotkeys hold >50% validator stake. Their reward-function tuning is what pays. If those hotkeys are project-affiliated, scoring effectively follows project preference.

### 14. Burn cost spikes without emission growth
Burn rising while emission flat = pure demand from speculators or insiders, not from miners who can earn. Bad time to enter.

### 15. Recent dereg cascade
Many top UIDs deregistered in the last week. Either a scoring change wiped people, or a coordinated rotation. Either way it signals instability.

---

## Documentation / community red flags

### 16. README claims decentralization the code contradicts
The classic DECEPTIVE gap. README says "open and fair"; code shows project API in the scoring path. Loud.

### 17. "Contact us for whitelisting"
README or Discord requires whitelisting to participate. Not a subnet, a gated marketplace.

### 18. No public scoring documentation
"How miners are scored" is either missing from docs or vague. Often correlates with the project not wanting the scoring scrutinized.

### 19. Recent breaking changes with no migration path
Multiple recent commits like "rewrite reward fn", "new protocol v2", "deprecate v1" without coordinated communication. Operator instability.

### 20. Project team is anonymous AND code is closed
Anonymous + open code is normal. Anonymous + closed code is a different risk class entirely.

---

## Operator/infra red flags

### 21. Mandatory project Discord for any operational step
"Get your validator key from Discord", "submit your dataset link in the #miners channel". This is gating disguised as community.

### 22. Subnet requires a non-Bittensor payment
Pay $X/mo to access dataset, register a license, etc. Not necessarily disqualifying but operationally adds project leverage over miners.

### 23. Required external dependency with no fallback
The miner only works while `https://service.<project>.ai` is up. If the service goes down (or rate-limits free users), the miner is dead.

---

## How to use this list in the report

In Stage 2 (gameability angle) and Stage 4 (gap table), explicitly enumerate which of these flags you found and which you specifically looked for and *did not* find. The "did not find" list is just as important — it builds reader trust.

Example phrasing in the report:

> **Centralization tells checked:**
> - Project-owned scoring API: not found (reward.py:L33-L78 is fully local)
> - Validator allow-list in miner: not found (base/miner.py uses default stake-based blacklist)
> - Encrypted protocol: not found
> - Top hotkey clustering: **found** — top 4 hotkeys resolve to coldkey `5F...abc` per TaoStats
> - Validator stake monopoly: **found** — one validator holds 61% stake
> - Reward function imported from external package: not found

That format is what an operator-grade report looks like.
