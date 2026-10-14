#!/usr/bin/env python3
"""Score the learner's own Agent Builder conversations, live, into ce-eval-results (source=you).

Polls the conversations of both workshop agents. Every completed round not yet in the index is
matched to an eval question (S01-S04, or a test case the learner added with add_case.py),
scored with the same checks + judge as the recorded eval, and indexed. Questions that match
nothing are still scored, by the judge alone, as scenario "other".

Runs in the background from Ch05 setup:  nohup python3 watch_mine.py --env-file /root/.env &
One pass only (for tests / the check script):  python3 watch_mine.py --env-file ... --once
"""
from __future__ import annotations

import argparse
import difflib
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from common import CE_AGENT, RAW_AGENT, Env
from run_eval import (MAPPING, MODES, RESULTS_INDEX, SCENARIOS, add_recorded_context, base_doc,
                      fill_from_round, index_doc, score_into)
from scoring import GroundTruth

CASES_INDEX = "ce-eval-cases"
MODE_OF = {v: k for k, v in MODES.items()}


def norm(q: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", q.lower()).strip()


def match_question(q: str, cases: list[dict]):
    """-> (scenario, label, case). Near-exact match only (typos ok), so a different question
    is never graded against the wrong ground truth."""
    nq = norm(q)
    for sid, (label, text) in SCENARIOS.items():
        if difflib.SequenceMatcher(None, nq, norm(text)).ratio() >= 0.9:
            return sid, label, None
    for c in cases:
        if difflib.SequenceMatcher(None, nq, norm(c["question"])).ratio() >= 0.9:
            return c["case_id"], "Your test case", c
    return "other", "Other question", None


def load_cases(env: Env) -> list[dict]:
    try:
        r = env.es_("POST", f"/{CASES_INDEX}/_search", {"size": 100})
        return [h["_source"] for h in r["hits"]["hits"]]
    except RuntimeError:
        return []


def scored_ids(env: Env) -> set[str]:
    """Conversations created by the eval itself (recorded runs), never re-scored as the learner's."""
    r = env.es_("POST", f"/{RESULTS_INDEX}/_search",
                {"size": 0, "query": {"bool": {"must_not": {"term": {"source": "you"}}}},
                 "aggs": {"c": {"terms": {"field": "conversation_id", "size": 10000}}}})
    return {b["key"] for b in r["aggregations"]["c"]["buckets"]}


def one_pass(env: Env, gt: GroundTruth, facts: dict, since: str = "", workers: int = 4) -> int:
    """Collect every completed, unscored round of both agents, then score newest first, in
    parallel, so a question asked just now never waits behind the Lab 1-3 backlog."""
    done = scored_ids(env)  # conversations the eval/add_case already scored (incl. recorded runs)
    have = {h["_id"] for h in env.es_("POST", f"/{RESULTS_INDEX}/_search",
                                      {"size": 10000, "_source": False,
                                       "query": {"term": {"source": "you"}}})["hits"]["hits"]}
    cases = load_cases(env)
    todo = []  # (started_at, agent, conversation_id, round number, round)
    for agent in (RAW_AGENT, CE_AGENT):
        convs = env.kb("GET", f"/api/agent_builder/conversations?agent_id={agent}").get("results", [])
        for c in convs:
            if c["id"] in done or c.get("status") != "completed" or c.get("updated_at", "") < since:
                continue
            full = env.kb("GET", f"/api/agent_builder/conversations/{c['id']}")
            for k, rd in enumerate(full.get("rounds", []), 1):
                if (f'{c["id"]}-{rd["id"]}' in have or rd.get("status") != "completed"
                        or rd.get("started_at", "") < since):
                    continue
                todo.append((rd.get("started_at", ""), agent, c["id"], k, rd))
    todo.sort(key=lambda t: t[0], reverse=True)

    def score(item):
        started, agent, conv_id, k, rd = item
        q = rd.get("input", {}).get("message", "")
        sid, label, case = match_question(q, cases)
        doc = base_doc("learner", "you", sid, label, q, MODE_OF[agent], k)
        doc["@timestamp"] = started or doc["@timestamp"]
        fill_from_round(doc, rd | {"conversation_id": conv_id}, (rd.get("time_to_last_token") or 0) / 1000)
        doc["seconds_source"] = "time_to_last_token"
        if case:
            doc["case_id"] = case["case_id"]
        try:
            score_into(env, gt, doc, facts.get(sid), case)
            doc["status"] = "ok"
            add_recorded_context(env, doc)
        except Exception as e:
            doc.update({"status": "error", "error": f"{type(e).__name__}: {e}"[:2000]})
        index_doc(env, doc)
        print(f"scored {agent} {sid}: {doc.get('llm_calls')} calls, correct={doc.get('correct')}", flush=True)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(score, todo))
    return len(todo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file")
    ap.add_argument("--interval", type=float, default=15)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--since", default="", help="ISO time; ignore older rounds (test projects with history)")
    args = ap.parse_args()
    env = Env(args.env_file)
    try:
        env.es_("PUT", f"/{RESULTS_INDEX}", MAPPING)
    except RuntimeError as e:
        if "resource_already_exists" not in str(e):
            raise
    gt = GroundTruth(env)
    facts, facts_at = {}, 0.0
    while True:
        try:
            if time.time() - facts_at > 3600:  # S02 depends on today's date
                facts, facts_at = {s: gt.facts(s) for s in SCENARIOS}, time.time()
            one_pass(env, gt, facts, args.since)
        except Exception:
            traceback.print_exc()
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
