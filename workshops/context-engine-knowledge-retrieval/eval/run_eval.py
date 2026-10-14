#!/usr/bin/env python3
"""Run the Ch05 eval: fixed questions x both agents x n repeats, scored, one doc per run.

Each run: converse API call -> efficiency metrics from model_usage/steps (same math as
bench.py) -> deterministic checks vs ES|QL ground truth -> LLM judge. Results go to
tools/eval/out/<eval_id>/runs/*.json and (unless --no-index) to the ce-eval-results index.
Failed runs are kept as status=error, never dropped.

Usage:
  python3 run_eval.py --env-file ~/repos/.env-chatty --n 5 --workers 4
  python3 run_eval.py --env-file ... --scenarios s01 s02 --agents ce --n 1 --source you
"""
from __future__ import annotations

import argparse
import json
import random
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from common import CE_AGENT, EVAL_DIR, RAW_AGENT, AGENT_NAMES, Env
from scoring import GroundTruth, judge

RESULTS_INDEX = "ce-eval-results"
CACHE_READ_MULT = 0.10  # same as bench.py: list-price proxy for cached input

SCENARIOS = {
    "s01": ("Churn risk", "Which Enterprise accounts have the highest churn risk, and what are they mostly calling us about?"),
    "s02": ("Renewals at risk", "Which Enterprise accounts renewing in the next 60 days have open P1 tickets, and which knowledge base articles cover their issues?"),
    "s03": ("P1 + churn", "Which accounts have open P1 tickets and high churn risk right now?"),
    "s04": ("KB coverage", "What does the knowledge base say about our top support ticket categories?"),
    "s05": ("Top ARR", "Which Enterprise accounts have the highest annual recurring revenue, and who owns them?"),
}
# How many Precision Labs indices a correct answer needs (S05 is the single-index control).
SCENARIO_INDICES = {"s01": 2, "s02": 3, "s03": 2, "s04": 2, "s05": 1}
MODES = {"raw": RAW_AGENT, "ce": CE_AGENT}

MAPPING = {"mappings": {"properties": {
    "@timestamp": {"type": "date"}, "eval_id": {"type": "keyword"}, "source": {"type": "keyword"},
    "scenario": {"type": "keyword"}, "scenario_label": {"type": "keyword"},
    "question": {"type": "text", "fields": {"kw": {"type": "keyword", "ignore_above": 1024}}},
    "round_id": {"type": "keyword"}, "recorded_at": {"type": "date"}, "seconds_source": {"type": "keyword"},
    "replayed": {"type": "boolean"}, "n_indices": {"type": "integer"}, "case_id": {"type": "keyword"}, "checks_text": {"type": "text"},
    "rec_median": {"type": "float"}, "rec_min": {"type": "integer"}, "rec_max": {"type": "integer"},
    "rec_n": {"type": "integer"}, "rec_correct": {"type": "integer"}, "rec_position": {"type": "keyword"},
    "rec_other_median": {"type": "float"}, "rec_other_min": {"type": "integer"}, "rec_other_max": {"type": "integer"},
    "mode": {"type": "keyword"}, "agent_id": {"type": "keyword"}, "agent_name": {"type": "keyword"},
    "run": {"type": "integer"}, "status": {"type": "keyword"}, "error": {"type": "text"},
    "model": {"type": "keyword"}, "conversation_id": {"type": "keyword"}, "trace_id": {"type": "keyword"},
    "llm_calls": {"type": "integer"}, "tool_calls": {"type": "integer"}, "tool_seq": {"type": "keyword"},
    "input_tokens": {"type": "long"}, "cached_tokens": {"type": "long"}, "output_tokens": {"type": "long"},
    "effective_tokens": {"type": "float"}, "seconds": {"type": "float"},
    "checks_score": {"type": "float"}, "checks_pass": {"type": "boolean"},
    "checks": {"type": "object", "enabled": False},
    "judge_correctness": {"type": "integer"}, "judge_completeness": {"type": "integer"},
    "judge_verdict": {"type": "keyword"}, "judge_reason": {"type": "text"}, "judge_model": {"type": "keyword"}, "judge_version": {"type": "keyword"},
    "correct": {"type": "boolean"}, "answer": {"type": "text"},
}}}


def metrics(resp: dict, seconds: float) -> dict:
    u = resp.get("model_usage", {})
    tools = [s for s in resp.get("steps", []) if s.get("type") == "tool_call"]
    inp, cached = u.get("input_tokens", 0), u.get("cached_input_tokens", 0)
    return {"llm_calls": u.get("llm_calls", 0), "tool_calls": len(tools),
            "tool_seq": [s.get("tool_id", "?") for s in tools],
            "input_tokens": inp, "cached_tokens": cached, "output_tokens": u.get("output_tokens", 0),
            "effective_tokens": round(inp - cached + cached * CACHE_READ_MULT, 1),
            "seconds": round(seconds, 1), "model": u.get("model") or (u.get("connectors") or [{}])[0].get("model")}


def checks_text(checks: list | None) -> str:
    """Readable form of the deterministic checks (the `checks` object is not indexed)."""
    if not checks:
        return "no deterministic checks for this question"
    return "\n".join(f'{"PASS" if c["pass"] else "FAIL"}: {c["name"]}; found: {", ".join(map(str, c["evidence"])) or "nothing"}'
                     for c in checks)


def score_into(env: Env, gt: GroundTruth, doc: dict, facts: dict | None, case: dict | None = None):
    """Add deterministic checks + judge to a doc that already has question/answer. Shared by
    run_eval (recorded), watch_mine (learner UI runs) and add_case (learner test cases)."""
    if case is not None:
        facts = case_facts(env, case)
        c = case_check(doc["answer"], case)
    elif facts is not None:
        c = gt.check(doc["scenario"], doc["answer"], facts)
    else:
        facts, c = {"note": "no ground truth for this question; judge plausibility only"}, None
    if c:
        doc.update({"checks": c["checks"], "checks_score": c["score"], "checks_pass": c["pass"]})
    doc["checks_text"] = checks_text(c["checks"] if c else None)
    if case is None and facts.get("note", "").startswith("no ground truth"):
        # nothing to grade against: record calls/tokens only, spend no judge call
        doc.update({"correct": None, "judge_verdict": "unverified",
                    "judge_reason": "Not one of the eval questions or your test cases, so there is no ground truth "
                                    "to grade against. LLM calls and tokens are still recorded."})
        return
    j = judge(env, doc["question"], doc["answer"], facts, c["checks"] if c else None)
    doc.update({"judge_correctness": j.get("correctness"), "judge_completeness": j.get("completeness"),
                "judge_verdict": j.get("verdict"), "judge_reason": j.get("reason"),
                "judge_model": j.get("judge_model"), "judge_version": j.get("judge_version")})
    doc["correct"] = bool(doc.get("checks_pass", True)) and j.get("verdict") == "pass"


def case_facts(env: Env, case: dict) -> dict:
    """A learner test case's ground truth is an ES|QL query they wrote."""
    rows = env.esql(case["truth_esql"])
    return {"ground_truth_esql": case["truth_esql"], "ground_truth_rows": rows[:50],
            "note": "Ground truth is the result of the ES|QL query above, written by the person who added this test case."}


def case_check(answer: str, case: dict) -> dict | None:
    terms = [t for t in case.get("expect", []) if t]
    if not terms:
        return None
    low = answer.lower()
    hits = [t for t in terms if t.lower() in low]
    need = max(1, (len(terms) + 1) // 2)
    chk = [{"name": f"names >= {need} of the {len(terms)} expected terms", "pass": len(hits) >= need, "evidence": hits}]
    return {"checks": chk, "score": 1.0 if chk[0]["pass"] else 0.0, "pass": chk[0]["pass"]}


def base_doc(eval_id: str, source: str, scenario: str, label: str, question: str, mode: str, k: int) -> dict:
    agent = MODES[mode]
    return {"@timestamp": datetime.now(timezone.utc).isoformat(), "eval_id": eval_id, "source": source,
            "scenario": scenario, "scenario_label": label, "question": question, "mode": mode,
            "agent_id": agent, "agent_name": AGENT_NAMES[agent], "run": k,
            "n_indices": SCENARIO_INDICES.get(scenario)}


def fill_from_round(doc: dict, resp: dict, seconds: float):
    """resp = converse response or a conversation round; same shape."""
    doc.update(metrics(resp, seconds))
    doc.update({"conversation_id": resp.get("conversation_id"), "round_id": resp.get("round_id") or resp.get("id"),
                "trace_id": resp.get("trace_id"), "answer": resp.get("response", {}).get("message", "")})


def one_run(env: Env, gt: GroundTruth, facts: dict, eval_id: str, source: str,
            scenario: str, mode: str, k: int, question: str | None = None, case: dict | None = None) -> dict:
    label, q = SCENARIOS.get(scenario, ("Your test case", question))
    q = question or q
    doc = base_doc(eval_id, source, scenario, label, q, mode, k)
    try:
        resp, secs = env.converse(MODES[mode], q)
        fill_from_round(doc, resp, secs)
        doc["seconds_source"] = "wall"
        score_into(env, gt, doc, facts.get(scenario), case)
        doc["status"] = "ok"
    except Exception as e:  # keep failures visible
        doc.update({"status": "error", "error": f"{type(e).__name__}: {e}"[:2000]})
        traceback.print_exc()
    return doc


def add_recorded_context(env: Env, doc: dict):
    """For a learner run on an eval question: where does it land vs the recorded runs of the
    same agent (and what did the other agent's recorded runs need)? Stored on the doc so the
    dashboard needs no cross-query logic."""
    if doc.get("scenario") not in SCENARIOS or doc.get("status") != "ok":
        return
    rows = env.esql(
        f'FROM {RESULTS_INDEX} | WHERE source == "recorded" AND status == "ok" AND scenario == "{doc["scenario"]}" '
        "| STATS med = MEDIAN(llm_calls), mn = MIN(llm_calls), mx = MAX(llm_calls), n = COUNT(*), "
        "ok = SUM(CASE(correct, 1, 0)) BY mode")
    by = {r["mode"]: r for r in rows}
    mine, other = by.get(doc["mode"]), by.get("ce" if doc["mode"] == "raw" else "raw")
    if not mine:
        return
    calls = doc["llm_calls"]
    doc.update({"rec_median": mine["med"], "rec_min": mine["mn"], "rec_max": mine["mx"], "rec_n": mine["n"],
                "rec_correct": mine["ok"],
                "rec_position": "below" if calls < mine["mn"] else "above" if calls > mine["mx"] else "inside"})
    if other:
        doc.update({"rec_other_median": other["med"], "rec_other_min": other["mn"], "rec_other_max": other["mx"]})


def index_doc(env: Env, doc: dict, refresh: str = "wait_for"):
    """Idempotent: _id = conversation + round, so re-scoring never double counts."""
    _id = f'{doc.get("conversation_id")}-{doc.get("round_id")}' if doc.get("conversation_id") else None
    path = f"/{RESULTS_INDEX}/_doc/{_id}" if _id else f"/{RESULTS_INDEX}/_doc"
    env.es_("PUT" if _id else "POST", f"{path}?refresh={refresh}", doc)


def ensure_index(env: Env):
    try:
        env.es_("PUT", f"/{RESULTS_INDEX}", MAPPING)
        print(f"created index {RESULTS_INDEX}")
    except RuntimeError as e:
        if "resource_already_exists" not in str(e):
            raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file")
    ap.add_argument("--scenarios", nargs="*", default=list(SCENARIOS))
    ap.add_argument("--agents", default="raw,ce")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--source", default="recorded", help="recorded | you")
    ap.add_argument("--eval-id", default="")
    ap.add_argument("--no-index", action="store_true")
    args = ap.parse_args()

    env = Env(args.env_file)
    gt = GroundTruth(env)
    eval_id = args.eval_id or datetime.now(timezone.utc).strftime("eval-%Y%m%dT%H%M%SZ")
    out = EVAL_DIR / "out" / eval_id / "runs"
    out.mkdir(parents=True, exist_ok=True)
    facts = {s: gt.facts(s) for s in args.scenarios if s in SCENARIOS}
    (out.parent / "ground-truth.json").write_text(json.dumps(
        {"computed_on": gt.today.isoformat(), "facts": facts}, indent=2, default=str))
    if not args.no_index:
        ensure_index(env)

    jobs = [(s, m, k) for k in range(1, args.n + 1) for s in args.scenarios for m in args.agents.split(",")]
    random.Random(42).shuffle(jobs)  # interleave agents/scenarios so load affects both sides alike
    print(f"{eval_id}: {len(jobs)} runs, {args.workers} workers")
    lock = threading.Lock()
    done = 0
    with ThreadPoolExecutor(args.workers) as pool:
        futs = {pool.submit(one_run, env, gt, facts, eval_id, args.source, s, m, k): (s, m, k) for s, m, k in jobs}
        for f in as_completed(futs):
            s, m, k = futs[f]
            doc = f.result()
            (out / f"{s}-{m}-{k}.json").write_text(json.dumps(doc, indent=2, default=str))
            if not args.no_index:
                index_doc(env, doc)
            with lock:
                done += 1
                print(f"[{done}/{len(jobs)}] {s} {m} #{k}: {doc['status']} "
                      f"llm={doc.get('llm_calls')} eff={doc.get('effective_tokens')} s={doc.get('seconds')} "
                      f"checks={doc.get('checks_score')} judge={doc.get('judge_verdict')}", flush=True)
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
