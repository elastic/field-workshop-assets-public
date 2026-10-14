#!/usr/bin/env python3
"""Add your own test case to the eval, then run it on both agents.

A test case = a question + an ES|QL query whose result is the right answer (+ optional terms
the answer must name). The query is your ground truth: the judge grades both agents against
its rows. This is how a real eval set grows: every question that matters gets a reference.

  python3 add_case.py --env-file /root/.env \\
    --question "Which industry has the most Enterprise accounts?" \\
    --truth-esql 'FROM precision-crm-accounts | WHERE account_tier == "Enterprise" | STATS n = COUNT(*) BY industry | SORT n DESC | LIMIT 3' \\
    --expect Manufacturing --n 2

The demo app's /eval page calls the same functions (validate, save_case, run_case).
The case is saved to ce-eval-cases, so asking the same question again in Agent Builder is also
graded against it (watch_mine.py).
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from common import Env
from run_eval import MAPPING, RESULTS_INDEX, SCENARIOS, index_doc, one_run
from scoring import JUDGE_RUBRIC, QUESTIONS_INDEX, GroundTruth
from watch_mine import CASES_INDEX, norm

MAX_TRUTH_ROWS = 50


def validate(env: Env, question: str, truth_esql: str) -> dict:
    """Checks that cost no LLM calls. Returns {ok, errors, warnings, columns, rows, suggested}."""
    errors, warnings = [], []
    q = (question or "").strip()
    if len(q) < 10:
        errors.append("Write a full question (at least 10 characters).")
    for sid, (label, text) in SCENARIOS.items():
        if q and difflib.SequenceMatcher(None, norm(q), norm(text)).ratio() >= 0.9:
            errors.append(f"That is eval question {sid.upper()} ({label}); it is already scored. Ask something new.")
    rows, columns = [], []
    if not (truth_esql or "").strip():
        errors.append("Write the ES|QL query whose result is the right answer.")
    else:
        try:
            r = env.es_("POST", "/_query?format=json", {"query": truth_esql})
            columns = [c["name"] for c in r.get("columns", [])]
            rows = [dict(zip(columns, v)) for v in r.get("values", [])]
            if not rows:
                errors.append("The query returns 0 rows, so there is nothing to grade against.")
            elif len(rows) > MAX_TRUTH_ROWS:
                errors.append(f"The query returns {len(rows)} rows; the judge reads at most {MAX_TRUTH_ROWS}. "
                              "Add a LIMIT or aggregate with STATS.")
            elif len(rows) > 10:
                warnings.append(f"{len(rows)} rows: fine, but a short answer will rarely name them all.")
        except RuntimeError as e:
            msg = str(e)
            reason = msg.split('"reason":"')[-1].split('"')[0] if '"reason":"' in msg else msg[-300:]
            errors.append("ES|QL error: " + reason.replace('\\n', ' '))
    suggested = [f"{v:.2f}" if isinstance(v, float) else str(v)
                 for v in rows[0].values() if v not in (None, "")][:3] if rows else []
    return {"ok": not errors, "errors": errors, "warnings": warnings, "columns": columns,
            "rows": rows[:MAX_TRUTH_ROWS], "suggested": suggested}


def save_case(env: Env, question: str, truth_esql: str, expect: list[str]) -> dict:
    expect = [t.strip() for t in expect if t and t.strip()]
    case_id = "c-" + hashlib.sha1(question.strip().lower().encode()).hexdigest()[:8]
    case = {"case_id": case_id, "question": question.strip(), "truth_esql": truth_esql,
            "expect": expect, "created_at": datetime.now(timezone.utc).isoformat()}
    env.es_("PUT", f"/{CASES_INDEX}/_doc/{case_id}?refresh=true", case)
    need = max(1, (len(expect) + 1) // 2)
    env.es_("PUT", f"/{QUESTIONS_INDEX}/_doc/{case_id}?refresh=true", {
        "scenario": case_id, "label": "Your test case", "question": case["question"], "truth_esql": truth_esql,
        "checks": [f"Names at least {need} of: {', '.join(expect)}"] if expect else [],
        "notes": "Ground truth is the ES|QL you wrote for this case.", "judge": JUDGE_RUBRIC, "kind": "case"})
    try:
        env.es_("PUT", f"/{RESULTS_INDEX}", MAPPING)
    except RuntimeError as e:
        if "resource_already_exists" not in str(e):
            raise
    return case


def run_case(env: Env, case: dict, n: int = 2, on_result=None) -> list[dict]:
    """Run both agents n times on the case; index and return the scored docs.
    on_result(doc) is called as each run finishes (the web page streams these)."""
    gt = GroundTruth(env)
    jobs = [(m, k) for k in range(1, n + 1) for m in ("raw", "ce")]

    def go(job):
        d = one_run(env, gt, {}, "learner", "you", case["case_id"], job[0], job[1],
                    question=case["question"], case=case)
        d["case_id"] = case["case_id"]
        index_doc(env, d)
        if on_result:
            on_result(d)
        return d

    with ThreadPoolExecutor(4) as pool:
        return list(pool.map(go, jobs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file")
    ap.add_argument("--question", required=True)
    ap.add_argument("--truth-esql", required=True, help="ES|QL whose result is the right answer")
    ap.add_argument("--expect", nargs="*", default=[], help="terms a correct answer must name")
    ap.add_argument("--n", type=int, default=2, help="runs per agent")
    args = ap.parse_args()
    env = Env(args.env_file)

    v = validate(env, args.question, args.truth_esql)  # no LLM calls before this passes
    for w in v["warnings"]:
        print(f"warning: {w}")
    if not v["ok"]:
        raise SystemExit("\n".join(f"error: {e}" for e in v["errors"]))
    print(f"ground truth: {len(v['rows'])} rows, first: {json.dumps(v['rows'][:3], default=str)}")
    case = save_case(env, args.question, args.truth_esql, args.expect)
    print(f"{case['case_id']}: running {2 * args.n} runs (both agents x {args.n}) ...", flush=True)

    def show(d):
        name = "Context Engine" if d["mode"] == "ce" else "Baseline"
        print(f"  {name} #{d['run']}: {d.get('status')} {d.get('llm_calls')} LLM calls, "
              f"{'correct' if d.get('correct') else 'WRONG'} (judge {d.get('judge_correctness')}/5): "
              f"{d.get('judge_reason')}", flush=True)

    run_case(env, case, args.n, show)
    print("Done. Open the Context Engine eval dashboard to compare.")


if __name__ == "__main__":
    main()
