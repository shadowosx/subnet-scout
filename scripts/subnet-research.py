#!/usr/bin/env python3
"""
Bittensor Subnet Intelligence Pipeline
Pulls data from Taostats API, Desearch (X/Twitter + Web), and GitHub
to produce comprehensive subnet research reports.

Usage:
  python3 subnet-research.py report <netuid>    # Full intelligence report
  python3 subnet-research.py scan               # Quick scan all subnets
  python3 subnet-research.py top [N]            # Top N most profitable (default 10)

Flags (all subcommands):
  --max-age <secs>     Reuse cached network results younger than this (default 3600).
  --no-cache           Ignore existing cache on read (results are still persisted).
  --github-days <days> GitHub commit history window for `report` (default 60).

Requires: TAOSTATS_API_KEY, DESEARCH_API_KEY in .env or environment

──────────────────────────────────────────────────────────────────────────────
UPGRADE NOTES (additive only — existing report/scan/top subcommands and the
top-level JSON key structure are preserved; new keys are namespaced/internal):

  1. Run-dir + caching + resumability (was: no persistence at all). Every
     network call is wrapped by cached_call(), which reads a fresh on-disk cache
     (<rundir>/cache/<call-name>.json, with a timestamp) when present and younger
     than --max-age, logging "[cache hit]" to stderr; otherwise it calls the API
     and persists the result. The assembled report is also written to
     <rundir>/report.json. A crash / 429 / 403 mid-run therefore resumes from
     cache on re-run instead of re-paying every API call. Run dir defaults to
     /tmp/subnet-scout/<netuid>/ (override via $SUBNET_SCOUT_RUNDIR). scan/top
     use a shared <rundir-base>/_scan/ and <rundir-base>/_top/ so their
     per-subnet loops are resumable too. New flags: --max-age, --no-cache.

  2. 403 handling. 403 is now treated as an auth failure: no transient retry,
     a clear redacted "auth failed — check API key" note to stderr, and the rest
     of the providers continue. (Previously 403 was retried like a 429, wasting
     ~30s of backoff per call.)

  3. Graceful desearch_py absence. The lazy `from desearch_py import ...`
     imports are funnelled through _import_desearch(), which on ImportError emits
     one "Desearch unavailable: pip install desearch-py" note and returns None so
     the rest of the report still assembles. See scripts/requirements.txt.

  4. GitHub history window. Commits are fetched with a raised per_page and a
     `since` time window (default 60 days, --github-days) so commit cadence and
     committer concentration are computable. A committer_concentration summary is
     added under github.

  5. NEVER-show fields. Per references/live-data-fields.md, raw `emission` and
     `pools` are no longer top-level report keys; they are moved under
     `_internal` (leading underscore) so the report/summary layer skips them
     while the data remains available for internal computation.

  6. Credentials stay write-only. Key values are never logged; _redact() scrubs
     long opaque tokens from any error text routed to stderr.
──────────────────────────────────────────────────────────────────────────────
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

# ── Config ──────────────────────────────────────────────────────────────────

# Load .env from multiple locations
_SKILL_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
for env_path in [".env", _SKILL_ENV, os.path.expanduser("~/.openclaw/.env")]:
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ.setdefault(key.strip(), val.strip())

TAOSTATS_API_KEY = os.environ.get("TAOSTATS_API_KEY", "")
DESEARCH_API_KEY = os.environ.get("DESEARCH_API_KEY", "")

# Post-halving constants (Dec 12, 2025)
BLOCK_REWARD_TAO = 0.5
BLOCKS_PER_DAY = 7200
DAILY_NETWORK_EMISSION = BLOCK_REWARD_TAO * BLOCKS_PER_DAY  # 3,600 TAO

# Upgrade defaults
DEFAULT_MAX_AGE = 3600          # seconds — cache reuse window
DEFAULT_GITHUB_DAYS = 60        # GitHub commit history window
GITHUB_COMMITS_PER_PAGE = 100   # raised from the old 5

# Cache runtime config (set by main() from CLI flags before any fetch runs).
_CACHE_MAX_AGE = DEFAULT_MAX_AGE
_CACHE_USE = True
_RUN_DIR = None  # set per-command
_GITHUB_DAYS = DEFAULT_GITHUB_DAYS  # set by main() before cmd_report runs


# ── Logging / redaction (Bug 6 — credentials stay write-only) ────────────────

def _log(msg):
    """Status line to stderr only (never stdout, never the report)."""
    print(msg, file=sys.stderr)


def _redact(text):
    """Scrub long opaque tokens (likely key fragments) from error text.

    Credentials are write-only: this guards against a key value leaking into a
    stderr message via an exception string or header echo.
    """
    if text is None:
        return text
    text = str(text)
    out = []
    for tok in text.split():
        if len(tok) >= 16 and any(c.isalnum() for c in tok) and "/" not in tok and "." not in tok:
            out.append("[REDACTED]")
        else:
            out.append(tok)
    return " ".join(out)


# ── Run-dir + cache layer (Bug 2 — persistence / resumability) ───────────────

def get_run_dir(subkey):
    """Return (and create) a run directory for this invocation.

    subkey is the netuid for `report`, or "_scan" / "_top" for the aggregate
    commands. Base dir is $SUBNET_SCOUT_RUNDIR or /tmp/subnet-scout.
    """
    base = os.environ.get("SUBNET_SCOUT_RUNDIR", "/tmp/subnet-scout")
    run_dir = os.path.join(base, str(subkey))
    os.makedirs(os.path.join(run_dir, "cache"), exist_ok=True)
    return run_dir


def _cache_path(call_name):
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', str(call_name))
    return os.path.join(_RUN_DIR, "cache", f"{safe}.json")


def cache_read(call_name):
    """Return cached payload if a fresh (< _CACHE_MAX_AGE) cache file exists.

    Cache files store {"_cached_at": <epoch>, "_call": <name>, "data": <payload>}.
    Logs "[cache hit]" to stderr on reuse. Respects --no-cache (read side).
    """
    if not _CACHE_USE or not _RUN_DIR:
        return None
    path = _cache_path(call_name)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            blob = json.load(fh)
    except (OSError, ValueError):
        return None
    cached_at = blob.get("_cached_at", 0)
    age = time.time() - cached_at
    if age < 0 or age > _CACHE_MAX_AGE:
        return None
    _log(f"  [cache hit] {call_name} (age {int(age)}s < max-age {_CACHE_MAX_AGE}s)")
    return blob.get("data")


def cache_write(call_name, data):
    """Persist a call result to <rundir>/cache/<call_name>.json with timestamp.

    Always writes (even under --no-cache) so a crash mid-run is resumable on the
    next invocation; --no-cache only disables READING stale cache. Atomic write
    (temp + rename) so a crash never leaves a half file.
    """
    if not _RUN_DIR:
        return
    path = _cache_path(call_name)
    blob = {
        "_cached_at": time.time(),
        "_cached_at_iso": datetime.now(timezone.utc).isoformat(),
        "_call": call_name,
        "data": data,
    }
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as fh:
            json.dump(blob, fh, indent=2, default=str)
        os.replace(tmp, path)
    except OSError as e:
        _log(f"  [cache] failed to persist {call_name}: {_redact(e)}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def cached_call(call_name, fn):
    """Resumable wrapper: reuse fresh cache, else call fn() and persist result.

    A None result is still persisted so a re-run does not blindly re-pay a call
    that legitimately produced no data within the cache window.
    """
    cached = cache_read(call_name)
    if cached is not None:
        return cached
    result = fn()
    cache_write(call_name, result)
    return result


def persist_report(report, name="report.json"):
    """Write the assembled report to <rundir>/<name> (atomic)."""
    if not _RUN_DIR:
        return
    path = os.path.join(_RUN_DIR, name)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp, path)
        _log(f"  [report] persisted to {path}")
    except OSError as e:
        _log(f"  [report] failed to persist — {_redact(e)}")


# ── Desearch import shim (Bug 3 — graceful absence) ──────────────────────────

_DESEARCH_WARNED = False


def _import_desearch():
    """Return the Desearch class, or None if desearch_py is not installed.

    Emits a single install hint to stderr on the first miss so callers can
    degrade cleanly instead of crashing.
    """
    global _DESEARCH_WARNED
    try:
        from desearch_py import Desearch
        return Desearch
    except ImportError:
        if not _DESEARCH_WARNED:
            _log("  [desearch] Desearch unavailable: pip install desearch-py — continuing without it.")
            _DESEARCH_WARNED = True
        return None


# ── Taostats API ────────────────────────────────────────────────────────────

TAOSTATS_BASE = "https://api.taostats.io"

def taostats_get(path, params=None):
    """Call Taostats API endpoint. Returns parsed JSON or None on error.

    403 is now treated as an auth failure (no retry) — Bug 2/7. 429 and other
    transient codes still back off and retry. Error text is redacted.
    """
    url = f"{TAOSTATS_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            fresh_req = urllib.request.Request(url, headers={
                "Authorization": TAOSTATS_API_KEY,
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; SubnetResearch/1.0)"
            })
            with urllib.request.urlopen(fresh_req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
                time.sleep(2)  # Rate limit: ~0.5 req/sec to avoid 429
                return data
        except urllib.error.HTTPError as e:
            if e.code == 403:
                # Auth failure — never succeeds on retry. Fail fast, keep going.
                _log(f"  [taostats] {path} auth failed (HTTP 403) — check API key. "
                     f"Skipping this provider.")
                return None
            if e.code == 429 and attempt < 2:
                wait = (attempt + 1) * 5
                _log(f"  [taostats] {path} rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            _log(f"  [taostats] {path} error: HTTP {e.code} {_redact(getattr(e, 'reason', ''))}")
            return None
        except Exception as e:
            _log(f"  [taostats] {path} error: {_redact(e)}")
            return None
    return None

def get_subnet_identity(netuid):
    """Get subnet name, website, GitHub, Discord, description, Twitter."""
    resp = cached_call(f"taostats_identity_{netuid}",
                       lambda: taostats_get("/api/subnet/identity/v1", {"netuid": netuid}))
    if resp and resp.get("data"):
        d = resp["data"][0]
        return {
            "subnet_name": d.get("subnet_name", ""),
            "description": d.get("description", ""),
            "summary": d.get("summary", ""),
            "website": (d.get("subnet_url") or "").strip(),
            "github_repo": (d.get("github_repo") or "").strip(),
            "discord": (d.get("discord") or "").strip(),
            "twitter": (d.get("twitter") or "").strip(),
            "contact": (d.get("subnet_contact") or "").strip(),
            "tags": d.get("tags", []),
        }
    return None

def get_subnet_emission(netuid):
    """Get emission data from Taostats (already accounts for halving)."""
    resp = cached_call(f"taostats_emission_{netuid}",
                       lambda: taostats_get("/api/dtao/subnet_emission/v1", {"netuid": netuid, "per_page": 1}))
    if resp and resp.get("data"):
        d = resp["data"][0]
        return {
            "block_number": d.get("block_number"),
            "timestamp": d.get("timestamp"),
            "tao_in_pool": d.get("tao_in_pool"),
            "alpha_in_pool": d.get("alpha_in_pool"),
            "alpha_rewards": d.get("alpha_rewards"),
            "symbol": d.get("symbol", ""),
        }
    return None

def get_subnet_pools(netuid):
    """Get pool data — TAO pool, alpha pool, rates."""
    resp = cached_call(f"taostats_pools_{netuid}",
                       lambda: taostats_get("/api/dtao/subnet_emission/v1", {"netuid": netuid, "per_page": 3}))
    if resp and resp.get("data") and len(resp["data"]) >= 2:
        latest = resp["data"][0]
        prev = resp["data"][1]
        tao_now = int(latest.get("tao_in_pool", 0))
        tao_prev = int(prev.get("tao_in_pool", 0))
        return {
            "tao_pool": tao_now,
            "tao_pool_tao": round(tao_now / 1e9, 2),
            "alpha_pool": int(latest.get("alpha_in_pool", 0)),
            "tao_flow": "inflow" if tao_now > tao_prev else "outflow",
            "tao_change": round((tao_now - tao_prev) / 1e9, 4),
        }
    return None

def get_subnet_info(netuid):
    """Get subnet info from subnet/latest — active miners, validators, reg cost, etc."""
    resp = cached_call(f"taostats_info_{netuid}",
                       lambda: taostats_get("/api/subnet/latest/v1", {"netuid": netuid}))
    if resp and resp.get("data"):
        d = resp["data"][0]
        neuron_reg_rao = int(d.get("neuron_registration_cost", 0))
        return {
            "active_miners": d.get("active_miners", 0),
            "active_validators": d.get("active_validators", 0),
            "active_keys": d.get("active_keys", 0),
            "max_neurons": d.get("max_neurons", 256),
            "tempo": d.get("tempo", 360),
            "registration_cost_tao": round(neuron_reg_rao / 1e9, 6),
            "incentive_burn": d.get("incentive_burn"),
            "emission": d.get("emission"),
            "projected_emission": d.get("projected_emission"),
            "registration_allowed": d.get("registration_allowed", False),
            "pow_registration_allowed": d.get("pow_registration_allowed", False),
        }
    return None

def get_tao_price():
    """Get current TAO price in USD."""
    resp = cached_call("taostats_price",
                       lambda: taostats_get("/api/price/latest/v1", {"asset": "tao"}))
    if resp and resp.get("data"):
        d = resp["data"][0]
        return {
            "price_usd": float(d.get("close", d.get("price", 0))),
            "market_cap": d.get("market_cap"),
            "circulating_supply": d.get("circulating_supply"),
        }
    return None

def get_metagraph_summary(netuid):
    """Get metagraph summary — miner/validator counts, emission distribution.

    Classification: incentive > 0 = miner, dividends > 0 = validator.
    Emission: uses daily_mining_alpha_as_tao / daily_validating_alpha_as_tao
    (alpha emissions only, NOT staking rewards from root network).
    """
    resp = cached_call(f"taostats_metagraph_{netuid}",
                       lambda: taostats_get("/api/metagraph/latest/v1", {"netuid": netuid, "per_page": 1024}))
    if not resp or not resp.get("data"):
        return None

    neurons = resp["data"]

    # Classify by incentive/dividends (NOT validator_permit — miners can have it)
    miners = [n for n in neurons if float(n.get("incentive") or 0) > 0]
    validators = [n for n in neurons if float(n.get("dividends") or 0) > 0]

    # Daily alpha emissions (subnet emission, not staking rewards)
    miner_daily_tao = []
    for m in miners:
        daily = int(m.get("daily_mining_alpha_as_tao") or 0)
        if daily > 0:
            miner_daily_tao.append(daily / 1e9)

    val_daily_tao = []
    for v in validators:
        daily = int(v.get("daily_validating_alpha_as_tao") or 0)
        if daily > 0:
            val_daily_tao.append(daily / 1e9)

    # Owner emission
    owner_daily_tao = sum(int(n.get("daily_owner_alpha_as_tao") or 0) for n in neurons) / 1e9

    # Total subnet emission = miner alpha + validator alpha + owner alpha
    total_emission = sum(miner_daily_tao) + sum(val_daily_tao) + owner_daily_tao

    result = {
        "total_neurons": len(neurons),
        "miners": len(miners),
        "validators": len(validators),
        "earning_miners": len(miner_daily_tao),
        "earning_validators": len(val_daily_tao),
        "daily_emission_tao": round(total_emission, 4),
        "miner_daily_emission_tao": round(sum(miner_daily_tao), 4),
        "validator_daily_emission_tao": round(sum(val_daily_tao), 4),
        "owner_daily_emission_tao": round(owner_daily_tao, 4),
    }

    if miner_daily_tao:
        result["avg_miner_daily_tao"] = round(sum(miner_daily_tao) / len(miner_daily_tao), 6)
        result["top_miner_daily_tao"] = round(max(miner_daily_tao), 6)
        result["bottom_miner_daily_tao"] = round(min(miner_daily_tao), 6)

    if val_daily_tao:
        result["avg_validator_daily_tao"] = round(sum(val_daily_tao) / len(val_daily_tao), 6)

    # Top 3 miners by daily earnings
    miner_earnings = []
    for m in miners:
        daily = int(m.get("daily_mining_alpha_as_tao") or 0)
        if daily > 0:
            miner_earnings.append({
                "uid": m.get("uid"),
                "daily_tao": round(daily / 1e9, 6),
                "incentive": round(float(m.get("incentive") or 0), 6),
                "hotkey": m.get("hotkey", {}).get("ss58", "")[:12] + "...",
            })
    miner_earnings.sort(key=lambda x: x["daily_tao"], reverse=True)
    result["top_3_miners"] = miner_earnings[:3]

    return result

def get_all_subnet_identities():
    """Get identities for all subnets in one call."""
    resp = cached_call("taostats_all_identities",
                       lambda: taostats_get("/api/subnet/identity/v1", {"per_page": 256}))
    if resp and resp.get("data"):
        return {d["netuid"]: d for d in resp["data"]}
    return {}

def get_all_subnet_emissions():
    """Get latest emission data for all subnets."""
    # Get emissions for each subnet — Taostats returns time series per netuid
    # For scan mode, we query all at once
    resp = cached_call("taostats_all_emissions",
                       lambda: taostats_get("/api/dtao/subnet_emission/v1", {"per_page": 256}))
    if resp and resp.get("data"):
        # Group by netuid, take latest per subnet
        by_netuid = {}
        for d in resp["data"]:
            nid = d["netuid"]
            if nid not in by_netuid:
                by_netuid[nid] = d
        return by_netuid
    return {}


# ── Desearch API (X/Twitter + Web) ─────────────────────────────────────────

def desearch_x_search(query, count=15):
    """Search X/Twitter for recent posts about a subnet."""
    if not DESEARCH_API_KEY:
        return {"error": "DESEARCH_API_KEY not set"}
    Desearch = _import_desearch()
    if Desearch is None:
        return {"error": "desearch_py not installed (pip install desearch-py)"}
    try:
        client = Desearch(api_key=DESEARCH_API_KEY)
        results = asyncio.run(client.x_search(
            query=query,
            sort="Latest",
            count=count
        ))
        # Normalize results
        tweets = []
        if isinstance(results, list):
            for t in results:
                tweet = t if isinstance(t, dict) else (t.dict() if hasattr(t, 'dict') else t.__dict__)
                tweets.append({
                    "text": tweet.get("text", "")[:280],
                    "user": tweet.get("user", {}).get("username", "") if isinstance(tweet.get("user"), dict) else "",
                    "likes": tweet.get("like_count", 0),
                    "retweets": tweet.get("retweet_count", 0),
                    "views": tweet.get("view_count", 0),
                    "url": tweet.get("url", ""),
                    "date": tweet.get("created_at", ""),
                })
        return {"tweets": tweets, "count": len(tweets)}
    except Exception as e:
        return {"error": _redact(e)}

def desearch_web_search(query):
    """Web search for project info, guides, articles."""
    if not DESEARCH_API_KEY:
        return {"error": "DESEARCH_API_KEY not set"}
    Desearch = _import_desearch()
    if Desearch is None:
        return {"error": "desearch_py not installed (pip install desearch-py)"}
    try:
        client = Desearch(api_key=DESEARCH_API_KEY)
        results = asyncio.run(client.web_search(query=query, start=0))

        def safe_dump(obj):
            if hasattr(obj, 'model_dump'):
                return obj.model_dump()
            elif hasattr(obj, 'dict'):
                return obj.dict()
            elif isinstance(obj, list):
                return [safe_dump(x) for x in obj]
            return obj

        return json.loads(json.dumps(safe_dump(results), default=str))
    except Exception as e:
        return {"error": _redact(e)}

def desearch_web_crawl(url):
    """Crawl a project website for content."""
    if not DESEARCH_API_KEY or not url:
        return None
    Desearch = _import_desearch()
    if Desearch is None:
        return None
    try:
        client = Desearch(api_key=DESEARCH_API_KEY)
        content = asyncio.run(client.web_crawl(url=url))
        if isinstance(content, str):
            return content[:5000]
        return str(content)[:5000]
    except Exception as e:
        return f"Error crawling {url}: {_redact(e)}"


# ── GitHub API ──────────────────────────────────────────────────────────────

def _github_headers():
    """GitHub headers, with optional GITHUB_TOKEN to lift the anon rate limit."""
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "subnet-research"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_get_json(url, timeout=10):
    """GET a GitHub JSON endpoint. 403 is auth/rate failure — fail fast, redact.

    Returns (parsed_json_or_None, headers_dict).
    """
    try:
        req = urllib.request.Request(url, headers=_github_headers())
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode()), dict(resp.headers)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            _log("  [github] HTTP 403 — auth/rate-limit failure. Set GITHUB_TOKEN "
                 "to raise the anonymous limit. Skipping this GitHub call.")
            return None, {}
        _log(f"  [github] error: HTTP {e.code} {_redact(getattr(e, 'reason', ''))}")
        return None, {}
    except Exception as e:
        _log(f"  [github] error: {_redact(e)}")
        return None, {}


def _summarize_committers(commits):
    """Compute committer concentration over a commit window (Bug 4)."""
    authors = {}
    for c in commits:
        commit = c.get("commit", {}) or {}
        name = (commit.get("author", {}) or {}).get("name", "") or "unknown"
        authors[name] = authors.get(name, 0) + 1
    total = sum(authors.values())
    ranked = sorted(authors.items(), key=lambda kv: kv[1], reverse=True)
    top_share = round(ranked[0][1] / total, 3) if total else 0
    return {
        "total_commits_in_window": total,
        "unique_committers": len(authors),
        "top_committer_share": top_share,
        "by_author": dict(ranked),
    }


def analyze_github(repo_url, github_days=DEFAULT_GITHUB_DAYS):
    """Analyze a GitHub repo — stars, commits, contributors, language.

    Commit history now uses a `since` window (default 60 days) and a raised
    per_page so commit cadence / committer concentration are computable (Bug 4).
    """
    if not repo_url:
        return None

    # Extract owner/repo from various URL formats
    match = re.search(r'github\.com/([^/]+)/([^/\s]+)', repo_url)
    if not match:
        return {"error": f"Cannot parse GitHub URL: {repo_url}"}

    owner = match.group(1)
    repo = match.group(2).rstrip('/')
    # Remove /tree/main etc
    repo = repo.split('/')[0]

    base = f"https://api.github.com/repos/{owner}/{repo}"

    result = {"owner": owner, "repo": repo, "url": f"https://github.com/{owner}/{repo}"}

    # Repo info
    data, _ = _github_get_json(base)
    if data:
        result["stars"] = data.get("stargazers_count", 0)
        result["forks"] = data.get("forks_count", 0)
        result["open_issues"] = data.get("open_issues_count", 0)
        result["language"] = data.get("language", "")
        result["updated_at"] = data.get("updated_at", "")
        result["created_at"] = data.get("created_at", "")
        result["description"] = data.get("description", "")
    else:
        result["repo_error"] = "could not fetch repo metadata"

    # Recent commits over a real time window (Bug 4)
    since = (datetime.now(timezone.utc) - timedelta(days=github_days)).isoformat()
    commits_url = (f"{base}/commits"
                   f"?per_page={GITHUB_COMMITS_PER_PAGE}"
                   f"&since={urllib.parse.quote(since)}")
    commits, _ = _github_get_json(commits_url)
    if commits is not None and isinstance(commits, list):
        result["commit_window_days"] = github_days
        result["recent_commits"] = [
            {
                "message": c.get("commit", {}).get("message", "").split('\n')[0][:100],
                "date": c.get("commit", {}).get("committer", {}).get("date", ""),
                "author": c.get("commit", {}).get("author", {}).get("name", ""),
            }
            for c in commits[:10]
        ]
        result["commits_in_window"] = len(commits)
        result["committer_concentration"] = _summarize_committers(commits)
        if commits:
            last_date = commits[0].get("commit", {}).get("committer", {}).get("date", "")
            if last_date:
                result["last_commit"] = last_date
                try:
                    last_dt = datetime.fromisoformat(last_date.replace('Z', '+00:00'))
                    days_ago = (datetime.now(last_dt.tzinfo) - last_dt).days
                    result["days_since_last_commit"] = days_ago
                except Exception:
                    pass
    else:
        result["commits_error"] = "could not fetch commits"

    # Contributors count
    contrib_url = f"{base}/contributors?per_page=1&anon=true"
    try:
        req = urllib.request.Request(contrib_url, headers=_github_headers())
        with urllib.request.urlopen(req, timeout=10) as resp:
            link = resp.headers.get('Link', '')
            if 'last' in link:
                m = re.search(r'page=(\d+)>; rel="last"', link)
                if m:
                    result["contributors"] = int(m.group(1))
            else:
                contributors = json.loads(resp.read().decode())
                result["contributors"] = len(contributors)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            _log("  [github] contributors HTTP 403 — auth/rate-limit. Set GITHUB_TOKEN.")
        result["contributors_error"] = f"HTTP {e.code}"
    except Exception as e:
        result["contributors_error"] = _redact(e)

    # README — the key to understanding how to mine
    try:
        readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md"
        req = urllib.request.Request(readme_url, headers={"User-Agent": "subnet-research"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            readme = resp.read().decode('utf-8', errors='ignore')
            # Keep first 8000 chars — enough for setup instructions
            result["readme"] = readme[:8000]
    except Exception:
        # Try master branch
        try:
            readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md"
            req = urllib.request.Request(readme_url, headers={"User-Agent": "subnet-research"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                readme = resp.read().decode('utf-8', errors='ignore')
                result["readme"] = readme[:8000]
        except Exception:
            pass

    return result


# ── Profitability Calculator ────────────────────────────────────────────────

def calculate_profitability(metagraph, tao_price_usd, reg_cost_tao, subnet_info=None):
    """Calculate mining profitability from metagraph data."""
    if not metagraph:
        return None

    result = {}
    avg_daily = metagraph.get("avg_miner_daily_tao", 0)
    earning = metagraph.get("earning_miners", 0)
    # Use subnet_info for active counts (most accurate), fall back to metagraph
    active = subnet_info.get("active_miners", 0) if subnet_info else metagraph.get("miners", 0)

    result["earning_miners"] = earning
    result["active_miners"] = active
    result["avg_daily_tao_per_miner"] = avg_daily
    result["avg_daily_usd_per_miner"] = round(avg_daily * tao_price_usd, 2) if tao_price_usd else 0
    result["top_daily_tao"] = metagraph.get("top_miner_daily_tao", 0)
    result["top_daily_usd"] = round(metagraph.get("top_miner_daily_tao", 0) * tao_price_usd, 2) if tao_price_usd else 0

    if reg_cost_tao and avg_daily > 0:
        result["reg_cost_tao"] = reg_cost_tao
        result["days_to_roi"] = round(reg_cost_tao / avg_daily, 1)

    # Competition score: lower is better (fewer miners competing for emission)
    total_emission = metagraph.get("miner_daily_emission_tao", 0)
    if active > 0 and total_emission > 0:
        result["competition_ratio"] = round(active / total_emission, 2)

    return result


# ── Report Commands ─────────────────────────────────────────────────────────

def _fetch_project_tweets(twitter_handle):
    """Fetch a project's own tweets, degrading gracefully if Desearch is absent."""
    if not DESEARCH_API_KEY:
        return None
    Desearch = _import_desearch()
    if Desearch is None:
        return None
    try:
        client = Desearch(api_key=DESEARCH_API_KEY)
        handle = twitter_handle.lstrip('@')
        own_tweets_resp = asyncio.run(client.x_user_posts(username=handle))
        # x_user_posts returns XUserPostsResponse — unwrap to a list
        own_tweets = None
        if hasattr(own_tweets_resp, 'posts'):
            own_tweets = own_tweets_resp.posts
        elif hasattr(own_tweets_resp, 'data'):
            own_tweets = own_tweets_resp.data
        elif isinstance(own_tweets_resp, list):
            own_tweets = own_tweets_resp
        elif isinstance(own_tweets_resp, dict):
            own_tweets = own_tweets_resp.get('posts') or own_tweets_resp.get('data') or []
        if own_tweets:
            return [
                {
                    "text": (t.get("text", "") if isinstance(t, dict) else getattr(t, "text", ""))[:280],
                    "date": t.get("created_at", "") if isinstance(t, dict) else getattr(t, "created_at", ""),
                    "likes": t.get("like_count", 0) if isinstance(t, dict) else getattr(t, "like_count", 0),
                    "views": t.get("view_count", 0) if isinstance(t, dict) else getattr(t, "view_count", 0),
                }
                for t in own_tweets[:10]
            ]
    except Exception as e:
        _log(f"  [desearch] project tweets error: {_redact(e)}")
    return None


def cmd_report(netuid):
    """Full intelligence report for a single subnet."""
    print(f"Generating intelligence report for Subnet {netuid}...\n", file=sys.stderr)
    _log(f"  [run-dir] {_RUN_DIR} (max-age {_CACHE_MAX_AGE}s, "
         f"cache {'on' if _CACHE_USE else 'off (read)'})")

    report = {"netuid": netuid, "generated_at": datetime.utcnow().isoformat() + "Z"}

    # 1. Identity
    print("  [1/8] Fetching identity...", file=sys.stderr)
    identity = get_subnet_identity(netuid)
    if identity:
        report["identity"] = identity

    subnet_name = identity.get("subnet_name", "") if identity else ""
    github_url = identity.get("github_repo", "") if identity else ""
    website_url = identity.get("website", "") if identity else ""
    twitter_handle = identity.get("twitter", "") if identity else ""

    # 2. Emission + Pools (NEVER-show raw fields — Bug 5 — moved to _internal)
    print("  [2/8] Fetching emission data...", file=sys.stderr)
    emission = get_subnet_emission(netuid)
    pools = get_subnet_pools(netuid)
    # Per references/live-data-fields.md, raw `emission` and `pools` must NOT be
    # surfaced in the operator-facing report. Keep them under "_internal" so the
    # report layer skips the subtree but the data remains for computation.
    internal = {}
    if emission:
        internal["emission"] = emission
    if pools:
        internal["pools"] = pools
    if internal:
        report["_internal"] = internal

    # 3. Subnet info (active miners/validators, reg cost, etc.)
    print("  [3/8] Fetching subnet info...", file=sys.stderr)
    subnet_info = get_subnet_info(netuid)
    if subnet_info:
        report["subnet_info"] = subnet_info
    reg_cost = subnet_info.get("registration_cost_tao", 0) if subnet_info else 0

    # 4. TAO price
    print("  [4/8] Fetching TAO price...", file=sys.stderr)
    price_data = get_tao_price()
    tao_price = 0
    if price_data:
        tao_price = price_data.get("price_usd", 0)
        report["tao_price_usd"] = tao_price

    # 5. Metagraph
    print("  [5/8] Fetching metagraph...", file=sys.stderr)
    metagraph = get_metagraph_summary(netuid)
    if metagraph:
        report["metagraph"] = metagraph

    # 6. Profitability
    profitability = calculate_profitability(metagraph, tao_price, reg_cost, subnet_info)
    if profitability:
        report["profitability"] = profitability

    # 7. GitHub
    print("  [6/8] Analyzing GitHub...", file=sys.stderr)
    if github_url:
        gh = cached_call(f"github_{netuid}",
                         lambda: analyze_github(github_url, _GITHUB_DAYS))
        if gh:
            report["github"] = gh

    # 8. X/Twitter sentiment — search for the project name specifically
    print("  [7/9] Searching X/Twitter...", file=sys.stderr)
    # Primary search: project name + subnet number
    if subnet_name:
        x_query = f"{subnet_name} bittensor"
    else:
        x_query = f"bittensor subnet {netuid}"
    x_data = cached_call(f"desearch_x_{netuid}",
                         lambda: desearch_x_search(x_query, count=20))
    if x_data:
        report["x_sentiment"] = x_data

    # Also get the project's own tweets if they have a Twitter handle
    if twitter_handle and twitter_handle.strip():
        print("  [7b/9] Fetching project's own tweets...", file=sys.stderr)
        project_tweets = cached_call(
            f"desearch_project_tweets_{netuid}",
            lambda: _fetch_project_tweets(twitter_handle))
        if project_tweets:
            report["project_tweets"] = project_tweets

    # 9. Web search — mining guides, setup instructions, reviews
    print("  [8/9] Running web search...", file=sys.stderr)
    web_query = f"bittensor {subnet_name} subnet {netuid} mining guide setup requirements"
    web_data = cached_call(f"desearch_web_{netuid}",
                           lambda: desearch_web_search(web_query))
    if web_data:
        report["web_research"] = web_data

    # 10. Crawl project website
    if website_url and website_url.startswith("http"):
        print("  [9/9] Crawling project website...", file=sys.stderr)
        site_content = cached_call(f"desearch_crawl_{netuid}",
                                   lambda: desearch_web_crawl(website_url))
        if site_content and len(site_content.strip()) > 50:
            report["website_content"] = site_content[:5000]

    print(f"\nReport complete for SN {netuid} ({subnet_name})", file=sys.stderr)
    persist_report(report)
    return report


def cmd_scan():
    """Quick scan of all subnets with identity + emission data."""
    print("Scanning all subnets via Taostats API...\n", file=sys.stderr)
    _log(f"  [run-dir] {_RUN_DIR} (max-age {_CACHE_MAX_AGE}s, "
         f"cache {'on' if _CACHE_USE else 'off (read)'})")

    identities = get_all_subnet_identities()
    emissions = get_all_subnet_emissions()
    price_data = get_tao_price()
    tao_price = price_data.get("price_usd", 0) if price_data else 0

    subnets = []
    for netuid, ident in sorted(identities.items()):
        entry = {
            "netuid": netuid,
            "name": ident.get("subnet_name") or "",
            "description": (ident.get("description") or "")[:100],
            "website": (ident.get("subnet_url") or "").strip(),
            "github": (ident.get("github_repo") or "").strip(),
            "twitter": (ident.get("twitter") or "").strip(),
        }

        em = emissions.get(netuid)
        if em:
            entry["tao_pool"] = round(int(em.get("tao_in_pool", 0)) / 1e9, 2)
            entry["alpha_rewards"] = em.get("alpha_rewards")

        subnets.append(entry)

    print(f"Scanned {len(subnets)} subnets", file=sys.stderr)
    result = {"subnets": subnets, "tao_price_usd": tao_price, "total_subnets": len(subnets)}
    persist_report(result, "scan.json")
    return result


def cmd_top(n=10):
    """Find top N most profitable subnets to mine."""
    print(f"Finding top {n} most profitable subnets...\n", file=sys.stderr)
    _log(f"  [run-dir] {_RUN_DIR} (max-age {_CACHE_MAX_AGE}s, "
         f"cache {'on' if _CACHE_USE else 'off (read)'})")

    identities = get_all_subnet_identities()
    price_data = get_tao_price()
    tao_price = price_data.get("price_usd", 0) if price_data else 0

    results = []
    netuids = sorted(identities.keys())

    for i, netuid in enumerate(netuids):
        if netuid == 0:
            continue  # Skip root subnet
        print(f"  [{i+1}/{len(netuids)}] Checking SN {netuid}...", file=sys.stderr)

        metagraph = get_metagraph_summary(netuid)
        if not metagraph:
            continue

        subnet_info = get_subnet_info(netuid)
        reg_cost = subnet_info.get("registration_cost_tao", 0) if subnet_info else 0
        profit = calculate_profitability(metagraph, tao_price, reg_cost, subnet_info)
        if not profit:
            continue

        ident = identities[netuid]
        entry = {
            "netuid": netuid,
            "name": ident.get("subnet_name") or "",
            "github": (ident.get("github_repo") or "").strip(),
            "active_miners": profit.get("active_miners", 0),
            "earning_miners": profit.get("earning_miners", 0),
            "avg_daily_tao": profit.get("avg_daily_tao_per_miner", 0),
            "avg_daily_usd": profit.get("avg_daily_usd_per_miner", 0),
            "top_daily_tao": profit.get("top_daily_tao", 0),
            "top_daily_usd": profit.get("top_daily_usd", 0),
            "reg_cost_tao": reg_cost,
            "days_to_roi": profit.get("days_to_roi"),
            "total_miner_emission_tao": metagraph.get("miner_daily_emission_tao", 0),
        }
        results.append(entry)

    # Sort by avg daily TAO per miner (descending)
    results.sort(key=lambda x: x.get("avg_daily_tao", 0), reverse=True)

    top = results[:n]
    print(f"\nTop {n} subnets by avg daily TAO per miner:", file=sys.stderr)
    for i, s in enumerate(top):
        print(f"  {i+1}. SN {s['netuid']} ({s['name']}) — {s['avg_daily_tao']:.4f} TAO/day (${s['avg_daily_usd']:.2f})", file=sys.stderr)

    result = {
        "top_subnets": top,
        "tao_price_usd": tao_price,
        "total_evaluated": len(results),
        "note": "Post-halving: network emits ~3,600 TAO/day (0.5 TAO/block). All figures from Taostats API."
    }
    persist_report(result, "top.json")
    return result


# ── Main ────────────────────────────────────────────────────────────────────

def _configure_cache(args, subkey):
    """Set the module-level cache config from parsed CLI args."""
    global _CACHE_MAX_AGE, _CACHE_USE, _RUN_DIR, _GITHUB_DAYS
    _CACHE_MAX_AGE = getattr(args, "max_age", DEFAULT_MAX_AGE)
    _CACHE_USE = not getattr(args, "no_cache", False)
    _GITHUB_DAYS = getattr(args, "github_days", DEFAULT_GITHUB_DAYS)
    _RUN_DIR = get_run_dir(subkey)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    parser = argparse.ArgumentParser(add_help=False)
    sub = parser.add_subparsers(dest="cmd")

    def _add_cache_flags(p):
        p.add_argument("--max-age", dest="max_age", type=int, default=DEFAULT_MAX_AGE,
                       help="reuse cached calls younger than this many seconds (default 3600)")
        p.add_argument("--no-cache", dest="no_cache", action="store_true",
                       help="ignore existing cache when reading (still persists fresh results)")

    p_report = sub.add_parser("report")
    p_report.add_argument("netuid", type=int)
    p_report.add_argument("--github-days", dest="github_days", type=int,
                          default=DEFAULT_GITHUB_DAYS,
                          help="GitHub commit history window in days (default 60)")
    _add_cache_flags(p_report)

    p_scan = sub.add_parser("scan")
    _add_cache_flags(p_scan)

    p_top = sub.add_parser("top")
    p_top.add_argument("n", type=int, nargs="?", default=10)
    _add_cache_flags(p_top)

    args = parser.parse_args()

    if args.cmd == "report":
        _configure_cache(args, args.netuid)
        result = cmd_report(args.netuid)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    elif args.cmd == "scan":
        _configure_cache(args, "_scan")
        result = cmd_scan()
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    elif args.cmd == "top":
        _configure_cache(args, "_top")
        result = cmd_top(args.n)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
