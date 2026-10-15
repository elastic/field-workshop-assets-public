"""Shared helpers for the Ch05 eval tools: env loading and HTTP against Kibana/ES.

Env: pass --env-file (e.g. ~/repos/.env-chatty) or export KIBANA_URL / ES_URL / ES_API_KEY.
Also accepts the ES_KIBANA_URL / ES_ENDPOINT names used by .env-chatty and sandbox /root/.env.
Never commit credentials; nothing here writes them anywhere.
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import time
import urllib.error
import urllib.request

TRACK_DIR = pathlib.Path(__file__).resolve().parents[2]
EVAL_DIR = pathlib.Path(__file__).resolve().parent
TRACES_INDEX = "traces-agent_builder.otel-default"
RAW_AGENT = "precision-cs-baseline"
CE_AGENT = "precision-cs-context"
AGENT_NAMES = {RAW_AGENT: "Precision CS Baseline", CE_AGENT: "Precision CS Context"}
GEMINI_CONNECTOR = ".google-gemini-3.0-flash-chat_completion"


class Env:
    def __init__(self, env_file: str | None = None):
        if env_file:
            for line in pathlib.Path(env_file).expanduser().read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        kb = os.environ.get("KIBANA_URL") or os.environ.get("ES_KIBANA_URL", "")
        es = os.environ.get("ES_URL") or os.environ.get("ES_ENDPOINT", "")
        self.kibana = kb.rstrip("/").removesuffix(":443")
        self.es = es.rstrip("/")
        self.api_key = os.environ.get("ES_API_KEY", "")
        # Kibana UI user. In the sandbox the Kibana tabs log in as `admin` (nginx injects Basic
        # auth), and Agent Builder conversations are private to their owner, so the learner's
        # chats are only visible as admin, not via the API key. Optional; None on test projects.
        self.kibana_basic = os.environ.get("CE_KIBANA_BASIC", "") or self._sandbox_admin()
        if not (self.kibana and self.es and self.api_key):
            raise SystemExit("ERROR: need KIBANA_URL, ES_URL, ES_API_KEY (or --env-file)")

    @staticmethod
    def _sandbox_admin() -> str:
        pr = pathlib.Path("/tmp/project_results.json")
        try:
            d = json.loads(pr.read_text())
            pw = next(iter(d.values()))["credentials"]["password"]
            return f"admin:{pw}" if pw else ""
        except Exception:
            return ""

    # ── HTTP ──────────────────────────────────────────────────────────────────
    def _req(self, method: str, url: str, body=None, headers=None, timeout=60):
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
        h = {"Authorization": f"ApiKey {self.api_key}", "Content-Type": "application/json"}
        h.update(headers or {})
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:800]
            raise RuntimeError(f"{method} {url} -> {e.code}: {detail}") from None

    def kb(self, method: str, path: str, body=None, timeout=60, internal=False, version=None,
           as_user=False):
        """as_user=True: authenticate as the Kibana UI user (see kibana_basic) instead of the API key."""
        h = {"kbn-xsrf": "true"}
        if as_user:
            if not self.kibana_basic:
                raise RuntimeError("no Kibana UI credentials available")
            h["Authorization"] = "Basic " + base64.b64encode(self.kibana_basic.encode()).decode()
        if internal:
            h["x-elastic-internal-origin"] = "Kibana"
        if version:
            h["elastic-api-version"] = version
        return self._req(method, f"{self.kibana}{path}", body, h, timeout)

    def es_(self, method: str, path: str, body=None, timeout=60):
        return self._req(method, f"{self.es}{path}", body, None, timeout)

    def esql(self, query: str, timeout=60) -> list[dict]:
        r = self.es_("POST", "/_query?format=json", {"query": query}, timeout)
        cols = [c["name"] for c in r.get("columns", [])]
        return [dict(zip(cols, row)) for row in r.get("values", [])]

    def converse(self, agent_id: str, question: str, connector_id: str | None = None,
                 timeout=300) -> tuple[dict, float]:
        body = {"agent_id": agent_id, "input": question}
        if connector_id:
            body["connector_id"] = connector_id
        t0 = time.time()
        r = self.kb("POST", "/api/agent_builder/converse", body, timeout=timeout)
        return r, time.time() - t0


def assignment_block(chapter_dir: str, lang: str, after: str) -> str:
    """Return the first ```lang fenced block that follows the line containing `after`.

    Keeps the eval tools in sync with what the learner actually pastes.
    """
    text = (TRACK_DIR / chapter_dir / "assignment.md").read_text()
    start = text.index(after)
    fence = text.index(f"```{lang}\n", start) + len(f"```{lang}\n")
    end = text.index("\n```", fence)
    return text[fence:end]
