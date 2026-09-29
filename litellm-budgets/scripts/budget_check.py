#!/usr/bin/env python3
"""Who is near or over budget on a LiteLLM proxy.

Stdlib only. Reads the running budget counters (`spend`) and caps
(`max_budget`, `soft_budget`) of keys, internal users, teams, organizations,
customers (end users) and model access groups, and lists everything at or above
a threshold of its cap.

`spend` on these objects is the counter enforcement compares against
`max_budget`; it resets every `budget_duration`. It is not lifetime spend (use
the litellm-usage skill for that).

Examples:
  python3 budget_check.py                       # everything at >= 80% of its cap
  python3 budget_check.py --threshold 0.5 --only keys,teams
  python3 budget_check.py --json

Written against LiteLLM v1.103 (September 2026).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, Optional

KINDS = ("keys", "users", "teams", "orgs", "customers", "access_groups")
MAX_PAGES = 1000


def num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _budget_table(obj: Dict[str, Any]) -> Dict[str, Any]:
    table = obj.get("litellm_budget_table")
    return table if isinstance(table, dict) else {}


def _first(*values: Any) -> Optional[float]:
    for value in values:
        parsed = num(value)
        if parsed is not None:
            return parsed
    return None


def normalize(kind: str, obj: Dict[str, Any]) -> Dict[str, Any]:
    """Map one list-endpoint object onto {kind, id, label, spend, max_budget, soft_budget, ...}."""
    table = _budget_table(obj)
    if kind == "keys":
        ident = obj.get("token") or obj.get("key_name") or "?"
        label = obj.get("key_alias") or obj.get("key_name") or ident[:12]
        max_budget = _first(obj.get("max_budget"), table.get("max_budget"))
        soft = _first(obj.get("soft_budget"), table.get("soft_budget"))
        spend = num(obj.get("spend"))
    elif kind == "users":
        ident = obj.get("user_id") or "?"
        label = obj.get("user_email") or obj.get("user_alias") or ident
        max_budget, soft, spend = num(obj.get("max_budget")), None, num(obj.get("spend"))
    elif kind == "teams":
        ident = obj.get("team_id") or "?"
        label = obj.get("team_alias") or ident
        max_budget, soft, spend = num(obj.get("max_budget")), num(obj.get("soft_budget")), num(obj.get("spend"))
    elif kind == "orgs":
        ident = obj.get("organization_id") or "?"
        label = obj.get("organization_alias") or ident
        max_budget = _first(table.get("max_budget"), obj.get("max_budget"))
        soft = _first(table.get("soft_budget"), obj.get("soft_budget"))
        spend = num(obj.get("spend"))
    elif kind == "customers":
        ident = obj.get("user_id") or "?"
        label = obj.get("alias") or ident
        max_budget, soft, spend = num(table.get("max_budget")), num(table.get("soft_budget")), num(obj.get("spend"))
    elif kind == "access_groups":
        ident = obj.get("access_group") or "?"
        label = ident
        budget = obj.get("budget") if isinstance(obj.get("budget"), dict) else {}
        max_budget, soft, spend = num(budget.get("max_budget")), num(budget.get("soft_budget")), num(obj.get("spend"))
    else:
        raise ValueError(f"unknown kind {kind!r}")
    return {
        "kind": kind,
        "id": ident,
        "label": str(label),
        "spend": spend or 0.0,
        "max_budget": max_budget,
        "soft_budget": soft,
        "budget_duration": obj.get("budget_duration") or table.get("budget_duration") or (obj.get("budget") or {}).get("budget_duration"),
        "budget_reset_at": obj.get("budget_reset_at") or table.get("budget_reset_at") or (obj.get("budget") or {}).get("budget_reset_at"),
        "blocked": bool(obj.get("blocked")),
    }


def evaluate(items: Iterable[Dict[str, Any]], threshold: float = 0.8) -> List[Dict[str, Any]]:
    """Keep items at or above `threshold` of max_budget, or past their soft_budget.

    status: "over" (spend >= max_budget, requests are being rejected),
            "near" (>= threshold of max_budget), or "soft" (past soft_budget only).
    A max_budget of 0 means zero allowance on v1.103+ (it used to mean unlimited for orgs).
    """
    flagged = []
    for item in items:
        spend = item.get("spend") or 0.0
        cap = item.get("max_budget")
        soft = item.get("soft_budget")
        pct = None
        status = None
        if cap is not None:
            # max_budget 0 is a zero allowance: every request is refused.
            pct = spend / cap if cap > 0 else None
            if spend >= cap:
                status = "over"
            elif pct >= threshold:
                status = "near"
        if status is None and soft is not None and soft > 0 and spend >= soft:
            status = "soft"
        if status is None:
            continue
        flagged.append({**item, "pct_of_max": pct, "status": status})
    order = {"over": 0, "near": 1, "soft": 2}
    flagged.sort(key=lambda r: (order[r["status"]], -(r["pct_of_max"] if r["pct_of_max"] is not None else 0), -r["spend"]))
    return flagged


def render_text(flagged: List[Dict[str, Any]], threshold: float, counted: Dict[str, int]) -> str:
    lines = [
        f"Budgets at >= {threshold:.0%} of max_budget (or past soft_budget). Checked: "
        + ", ".join(f"{k}={v}" for k, v in counted.items())
    ]
    if not flagged:
        lines.append("Nothing is near or over budget.")
        return "\n".join(lines)
    header = f"{'Status':<6} {'Kind':<13} {'Name':<40} {'Spend':>12} {'Max':>12} {'Used':>7}  Resets"
    lines += [header, "-" * len(header)]
    for r in flagged:
        cap = "-" if r["max_budget"] is None else f"${r['max_budget']:,.2f}"
        pct = "-" if r["pct_of_max"] is None else f"{r['pct_of_max']:.0%}"
        resets = r.get("budget_reset_at") or (f"every {r['budget_duration']}" if r.get("budget_duration") else "never")
        lines.append(
            f"{r['status']:<6} {r['kind']:<13} {r['label'][:40]:<40} {'$' + format(r['spend'], ',.2f'):>12} {cap:>12} {pct:>7}  {resets}"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #


class HttpError(Exception):
    def __init__(self, status: int, body: str, path: str):
        super().__init__(f"HTTP {status} from {path}: {body[:300]}")
        self.status = status


def make_getter(base_url: str, api_key: str, timeout: float = 60) -> Callable[[str, Dict[str, Any]], Any]:
    base = base_url.rstrip("/")

    def get_json(path: str, params: Dict[str, Any]) -> Any:
        url = f"{base}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8") or "null")
        except urllib.error.HTTPError as e:
            raise HttpError(e.code, e.read().decode("utf-8", "replace"), path) from None

    return get_json


def _paged(get_json: Callable[[str, Dict[str, Any]], Any], path: str, list_field: str, params: Dict[str, Any], page_param: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    page = 1
    while page <= MAX_PAGES:
        body = get_json(path, {**params, page_param: page}) or {}
        rows = body.get(list_field) or []
        out.extend(rows)
        total_pages = int(num(body.get("total_pages")) or 1)
        if not rows or page >= total_pages:
            break
        page += 1
    return out


def fetch(kind: str, get_json: Callable[[str, Dict[str, Any]], Any]) -> List[Dict[str, Any]]:
    if kind == "keys":
        return _paged(get_json, "/key/list", "keys", {"return_full_object": "true", "size": 100}, "page")
    if kind == "users":
        return _paged(get_json, "/user/list", "users", {"page_size": 100}, "page")
    if kind == "teams":
        return _paged(get_json, "/v2/team/list", "teams", {"page_size": 100}, "page")
    if kind == "orgs":
        body = get_json("/organization/list", {})
        return body if isinstance(body, list) else []
    if kind == "customers":
        body = get_json("/customer/list", {})
        return body if isinstance(body, list) else []
    if kind == "access_groups":
        body = get_json("/access_group/list", {}) or {}
        return body.get("access_groups") or []
    raise ValueError(kind)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="List LiteLLM objects near or over budget")
    p.add_argument("--base-url", default=os.environ.get("LITELLM_BASE_URL"))
    p.add_argument("--api-key", default=os.environ.get("LITELLM_API_KEY"))
    p.add_argument("--threshold", type=float, default=0.8, help="fraction of max_budget to flag (default 0.8)")
    p.add_argument("--only", default=",".join(KINDS), help=f"comma-separated subset of: {', '.join(KINDS)}")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    if not args.base_url or not args.api_key:
        print("Set LITELLM_BASE_URL and LITELLM_API_KEY (or pass --base-url / --api-key).", file=sys.stderr)
        return 2
    kinds = [k.strip() for k in args.only.split(",") if k.strip()]
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        print(f"unknown --only value(s): {', '.join(bad)}", file=sys.stderr)
        return 2

    get_json = make_getter(args.base_url, args.api_key)
    items: List[Dict[str, Any]] = []
    counted: Dict[str, int] = {}
    skipped: Dict[str, str] = {}
    for kind in kinds:
        try:
            objs = fetch(kind, get_json)
        except HttpError as e:
            # 404 = route not on this proxy version (access groups need v1.100+); 401/403 = key lacks the role.
            skipped[kind] = f"HTTP {e.status}"
            continue
        except urllib.error.URLError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        counted[kind] = len(objs)
        items.extend(normalize(kind, o) for o in objs if isinstance(o, dict))

    flagged = evaluate(items, args.threshold)
    if args.json:
        print(json.dumps({"threshold": args.threshold, "checked": counted, "skipped": skipped, "flagged": flagged}, indent=2, default=str))
    else:
        print(render_text(flagged, args.threshold, counted))
        for kind, why in skipped.items():
            print(f"Skipped {kind}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
