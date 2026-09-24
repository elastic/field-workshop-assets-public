"""LangChain BaseChatModel adapter for Elasticsearch's
_inference/chat_completion/<inference_id>/_stream endpoint.

Replaces ChatOpenAI + OpenRouter in the reference notebooks (index_facts_kis.ipynb,
index_metadata_kis.ipynb) so attendees only need an ES API key. Verified live against
a Serverless project (2026-08-03) with plain calls, tool binding, and full multi-turn
tool-call round trips via deepagents.create_deep_agent(model=...).

ChatOpenAI(base_url=...) cannot point at this endpoint directly: the OpenAI SDK sends
`Authorization: Bearer` (ES needs `ApiKey`) and always appends `/chat/completions` to
base_url, while ES needs the inference_id as a URL path segment. Hence this adapter.
"""
import json
from typing import Any, List, Optional

import requests
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool


def _as_text(content) -> str:
    """Normalize LangChain content to a plain string.
    deepagents injects skills as a list of content blocks [{type, text}, ...];
    EIS requires a string.  Join all text blocks; fall back to "." if empty.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text") or block.get("content") or "")
            else:
                parts.append(str(block))
        return "\n".join(p for p in parts if p)
    return str(content) if content is not None else ""


def _lc_message_to_openai_dict(msg: BaseMessage) -> dict:
    if isinstance(msg, ToolMessage):
        content = _as_text(msg.content) or "."
        return {"role": "tool", "tool_call_id": msg.tool_call_id, "content": content}
    role_map = {"human": "user", "ai": "assistant", "system": "system"}
    role = role_map.get(msg.type, msg.type)
    d = {"role": role, "content": _as_text(msg.content) or "."}
    if isinstance(msg, AIMessage) and msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {"name": tc["name"], "arguments": json.dumps(tc.get("args") or {})},
            }
            for tc in msg.tool_calls
        ]
    return d


class ElasticInferenceChatModel(BaseChatModel):
    """Talks directly to ES's chat_completion _stream endpoint (no OpenAI SDK)."""

    es_url: str
    inference_id: str
    api_key: str
    _bound_tools: Optional[List[dict]] = None

    @property
    def _llm_type(self) -> str:
        return "elastic-inference-chat"

    def bind_tools(self, tools, **kwargs):
        from langchain_core.utils.function_calling import convert_to_openai_tool

        new = self.__class__(
            es_url=self.es_url, inference_id=self.inference_id, api_key=self.api_key
        )
        new._bound_tools = [convert_to_openai_tool(t) for t in tools]
        return new

    def _generate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        from langchain_core.messages import SystemMessage, HumanMessage
        sys_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        human_msgs = [m for m in messages if isinstance(m, HumanMessage)]
        other_msgs = [m for m in messages if not isinstance(m, (SystemMessage, HumanMessage))]
        # Keep system + original question + last 18 tool-call messages to stay under EIS payload limit.
        # With 500-char truncated tool results this keeps per-request payload well under the EIS limit
        # even when the agent runs many steps against large-document indices like browsecomp-plus.
        recent = other_msgs[-18:]
        # Anthropic requires every tool_result have a matching tool_use in the preceding message.
        # If summarization middleware trimmed history, the window may start with an orphaned
        # ToolMessage -- drop all leading ToolMessages to avoid EIS 400.
        while recent and isinstance(recent[0], ToolMessage):
            recent = recent[1:]
        trimmed = sys_msgs + human_msgs[:1] + recent

        body = {"messages": [_lc_message_to_openai_dict(m) for m in trimmed]}
        if self._bound_tools:
            body["tools"] = self._bound_tools

        resp = requests.post(
            f"{self.es_url}/_inference/chat_completion/{self.inference_id}/_stream",
            headers={"Authorization": f"ApiKey {self.api_key}", "Content-Type": "application/json"},
            json=body,
            stream=True,
        )
        if not resp.ok:
            raise requests.exceptions.HTTPError(
                f"EIS {resp.status_code}: {resp.text[:2000]}",
                response=resp,
            )

        content = ""
        tool_calls_acc = {}
        finish_reason = None
        usage = {}

        # SSE spec: a single event's `data:` can legitimately span multiple
        # consecutive `data:` lines, joined with "\n" to form one payload --
        # naively json.loads()-ing each line independently breaks the moment
        # model output contains an actual newline. Buffer per-event instead.
        data_lines = []

        def _flush():
            if not data_lines:
                return None
            payload = "\n".join(data_lines)
            data_lines.clear()
            return payload

        # decode_unicode=True decodes per network chunk, not per line -- a
        # multi-byte UTF-8 character split across a chunk boundary comes out
        # as mojibake and corrupts the JSON (intermittent, network-timing
        # dependent). Iterate raw bytes instead; splitting on b"\n" is always
        # byte-safe, so decoding each complete line afterward is always valid.
        for raw_bytes in resp.iter_lines(decode_unicode=False):
            if not raw_bytes:
                # Blank line = event boundary.
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
            chunk = json.loads(data)
            if chunk.get("usage"):
                usage = chunk["usage"]
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            if choices[0].get("finish_reason"):
                finish_reason = choices[0]["finish_reason"]
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

        tool_calls = []
        for slot in tool_calls_acc.values():
            tool_calls.append(
                {
                    "id": slot["id"],
                    "name": slot["name"],
                    "args": json.loads(slot["arguments"]) if slot["arguments"] else {},
                }
            )

        ai_msg = AIMessage(content=content, tool_calls=tool_calls)
        ai_msg.response_metadata["finish_reason"] = finish_reason
        # get_usage_metadata_callback's on_llm_end silently drops usage_metadata
        # if response_metadata["model_name"] is missing -- required, not cosmetic.
        ai_msg.response_metadata["model_name"] = self.inference_id
        ai_msg.usage_metadata = {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])
