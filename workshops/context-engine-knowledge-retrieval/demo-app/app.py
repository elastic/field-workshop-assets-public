"""
Precision Labs CS Intelligence — Context Engine demo app.

Serves static/index.html (Newsprint UI) and replay-mode scenario endpoints.
Live mode (DEMO_LIVE_ENABLED=true) calls the actual Agent Builder agents
(precision-cs-baseline for raw, precision-cs-context for CE mode) via the
Kibana converse API — so CE improvement is real, not simulated.

Environment:
    ES_URL              — Elasticsearch endpoint URL
    ES_API_KEY          — Elasticsearch API key (also used for Kibana auth)
    KIBANA_URL          — Kibana endpoint URL (required for live mode)
    CE_AI_INDEX         — AI index id (default: ai-index-idx-precision-corpus)
    DEMO_LIVE_ENABLED   — "true" to enable live agent calls (default: false)
    DEMO_PORT           — port to listen on (default: 5001)
    CE_EVAL_DIR         — path to tools/eval (default: ../eval); enables the /eval page
"""
import json
import os
import pathlib
import sys
import threading
import time
import uuid

from flask import Flask, jsonify, abort, request

BASE = pathlib.Path(__file__).parent
app = Flask(__name__, static_folder='static')

REPLAYS_DIR = BASE / 'replays'

SCENARIOS = [
    {"id": "s01", "label": "S01", "name": "Churn Risk",
     "question": "Which Enterprise accounts have the highest churn risk, and what are they mostly calling us about?"},
    {"id": "s02", "label": "S02", "name": "Renewal Risk",
     "question": "Which Enterprise accounts renewing in the next 60 days have open P1 tickets, and which knowledge base articles cover their issues?"},
    {"id": "s03", "label": "S03", "name": "P1 + Churn",
     "question": "Which accounts have open P1 tickets and high churn risk right now?"},
    {"id": "s04", "label": "S04", "name": "KB Coverage",
     "question": "What does the knowledge base say about our top support ticket categories?"},
]

_run_count = {"count": 0}
_live_enabled = os.environ.get("DEMO_LIVE_ENABLED", "false").lower() == "true"
KIBANA_URL = os.environ.get("KIBANA_URL", "")
AI_INDEX = os.environ.get("CE_AI_INDEX", "ai-index-idx-precision-corpus")
CACHE_READ_MULT = 0.10  # Anthropic list price; label: "list-price proxy; EIS billing may differ"


def _es_reachable():
    es_url = os.environ.get("ES_URL", "")
    api_key = os.environ.get("ES_API_KEY", "")
    if not es_url or not api_key:
        return False
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{es_url.rstrip('/')}/_cluster/health",
            headers={"Authorization": f"ApiKey {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _ki_count():
    if not _live_enabled:
        return None
    try:
        es_url = os.environ.get("ES_URL", "")
        api_key = os.environ.get("ES_API_KEY", "")
        if not es_url or not api_key:
            return None
        import urllib.request, json as _json
        body = _json.dumps({"query": {"bool": {"should": [
            {"term": {"type": "index_metadata"}},
            {"term": {"type": "index_metadata_entry"}}
        ], "minimum_should_match": 1}}}).encode()
        req = urllib.request.Request(
            f"{es_url.rstrip('/')}/{AI_INDEX}/_count",
            data=body,
            headers={"Authorization": f"ApiKey {api_key}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            return _json.loads(r.read()).get("count", 0)
    except Exception:
        return None


def _call_ab_agent(agent_id: str, question: str) -> dict:
    """Call an Agent Builder agent via the Kibana converse API.

    Payload shape: {"agent_id": "...", "input": "<plain string question>"}
    Ref: POST /api/agent_builder/converse
    """
    import requests as _requests
    kibana_url = KIBANA_URL.rstrip('/')
    api_key = os.environ.get("ES_API_KEY", "")
    if not kibana_url or not api_key:
        raise RuntimeError("KIBANA_URL and ES_API_KEY must be set for live mode")
    try:
        resp = _requests.post(
            f"{kibana_url}/api/agent_builder/converse",
            headers={
                "Authorization": f"ApiKey {api_key}",
                "Content-Type": "application/json",
                "kbn-xsrf": "true",
            },
            json={"agent_id": agent_id, "input": question},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()
    except _requests.HTTPError as e:
        raise RuntimeError(f"AB API {e.response.status_code}: {e.response.text[:300]}")


def _ab_to_replay_shape(ab_resp: dict, scenario: str, mode: str, elapsed: float) -> dict:
    """Convert an AB converse API response to the replay JSON shape the UI expects."""
    tool_steps = [s for s in ab_resp.get("steps", []) if s.get("type") == "tool_call"]
    usage = ab_resp.get("model_usage", {})
    input_tokens = usage.get("input_tokens", 0)
    cached_tokens = usage.get("cached_input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    llm_calls = usage.get("llm_calls", len(tool_steps))
    effective_tokens = round((input_tokens - cached_tokens) + cached_tokens * CACHE_READ_MULT)
    per = input_tokens // max(len(tool_steps), 1)

    turns = []
    for i, s in enumerate(tool_steps):
        tool_id = s.get("tool_id", "?")
        params = s.get("params", {})
        try:
            params_str = json.dumps(params, separators=(',', ':'))[:500]
        except Exception:
            params_str = str(params)[:500]
        turns.append({
            "n": i + 1,
            "tool": tool_id,
            "summary": tool_id,
            "input": params_str,
            "cumulative_input_tokens": per * (i + 1),
            "tokens_estimated": True,
        })

    answer = (ab_resp.get("response") or {}).get("message") or "(no answer returned)"
    return {
        "scenario": scenario.upper(),
        "mode": mode,
        "source": "live",
        "answer_markdown": answer,
        "turns": turns,
        "metrics": {
            "turns": llm_calls,
            "tool_calls": len(tool_steps),
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_tokens,
            "effective_tokens": effective_tokens,
            "output_tokens": output_tokens,
            "seconds": round(elapsed, 1),
            "tokens_estimated": True,
            "cache_read_mult": CACHE_READ_MULT,
        },
    }


@app.route("/")
def index():
    return app.send_static_file('index.html')


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "mode_live_available": _live_enabled,
        "es_reachable": _es_reachable(),
        "ki_count": _ki_count(),
    })


@app.route("/ready")
def ready():
    return health()


@app.route("/api/config")
def config():
    return jsonify({
        "live_enabled": _live_enabled,
        "scenarios": SCENARIOS,
    })


@app.route("/api/replay/<scenario>/<mode>")
def replay(scenario, mode):
    if scenario.lower() not in ("s01", "s02", "s03", "s04"):
        abort(404)
    if mode.lower() not in ("raw", "ce"):
        abort(404)
    replay_file = REPLAYS_DIR / f"{scenario.upper()}_{mode.lower()}.json"
    if not replay_file.exists():
        abort(404)
    with open(replay_file) as f:
        data = json.load(f)
    _run_count["count"] += 1
    return jsonify(data)


@app.route("/api/live/<scenario>/<mode>")
def live_run(scenario, mode):
    if not _live_enabled:
        return jsonify({"error": "live mode not enabled", "fallback": "replay"})
    if scenario.lower() not in ("s01", "s02", "s03", "s04"):
        return jsonify({"error": "unknown scenario", "fallback": "replay"})
    if mode.lower() not in ("raw", "ce"):
        return jsonify({"error": "unknown mode", "fallback": "replay"})

    sc = next((s for s in SCENARIOS if s["id"] == scenario.lower()), None)
    if not sc:
        return jsonify({"error": "scenario not found", "fallback": "replay"})

    agent_id = "precision-cs-context" if mode.lower() == "ce" else "precision-cs-baseline"
    question = sc["question"]

    try:
        t0 = time.time()
        ab_resp = _call_ab_agent(agent_id, question)
        elapsed = time.time() - t0
        _run_count["count"] += 1
        return jsonify(_ab_to_replay_shape(ab_resp, scenario, mode, elapsed))
    except Exception as exc:
        return jsonify({"error": str(exc), "fallback": "replay"})


# ── Eval: learner test cases (Lab 4) ─────────────────────────────────────────
# Reuses tools/eval (validate -> save_case -> run_case), the same code as add_case.py.
EVAL_DIR = pathlib.Path(os.environ.get("CE_EVAL_DIR", BASE.parent / "eval"))
_jobs: dict[str, dict] = {}


def _eval_mods():
    if str(EVAL_DIR) not in sys.path:
        sys.path.insert(0, str(EVAL_DIR))
    import add_case
    from common import Env
    return add_case, Env()


@app.route("/eval")
def eval_page():
    return app.send_static_file('eval.html')


@app.route("/api/eval/validate", methods=["POST"])
def eval_validate():
    body = request.get_json(force=True) or {}
    try:
        add_case, env = _eval_mods()
        return jsonify(add_case.validate(env, body.get("question", ""), body.get("truth_esql", "")))
    except Exception as exc:
        return jsonify({"ok": False, "errors": [f"Eval tools unavailable: {exc}"], "warnings": [], "rows": []})


@app.route("/api/eval/run", methods=["POST"])
def eval_run():
    body = request.get_json(force=True) or {}
    add_case, env = _eval_mods()
    v = add_case.validate(env, body.get("question", ""), body.get("truth_esql", ""))
    if not v["ok"]:  # never spend LLM calls on a case that fails validation
        return jsonify({"error": "validation failed", "validation": v}), 400
    n = max(1, min(int(body.get("n", 2)), 3))
    case = add_case.save_case(env, body["question"], body["truth_esql"], body.get("expect", []))
    job_id = uuid.uuid4().hex[:10]
    job = {"id": job_id, "case": case, "total": 2 * n, "results": [], "status": "running", "error": None}
    _jobs[job_id] = job

    def keep(d):
        job["results"].append({k: d.get(k) for k in (
            "mode", "run", "status", "llm_calls", "effective_tokens", "correct", "checks_pass", "checks_text",
            "judge_correctness", "judge_completeness", "judge_reason", "answer", "error")})

    def work():
        try:
            add_case.run_case(env, case, n, keep)
            job["status"] = "done"
        except Exception as exc:
            job.update({"status": "error", "error": str(exc)[:500]})

    threading.Thread(target=work, daemon=True).start()
    return jsonify({"job_id": job_id, "case_id": case["case_id"], "total": job["total"]})


_replay = {"status": "idle", "done": 0, "total": 0}


@app.route("/api/eval/replay", methods=["POST", "GET"])
def eval_replay():
    """Optional: clear the recorded runs and stream them back, one every 3 s, so the dashboard
    fills in live. Every replayed run is labelled REPLAY on the dashboard; no LLM calls."""
    if request.method == "GET" or _replay["status"] == "running":
        return jsonify(_replay)
    if str(EVAL_DIR) not in sys.path:
        sys.path.insert(0, str(EVAL_DIR))
    import load_recorded
    from common import Env
    env = Env()
    _replay.update({"status": "running", "done": 0, "total": 0})

    def tick(i, n, d):
        _replay.update({"done": i, "total": n})

    def work():
        try:
            load_recorded.load(env, pace=3, on_doc=tick)
            _replay["status"] = "done"
        except Exception as exc:
            _replay.update({"status": "error", "error": str(exc)[:300]})

    threading.Thread(target=work, daemon=True).start()
    return jsonify(_replay)


@app.route("/api/eval/job/<job_id>")
def eval_job(job_id):
    job = _jobs.get(job_id)
    if not job:
        abort(404)
    return jsonify({k: job[k] for k in ("id", "total", "results", "status", "error")} | {"case_id": job["case"]["case_id"]})


@app.route("/api/runs/count")
def runs_count():
    return jsonify({"count": _run_count["count"]})


@app.route("/api/runs/mark-solved", methods=["POST"])
def mark_solved():
    _run_count["count"] = max(_run_count["count"], 2)
    return jsonify({"count": _run_count["count"]})


if __name__ == "__main__":
    port = int(os.environ.get("DEMO_PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
