# Monitoring templates (instantiated by SETUP mode)

These are **parameterized starting points**, not finished tools. The SETUP mode (Stage 10) and OPERATE mode (Stage 11) instantiate them by replacing `{{PLACEHOLDER}}` tokens, then the operator reviews them before wiring into pm2/cron. They are deliberately **subnet-agnostic** — nothing here is specific to any one subnet.

> Truth-first: every watcher fails **loudly** (non-zero exit, stderr message) rather than silently. A monitor that lies by omission is worse than no monitor. After instantiation, run each once by hand and confirm the numbers match `btcli subnet show` / taostats before trusting alerts.

## Files

| Template | What it watches | Why it exists |
|----------|-----------------|---------------|
| `rank_earnings_watcher.py.template` | On-chain incentive / emission / rank / trust for your UID, every poll cycle | The **only** ground truth for "am I earning." Alerts on zero-emission streaks and near-deregistration. |
| `liveness_watcher.py.template` | Process up **and** the real work signal progressing | Catches the "alive but not actually working" trap (a process that's up but whose real work has stalled — e.g. a dead worker masked by cached I/O). |
| `disk_monitor.sh.template` | Disk usage on the data path | Full disk silently corrupts checkpoints / kills miners. |
| `restart_guard.sh.template` | Process down or stalled → restart (rate-limited) | Recovers from crashes/stalls without restart-loops. |

## Placeholders

Replace every `{{TOKEN}}` before use:

| Token | Meaning | Example |
|-------|---------|---------|
| `{{NETUID}}` | Subnet netuid | `19` |
| `{{WALLET_NAME}}` | Coldkey wallet name | `default` |
| `{{HOTKEY_NAME}}` | Hotkey name | `miner1` |
| `{{HOTKEY_SS58}}` | Hotkey ss58 address (the on-chain identity to match) | `5F...` |
| `{{PROC_NAME}}` | pm2/process name of the miner | `miner` |
| `{{BTCLI}}` | Resolved btcli invocation (see tooling-reference.md) | `/Users/you/.local/bin/btcli` |
| `{{POLL_SECONDS}}` | Seconds between polls (≈ tempo/2; tempo ~360 blocks ≈ 72 min) | `2160` |
| `{{ALERT_CMD}}` | Shell command that receives an alert message on stdin | `tee -a alerts.log` or a Discord/Telegram webhook curl |
| `{{DISK_PATH}}` | Path to monitor | `/` or the checkpoint dir |
| `{{DISK_THRESHOLD_PCT}}` | Alert above this disk % | `85` |
| `{{WORK_SIGNAL_CMD}}` | A command that prints a monotonically-increasing counter or a freshness epoch-seconds value for the miner's REAL work (NOT "process up") | `cat /var/run/miner/step.txt` |

## Instantiation (how SETUP wires these)

```bash
SRC="$SKILL_DIR/references/monitoring-templates"
DST="$HOME/.subnet-scout/monitoring/sn{{NETUID}}"; mkdir -p "$DST"
for t in rank_earnings_watcher.py liveness_watcher.py disk_monitor.sh restart_guard.sh; do
  sed -e "s|{{NETUID}}|$NETUID|g" -e "s|{{HOTKEY_SS58}}|$HOTKEY_SS58|g" \
      -e "s|{{PROC_NAME}}|$PROC_NAME|g" -e "s|{{BTCLI}}|$BTCLI|g" \
      -e "s|{{POLL_SECONDS}}|$POLL_SECONDS|g" -e "s|{{ALERT_CMD}}|$ALERT_CMD|g" \
      -e "s|{{DISK_PATH}}|$DISK_PATH|g" -e "s|{{DISK_THRESHOLD_PCT}}|$DISK_THRESHOLD_PCT|g" \
      -e "s|{{WORK_SIGNAL_CMD}}|$WORK_SIGNAL_CMD|g" \
      "$SRC/$t.template" > "$DST/$t"
done
chmod +x "$DST"/*.sh
# Then, after the operator reviews them:
pm2 start "$DST/rank_earnings_watcher.py" --name sn{{NETUID}}-earnings --interpreter python3
pm2 start "$DST/liveness_watcher.py"      --name sn{{NETUID}}-liveness  --interpreter python3
# disk_monitor.sh / restart_guard.sh via cron (e.g. */5 * * * *)
```

Tune `{{POLL_SECONDS}}` to ~half the subnet's tempo so you see each weight-set without hammering the chain.
