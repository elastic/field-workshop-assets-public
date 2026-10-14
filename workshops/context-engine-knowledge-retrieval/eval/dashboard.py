#!/usr/bin/env python3
"""Create or update the "Context Engine eval" dashboard from panels/*.html + *.esql.

Hybrid: custom panels (HTML + one ES|QL query) where Lens cannot draw it (scoreboard, your-run
card, dot plot); a native ES|QL data table for every run (click to filter, sort, expand, Inspect).
Layout targets ~1150x600 usable Kibana canvas (Instruqt tab next to the assignment pane):
everything above the table fits without scrolling.

Usage: python3 dashboard.py --env-file ~/repos/.env-chatty
"""
from __future__ import annotations

import argparse

from common import EVAL_DIR, Env

DASHBOARD_ID = "ce-eval"
TITLE = "Context Engine eval: Baseline vs Context Engine"
CUSTOM = [  # (file stem, title, grid)
    ("scoreboard", "Recorded eval scoreboard", {"x": 0, "y": 0, "w": 48, "h": 11}),
    ("yourrun", "Your latest run", {"x": 0, "y": 11, "w": 14, "h": 13}),
    ("dotplot", "Every run", {"x": 14, "y": 11, "w": 34, "h": 13}),
    ("scoring", "How each question is scored", {"x": 0, "y": 24, "w": 48, "h": 28}),
]
RUNS_SESSION_ID = "ce-eval-runs"  # saved Discover session (ES|QL); created by ensure_runs_session()
RUNS_COLUMNS = ["run_kind", "scenario", "agent", "result", "llm_calls", "judge_reason"]


def read(stem: str, ext: str) -> str:
    return (EVAL_DIR / "panels" / f"{stem}.{ext}").read_text()


def build() -> dict:
    panels = [{"type": "custom_content", "grid": grid, "config": {
        "title": title, "hide_title": True,
        "esql_query": [read(stem, "esql").strip()], "template": read(stem, "html")}}
        for stem, title, grid in CUSTOM]
    panels.append({"type": "discover_session", "grid": {"x": 0, "y": 52, "w": 48, "h": 16},
                   "config": {"ref_id": RUNS_SESSION_ID}})
    return {"title": TITLE, "time_range": {"from": "now-30d", "to": "now"},
            "refresh_interval": {"pause": False, "value": 15000}, "panels": panels}


def ensure_runs_session(env: Env):
    """Discover session (ES|QL) listing every run: 'View details' shows the whole doc formatted
    (answer, checks_text, judge reason). Serverless only exposes saved objects via _import."""
    import json
    import urllib.request
    import uuid
    obj = {"id": RUNS_SESSION_ID, "type": "search", "references": [], "attributes": {
        "title": "Context Engine eval: all scored runs",
        "description": "One row per scored run. Open a row to read the answer, the checks and the judge's reason.",
        "columns": RUNS_COLUMNS, "sort": [["@timestamp", "desc"]], "grid": {}, "hideChart": True,
        "isTextBasedQuery": True,
        "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(
            {"query": {"esql": read("runs", "esql").strip()}, "filter": []})}}}
    boundary = "----ceeval" + uuid.uuid4().hex
    data = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="runs.ndjson"\r\n'
            "Content-Type: application/ndjson\r\n\r\n").encode() + json.dumps(obj).encode() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{env.kibana}/api/saved_objects/_import?overwrite=true", data=data, method="POST",
                                 headers={"Authorization": f"ApiKey {env.api_key}", "kbn-xsrf": "true",
                                          "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.loads(r.read())
    if not res.get("success"):
        raise SystemExit(f"Discover session import failed: {res}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file")
    env = Env(ap.parse_args().env_file)
    ensure_runs_session(env)
    body = build()
    try:
        env.kb("PUT", f"/api/dashboards/{DASHBOARD_ID}", body, version="2023-10-31")
    except RuntimeError as e:
        if "404" not in str(e):
            raise
        env.kb("POST", "/api/dashboards", body | {"id": DASHBOARD_ID}, version="2023-10-31")
    print(f"{env.kibana}/app/dashboards#/view/{DASHBOARD_ID}")


if __name__ == "__main__":
    main()
