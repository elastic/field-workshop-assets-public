"""context_lab.py — Minimal agent loop for the Context Engine workshop.

Drop-in replacement for deepagents + ElasticInferenceChatModel.
No LangChain, no deepagents. Dependencies: requests, elasticsearch-py.

Usage in a notebook:
    from context_lab import configure, run_agent, ESQL_TOOL, MAPPING_TOOL, load_skill, compare
    configure(
        es_url=os.environ["ES_ENDPOINT"],
        api_key=os.environ["ES_API_KEY"],
        inference_id=".anthropic-claude-4.6-sonnet-chat_completion",
    )
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Module state — set once by configure()
# ---------------------------------------------------------------------------

_cfg: dict = {}
_client = None  # elasticsearch.Elasticsearch instance

MAX_TOOL_CHARS = 500  # per-field truncation for large-doc corpora (e.g. browsecomp-plus ~40K chars)


def configure(es_url: str, api_key: str, inference_id: str) -> None:
    """Set EIS and Elasticsearch credentials for this notebook session."""
    global _cfg, _client
    from elasticsearch import Elasticsearch
    _cfg = {"es_url": es_url, "api_key": api_key, "inference_id": inference_id}
    _client = Elasticsearch(hosts=[es_url], api_key=api_key)


# ---------------------------------------------------------------------------
# SSE streaming call to EIS
# ---------------------------------------------------------------------------

def stream_chat(
    messages: list,
    tools: list | None = None,
) -> tuple:
    """POST messages to EIS chat_completion/_stream.

    Returns (content: str, tool_calls: list[dict], usage: dict).
    content is "" when finish_reason is tool_calls.
    usage keys: input_tokens, output_tokens, total_tokens.
    """
    if not _cfg:
        raise RuntimeError("Call configure() before using context_lab")

    body: dict = {"messages": messages}
    if tools:
        body["tools"] = [t["schema"] for t in tools]

    resp = requests.post(
        f"{_cfg['es_url']}/_inference/chat_completion/{_cfg['inference_id']}/_stream",
        headers={"Authorization": f"ApiKey {_cfg['api_key']}", "Content-Type": "application/json"},
        json=body,
        stream=True,
        timeout=120,
    )
    if not resp.ok:
        raise requests.exceptions.HTTPError(
            f"EIS {resp.status_code}: {resp.text[:2000]}", response=resp
        )

    content = ""
    tool_calls_acc: dict = {}
    usage: dict = {}
    data_lines: list = []

    def _flush():
        if not data_lines:
            return None
        payload = "\n".join(data_lines)
        data_lines.clear()
        return payload

    # SSE spec: a single event's `data:` can legitimately span multiple
    # consecutive `data:` lines, joined with "\n" to form one payload —
    # naively json.loads()-ing each line independently breaks the moment
    # model output contains an actual newline.  Buffer per-event instead.
    #
    # decode_unicode=True decodes per network chunk, not per line — a
    # multi-byte UTF-8 character split across a chunk boundary comes out
    # as mojibake (intermittent, network-timing dependent).  Iterate raw
    # bytes; splitting on b"\n" is always byte-safe.
    for raw_bytes in resp.iter_lines(decode_unicode=False):
        if not raw_bytes:
            data = _flush()
            if data is None:
                continue
        else:
            line = raw_bytes.decode("utf-8").lstrip("﻿")
            if not line.startswith("data:"):
                continue
            data_lines.append(line[len("data:"):].strip())
            continue

        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        if chunk.get("usage"):
            usage = chunk["usage"]
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta", {})
        if delta.get("content"):
            content += delta["content"]
        for tc in delta.get("tool_calls", []):
            idx = tc["index"]
            slot = tool_calls_acc.setdefault(idx, {"id": None, "name": None, "arguments": ""})
            if tc.get("id"):
                slot["id"] = tc["id"]
            fn = tc.get("function", {})
            if fn.get("name"):
                slot["name"] = fn["name"]
            if fn.get("arguments"):
                slot["arguments"] += fn["arguments"]

    # Flush any residual data_lines not terminated by a blank line (stream ended at [DONE]).
    leftover = _flush()
    if leftover and leftover != "[DONE]":
        try:
            chunk = json.loads(leftover)
            if chunk.get("usage"):
                usage = chunk["usage"]
        except json.JSONDecodeError:
            pass

    tool_calls = []
    for s in tool_calls_acc.values():
        try:
            args = json.loads(s["arguments"]) if s["arguments"] else {}
        except json.JSONDecodeError:
            args = {"_parse_error": s["arguments"]}
        tool_calls.append({"id": s["id"], "name": s["name"], "args": args})

    norm_usage = {
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
    return content, tool_calls, norm_usage


# ---------------------------------------------------------------------------
# Built-in tools
# ---------------------------------------------------------------------------

def _esql_query(query: str):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resp = _client.esql.query(query=query, format="json")
    cols = [c["name"] for c in resp["columns"]]
    all_values = resp["values"]
    rows = []
    for row in all_values[:5]:
        d = dict(zip(cols, row))
        for k, v in d.items():
            if isinstance(v, str) and len(v) > MAX_TOOL_CHARS:
                d[k] = v[:MAX_TOOL_CHARS] + f" ...[{len(v) - MAX_TOOL_CHARS} chars truncated]"
        rows.append(d)
    if len(all_values) > 5:
        rows.append({"_note": f"showing 5 of {len(all_values)} rows"})
    return rows


def _get_mapping(index: str):
    return _client.indices.get_mapping(index=index).body


ESQL_TOOL = {
    "fn": _esql_query,
    "schema": {
        "type": "function",
        "function": {
            "name": "esql_query",
            "description": (
                "Execute an ES|QL query against Elasticsearch and return matching rows. "
                'Full-text search syntax: WHERE MATCH(field, "value") — never use '
                'field MATCH "value". Always include a LIMIT clause.'
            ),
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A complete ES|QL query, e.g. 'FROM my-index | WHERE MATCH(text, \"topic\") | LIMIT 5'",
                    },
                },
            },
        },
    },
}

MAPPING_TOOL = {
    "fn": _get_mapping,
    "schema": {
        "type": "function",
        "function": {
            "name": "get_mapping",
            "description": "Return the field mapping for an Elasticsearch index or pattern.",
            "parameters": {
                "type": "object",
                "required": ["index"],
                "properties": {
                    "index": {
                        "type": "string",
                        "description": "Index name or pattern, e.g. 'browsecomp-plus'",
                    },
                },
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

@dataclass
class AgentRun:
    """Result of a single run_agent call."""
    answer: str | None          # final assistant text; None if hit_limit
    input_tokens: int           # total input tokens across all turns
    output_tokens: int          # total output tokens across all turns
    turns: int                  # number of LLM calls made
    tool_calls: int             # total tool invocations
    turn_input_tokens: list = field(default_factory=list)  # per-turn input — shows quadratic growth
    messages: list = field(default_factory=list)           # full message history — the teaching artifact
    hit_limit: bool = False


def run_agent(
    system_prompt: str,
    question: str,
    tools: list,
    max_turns: int = 12,
    verbose: bool = True,
) -> AgentRun:
    """Run a tool-calling agent loop against EIS.

    tools: list of tool dicts (e.g. [ESQL_TOOL, MAPPING_TOOL])
    Returns AgentRun with token counts, full message history, and per-turn input tokens.
    """
    if max_turns < 1:
        raise ValueError("max_turns must be >= 1")

    tool_map = {t["schema"]["function"]["name"]: t["fn"] for t in tools}

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    total_input = total_output = total_tool_calls = turns = 0
    turn_input_tokens = []

    for turn in range(max_turns):
        turns = turn + 1
        content, tool_calls, usage = stream_chat(messages, tools=tools)

        in_tok = usage["input_tokens"]
        out_tok = usage["output_tokens"]
        total_input += in_tok
        total_output += out_tok
        turn_input_tokens.append(in_tok)

        if in_tok == 0:
            print(f"  WARNING: turn {turns} reported 0 input tokens — usage may not have been flushed")

        if verbose:
            print(f"  turn {turns}: {in_tok:,} input tokens", end="")

        # EIS/Anthropic: assistant content must be a non-empty string even when
        # the turn's purpose is purely to dispatch tool calls.
        assistant_msg: dict = {"role": "assistant", "content": content or "."}
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])},
                }
                for tc in tool_calls
            ]
        messages.append(assistant_msg)

        if not tool_calls:
            if verbose:
                print()
            break

        total_tool_calls += len(tool_calls)
        if verbose:
            names = ", ".join(tc["name"] for tc in tool_calls)
            print(f"  →  [{names}]")

        for tc in tool_calls:
            fn = tool_map.get(tc["name"])
            if fn is None:
                result_str = f"Unknown tool: {tc['name']}"
            else:
                try:
                    result = fn(**tc["args"])
                    result_str = json.dumps(result) if not isinstance(result, str) else result
                except Exception as e:
                    result_str = f"Tool error: {e}"

            # _esql_query already does per-field truncation at MAX_TOOL_CHARS.
            # Safety-net here is 10x to pass multi-row results intact.
            if len(result_str) > MAX_TOOL_CHARS * 10:
                result_str = result_str[:MAX_TOOL_CHARS * 10] + " ...[truncated]"

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result_str or ".",
            })
    else:
        if verbose:
            print(f"\n[hit {max_turns}-turn limit — {total_input:,} input tokens so far]")
        return AgentRun(
            answer=None,
            input_tokens=total_input,
            output_tokens=total_output,
            turns=turns,
            tool_calls=total_tool_calls,
            turn_input_tokens=turn_input_tokens,
            messages=messages,
            hit_limit=True,
        )

    # On a clean exit, return "" rather than None so `run.answer is None` reliably
    # means hit_limit — students write `if run.answer:` to check for a real response.
    answer = content if content else ""
    return AgentRun(
        answer=answer,
        input_tokens=total_input,
        output_tokens=total_output,
        turns=turns,
        tool_calls=total_tool_calls,
        turn_input_tokens=turn_input_tokens,
        messages=messages,
        hit_limit=False,
    )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def load_skill(path: str) -> str:
    """Read a SKILL.md and return its contents as a string."""
    return Path(path).read_text(encoding="utf-8")


def compare(*runs: AgentRun, labels: list | None = None) -> None:
    """Print a side-by-side comparison table for two or more AgentRun results."""
    if labels is None:
        labels = [f"run{i + 1}" for i in range(len(runs))]
    if len(labels) != len(runs):
        raise ValueError(f"len(labels)={len(labels)} must match len(runs)={len(runs)}")

    col_w = max(len(lb) for lb in labels) + 2
    header = (
        f"{'':>{col_w}}  {'turns':>6}  {'tool calls':>10}"
        f"  {'input tokens':>13}  {'output tokens':>14}"
    )
    print(header)
    print("-" * len(header))
    for label, run in zip(labels, runs):
        flag = " !" if run.hit_limit else ""
        print(
            f"{label:>{col_w}}  {run.turns:>6}  {run.tool_calls:>10}"
            f"  {run.input_tokens:>13,}  {run.output_tokens:>14,}{flag}"
        )

    if len(runs) >= 2:
        print()
        baseline_tok = runs[0].input_tokens
        for label, run in zip(labels[1:], runs[1:]):
            if baseline_tok > 0:
                # Positive = fewer tokens (good). Negative = more tokens (regression).
                reduction = (baseline_tok - run.input_tokens) / baseline_tok * 100
                print(f"  {label} vs {labels[0]}: {reduction:+.1f}% fewer input tokens")
