#!/usr/bin/env python3
"""Export the recorded eval to a fixture, or load it into ce-eval-results (instant or as a replay).

  # once, after recording + rescoring on the test project:
  python3 load_recorded.py --export eval-recorded-20261014

  # sandbox setup (instant load; @timestamp = now, original time kept in recorded_at):
  python3 load_recorded.py --env-file /root/.env --reset

  # replay stream: clear the recorded runs, then write them back one every N seconds so the
  # dashboard fills in while learners watch. Docs carry replayed=true; the feed labels them.
  python3 load_recorded.py --env-file /root/.env --pace 3
"""
from __future__ import annotations

import argparse
import gzip
import json
import time
from datetime import datetime, timedelta, timezone

from common import EVAL_DIR, TRACK_DIR, Env
from run_eval import MAPPING, RESULTS_INDEX, SCENARIOS, index_doc
from scoring import write_question_docs

FIXTURE = TRACK_DIR / "tools" / "fixtures" / "ce-eval-recorded.ndjson.gz"


def export(eval_id: str):
    docs = [json.loads(f.read_text()) for f in sorted((EVAL_DIR / "out" / eval_id / "runs").glob("*.json"))]
    docs.sort(key=lambda d: d["@timestamp"])
    with gzip.open(FIXTURE, "wt") as fh:
        for d in docs:
            d["recorded_at"] = d.pop("@timestamp")
            fh.write(json.dumps(d, default=str) + "\n")
    print(f"wrote {len(docs)} docs to {FIXTURE}")


def load(env: Env, pace: float = 0, reset: bool = False, on_doc=None) -> int:
    if reset:
        try:
            env.es_("DELETE", f"/{RESULTS_INDEX}")
        except RuntimeError as e:
            if "404" not in str(e):
                raise
    try:
        env.es_("PUT", f"/{RESULTS_INDEX}", MAPPING)
    except RuntimeError as e:
        if "resource_already_exists" not in str(e):
            raise
    env.es_("POST", f"/{RESULTS_INDEX}/_delete_by_query?refresh=true",
            {"query": {"term": {"source": "recorded"}}})
    write_question_docs(env, SCENARIOS)
    with gzip.open(FIXTURE, "rt") as fh:
        docs = [json.loads(line) for line in fh if line.strip()]
    now = datetime.now(timezone.utc)
    for i, d in enumerate(docs):
        if pace:
            d["@timestamp"] = datetime.now(timezone.utc).isoformat()
            d["replayed"] = True
        else:  # keep the original order, compressed into the last few minutes
            d["@timestamp"] = (now - timedelta(seconds=5 * (len(docs) - i))).isoformat()
        index_doc(env, d, "wait_for" if pace else "false")
        if on_doc:
            on_doc(i + 1, len(docs), d)
        if pace:
            time.sleep(pace)
    env.es_("POST", f"/{RESULTS_INDEX}/_refresh")
    return len(docs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file")
    ap.add_argument("--export", metavar="EVAL_ID")
    ap.add_argument("--reset", action="store_true", help="drop and recreate ce-eval-results first")
    ap.add_argument("--pace", type=float, default=0, help="seconds between docs (replay); 0 = instant")
    args = ap.parse_args()
    if args.export:
        return export(args.export)

    env = Env(args.env_file)
    show = (lambda i, n, d: print(f"[{i}/{n}] {d['scenario']} {d['mode']} #{d['run']}", flush=True)) if args.pace else None
    n = load(env, args.pace, args.reset, show)
    print(f"loaded {n} recorded runs into {RESULTS_INDEX}")


if __name__ == "__main__":
    main()
