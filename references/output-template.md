# Final report — exact section order

Use these sections in this exact order. Do not rename them. Do not add or remove sections — if a section can't be filled, write "Unknown — could not verify" and explain in **Known unknowns**.

---

## Repos, files, and sources inspected

Bulleted list. Every entry is one line.
- File: `path/to/file.py` — one-line role.
- Doc: `README.md` / `docs/architecture.md` — what you got from it.
- URL: `https://taostats.io/subnets/<N>` — what data you pulled.
- Command: `git log -n 20 --oneline` — what it showed.

This section is the audit trail. If a reader doubts a later claim, they should be able to retrace it from here.

## Commands and live checks run

Bulleted list of exact commands / WebFetch URLs / scripts run. If a check failed (rate limit, 404, timeout), say so on the same line.

## What this subnet really does

Plain English, 1–3 paragraphs. What service the subnet performs. What miners are responsible for. What validators are responsible for. What gets rewarded *in practice* — not what the README says. End with one sentence: "In practice, this subnet pays miners to <X>."

## How miners actually earn

The exact earning path, step by step:

1. Miner receives `<synapse type>` at `<path:line>`.
2. Miner must produce `<output shape>` within `<time budget>`.
3. Validator scores using `<reward function at path:line>` which computes `<signal>`.
4. Acceptance condition: `<what makes score > 0>`.
5. Penalty / zero condition: `<what zeros the score>`.
6. Weight aggregation: `<how scores → weights → incentive>`.

Then a short paragraph: what success **actually** depends on (pick from: model quality, latency, validator mimicry, hidden data, infra reliability, queue position, API quality, distribution, capital, off-chain coordination). Be specific.

## What validators actually check

Practical, code-based. What does the validator sample? What does it compare? Is the scoring deterministic, stochastic, or fuzzy? Can different validators disagree and how much? Can the scoring be gamed by prompt cloning, deterministic matching, or narrow strategies? Cite `path:line`.

## Files that matter most

5–10 files, each with a one-paragraph "why this file matters for a miner". Order by importance: reward function first, then protocol, then validator forward, then miner forward, then config/constants.

## External dependencies and hidden infrastructure

Everything off-chain, paid, rate-limited, or operationally critical:
- External APIs (with cost / rate-limit / region notes)
- Required credentials (HF token, OpenAI key, etc.)
- Project-owned services (dashboards, oracles, scoring APIs)
- Datasets / model weights (public or gated)
- State / persistence (sqlite, redis, S3)
- Anything the project can switch off remotely

For each: who controls it, what happens if it breaks, what the cost is.

## Can this run on a normal VPS?

One of: **Yes** / **Partially** / **No**. Then 1 paragraph explanation. State the minimum acceptable spec and the practical-competitive spec separately. If a GPU is required, name a sample box and rough $/month.

## What it actually takes to start mining

Bullet list:
- Wallet: `<coldkey + hotkey via btcli>`
- Registration: `<burn cost in TAO from live TaoStats>` on netuid `<N>`
- Machine: `<spec>`
- Ports: `<port range>` reachable on public IP
- Accounts / API keys: `<list>`
- Software install: `<one-line summary>`
- Time to first heartbeat: `<rough estimate>`

## Cost breakdown

Two parts:

**One-time:**
- Registration burn: `<X TAO ≈ $Y at current rate>`
- Hardware (if bought): `$<…>`
- Initial credits: `$<…>`

**Recurring (monthly):**
- VPS / GPU: `$<…>`
- Inference API: `$<…>`
- Other: `$<…>`
- **Total: $<…>/mo**

Hidden costs (call them out): debugging time, monitoring, recovery from dereg, opportunity cost of TAO held vs sold.

## What makes a weak miner

1 short paragraph. What the default template + small model + cheap box looks like. Expected outcome (incentive range, dereg risk).

## What makes an average miner

1 short paragraph. Sensible tuning, decent model, reliable infra. Expected outcome.

## What makes a strong miner

1 short paragraph. Specific improvements aligned to the reward function. Expected outcome.

## What top miners are probably doing differently

This is the section that requires the most evidence and the most candor. 2–3 paragraphs. Reason from the reward function and leaderboard concentration: what's the moat? Be specific:

- "Top miners likely fine-tuned a 7B model on `<specific dataset>` because reward.py:L88 computes BLEU against `<reference>`."
- "Top hotkeys are clustered under one coldkey (see TaoStats) — likely project self-mining."
- "Top miners run on the same cloud region as the largest validator — latency multiplier at validator/forward.py:L41."

If you can't verify a moat, say so. Do not invent "they probably have a secret dataset" without evidence.

## Earning reality check

Direct answer to: **can a solo operator on a small budget realistically earn here?** Pick one:

- **Yes — earning is reachable** (with conditions)
- **Partially — survival is reachable, profit is not** (with conditions)
- **No — earning is locked to insiders or large operators** (with reasons)

3–6 lines of explanation citing earlier sections.

## Known unknowns

Bulleted list. Everything you tried to verify and couldn't:
- "TaoStats was rate-limited — could not confirm current burn cost."
- "Reward function uses a remote `score_endpoint` whose source is not in the repo — could not inspect."
- "No public leaderboard — concentration claims unverified."

This section is required. A short "Known unknowns" usually means you didn't push hard enough.

## Is this worth it for me?

Pick exactly one verdict:

- **AVOID**
- **WATCH**
- **CHEAP TEST**
- **SERIOUS OPPORTUNITY**

Then 4–8 lines defending the verdict with specific evidence from earlier sections.

## Structured plan to go from zero to earning

A numbered, end-to-end plan (10–15 steps). See SKILL.md Stage 6 for the required substance: preparation, infra, registration, first miner, first validation of correctness, first earning attempt, iteration loop, competitiveness path, monitoring, scale signals, kill criteria.

The plan must be specific to *this* subnet. Generic Bittensor steps are filler.

## Kill criteria

Bulleted list. The exact signals that mean "stop". Examples:
- "Incentive remains ≤ `0.0005` for 7 consecutive days after a serious tuning attempt."
- "Burn cost rises above `<X TAO>` while emission rate falls below `<Y>`."
- "Project pushes a breaking change to the scoring endpoint requiring a Discord-issued key."

Each kill criterion is a *specific, observable* trigger. Vague signals ("if it stops feeling worth it") are not kill criteria.

## Confidence (/5)

A number from 1 to 5, with one paragraph explaining. Anchor:
- **5/5** — full live data, code fully understood, multiple cross-checks agree
- **4/5** — code fully understood, live data partial, no contradictions
- **3/5** — code mostly understood, live data weak, some gaps
- **2/5** — code partially understood, live data missing, important assumptions unverified
- **1/5** — speculative; insufficient data for an operator decision

Be honest. Most first-pass reports land at 3/5. Inflating confidence is a serious failure mode.
