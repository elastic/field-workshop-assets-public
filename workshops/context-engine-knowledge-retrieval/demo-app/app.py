"""
Precision Labs CS Intelligence — Context Engine demo app.

Serves static/index.html (Newsprint UI) and replay-mode scenario endpoints.
Live mode (DEMO_LIVE_ENABLED=true) is Tier 2b — not active in workshop replay mode.

Environment:
    ES_URL              — Elasticsearch endpoint URL
    ES_API_KEY          — Elasticsearch API key
    CE_AI_INDEX         — AI index id (default: ai-index-idx-precision-corpus)
    DEMO_LIVE_ENABLED   — "true" to enable live agent calls (default: false)
    DEMO_PORT           — port to listen on (default: 5001)
"""
import json
import os
import pathlib
import sys
import time

from flask import Flask, jsonify, request, abort

BASE = pathlib.Path(__file__).parent
# Add harness/ to path so context_lab is importable when live mode is active
sys.path.insert(0, str(BASE / 'harness'))

app = Flask(__name__, static_folder='static')

REPLAYS_DIR = BASE / 'replays'

SCENARIOS = [
    {"id": "s01", "label": "S01", "name": "Churn Risk",
     "question": "Which Enterprise accounts have the highest churn risk, and what are they mostly calling us about?"},
    {"id": "s02", "label": "S02", "name": "Pro-Tier Issues",
     "question": "What are the most common support issues for Pro-tier accounts this quarter?"},
    {"id": "s03", "label": "S03", "name": "P1 + Churn",
     "question": "Which accounts have open P1 tickets and high churn risk right now?"},
    {"id": "s04", "label": "S04", "name": "KB Coverage",
     "question": "What does the knowledge base say about our top support ticket categories?"},
]

_run_count = {"count": 0}
_live_enabled = os.environ.get("DEMO_LIVE_ENABLED", "false").lower() == "true"


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
        ai_index = os.environ.get("CE_AI_INDEX", "ai-index-idx-precision-corpus")
        if not es_url or not api_key:
            return None
        import urllib.request, json as _json
        body = _json.dumps({"query": {"bool": {"should": [
            {"term": {"type": "index_metadata"}},
            {"term": {"type": "index_metadata_entry"}}
        ], "minimum_should_match": 1}}}).encode()
        req = urllib.request.Request(
            f"{es_url.rstrip('/')}/{ai_index}/_count",
            data=body,
            headers={"Authorization": f"ApiKey {api_key}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            return _json.loads(r.read()).get("count", 0)
    except Exception:
        return None


@app.route("/")
def index():
    return app.send_static_file('index.html')


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "mode_live_available": _live_enabled,
        "es_reachable": _es_reachable(),
        "ki_count": _ki_count()
    })


@app.route("/ready")
def ready():
    return health()


@app.route("/api/config")
def config():
    return jsonify({
        "live_enabled": _live_enabled,
        "scenarios": SCENARIOS
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


@app.route("/api/runs/count")
def runs_count():
    return jsonify({"count": _run_count["count"]})


@app.route("/api/runs/mark-solved", methods=["POST"])
def mark_solved():
    _run_count["count"] = max(_run_count["count"], 2)
    return jsonify({"count": _run_count["count"]})


AI_INDEX = os.environ.get("CE_AI_INDEX", "ai-index-idx-precision-corpus")

SYSTEM_PROMPT_BASE = (
    "You are a customer success AI assistant for Precision Labs. "
    "You have access to three data sources: precision-crm-accounts (customer accounts with "
    "ARR, churn risk, tier), precision-support-tickets (support tickets linked by account_id), "
    "and precision-kb-articles (knowledge base articles). "
    "Answer questions accurately. When referencing accounts, include company name, tier, and ARR."
)
SYSTEM_PROMPT_WITH_KI = SYSTEM_PROMPT_BASE + (
    " IMPORTANT: Call query_ki as your VERY FIRST tool call before any other tool. "
    "Use the KI content to learn field names, join keys, and access patterns before querying."
)

_configured = False
_current_model = os.environ.get("EIS_INFERENCE_ID", ".anthropic-claude-4.5-haiku-chat_completion")
_context_lab = None


def _ensure_context_lab():
    global _context_lab, _configured, _current_model
    if _context_lab is not None:
        return _context_lab
    try:
        import context_lab as cl
        cl.configure(
            es_url=os.environ.get("ES_URL", ""),
            api_key=os.environ.get("ES_API_KEY", ""),
            inference_id=_current_model,
        )
        _context_lab = cl
        _configured = True
        return cl
    except Exception:
        return None


def _make_query_ki_tool():
    def _query_ki(query: str, k: int = 8):
        from elasticsearch import Elasticsearch
        es_url = os.environ.get("ES_URL", "")
        api_key = os.environ.get("ES_API_KEY", "")
        client = Elasticsearch(hosts=[es_url], api_key=api_key)
        resp = client.search(
            index=AI_INDEX,
            query={"multi_match": {"query": query, "fields": ["content", "title", "description"]}},
            size=k,
        )
        results = []
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            limit = 2500 if src.get("type") in ("index_metadata", "index_metadata_entry") else 600
            results.append({
                "_id": hit["_id"],
                "type": src.get("type", ""),
                "content": str(src.get("content", ""))[:limit],
            })
        return results

    return {
        "fn": _query_ki,
        "schema": {
            "type": "function",
            "function": {
                "name": "query_ki",
                "description": (
                    "Search the AI Index for Knowledge Indicators relevant to your query. "
                    "Returns routing KIs (index profiles with field names and join keys). "
                    "Always call this before searching source indices directly."
                ),
                "parameters": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string", "description": "Natural language query"},
                        "k": {"type": "integer", "description": "Max KIs to return (default 8)"},
                    },
                },
            },
        },
    }


def _result_to_replay_shape(result, scenario, mode, elapsed):
    import json as _json
    cumulative = 0
    turns = []
    call_n = 0
    turn_tokens = result.turn_input_tokens if hasattr(result, 'turn_input_tokens') else []
    turn_idx = 0
    for msg in (result.messages if hasattr(result, 'messages') else []):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            per = turn_tokens[turn_idx] if turn_idx < len(turn_tokens) else 0
            cumulative += per
            turn_idx += 1
            for tc in msg["tool_calls"]:
                call_n += 1
                fn = tc.get("function", {})
                args = fn.get("arguments", "")
                try:
                    args_str = _json.dumps(_json.loads(args), separators=(',', ':'))[:500]
                except Exception:
                    args_str = str(args)[:500]
                turns.append({
                    "n": call_n,
                    "tool": fn.get("name", "?"),
                    "summary": fn.get("name", "?"),
                    "input": args_str,
                    "cumulative_input_tokens": cumulative,
                })
    answer = getattr(result, 'answer', None) or "(agent hit turn limit)"
    return {
        "scenario": scenario.upper(),
        "mode": mode,
        "source": "live",
        "answer_markdown": answer,
        "turns": turns,
        "metrics": {
            "turns": getattr(result, 'turns', len(turns)),
            "tool_calls": call_n,
            "input_tokens": getattr(result, 'input_tokens', cumulative),
            "seconds": round(elapsed, 1),
            "tokens_estimated": False,
        },
    }


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
    question = sc["question"]

    try:
        cl = _ensure_context_lab()
        if cl is None:
            raise RuntimeError("context_lab not available")

        t0 = time.time()
        if mode.lower() == "ce":
            query_ki_tool = _make_query_ki_tool()
            tools = [query_ki_tool, cl.ESQL_TOOL]
            sys_prompt = SYSTEM_PROMPT_WITH_KI
        else:
            tools = [cl.ESQL_TOOL, cl.MAPPING_TOOL]
            sys_prompt = SYSTEM_PROMPT_BASE

        result = cl.run_agent(
            system_prompt=sys_prompt,
            question=question,
            tools=tools,
            max_turns=12,
        )
        elapsed = time.time() - t0
        _run_count["count"] += 1
        return jsonify(_result_to_replay_shape(result, scenario, mode, elapsed))

    except Exception as exc:
        return jsonify({"error": str(exc), "fallback": "replay"})


if _live_enabled:
    try:
        @app.route("/ask", methods=["POST"])
        def ask():
            payload = request.get_json(force=True)
            question = payload.get("question", "").strip()
            use_ki = bool(payload.get("use_ki", False))
            if not question:
                return jsonify({"error": "question is required"}), 400
            try:
                cl = _ensure_context_lab()
                if cl is None:
                    raise RuntimeError("context_lab not available")
                sys_prompt = SYSTEM_PROMPT_WITH_KI if use_ki else SYSTEM_PROMPT_BASE
                tools = [cl.ESQL_TOOL, cl.MAPPING_TOOL]
                result = cl.run_agent(system_prompt=sys_prompt, question=question, tools=tools, max_turns=12)
                _run_count["count"] += 1
                return jsonify({
                    "answer": result.answer or "(agent hit turn limit)",
                    "turn_count": result.turns,
                    "input_tokens": result.input_tokens,
                    "tool_calls": [],
                    "turn_input_tokens": result.turn_input_tokens,
                })
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500
    except Exception:
        pass
else:
    @app.route("/ask", methods=["POST"])
    def ask_disabled():
        return jsonify({"error": "live mode disabled"}), 404


if __name__ == "__main__":
    port = int(os.environ.get("DEMO_PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
