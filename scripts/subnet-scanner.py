#!/usr/bin/env python3
"""
Bittensor Subnet Scanner -- outputs clean JSON for Cody to analyze.

Usage:
  python3 subnet-scanner.py            # List all subnets (finney)
  python3 subnet-scanner.py 102        # Per-UID metagraph for subnet 102

================================================================================
BTCLI RESOLUTION (portable, no hardcoded paths)
--------------------------------------------------------------------------------
resolve_btcli() returns an argv *prefix* (a list) that invokes btcli, trying in
order and caching the first that works:
  1. shutil.which("btcli")                      -> PATH shim (~/.local/bin/btcli)
  2. $BTCLI_PATH (or legacy $BTCLI)             -> explicit override
  3. ~/.local/bin/btcli                         -> common uv-tool / pip --user loc
  4. ["uv","tool","run","bittensor-cli","--"]   -> uv tool-install case
  5. ["python3","-m","bittensor_cli"]           -> module fallback
Each candidate is probed with `--version`; the first that exits 0 is cached.
If NOTHING resolves, every call returns a structured error (NO fabricated data).

COMMAND SURFACE (btcli 9.21.1, verified on this machine)
  - subnet list                       -> all subnets
  - subnet show --netuid N            -> metagraph view ("Inspect the metagraph")
    NOTE: there is NO `subnet metagraph` verb in 9.21.1; `show` replaced it.
    `show` is run with `--no-prompt` to avoid hanging on the mechanism prompt.
  - JSON: confirmed flag is `--json-output` (alias `--json-out`) on both verbs.
    We try `--json-output` then `--json-out`; if neither yields JSON we fall
    back to rich-table text parsing.

OUTPUT SCHEMA (single JSON document on stdout)
--------------------------------------------------------------------------------
Every document carries:
  ok       : bool          -- did the btcli call succeed?
  btcli    : list[str]|null-- the resolved invocation prefix (or null)
  source   : str           -- "btcli-json" | "btcli-text" | "none"
  error    : str|null      -- populated ON FAILURE; never invented data

Subnet-list document (no arg):
  { ok, btcli, source, json_flag, error, total_subnets,
    subnets: [ { netuid, symbol, name, ...verbatim scalar fields } ] }

Metagraph document (<netuid> arg):
  { ok, btcli, source, json_flag, error, netuid, total_uids,
    neurons: [ { uid, hotkey, coldkey, stake, alpha_stake, tao_stake,
                 dividends, incentive, emission, rank, trust,
                 validator_permit, axon } ],
    top_3_miners_by_incentive: [ {uid, incentive, hotkey, stake} ],
    stake_concentration: { total_stake, validator_count, top_validators[],
                           top5_validator_stake, top5_validator_share,
                           validator_stake_hhi } }

  Real btcli 9.21.1 layout: `subnet show --json-output` returns per-UID rows
  under `rows` carrying uid/stake/alpha_stake/tao_stake/dividends/incentive/
  emission/hotkey/coldkey. rank/trust/axon are NOT in that layout -> stay null.
  validator_permit is DERIVED from dividends>0 when no explicit permit field is
  present (the skill convention: validator := dividends>0).

TRUTH-FIRST: any btcli failure sets ok=false and fills `error`. The neuron list
and aggregates are then empty -- numbers are NEVER fabricated.
================================================================================
"""

import json
import os
import re
import shutil
import subprocess
import sys

# ---------------------------------------------------------------------------
# btcli resolution
# ---------------------------------------------------------------------------

_BTCLI_CACHE = None          # cached resolved argv prefix (list) once probed
_BTCLI_RESOLVE_ERR = None    # cached failure reason if nothing resolved


def _probe(prefix):
    """Return True if `prefix + ['--version']` runs and exits 0."""
    try:
        r = subprocess.run(
            list(prefix) + ["--version"],
            capture_output=True, text=True, timeout=30,
        )
        return r.returncode == 0
    except Exception:
        return False


def resolve_btcli():
    """Return an argv prefix list that invokes btcli, portably.

    Tries (in order): PATH shim -> $BTCLI_PATH/$BTCLI -> ~/.local/bin/btcli ->
    `uv tool run bittensor-cli --` -> `python3 -m bittensor_cli`. The first
    candidate that responds to `--version` is cached and returned.

    Returns the prefix list, or None if nothing resolves (caller must emit a
    structured error and NOT fabricate data).
    """
    global _BTCLI_CACHE, _BTCLI_RESOLVE_ERR
    if _BTCLI_CACHE is not None:
        return _BTCLI_CACHE
    if _BTCLI_RESOLVE_ERR is not None:
        return None

    candidates = []

    which = shutil.which("btcli")
    if which:
        candidates.append([which])

    env_path = os.environ.get("BTCLI_PATH") or os.environ.get("BTCLI")
    if env_path:
        candidates.append([env_path])

    home_local = os.path.expanduser("~/.local/bin/btcli")
    if os.path.exists(home_local):
        candidates.append([home_local])

    uv = shutil.which("uv")
    if uv:
        # uv tool-install case (matches how btcli is installed on this machine)
        candidates.append([uv, "tool", "run", "bittensor-cli", "--"])

    py = shutil.which("python3") or sys.executable
    if py:
        candidates.append([py, "-m", "bittensor_cli"])

    tried = []
    for cand in candidates:
        tried.append(" ".join(cand))
        if _probe(cand):
            _BTCLI_CACHE = cand
            return _BTCLI_CACHE

    _BTCLI_RESOLVE_ERR = (
        "btcli could not be resolved. Tried: "
        + ("; ".join(tried) if tried else "(no candidates found)")
        + ". Install with `uv tool install bittensor-cli` or "
        "`pip install --user bittensor-cli`, or set $BTCLI_PATH."
    )
    return None


def run_btcli(args, timeout=120):
    """Run a btcli command. Returns (ok, stdout, stderr, error).

    error is None on success, otherwise a human-readable reason. On any failure
    ok is False and the caller must NOT invent data.
    """
    prefix = resolve_btcli()
    if prefix is None:
        return (False, "", "", _BTCLI_RESOLVE_ERR)

    cmd = list(prefix) + list(args)
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return (False, "", "", f"btcli timed out after {timeout}s: {' '.join(cmd)}")
    except FileNotFoundError as e:
        return (False, "", "", f"btcli invocation not found: {e}")
    except Exception as e:
        return (False, "", "", f"btcli execution error: {e}")

    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip()
        return (False, r.stdout, r.stderr,
                f"btcli exited {r.returncode}: {msg[:400] or 'no output'}")
    return (True, r.stdout, r.stderr, None)


# ---------------------------------------------------------------------------
# text / json helpers
# ---------------------------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
_OSC = re.compile(r"\x1b\][^\x07]*\x07")


def _strip_ansi(text):
    text = _OSC.sub("", text)
    text = _ANSI.sub("", text)
    # normalize rich box-drawing to ascii for the text-parsing fallback
    return (text.replace("│", "|").replace("─", "-")
                .replace("╭", "+").replace("╰", "+")
                .replace("╮", "+").replace("╯", "+")
                .replace("├", "+").replace("┤", "+")
                .replace("┬", "+").replace("┴", "+")
                .replace("┼", "+"))


def _to_float(s):
    """Best-effort float from a btcli cell (strips tau, commas, %, units)."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.search(r"-?\d[\d,]*\.?\d*", str(s).replace("τ", ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _truthy(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("true", "yes", "y", "1", "*", "✔", "✓")


def _extract_json_spans(text):
    """Yield candidate JSON substrings (object or array) from mixed output."""
    s = text.strip()
    if s and s[0] in "[{":
        yield s
    # also try to locate the first balanced {...} or [...] span
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if 0 <= start < end:
            yield text[start:end + 1]


def _try_json_call(args, json_flags=("--json-output", "--json-out")):
    """Run an args list with each json flag in turn; return (data, flag) or (None, None).

    A flag that btcli rejects (non-zero exit) or that yields non-JSON is skipped.
    """
    for flag in json_flags:
        ok, out, _err, _e = run_btcli(list(args) + [flag])
        if not ok or not out:
            continue
        cleaned = _strip_ansi(out).strip()
        for blob in _extract_json_spans(cleaned):
            try:
                # strict=False: btcli embeds raw newlines inside string values
                # (e.g. "identity": "General Tensor \n(RoundTable21)"), which
                # strict JSON rejects. Tolerating control chars in strings lets
                # us parse real btcli 9.21.1 output without losing data.
                return json.loads(blob, strict=False), flag
            except (ValueError, TypeError):
                continue
    return None, None


# ---------------------------------------------------------------------------
# subnet list
# ---------------------------------------------------------------------------

def _normalize_subnet_records(data):
    """Coerce btcli JSON (shape varies by version) into a flat subnet list.

    btcli 9.21.1 `subnet list --json-output` returns a dict with a `subnets`
    member that is itself a dict KEYED BY NETUID STRING ("0","1","2",...), each
    value a record dict. We also accept list-shaped containers and a top-level
    dict-keyed-by-netuid for forward/backward compatibility.
    """
    # `pairs` is a list of (netuid_hint, record_dict); netuid_hint may be None.
    pairs = []
    if isinstance(data, list):
        pairs = [(None, r) for r in data if isinstance(r, dict)]
    elif isinstance(data, dict):
        container = None
        for key in ("subnets", "data", "results", "rows", "netuids"):
            if key in data:
                container = data[key]
                break
        if container is None and data and all(str(k).isdigit() for k in data.keys()):
            container = data  # top-level dict keyed by netuid
        if isinstance(container, list):
            pairs = [(None, r) for r in container if isinstance(r, dict)]
        elif isinstance(container, dict):
            pairs = [(k, v) for k, v in container.items() if isinstance(v, dict)]
    if not pairs:
        return []

    out = []
    for netuid_hint, r in pairs:
        netuid = (r.get("netuid") if r.get("netuid") is not None
                  else r.get("net_uid", r.get("uid", r.get("id"))))
        if netuid is None and netuid_hint is not None:
            netuid = netuid_hint
        rec = {
            "netuid": int(netuid) if netuid is not None and str(netuid).isdigit() else netuid,
            "symbol": r.get("symbol") or r.get("token_symbol"),
            "name": r.get("subnet_name") or r.get("name") or r.get("full_name"),
        }
        # keep remaining scalar fields verbatim (truth-first: don't drop data)
        for k, v in r.items():
            if k not in rec and isinstance(v, (str, int, float, bool)) and v is not None:
                rec.setdefault(k, v)
        out.append(rec)
    # sort by netuid when available for stable, readable output
    out.sort(key=lambda x: x["netuid"] if isinstance(x.get("netuid"), int) else 1 << 30)
    return out


def _parse_subnet_list_text(raw):
    """Fallback: parse the rich-table `subnet list` output into records."""
    subnets = []
    for line in _strip_ansi(raw).split("\n"):
        line = line.strip()
        m = re.match(r"^\s*(\d+)\s*\|", line)
        if not m:
            continue
        netuid = int(m.group(1))
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]
        symbol = parts[1] if len(parts) > 1 else None
        name = parts[2] if len(parts) > 2 else symbol
        subnets.append({"netuid": netuid, "symbol": symbol, "name": name})
    return subnets


def get_subnet_list_json(network="finney"):
    """Return the structured subnet-list document (see top-of-file schema)."""
    base_args = ["subnet", "list", "--network", network]

    data, used_flag = _try_json_call(base_args)
    if data is not None:
        subnets = _normalize_subnet_records(data)
        return {
            "ok": True,
            "btcli": resolve_btcli(),
            "source": "btcli-json",
            "json_flag": used_flag,
            "error": None if subnets else "btcli JSON parsed but no subnet rows found (schema may differ)",
            "total_subnets": len(subnets),
            "subnets": subnets,
        }

    # text fallback
    ok, out, _err, error = run_btcli(base_args)
    if not ok:
        return {
            "ok": False,
            "btcli": resolve_btcli(),
            "source": "none",
            "json_flag": None,
            "error": error,
            "total_subnets": 0,
            "subnets": [],
        }
    subnets = _parse_subnet_list_text(out)
    return {
        "ok": True,
        "btcli": resolve_btcli(),
        "source": "btcli-text",
        "json_flag": None,
        "error": None if subnets else "btcli returned output but no subnet rows could be parsed (table format may have changed)",
        "total_subnets": len(subnets),
        "subnets": subnets,
    }


# ---------------------------------------------------------------------------
# metagraph (per-UID)
# ---------------------------------------------------------------------------

# canonical field -> candidate keys seen across btcli/SDK JSON shapes.
# btcli 9.21.1 `subnet show --json-output` emits per-UID list-of-dict under
# `rows` with fields: uid, stake, alpha_stake, tao_stake, dividends, incentive,
# emission, hotkey, coldkey. It does NOT carry rank/trust/validator_permit/axon
# in that layout, so those stay null (truth-first) unless another shape supplies
# them. `validator_permit` is DERIVED from dividends>0 when no explicit field
# exists (matches the skill's `validator := dividends>0` convention).
_FIELD_ALIASES = {
    "uid": ("uid", "UID", "neuron_uid"),
    "hotkey": ("hotkey", "hotkey_ss58", "hot_key", "hotkey_address"),
    "coldkey": ("coldkey", "coldkey_ss58", "cold_key", "coldkey_address"),
    "stake": ("stake", "total_stake", "stake_tao", "S", "alpha_stake"),
    "alpha_stake": ("alpha_stake",),
    "tao_stake": ("tao_stake",),
    "dividends": ("dividends", "D"),
    "incentive": ("incentive", "I"),
    "emission": ("emission", "E", "emission_tao"),
    "rank": ("rank", "R"),
    "trust": ("trust", "T"),
    "validator_permit": ("validator_permit", "validator_permitted", "vpermit",
                         "is_validator", "validatorPermit"),
}


def _pick(d, names):
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return None


def _axon_str(d):
    """Build 'ip:port' from whatever axon shape btcli exposes."""
    axon = d.get("axon") or d.get("axon_info")
    ip = port = None
    if isinstance(axon, dict):
        ip = axon.get("ip") or axon.get("ip_str") or axon.get("address")
        port = axon.get("port")
    elif isinstance(axon, str):
        return axon or None
    if ip is None:
        ip = d.get("axon_ip") or d.get("ip")
    if port is None:
        port = d.get("axon_port") or d.get("port")
    if ip in (None, "", "0.0.0.0", 0):
        return None
    return f"{ip}:{port}" if port else str(ip)


def _normalize_neuron_rows(data):
    """Extract the per-UID neuron rows from a metagraph JSON document."""
    rows = None
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        for key in ("neurons", "metagraph", "data", "results", "rows", "uids"):
            v = data.get(key)
            if isinstance(v, list):
                rows = v
                break
            if isinstance(v, dict) and isinstance(v.get("neurons"), list):
                rows = v["neurons"]
                break
    if rows is None:
        return []

    neurons = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        uid = _pick(r, _FIELD_ALIASES["uid"])
        dividends = _to_float(_pick(r, _FIELD_ALIASES["dividends"]))
        permit_raw = _pick(r, _FIELD_ALIASES["validator_permit"])
        # explicit permit field wins; otherwise derive from dividends>0
        if permit_raw is not None:
            validator_permit = _truthy(permit_raw)
        else:
            validator_permit = bool(dividends and dividends > 0)
        neurons.append({
            "uid": int(uid) if uid is not None and str(uid).replace("-", "").isdigit() else uid,
            "hotkey": _pick(r, _FIELD_ALIASES["hotkey"]),
            "coldkey": _pick(r, _FIELD_ALIASES["coldkey"]),
            "stake": _to_float(_pick(r, _FIELD_ALIASES["stake"])),
            "alpha_stake": _to_float(_pick(r, _FIELD_ALIASES["alpha_stake"])),
            "tao_stake": _to_float(_pick(r, _FIELD_ALIASES["tao_stake"])),
            "dividends": dividends,
            "incentive": _to_float(_pick(r, _FIELD_ALIASES["incentive"])),
            "emission": _to_float(_pick(r, _FIELD_ALIASES["emission"])),
            "rank": _to_float(_pick(r, _FIELD_ALIASES["rank"])),
            "trust": _to_float(_pick(r, _FIELD_ALIASES["trust"])),
            "validator_permit": validator_permit,
            "axon": _axon_str(r),
        })
    return neurons


def _parse_metagraph_text(raw):
    """Fallback: parse `subnet show` rich-table rows into per-UID neurons.

    Column order is inferred from the header row when present; otherwise a
    best-effort positional guess is used. Missing/ambiguous cells stay null
    rather than being fabricated.
    """
    lines = _strip_ansi(raw).split("\n")

    # locate a header row to map columns (best effort)
    header_map = {}
    for line in lines:
        low = line.lower()
        if "|" in line and "uid" in low and ("incentive" in low or "stake" in low):
            cols = [c.strip().lower() for c in line.split("|")]
            for idx, c in enumerate(cols):
                if not c:
                    continue
                if c.startswith("uid"):
                    header_map[idx] = "uid"
                elif "hotkey" in c:
                    header_map[idx] = "hotkey"
                elif "coldkey" in c:
                    header_map[idx] = "coldkey"
                elif "stake" in c:
                    header_map[idx] = "stake"
                elif "incentive" in c:
                    header_map[idx] = "incentive"
                elif "emission" in c:
                    header_map[idx] = "emission"
                elif c.startswith("rank"):
                    header_map[idx] = "rank"
                elif c.startswith("trust"):
                    header_map[idx] = "trust"
                elif "vtrust" in c or "validator" in c or "permit" in c:
                    header_map[idx] = "validator_permit"
                elif "axon" in c or c == "ip":
                    header_map[idx] = "axon"
            break

    neurons = []
    for line in lines:
        if "|" not in line:
            continue
        if not re.match(r"^\s*\|?\s*\d+\s*\|", line):
            continue
        cells = [c.strip() for c in line.split("|")]
        rec = {"uid": None, "hotkey": None, "coldkey": None, "stake": None,
               "incentive": None, "emission": None, "rank": None,
               "trust": None, "validator_permit": False, "axon": None}
        mapped = False
        for idx, field in header_map.items():
            if idx < len(cells):
                val = cells[idx].strip()
                if field in ("stake", "incentive", "emission", "rank", "trust"):
                    rec[field] = _to_float(val)
                elif field == "validator_permit":
                    rec[field] = _truthy(val)
                elif field == "uid":
                    rec[field] = int(val) if val.isdigit() else val
                else:
                    rec[field] = val or None
                mapped = True
        if not mapped:
            # no header -> positional best effort: first numeric cell is uid
            nums = [c for c in cells if c]
            uid_cell = next((c for c in nums if c.isdigit()), None)
            if uid_cell is None:
                continue
            rec["uid"] = int(uid_cell)
            rec["_raw"] = " | ".join(nums[:10])
        if rec.get("uid") is not None:
            neurons.append(rec)
    return neurons


def _compute_aggregates(neurons):
    """Top-3 miners by incentive + stake concentration of top validators."""
    top3 = sorted(
        [n for n in neurons if isinstance(n.get("incentive"), (int, float))],
        key=lambda n: n["incentive"], reverse=True,
    )[:3]
    top_3_miners = [
        {"uid": n["uid"], "incentive": n["incentive"],
         "hotkey": n.get("hotkey"), "stake": n.get("stake")}
        for n in top3
    ]

    validators = [n for n in neurons
                  if n.get("validator_permit")
                  and isinstance(n.get("stake"), (int, float))]
    total_stake = sum(n["stake"] for n in neurons
                      if isinstance(n.get("stake"), (int, float)))
    top_vals = sorted(validators, key=lambda n: n["stake"], reverse=True)[:5]
    top_val_stake = sum(n["stake"] for n in top_vals)
    top_val_share = (top_val_stake / total_stake) if total_stake else None

    # Herfindahl-Hirschman Index over validator stake shares (0..1)
    hhi = None
    if validators and total_stake:
        hhi = sum((n["stake"] / total_stake) ** 2 for n in validators)

    return top_3_miners, {
        "total_stake": total_stake,
        "validator_count": len(validators),
        "top_validators": [
            {"uid": n["uid"], "stake": n["stake"], "hotkey": n.get("hotkey")}
            for n in top_vals
        ],
        "top5_validator_stake": top_val_stake,
        "top5_validator_share": top_val_share,
        "validator_stake_hhi": hhi,
    }


def get_metagraph_json(netuid, network="finney"):
    """Return the structured per-UID metagraph document (see top-of-file)."""
    # --no-prompt avoids hanging on the mechanism-selection prompt that `show`
    # raises when a subnet has multiple mechanisms (defaults to mechid 0).
    base_args = ["subnet", "show", "--netuid", str(netuid),
                 "--network", network, "--no-prompt"]

    data, used_flag = _try_json_call(base_args)
    if data is not None:
        neurons = _normalize_neuron_rows(data)
        top3, conc = _compute_aggregates(neurons)
        return {
            "ok": True,
            "btcli": resolve_btcli(),
            "source": "btcli-json",
            "json_flag": used_flag,
            "error": None if neurons else "btcli JSON parsed but no neuron rows found (schema may differ)",
            "netuid": int(netuid),
            "total_uids": len(neurons),
            "neurons": neurons,
            "top_3_miners_by_incentive": top3,
            "stake_concentration": conc,
        }

    # text fallback
    ok, out, _err, error = run_btcli(base_args)
    if not ok:
        return {
            "ok": False,
            "btcli": resolve_btcli(),
            "source": "none",
            "json_flag": None,
            "error": error,
            "netuid": int(netuid),
            "total_uids": 0,
            "neurons": [],
            "top_3_miners_by_incentive": [],
            "stake_concentration": {},
        }
    neurons = _parse_metagraph_text(out)
    top3, conc = _compute_aggregates(neurons)
    return {
        "ok": True,
        "btcli": resolve_btcli(),
        "source": "btcli-text",
        "json_flag": None,
        "error": None if neurons else "btcli returned output but no per-UID rows could be parsed (table format may have changed)",
        "netuid": int(netuid),
        "total_uids": len(neurons),
        "neurons": neurons,
        "top_3_miners_by_incentive": top3,
        "stake_concentration": conc,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv):
    if len(argv) > 1:
        arg = argv[1]
        if not re.fullmatch(r"\d+", arg):
            print(json.dumps({
                "ok": False,
                "error": f"Invalid netuid '{arg}'. Pass an integer netuid, or no "
                         "argument to list all subnets.",
            }, indent=2))
            return 2
        data = get_metagraph_json(int(arg))
        print(json.dumps(data, indent=2))
        return 0 if data.get("ok") else 1

    data = get_subnet_list_json()
    print(json.dumps(data, indent=2))
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
