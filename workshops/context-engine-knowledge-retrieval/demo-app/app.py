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
"""
import json
import os
import pathlib
import time

from flask import Flask, jsonify, abort

BASE = pathlib.Path(__file__).parent
app = Flask(__name__, static_folder='static')

REPLAYS_DIR = BASE / 'replays'

SCENARIOS = [
    {"id": "s01", "label": "S01", "name": "Churn Risk",
     "question": "Which Enterprise accounts have the highest churn risk, and what are they mostly calling us about?"},
    {"id": "s02", "label": "S02", "name": "Mid-Market Issues",
     "question": "What are the most common support issues for Mid-Market accounts this quarter?"},
    {"id": "s03", "label": "S03", "name": "P1 + Churn",
     "question": "Which accounts have open P1 tickets and high churn risk right now?"},
    {"id": "s04", "label": "S04", "name": "KB Coverage",
     "question": "What does the knowledge base say about our top support ticket categories?"},
]

_run_count = {"count": 0}
_live_enabled = os.environ.get("DEMO_LIVE_ENABLED", "false").lower() == "true"
KIBANA_URL = os.environ.get("KIBANA_URL", "")
AI_INDEX = os.environ.get("CE_AI_INDEX", "ai-index-idx-precision-corpus")


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
            "turns": usage.get("llm_calls", len(tool_steps)),
            "tool_calls": len(tool_steps),
            "input_tokens": input_tokens,
            "seconds": round(elapsed, 1),
            "tokens_estimated": True,
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
