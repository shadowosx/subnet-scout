# Verdict rubric

Use this to choose **exactly one** of the four verdicts at Stage 5. Default to the more pessimistic verdict when uncertain — optimism bias is the failure mode this rubric is designed to fight.

---

## AVOID

Issue any of the following triggers `AVOID`:

- **Hard centralization in code.** Validator imports a project-owned scoring endpoint, hard-coded validator allow-list in miners, license-key gating, encrypted protocol with project-controlled keys.
- **Insider self-mining tells.** Top hotkeys cluster under a small set of coldkeys you can trace to the project team or one address; leaderboard frozen at top for weeks with no churn.
- **Deceptive marketing gap.** README claims "fair / open / decentralized" while code reveals validator-gated or off-chain-API-dependent reality (DECEPTIVE row in the gap table).
- **Dead project.** No commits or merged PRs in 60+ days, broken validator template, abandoned Discord/docs.
- **Unwinnable reward function for a solo operator.** Scoring path requires capability a solo operator demonstrably cannot reach (e.g. proprietary 70B+ closed-source weights, exclusive paid dataset, real-time exclusive data feed).
- **Outright scam tells.** Token-style pump narrative, no working code, payments solicited off-protocol.

Operator action: don't register. Don't burn TAO. If already registered, plan exit.

## WATCH

Use `WATCH` when:

- The subnet may be legitimate but is **not yet legible** from outside — e.g. just launched, no leaderboard, no live emissions data.
- The code is healthy but a known breaking change is imminent (upcoming hard fork, validator rewrite, scoring endpoint migration).
- Top concentration is high but recent (e.g. last 2 weeks) — could be either early-mover advantage that normalizes, or insider lock-in that won't.
- The reward function is interesting but its inputs depend on a service that hasn't shipped yet.

Operator action: bookmark, set a calendar reminder (e.g. 3 weeks), re-evaluate. Do not register yet. If the user wants to *learn* the subnet, fine to run the template against testnet only.

## CHEAP TEST

Use `CHEAP TEST` when:

- Registration burn is low enough that the loss is tolerable (rule of thumb: ≤ 5% of the user's stated TAO budget, or < $50 equivalent if no budget stated).
- The earning path is *learnable* — reward function is comprehensible, no hidden infrastructure, code is open.
- Top-tier moat is real but reproducible (e.g. fine-tune a model, build a small dataset) rather than gated (e.g. project-issued API key).
- Monthly infra cost is small ($10–50) and bounded.
- The user wants to learn by doing, not necessarily extract profit immediately.

The operator commits to a **time-boxed** experiment (typical: 2–4 weeks) with explicit kill criteria. The expected outcome is not "profit" — it's "decide cleanly whether to scale or quit".

Operator action: register one hotkey, run a properly-tuned miner, watch the agreed metrics, hit the kill criteria or commit to scaling.

## SERIOUS OPPORTUNITY

Use `SERIOUS OPPORTUNITY` only when **all** of the following are true:

- Reward function is fully on-validator, deterministic, and not dependent on a project-controlled API.
- Multiple independent validators with comparable stake — no single hotkey dominates consensus.
- Top miners visibly include non-team operators (verifiable via leaderboard / chain history).
- The competitive moat is reproducible skill or infra, not gated access.
- Live economics (emissions × incentive share at the rank a strong operator can realistically achieve) clear the user's stated cost floor with margin.
- Code is healthy and actively maintained.
- Subnet is past the "early lottery" phase but not yet ossified (rough heuristic: 1–6 months post-launch, churn still visible in top 20).

A subnet that earns `SERIOUS OPPORTUNITY` should justify serious operator investment — single GPU minimum, possibly multiple hotkeys, sustained tuning effort, weeks-to-months horizon.

This verdict should be **rare**. Most subnets, on honest inspection, are `CHEAP TEST` or `WATCH`. If your draft report wants to land on `SERIOUS OPPORTUNITY`, re-read the gap table and the centralization tells once more before committing.

---

## Tie-breaking when borderline

- AVOID vs WATCH → if you found a HARD or DECEPTIVE marketing gap, choose AVOID.
- WATCH vs CHEAP TEST → if you cannot verify current emissions or burn cost, choose WATCH. Live-data blindness is not "cheap to test", it's "untestable until verified".
- CHEAP TEST vs SERIOUS OPPORTUNITY → if you cannot point to at least one non-team operator in the top 10 with traceable history, demote to CHEAP TEST.
- Two verdicts tied → take the more conservative one. The cost of a false `SERIOUS` is a real money loss; the cost of a false `WATCH` is a 3-week delay.

## Forbidden verdict patterns

- Do not invent a fifth verdict ("mostly avoid", "guarded watch"). The rubric is four buckets on purpose.
- Do not soften AVOID by appending CHEAP TEST conditions. A subnet is either avoidable or testable — not both.
- Do not promote to SERIOUS OPPORTUNITY based on README claims. Promotion requires code + live data + operator-verifiable competition.
