# subnet-scout

A Claude Code skill for Bittensor subnet operators. Four modes:

| Mode | Question it answers |
| --- | --- |
| SCOUT | Is this subnet worth mining? Produces a due-diligence verdict. |
| UNDERSTAND | How does this subnet pay miners? Explains the incentive model. |
| SETUP | Bring up a miner, safety-gated behind a SCOUT verdict. |
| OPERATE | Why is my miner earning zero? Live diagnostics. |

It reads the subnet repository end-to-end and combines that with live chain,
market and web data.

## Install

Clone into your Claude Code skills folder:

```bash
git clone https://github.com/shadowosx/subnet-scout.git ~/.claude/skills/subnet-scout
```

Or, to make it available in a single project only:

```bash
git clone https://github.com/shadowosx/subnet-scout.git .claude/skills/subnet-scout
```

Restart Claude Code (or open a new session). The skill shows up as `/subnet-scout`.

## Optional API keys

Live data is richer with a Taostats key and a Desearch key. Copy the example
file and fill in your own values:

```bash
cp ~/.claude/skills/subnet-scout/.env.example ~/.claude/skills/subnet-scout/.env
```

The scripts also read the same variables from your shell environment or
`~/.openclaw/.env`. Keys are never printed or stored by the skill.

## Helper scripts

The scripts in `scripts/` need a few Python packages:

```bash
pip install -r ~/.claude/skills/subnet-scout/scripts/requirements.txt
```

## Usage

Inside Claude Code:

```
/subnet-scout is subnet 64 worth mining?
/subnet-scout how do miners earn on https://github.com/some-org/some-subnet
/subnet-scout why is my miner on SN18 earning zero
```

## Layout

- `SKILL.md` is the entry point Claude loads.
- `references/` holds the rubrics, protocols and Bittensor background the skill reads on demand.
- `references/monitoring-templates/` holds watcher and restart-guard templates for the OPERATE mode.
- `scripts/` holds the repo mapper and the live-data research and scanner helpers.
