#!/usr/bin/env python3
"""Daily spend / token / request report for a LiteLLM proxy.

Stdlib only. Calls the right /<entity>/daily/activity endpoint, prefers the
unpaginated /aggregated variant where one exists (user, team), otherwise walks
pages until metadata.has_more is false, merges rows that share a date across
pages, and prints a Date | Requests | Tokens | Spend table with totals.

Examples:
  python3 usage_report.py                              # whole proxy, this month
  python3 usage_report.py --by team --ids team-a,team-b --top models
  python3 usage_report.py --by tag --ids job:nightly-eval --start 2026-09-01 --end 2026-09-28
  python3 usage_report.py --by customer --top entities --json

Written against LiteLLM v1.103 (September 2026).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

# by -> (paginated path, id query param, aggregated path or None, id param is a CSV list)
ENDPOINTS: Dict[str, Tuple[str, Optional[str], Optional[str], bool]] = {
    "overall": ("/user/daily/activity", None, "/user/daily/activity/aggregated", False),
    "user": ("/user/daily/activity", "user_id", "/user/daily/activity/aggregated", False),
    "team": ("/team/daily/activity", "team_ids", "/team/daily/activity/aggregated", True),
    "org": ("/organization/daily/activity", "organization_ids", None, True),
    "tag": ("/tag/daily/activity", "tags", None, True),
    "customer": ("/customer/daily/activity", "end_user_ids", None, True),
    "agent": ("/agent/daily/activity", "agent_ids", None, True),
}

# Aggregated endpoints that also return breakdown.entities. The user one does not.
AGGREGATED_HAS_ENTITIES = {"team"}
TEAM_AGGREGATED_MAX_DAYS = 400
PAGE_SIZE = 1000  # /user/daily/activity caps page_size at 1000; the others are uncapped
MAX_PAGES = 10000

BREAKDOWN_DIMENSIONS = ("models", "model_groups", "providers", "endpoints", "api_keys", "mcp_servers", "entities")
TOP_CHOICES = ("models", "model_groups", "providers", "endpoints", "api_keys", "mcp_servers", "entities")

ENTITY_LABEL_FIELDS = ("team_alias", "organization_alias", "alias", "user_email", "user_alias", "agent_name", "name")


# --------------------------------------------------------------------------- #
# Pure helpers (exercised by tests with fixture JSON)
# --------------------------------------------------------------------------- #



def money(value: float) -> str:
    """USD with 4 decimals, or 2 significant digits for sub-cent amounts so tiny spend is not rounded away."""
    if value and abs(value) < 0.01:
        return "$" + format(float(f"{value:.2g}"), "f").rstrip("0")
    return "$" + format(value, ",.4f")

def num(value: Any) -> float:
    """Coerce a metric value to a number; None, strings and junk become 0."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def add_metrics(into: Dict[str, Any], other: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sum every numeric field of `other` into `into` (SpendMetrics-shaped dicts)."""
    for key, value in (other or {}).items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        into[key] = num(into.get(key)) + value
    return into


def default_range(today: Optional[_dt.date] = None) -> Tuple[str, str]:
    """First day of the current month through today, as YYYY-MM-DD."""
    today = today or _dt.datetime.now(_dt.timezone.utc).date()
    return today.replace(day=1).isoformat(), today.isoformat()


def days_between(start: str, end: str) -> int:
    return (_dt.date.fromisoformat(end) - _dt.date.fromisoformat(start)).days


def split_ids(ids: Optional[str]) -> List[str]:
    return [part.strip() for part in (ids or "").split(",") if part.strip()]


def plan_requests(
    by: str,
    ids: List[str],
    start: str,
    end: str,
    model: Optional[str] = None,
    key_hash: Optional[str] = None,
    need_entities: bool = False,
    prefer_aggregated: bool = True,
) -> List[Dict[str, Any]]:
    """Return the list of calls to make. Each item: {path, params, paginated, entity}.

    `entity` is set when one call covers exactly one id of an endpoint whose id
    filter is singular (user_id), so the caller can label the rows afterwards.
    """
    if by not in ENDPOINTS:
        raise ValueError(f"unknown --by {by!r}; choose one of {', '.join(ENDPOINTS)}")
    paginated_path, id_param, aggregated_path, id_is_list = ENDPOINTS[by]
    if by == "overall":
        ids = []

    use_aggregated = bool(prefer_aggregated and aggregated_path)
    if use_aggregated and need_entities and by not in AGGREGATED_HAS_ENTITIES and not (by == "user" and ids):
        # /user/daily/activity/aggregated has no breakdown.entities; per-user rows
        # for an unfiltered view only come back from the paginated endpoint.
        use_aggregated = False
    if use_aggregated and by == "team" and days_between(start, end) > TEAM_AGGREGATED_MAX_DAYS:
        use_aggregated = False

    base: Dict[str, Any] = {"start_date": start, "end_date": end}
    if model:
        base["model"] = model
    if key_hash:
        base["api_key"] = key_hash

    def one(params: Dict[str, Any], entity: Optional[str]) -> Dict[str, Any]:
        path = aggregated_path if use_aggregated else paginated_path
        if not use_aggregated:
            params = {**params, "page_size": PAGE_SIZE}
        return {"path": path, "params": params, "paginated": not use_aggregated, "entity": entity}

    if not ids or id_param is None:
        return [one(dict(base), None)]
    if id_is_list:
        return [one({**base, id_param: ",".join(ids)}, None)]
    return [one({**base, id_param: single}, single) for single in ids]


def fetch_all(get_json: Callable[[str, Dict[str, Any]], Dict[str, Any]], request: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Call one planned request; walk pages until has_more is false. Returns raw result rows."""
    if not request.get("paginated"):
        body = get_json(request["path"], request["params"]) or {}
        return list(body.get("results") or [])

    rows: List[Dict[str, Any]] = []
    page = 1
    while page <= MAX_PAGES:
        body = get_json(request["path"], {**request["params"], "page": page}) or {}
        results = list(body.get("results") or [])
        rows.extend(results)
        meta = body.get("metadata") or {}
        has_more = meta.get("has_more")
        if has_more is None:  # very old proxies: fall back to total_pages
            has_more = page < int(num(meta.get("total_pages")) or 0)
        if not has_more or not results:
            break
        page += 1
    return rows


def label_entity(rows: Iterable[Dict[str, Any]], entity_id: str) -> List[Dict[str, Any]]:
    """Attribute each day's metrics to breakdown.entities[entity_id] (used for per-user loops)."""
    labelled = []
    for row in rows:
        row = dict(row)
        breakdown = dict(row.get("breakdown") or {})
        breakdown["entities"] = {entity_id: {"metrics": dict(row.get("metrics") or {}), "metadata": {}}}
        row["breakdown"] = breakdown
        labelled.append(row)
    return labelled


def merge_days(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Merge rows by date. A busy date spans several pages, so never assume one row per day."""
    days: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        date = str(row.get("date") or "unknown")[:10]
        day = days.setdefault(date, {"date": date, "metrics": {}, "breakdown": {}})
        add_metrics(day["metrics"], row.get("metrics"))
        for dim, entries in (row.get("breakdown") or {}).items():
            if not isinstance(entries, dict):
                continue
            target = day["breakdown"].setdefault(dim, {})
            for name, entry in entries.items():
                entry = entry or {}
                slot = target.setdefault(name, {"metrics": {}, "metadata": {}})
                add_metrics(slot["metrics"], entry.get("metrics"))
                if not slot["metadata"] and isinstance(entry.get("metadata"), dict):
                    slot["metadata"] = entry["metadata"]
    return days


def day_rows(days: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten merged days into sorted table rows."""
    out = []
    for date in sorted(days):
        m = days[date]["metrics"]
        out.append(
            {
                "date": date,
                "api_requests": int(num(m.get("api_requests"))),
                "successful_requests": int(num(m.get("successful_requests"))),
                "failed_requests": int(num(m.get("failed_requests"))),
                "prompt_tokens": int(num(m.get("prompt_tokens"))),
                "completion_tokens": int(num(m.get("completion_tokens"))),
                "total_tokens": int(num(m.get("total_tokens"))),
                "spend": float(num(m.get("spend"))),
            }
        )
    return out


def totals(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    total: Dict[str, Any] = {
        "api_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "spend": 0.0,
    }
    for row in rows:
        for key in total:
            total[key] += row.get(key, 0) or 0
    return total


def failed_days(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in rows if row.get("failed_requests", 0) > 0]


def entry_label(dim: str, name: str, metadata: Optional[Dict[str, Any]]) -> str:
    metadata = metadata or {}
    if dim == "api_keys":
        alias = metadata.get("key_alias")
        short = name[:12] + "..." if len(name) > 15 else name
        return f"{alias} ({short})" if alias else short
    if dim == "entities":
        for field in ENTITY_LABEL_FIELDS:
            if metadata.get(field):
                return f"{metadata[field]} ({name})"
    return name


def top_n(days: Dict[str, Dict[str, Any]], dim: str, n: int = 10) -> List[Dict[str, Any]]:
    """Sum one breakdown dimension across all days and return the n biggest by spend."""
    acc: Dict[str, Dict[str, Any]] = {}
    for day in days.values():
        for name, entry in ((day.get("breakdown") or {}).get(dim) or {}).items():
            slot = acc.setdefault(name, {"metrics": {}, "metadata": {}})
            add_metrics(slot["metrics"], entry.get("metrics"))
            if not slot["metadata"] and entry.get("metadata"):
                slot["metadata"] = entry["metadata"]
    ranked = sorted(acc.items(), key=lambda kv: num(kv[1]["metrics"].get("spend")), reverse=True)
    out = []
    for name, slot in ranked[: max(n, 0)]:
        m = slot["metrics"]
        out.append(
            {
                "name": name,
                "label": entry_label(dim, name, slot["metadata"]),
                "spend": float(num(m.get("spend"))),
                "api_requests": int(num(m.get("api_requests"))),
                "failed_requests": int(num(m.get("failed_requests"))),
                "total_tokens": int(num(m.get("total_tokens"))),
            }
        )
    return out


def warnings_for(by: str, ids: List[str], plans: List[Dict[str, Any]]) -> List[str]:
    notes = []
    if by == "tag" and len(ids) != 1:
        notes.append(
            "Tag totals double count: a request carrying N tags is counted once per tag, and an "
            "unfiltered view includes User-Agent: tags. Read per-tag numbers with --top entities."
        )
    if by in ("overall", "user") and not ids:
        notes.append("Unfiltered user activity is proxy-wide only for proxy_admin / proxy_admin_viewer keys; other keys see only their own rows.")
    if any(p["paginated"] for p in plans) and by in ("user", "overall", "team"):
        notes.append("Used the paginated endpoint (entity breakdown requested, range too long, or /aggregated unavailable).")
    return notes


def build_report(
    by: str,
    start: str,
    end: str,
    days: Dict[str, Dict[str, Any]],
    plans: List[Dict[str, Any]],
    ids: List[str],
    top_dims: List[str],
    n: int,
) -> Dict[str, Any]:
    rows = day_rows(days)
    return {
        "by": by,
        "ids": ids,
        "start_date": start,
        "end_date": end,
        "endpoints": sorted({p["path"] for p in plans}),
        "days": rows,
        "totals": totals(rows),
        "failed_days": [r["date"] for r in failed_days(rows)],
        "top": {dim: top_n(days, dim, n) for dim in top_dims},
        "warnings": warnings_for(by, ids, plans),
    }


def render_text(report: Dict[str, Any]) -> str:
    lines = []
    scope = report["by"] + (f" {','.join(report['ids'])}" if report["ids"] else "")
    lines.append(f"Usage by {scope}, {report['start_date']} to {report['end_date']} (UTC days)")
    lines.append(f"Source: {', '.join(report['endpoints'])}")
    lines.append("")
    header = f"{'Date':<12} {'Requests':>10} {'Tokens':>14} {'Spend':>12}"
    lines.append(header)
    lines.append("-" * len(header))
    for row in report["days"]:
        flag = f"  ! {row['failed_requests']} failed" if row["failed_requests"] else ""
        lines.append(
            f"{row['date']:<12} {row['api_requests']:>10,} {row['total_tokens']:>14,} {money(row['spend']):>12}{flag}"
        )
    if not report["days"]:
        lines.append("(no activity in range)")
    t = report["totals"]
    lines.append("-" * len(header))
    lines.append(f"{'TOTAL':<12} {t['api_requests']:>10,} {t['total_tokens']:>14,} {money(t['spend']):>12}")
    if t["failed_requests"]:
        lines.append(
            f"\nFailed requests: {t['failed_requests']:,} of {t['api_requests']:,} on "
            f"{len(report['failed_days'])} day(s): {', '.join(report['failed_days'])}"
        )
    for dim, entries in report["top"].items():
        lines.append("")
        lines.append(f"Top {dim} by spend")
        if not entries:
            lines.append("  (none in breakdown)")
        for entry in entries:
            lines.append(
                f"  {entry['label'][:48]:<48} {money(entry['spend']):>12} {entry['api_requests']:>9,} req {entry['total_tokens']:>13,} tok"
            )
    for note in report["warnings"]:
        lines.append(f"\nNote: {note}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #


class HttpError(Exception):
    def __init__(self, status: int, body: str, url: str):
        super().__init__(f"HTTP {status} from {url}: {body[:500]}")
        self.status = status
        self.body = body


def make_getter(base_url: str, api_key: str, timeout: float = 120) -> Callable[[str, Dict[str, Any]], Dict[str, Any]]:
    base = base_url.rstrip("/")

    def get_json(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{base}{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            raise HttpError(e.code, e.read().decode("utf-8", "replace"), path) from None

    return get_json


def run(args: argparse.Namespace, get_json: Callable[[str, Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
    start, end = args.start, args.end
    if not start or not end:
        d_start, d_end = default_range()
        start, end = start or d_start, end or d_end
    ids = split_ids(args.ids)
    top_dims = split_ids(args.top)
    for dim in top_dims:
        if dim not in TOP_CHOICES:
            raise ValueError(f"--top {dim!r} is not one of {', '.join(TOP_CHOICES)}")

    plans = plan_requests(
        args.by, ids, start, end, model=args.model, key_hash=args.key_hash, need_entities="entities" in top_dims
    )
    rows: List[Dict[str, Any]] = []
    for plan in plans:
        try:
            got = fetch_all(get_json, plan)
        except HttpError as e:
            # Older proxy without the /aggregated route: retry the paginated one.
            if e.status == 404 and not plan["paginated"]:
                plan.update(path=ENDPOINTS[args.by][0], paginated=True, params={**plan["params"], "page_size": PAGE_SIZE})
                got = fetch_all(get_json, plan)
            else:
                raise
        rows.extend(label_entity(got, plan["entity"]) if plan["entity"] else got)
    return build_report(args.by, start, end, merge_days(rows), plans, ids, top_dims, args.limit)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="LiteLLM daily usage report")
    p.add_argument("--base-url", default=os.environ.get("LITELLM_BASE_URL"))
    p.add_argument("--api-key", default=os.environ.get("LITELLM_API_KEY"))
    p.add_argument("--by", choices=list(ENDPOINTS), default="overall")
    p.add_argument("--ids", help="comma-separated user/team/org ids, tags, customer ids, or agent ids")
    p.add_argument("--start", help="YYYY-MM-DD (default: first day of this month, UTC)")
    p.add_argument("--end", help="YYYY-MM-DD inclusive (default: today, UTC)")
    p.add_argument("--model", help="only count this model")
    p.add_argument("--key-hash", help="only count this key (sha256 hash / token)")
    p.add_argument("--top", default="", help=f"comma-separated breakdowns to rank: {', '.join(TOP_CHOICES)}")
    p.add_argument("--limit", type=int, default=10, help="rows per --top breakdown (default 10)")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.base_url or not args.api_key:
        print("Set LITELLM_BASE_URL and LITELLM_API_KEY (or pass --base-url / --api-key).", file=sys.stderr)
        return 2
    try:
        report = run(args, make_getter(args.base_url, args.api_key))
    except HttpError as e:
        print(str(e), file=sys.stderr)
        return 1
    except (ValueError, urllib.error.URLError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2) if args.json else render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
