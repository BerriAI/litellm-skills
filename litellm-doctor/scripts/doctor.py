#!/usr/bin/env python3
"""Read-only health report for a LiteLLM proxy.

Stdlib only. Every call is a GET. Runs the checks an admin would run by hand
(liveness, readiness, version, license, models, callbacks, recent failures),
optionally inspects one key and probes one model, and prints a summary with
OK / WARN / FAIL lines and a likely cause for each failure group.

Examples:
  python3 doctor.py                                  # uses LITELLM_BASE_URL / LITELLM_API_KEY
  python3 doctor.py --key billing-agent-prod-hash --model gpt-5.5
  python3 doctor.py --hours 6 --json
  python3 doctor.py --probe-model claude-sonnet-5-5  # GET /health?model=..., makes one real LLM call

Written against LiteLLM v1.103 (September 2026).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

OK, WARN, FAIL, INFO = "OK", "WARN", "FAIL", "INFO"

# --------------------------------------------------------------------------- #
# Pure helpers (exercised by tests/test_doctor_script.py without network)
# --------------------------------------------------------------------------- #


def normalize_base_url(url: str) -> str:
    """Strip whitespace and trailing slashes; add http:// when no scheme is given."""
    url = (url or "").strip().rstrip("/")
    if url and "://" not in url:
        url = "http://" + url
    return url


def parse_time(value: Any) -> Optional[_dt.datetime]:
    """Parse an ISO timestamp from the proxy into an aware UTC datetime, or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = _dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc)


def error_text(body: Any) -> str:
    """Pull the human message out of a proxy error body (dict or text)."""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err)
        if err is not None:
            return str(err)
        detail = body.get("detail")
        if isinstance(detail, dict):
            return str(detail.get("error") or detail)
        if detail is not None:
            return str(detail)
    return str(body or "")


def error_type(body: Any) -> str:
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        return str(body["error"].get("type") or "")
    return ""


def classify_failure(
    status: Optional[int],
    message: str = "",
    err_type: str = "",
    rate_limit_category: str = "",
    rate_limit_type: str = "",
) -> str:
    """Map an HTTP status plus the proxy's error text to a likely cause and next check."""
    msg = (message or "").lower()
    t = (err_type or "").lower()
    if status is None:
        return "Could not reach the proxy: wrong URL, proxy down, or network/TLS problem."
    if t == "budget_exceeded" or "budget has been exceeded" in msg or rate_limit_type == "budget":
        return "Budget exceeded (429 on v1.103 and earlier, 422 on newer builds). Check /key/info spend vs max_budget, then the team and user budgets."
    if status == 401:
        if "expired key" in msg or t == "expired_key":
            return "Key expired. Extend with /key/update duration or issue a new key."
        if "blocked" in msg:
            return "Key or team is blocked. /key/unblock (or /team/unblock) if intended."
        if "only proxy admin" in msg:
            return "Valid key but not a proxy admin, calling an admin route. Use an admin key."
        if "no api key passed" in msg or "malformed" in msg:
            return "No key or wrong header. Send Authorization: Bearer sk-... (or x-litellm-api-key)."
        return "Key not recognized: typo, deleted key, or a key from another proxy/database."
    if status == 403:
        if "model_access_denied" in t or "not available for this api key" in msg or "not allowed to access model" in msg:
            return "Model not in the key's (or team's/user's) allowed models. Compare /key/info models with the model name."
        if "not allowed to call this route" in msg:
            return "Key's allowed_routes / key_type (e.g. llm_api) forbids this route."
        if "enterprise" in msg or "premium" in msg:
            return "Enterprise-only feature on a proxy without a license (see /health/license)."
        return "Authenticated but not permitted (role, team admin scope, or route restriction)."
    if status == 400 and "invalid model name" in msg:
        return "Model name not on the proxy. List /v1/models with the same key; check aliases and wildcards."
    if status == 404:
        return "Not found: wrong ID or path, or the endpoint does not exist on this proxy version."
    if status == 429:
        if rate_limit_category.startswith("vendor"):
            return "Provider rate limit (upstream 429). Add deployments/fallbacks or raise the provider quota."
        if "rate limit exceeded for" in msg or rate_limit_category.startswith("litellm"):
            return "Proxy rpm/tpm/parallel limit hit; the message names the key/team/user and limit. Raise it or wait for reset."
        if "cooldown" in msg or "no deployments available" in msg:
            return "All deployments for the model are cooling down after errors. Check /health?model=..."
        return "Rate limited. Check error_information.error_rate_limit_category in /spend/logs/v2 to tell proxy vs provider."
    if status == 503 and ("database" in msg or "db" in t or t == "no_db_connection"):
        return "Database unreachable. Check DATABASE_URL, Postgres health, and /health/readiness db field."
    if status in (408, 504) or "timeout" in msg or "timed out" in msg:
        return "Provider or proxy timeout. Check /health?model=..., request_timeout, and provider status."
    if status is not None and status >= 500:
        if "no deployments available" in msg or "cooldown" in msg:
            return "No healthy deployment for the model group. Run /health?model=... for the provider error."
        return "Upstream provider or proxy error; the message usually names the provider. Probe with /health?model=..."
    if status == 422:
        return "Request body failed validation; the message names the field."
    return "See the error message."


def model_allowed(allowed: Iterable[str], model: str, known_models: Optional[Iterable[str]] = None) -> str:
    """Would a key/team `models` list admit `model`? Returns 'yes', 'no', or 'maybe'.

    Entries that are not model names on the proxy may be access groups, which only
    the proxy can expand, so an unmatched list containing one is 'maybe'. Pass the
    admin's /v1/models ids as `known_models` to tell the two apart.
    """
    names = [m for m in (allowed or []) if isinstance(m, str)]
    if not names:
        return "yes"  # empty list inherits the owner's access
    if model in names or "*" in names or "all-proxy-models" in names:
        return "yes"
    for pattern in names:
        if pattern.endswith("*") and model.startswith(pattern[:-1]):
            return "yes"
    if known_models is None:
        return "maybe"
    known = set(known_models)
    return "maybe" if any(n not in known for n in names) else "no"


def summarize_key(
    info: Dict[str, Any],
    now: Optional[_dt.datetime] = None,
    model: Optional[str] = None,
    known_models: Optional[Iterable[str]] = None,
) -> List[Tuple[str, str]]:
    """Findings for one /key/info `info` object, worst first."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    out: List[Tuple[str, str]] = []
    label = info.get("key_alias") or info.get("token") or "key"
    if info.get("blocked"):
        out.append((FAIL, f"{label} is blocked (/key/unblock to restore)."))
    expires = parse_time(info.get("expires"))
    if expires is not None and expires <= now:
        out.append((FAIL, f"{label} expired at {expires.isoformat()}."))
    elif expires is not None and (expires - now).days < 7:
        out.append((WARN, f"{label} expires soon: {expires.isoformat()}."))
    spend = info.get("spend") or 0
    max_budget = info.get("max_budget")
    if isinstance(max_budget, (int, float)):
        if spend >= max_budget:
            reset = info.get("budget_reset_at") or "no reset scheduled"
            out.append((FAIL, f"{label} is over budget: spend {spend:.4f} >= max_budget {max_budget} (resets: {reset})."))
        elif max_budget > 0 and spend / max_budget >= 0.8:
            out.append((WARN, f"{label} has used {spend / max_budget:.0%} of its ${max_budget} budget."))
    models = info.get("models") or []
    if model:
        verdict = model_allowed(models, model, known_models)
        if verdict == "no":
            out.append((FAIL, f"{model} is not in {label}'s models {models}."))
        elif verdict == "maybe":
            out.append((WARN, f"{model} is not listed in {models}; allowed only if one is an access group containing it."))
        else:
            out.append((OK, f"{label} may call {model} (team and user model limits still apply)."))
    if info.get("key_type") == "llm_api":
        out.append((INFO, f"{label} is key_type llm_api: it cannot call admin/management routes."))
    limits = {k: info.get(k) for k in ("rpm_limit", "tpm_limit", "max_parallel_requests") if info.get(k) is not None}
    if limits:
        out.append((INFO, "limits: " + ", ".join(f"{k}={v}" for k, v in limits.items())))
    if info.get("team_id"):
        out.append((INFO, f"belongs to team {info['team_id']}: team budget, models, and limits also apply (/team/info)."))
    if not any(level in (FAIL, WARN) for level, _ in out):
        out.insert(0, (OK, f"{label}: not blocked, not expired, within budget."))
    return out


def summarize_failures(rows: Iterable[Dict[str, Any]], top: int = 5) -> List[Dict[str, Any]]:
    """Group failed /spend/logs/v2 rows by (status code, error class, model group)."""
    groups: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        info = metadata.get("error_information") if isinstance(metadata.get("error_information"), dict) else {}
        code = str(info.get("error_code") or "?")
        klass = str(info.get("error_class") or "?")
        group = str(row.get("model_group") or row.get("model") or "?")
        key = (code, klass, group)
        entry = groups.setdefault(
            key,
            {
                "error_code": code,
                "error_class": klass,
                "model_group": group,
                "count": 0,
                "provider": info.get("llm_provider") or row.get("custom_llm_provider") or "",
                "rate_limit_category": info.get("error_rate_limit_category") or "",
                "rate_limit_type": info.get("error_rate_limit_type") or "",
                "sample": str(info.get("error_message") or "")[:200],
                "last_request_id": row.get("request_id"),
            },
        )
        entry["count"] += 1
    ranked = sorted(groups.values(), key=lambda e: e["count"], reverse=True)[:top]
    for entry in ranked:
        status = int(entry["error_code"]) if entry["error_code"].isdigit() else None
        entry["likely_cause"] = classify_failure(
            status if status is not None else 500,
            entry["sample"] + " " + entry["error_class"],
            rate_limit_category=str(entry["rate_limit_category"]),
            rate_limit_type=str(entry["rate_limit_type"]),
        )
    return ranked


def summarize_health(payload: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Findings from GET /health (healthy_endpoints / unhealthy_endpoints)."""
    healthy = payload.get("healthy_endpoints") or []
    unhealthy = payload.get("unhealthy_endpoints") or []
    out: List[Tuple[str, str]] = []
    if not healthy and not unhealthy:
        return [(WARN, "no deployments checked (none visible to this key, or none configured)")]
    out.append((OK if not unhealthy else (FAIL if not healthy else WARN), f"{len(healthy)} healthy, {len(unhealthy)} unhealthy deployment(s)"))
    for ep in unhealthy[:10]:
        err = str(ep.get("error") or "").splitlines()[0][:200] if ep.get("error") else "no error text"
        out.append((FAIL, f"{ep.get('model', '?')}: {err}"))
    return out


def summarize_readiness(payload: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Findings from /health/readiness or /health/readiness/details."""
    out: List[Tuple[str, str]] = []
    status = payload.get("status")
    db = payload.get("db")
    out.append((OK if status == "healthy" else FAIL, f"status={status}"))
    if db == "connected":
        out.append((OK, "database connected"))
    elif db == "Not connected":
        out.append((WARN, "no database configured: keys, spend, and runtime models/guardrails are unavailable"))
    elif db is not None:
        out.append((FAIL, f"database {db}: auth and spend writes will fail unless allow_requests_on_db_unavailable is set"))
    if payload.get("is_detailed_debug"):
        out.append((WARN, "detailed debug logging is on (slow and verbose; turn off in production)"))
    if payload.get("show_no_redis_warning"):
        out.append((WARN, "multiple workers/instances without Redis: rate limits and caches are per-process"))
    return out


def status_line(level: str, name: str, detail: str) -> str:
    return f"[{level:<4}] {name}: {detail}"


# --------------------------------------------------------------------------- #
# Network
# --------------------------------------------------------------------------- #


def http_get(base: str, path: str, api_key: Optional[str], params: Optional[Dict[str, Any]] = None, timeout: float = 15.0) -> Tuple[Optional[int], Any, float]:
    """GET base+path. Returns (status or None if unreachable, parsed body, seconds)."""
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        status = e.code
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, str(getattr(e, "reason", e)), time.monotonic() - started
    elapsed = time.monotonic() - started
    try:
        return status, json.loads(raw), elapsed
    except ValueError:
        return status, raw, elapsed


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


def run(args: argparse.Namespace) -> Dict[str, Any]:
    base = normalize_base_url(args.base_url)
    key = args.api_key
    report: Dict[str, Any] = {"base_url": base, "checks": []}

    def add(name: str, level: str, detail: str, **extra: Any) -> None:
        report["checks"].append({"check": name, "level": level, "detail": detail, **extra})

    def get(path: str, auth: bool = True, **params: Any) -> Tuple[Optional[int], Any, float]:
        return http_get(base, path, key if auth else None, params or None, timeout=args.timeout)

    status, body, secs = get("/health/liveliness", auth=False)
    if status is None:
        add("liveness", FAIL, f"unreachable: {body}. " + classify_failure(None))
        return report
    add("liveness", OK if status == 200 else FAIL, f"HTTP {status} in {secs * 1000:.0f} ms")

    status, body, _ = get("/health/readiness", auth=False)
    if isinstance(body, dict):
        for level, detail in summarize_readiness(body):
            add("readiness", level, detail)
    else:
        add("readiness", FAIL, f"HTTP {status}: {error_text(body)[:200]}")

    status, body, _ = get("/health/readiness/details")
    if status == 200 and isinstance(body, dict):
        report["litellm_version"] = body.get("litellm_version")
        add("version", INFO, f"litellm {body.get('litellm_version')}, log_level={body.get('log_level')}, cache={body.get('cache')}")
        for level, detail in summarize_readiness(body)[1:]:
            if level != OK:
                add("readiness_details", level, detail)
    else:
        msg = error_text(body)[:200].rstrip(". ")
        add("auth", FAIL, f"HTTP {status}: {msg}. " + classify_failure(status, error_text(body), error_type(body)))
        if status in (401, 403):
            return report  # every remaining check needs a working key

    status, body, _ = get("/debug/report")
    if status == 200 and isinstance(body, dict):
        add("environment", INFO, f"deployment={body.get('deployment')}, python={body.get('python_version')}")
        report["config_lines"] = body.get("config_lines")
    elif status == 403:
        add("environment", INFO, "/debug/report needs a proxy admin key")

    status, body, _ = get("/health/license")
    if status == 200 and isinstance(body, dict):
        expiry = body.get("expiration_date")
        add("license", INFO, f"{body.get('license_type')}" + (f" (expires {expiry})" if expiry else ""))

    status, body, _ = get("/v1/models")
    if status == 200 and isinstance(body, dict):
        ids = [m.get("id") for m in body.get("data") or [] if isinstance(m, dict)]
        add("models", OK if ids else WARN, f"{len(ids)} model(s) visible to this key" + ("" if ids else ": add one or check key/team models"))
        report["models"] = ids

    status, body, _ = get("/model/deprecations")
    if status == 200 and isinstance(body, dict):
        dep = [m.get("model_name") for m in body.get("deprecated") or [] if isinstance(m, dict)]
        soon = [m.get("model_name") for m in body.get("imminent") or [] if isinstance(m, dict)]
        if dep:
            add("deprecations", FAIL, f"past deprecation date: {dep}")
        if soon:
            add("deprecations", WARN, f"deprecating within 30 days: {soon}")

    status, body, _ = get("/active/callbacks")
    if status == 200 and isinstance(body, dict):
        add("callbacks", INFO, f"{body.get('num_callbacks')} callback(s), alerting={body.get('alerting')}")

    end = _dt.datetime.now(_dt.timezone.utc)
    start = end - _dt.timedelta(hours=args.hours)
    fmt = "%Y-%m-%d %H:%M:%S"
    status, body, _ = get(
        "/spend/logs/v2",
        start_date=start.strftime(fmt),
        end_date=end.strftime(fmt),
        status_filter="failure",
        page_size=100,
        exclude_internal_health_checks="true",
    )
    if status == 200 and isinstance(body, dict):
        rows = body.get("data") or []
        total = body.get("total", len(rows))
        groups = summarize_failures(rows)
        report["failures"] = groups
        add("failures", OK if not total else WARN, f"{total} failed request(s) in the last {args.hours}h (grouped from the latest {len(rows)})")
        for g in groups:
            add("failures", WARN, f"{g['count']}x HTTP {g['error_code']} {g['error_class']} on {g['model_group']}: {g['likely_cause']}", sample=g["sample"], request_id=g["last_request_id"])
    elif status is not None:
        add("failures", INFO, f"/spend/logs/v2 HTTP {status} (needs a database and an admin or viewer key)")

    if args.key:
        status, body, _ = get("/key/info", key=args.key)
        if status == 200 and isinstance(body, dict) and isinstance(body.get("info"), dict):
            for level, detail in summarize_key(body["info"], model=args.model, known_models=report.get("models")):
                add("key", level, detail)
        else:
            add("key", FAIL, f"/key/info HTTP {status}: {error_text(body)[:200]}")
    elif args.model and report.get("models") is not None and args.model not in report["models"]:
        add("model", WARN, f"{args.model} is not in /v1/models for this key (name typo, alias, or access)")

    if args.probe_model:
        status, body, secs = get("/health", model=args.probe_model)
        if isinstance(body, dict) and ("healthy_endpoints" in body or "unhealthy_endpoints" in body):
            for i, (level, detail) in enumerate(summarize_health(body)):
                add("probe", level, f"{detail} ({secs:.1f}s)" if i == 0 else detail)
        else:
            add("probe", FAIL, f"/health?model={args.probe_model} HTTP {status}: {error_text(body)[:200]}")
    return report


def render(report: Dict[str, Any]) -> str:
    lines = [f"LiteLLM doctor: {report['base_url']}  version={report.get('litellm_version', '?')}"]
    lines += [status_line(c["level"], c["check"], c["detail"]) for c in report["checks"]]
    counts = Counter(c["level"] for c in report["checks"])
    lines.append(f"Summary: {counts.get(FAIL, 0)} fail, {counts.get(WARN, 0)} warn, {counts.get(OK, 0)} ok")
    return "\n".join(lines)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Read-only LiteLLM proxy diagnostics (GET requests only).")
    p.add_argument("--base-url", default=os.environ.get("LITELLM_BASE_URL", ""), help="default: $LITELLM_BASE_URL")
    p.add_argument("--api-key", default=os.environ.get("LITELLM_API_KEY", ""), help="default: $LITELLM_API_KEY")
    p.add_argument("--key", help="a virtual key (sk-...) or its hash to inspect with /key/info")
    p.add_argument("--model", help="with --key: can the key call this model?")
    p.add_argument("--probe-model", help="GET /health?model=NAME: one real call per deployment of that model")
    p.add_argument("--hours", type=int, default=24, help="failure lookback window (default 24)")
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--json", action="store_true", help="print the raw report as JSON")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.base_url:
        print("Set LITELLM_BASE_URL or pass --base-url.", file=sys.stderr)
        return 2
    report = run(args)
    print(json.dumps(report, indent=2, default=str) if args.json else render(report))
    return 1 if any(c["level"] == FAIL for c in report["checks"]) else 0


if __name__ == "__main__":
    sys.exit(main())
