#!/usr/bin/env bash
# map-repo.sh — heuristic first-pass enumeration of a Bittensor subnet repo.
# Output is structured under headings so the calling agent can parse it.
# Heuristic only — verify every hit by reading the file.

set -u

ROOT="${1:-.}"
if [[ ! -d "$ROOT" ]]; then
  echo "ERR: not a directory: $ROOT" >&2
  exit 2
fi

cd "$ROOT" || exit 2

# Prefer ripgrep if available
if command -v rg >/dev/null 2>&1; then
  GREP="rg --no-heading --line-number --color=never"
  LIST="rg --files --color=never"
else
  GREP="grep -RnH"
  LIST="find . -type f"
fi

section() { printf "\n=== %s ===\n" "$1"; }

section "Repo root"
echo "$(pwd)"

section "Top-level layout"
ls -1 | head -60

section "Likely subnet identification (pyproject / setup.py / package name)"
for f in pyproject.toml setup.py setup.cfg package.json README.md; do
  if [[ -f "$f" ]]; then
    echo "-- $f (first 40 lines) --"
    head -n 40 "$f"
  fi
done

section "Bittensor imports (where the actual subnet code lives)"
$GREP -l "import bittensor\|from bittensor" 2>/dev/null | head -50

section "Miner entrypoints"
$LIST 2>/dev/null | grep -Ei "(neurons/)?miner\.py$|cmd/miner|bin/miner" | head -20

section "Validator entrypoints"
$LIST 2>/dev/null | grep -Ei "(neurons/)?validator\.py$|cmd/validator|bin/validator" | head -20

section "Protocol / Synapse definitions"
$GREP "class .*\(bt\.Synapse\)\|class .*\(bittensor\.Synapse\)\|bt\.Synapse\)" 2>/dev/null | head -30

section "Reward / scoring functions"
$LIST 2>/dev/null | grep -Ei "reward|score|scoring" | grep -Ei "\.py$" | head -30
$GREP "def reward\|def get_rewards\|def score\|def compute_score\|def calculate_reward" 2>/dev/null | head -40

section "Weight setting"
$GREP "set_weights\|process_weights_for_netuid\|update_scores" 2>/dev/null | head -30

section "Forward functions (miner & validator)"
$GREP "async def forward\|def forward(" 2>/dev/null | head -30

section "Config / constants"
$LIST 2>/dev/null | grep -Ei "config\.py$|constants\.py$|defaults\.(yaml|yml)$|\.env(\.example|\.template)?$" | head -30

section "External-service tells (paid APIs, ML services, scraping, queues)"
$GREP -E "openai|anthropic|huggingface_hub|wandb|boto3|redis|playwright|selenium|tweepy|discord\.py|requests\.(get|post)" 2>/dev/null | head -50 | sed 's/\(.\{200\}\).*/\1.../'

section "External URLs hard-coded in code"
$GREP -Eo "https?://[A-Za-z0-9._/?=#%&+-]+" 2>/dev/null | sort -u | head -50

section "Docker / compose / orchestration"
$LIST 2>/dev/null | grep -Ei "Dockerfile|docker-compose\.ya?ml|pm2\.config\.|systemd|Makefile" | head -20

section "Scripts directory"
[[ -d scripts ]] && ls -1 scripts | head -40

section "Docs / architecture"
$LIST 2>/dev/null | grep -Ei "\.md$|^docs/" | head -40

section "Recent git activity (last 50 commits, last 60 days)"
if [[ -d .git ]]; then
  git log --oneline -n 50 2>/dev/null | head -50
  echo
  echo "-- committers in last 60 days --"
  git log --since="60 days ago" --format="%an" 2>/dev/null | sort | uniq -c | sort -rn | head -20
else
  echo "(not a git repo)"
fi

section "Hotkey allow-list / blacklist tells"
$GREP -E "ALLOWED_VALIDATORS|WHITELIST|BLACKLIST|allowed_hotkeys|allowed_coldkeys" 2>/dev/null | head -20

section "Encrypted / signed payload tells"
$GREP -E "ciphertext|encrypt|decrypt|nacl|nonce: bytes|signature: bytes" 2>/dev/null | head -20

section "Tests"
$LIST 2>/dev/null | grep -E "test_.*\.py$|/tests?/" | head -30

echo
echo "=== END MAP ==="
