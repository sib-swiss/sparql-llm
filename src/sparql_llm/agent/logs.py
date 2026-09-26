"""Log chat requests to a JSONL file (replaces the previous Langfuse tracing).

One line is appended per request (a round of a conversation), multi turn conversations can be
rebuilt by grouping lines on `sessionId`. Field names are kept close to the Langfuse trace
export used by https://github.com/sib-swiss/chat-logs-viewer: `id`, `timestamp`, `sessionId`,
`input`, `output`, `metadata`, `usage`, `totalCost`, plus `endTime`, `latency`, `llmCalls`
and `error`.
"""

from __future__ import annotations

import fcntl
import json
import pathlib
import time
import uuid
from datetime import datetime, timezone
from functools import cache
from typing import Any

import httpx
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from sparql_llm.config import settings
from sparql_llm.utils import logger


@cache
def get_openrouter_prices() -> dict[str, dict[str, float]]:
    """Get the prompt/completion prices per token of all OpenRouter models, fetched once per process.

    Used to estimate the cost of streamed calls (OpenRouter only returns the cost in non streamed
    responses). Also cached on failure, to not retry the request on every LLM call.
    """
    prices: dict[str, dict[str, float]] = {}
    try:
        resp = httpx.get("https://openrouter.ai/api/v1/models", timeout=10)
        for model in resp.json().get("data", []):
            pricing = model.get("pricing") or {}
            prices[model["id"]] = {k: float(v) for k, v in pricing.items() if isinstance(v, (str, int, float))}
    except Exception as e:
        logger.warning(f"⚠️ Could not retrieve models pricing from OpenRouter: {e}")
    return prices


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0) -> float | None:
    """Estimate the cost in USD of a LLM call using the OpenRouter prices."""
    pricing = get_openrouter_prices().get(model)
    # Variable priced models (e.g. openrouter/auto) have negative prices
    if not pricing or any(v < 0 for v in pricing.values()):
        return None
    # Cached prompt tokens are billed at a cheaper rate
    cached = min(cached_tokens, prompt_tokens)
    return (
        (prompt_tokens - cached) * pricing.get("prompt", 0)
        + cached * pricing.get("input_cache_read", pricing.get("prompt", 0))
        + completion_tokens * pricing.get("completion", 0)
    )


class UsageTracker(BaseCallbackHandler):
    """LangChain callback handler collecting token usage and cost of every LLM call of a run.

    One instance per chat request: LangGraph passes it down to all nodes, so calls made by
    the extraction/validation nodes are counted too (they are not part of the final state).
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._models: dict[Any, str] = {}

    def on_chat_model_start(self, serialized: dict[str, Any], messages: Any, **kwargs: Any) -> None:
        """Keep the model name of a starting call (not reliably available when streaming)."""
        params = kwargs.get("invocation_params") or {}
        self._models[kwargs.get("run_id")] = params.get("model_name") or params.get("model") or ""

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        """Same as `on_chat_model_start` for non chat models."""
        self.on_chat_model_start(serialized, prompts, **kwargs)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Record usage of a finished LLM call, from llm_output or from the generated message."""
        llm_output = response.llm_output or {}
        token_usage: dict[str, Any] = llm_output.get("token_usage") or {}
        model = llm_output.get("model_name") or llm_output.get("model") or self._models.pop(kwargs.get("run_id"), "")
        call = {
            "model": model,
            "promptTokens": token_usage.get("prompt_tokens", 0),
            "completionTokens": token_usage.get("completion_tokens", 0),
            "totalTokens": token_usage.get("total_tokens", 0),
            "reasoningTokens": (token_usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
            "cachedTokens": (token_usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
            # OpenRouter returns the cost in USD when usage accounting is enabled
            "cost": token_usage.get("cost"),
        }
        # When streaming, usage is only available on the message itself
        if not call["totalTokens"]:
            for gen_list in response.generations:
                for gen in gen_list:
                    usage = getattr(getattr(gen, "message", None), "usage_metadata", None) or {}
                    if usage:
                        call["promptTokens"] += usage.get("input_tokens", 0)
                        call["completionTokens"] += usage.get("output_tokens", 0)
                        call["totalTokens"] += usage.get("total_tokens", 0)
                        call["reasoningTokens"] += (usage.get("output_token_details") or {}).get("reasoning", 0)
                        call["cachedTokens"] += (usage.get("input_token_details") or {}).get("cache_read", 0)
        # Streamed responses never carry the cost: estimate it from the model prices
        if call["cost"] is None and call["totalTokens"]:
            call["cost"] = estimate_cost(
                call["model"], call["promptTokens"], call["completionTokens"], call["cachedTokens"]
            )
            call["costEstimated"] = call["cost"] is not None
        self.calls.append(call)

    def summary(self) -> dict[str, Any]:
        """Aggregate usage over all the LLM calls of the run."""
        keys = ("promptTokens", "completionTokens", "totalTokens", "reasoningTokens", "cachedTokens")
        return {key: sum(c[key] for c in self.calls) for key in keys}

    def total_cost(self) -> float | None:
        """Total cost in USD, None when no provider reported a cost."""
        costs = [c["cost"] for c in self.calls if isinstance(c["cost"], (int, float))]
        return sum(costs) if costs else None


def log_conversation(
    *,
    inputs: Any,
    output: Any,
    metadata: dict[str, Any],
    session_id: str | None = None,
    usage_tracker: UsageTracker | None = None,
    started_at: float,
    error: str | None = None,
    filepath: str | None = None,
) -> None:
    """Append a finished chat request to the JSONL logs.

    Args:
        inputs: The inputs passed to the graph (messages sent by the user).
        output: The final state of the graph (already converted to plain dicts).
        metadata: Runtime configuration of the request (model, feature flags...).
        session_id: Client session ID used to group multi turn conversations.
        usage_tracker: Handler that collected tokens/cost of the LLM calls.
        started_at: `time.time()` when the request started.
        error: Error message if the request failed.
        filepath: Override the log file path.
    """
    ended_at = time.time()
    entry: dict[str, Any] = {
        "id": uuid.uuid4().hex,
        "timestamp": datetime.fromtimestamp(started_at, tz=timezone.utc).isoformat(),
        "endTime": datetime.fromtimestamp(ended_at, tz=timezone.utc).isoformat(),
        "latency": round(ended_at - started_at, 3),
        "name": settings.app_name,
        "sessionId": session_id,
        "input": inputs,
        "output": output,
        "metadata": metadata,
        "usage": usage_tracker.summary() if usage_tracker else {},
        "totalCost": usage_tracker.total_cost() if usage_tracker else None,
        "llmCalls": usage_tracker.calls if usage_tracker else [],
        "error": error,
    }
    path = pathlib.Path(filepath or settings.requests_logs_filepath)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
        with path.open("a", encoding="utf-8") as f:
            # Lock so lines from concurrent API workers are never interleaved
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(line)
                f.flush()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as e:
        logger.warning(f"⚠️ Could not write conversation log to {path}: {e}")
