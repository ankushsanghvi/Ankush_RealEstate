"""Thin, defensive wrapper around the Anthropic SDK.

Design: every agent that uses the LLM asks for a *typed* result (a Pydantic
model) and always has a deterministic fallback. This wrapper therefore returns
`None` on any failure instead of raising, and records which engine answered so
the response can say honestly whether it was "llm", "llm-degraded" (fallback
model) or "rules" (no LLM at all).

Structured output strategy (self-healing):
  * `native`  – Anthropic structured outputs (`messages.parse`, JSON schema enforced server-side).
  * `json`    – the schema is placed in the system prompt and the reply is parsed
                defensively (code fences stripped, first JSON object extracted, validated).
  `auto` tries native once; if the provider ignores it (some gateways strip
  `output_config`), the wrapper switches to `json` for the rest of the process.

API format: `messages` uses the official Anthropic SDK (api.anthropic.com or an
Anthropic-compatible gateway). `chat` posts OpenAI-style JSON to
`{base_url}/v1/chat/completions` for gateways that expose newer/cheaper models only
in that format; it always uses the json-instruction strategy.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I | re.M)


def extract_json(text: str) -> str:
    """Pull the first balanced JSON object out of free text."""
    text = _FENCE.sub("", text.strip())
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in response")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError("unbalanced JSON object in response")


class ChatHTTPError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class LLM:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.llm_model
        self.fallback_model = settings.llm_fallback_model
        self.mode = settings.llm_structured_output  # auto | native | json
        self.enabled = bool(settings.anthropic_api_key) and settings.llm_enabled
        self.calls = 0
        self.failures = 0
        self.degraded_calls = 0
        self.total_latency_ms = 0
        self.last_error: str | None = None
        self.consecutive_failures = 0
        self.cooldown_until = 0.0   # circuit breaker: skip the LLM entirely while open
        self._client = None
        self._http = None
        self.api_format = settings.llm_api_format
        if self.enabled and self.api_format == "chat":
            import httpx

            self._http = httpx.Client(base_url=(settings.anthropic_base_url or "https://api.anthropic.com").rstrip("/"), timeout=settings.llm_timeout_s,
                                      headers={"Authorization": f"Bearer {settings.anthropic_api_key}", "Content-Type": "application/json"})
            self.mode = "json"
        elif self.enabled:
            import anthropic

            self._client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key, base_url=settings.anthropic_base_url or None,
                timeout=settings.llm_timeout_s, max_retries=1,
            )

    @property
    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "provider": self.settings.anthropic_base_url or "api.anthropic.com",
            "model": self.model if self.enabled else None,
            "fallbackModel": self.fallback_model if self.enabled else None,
            "fastModel": self.settings.llm_fast_model if self.enabled else None,
            "apiFormat": self.api_format,
            "structuredOutput": self.mode,
            "calls": self.calls,
            "failures": self.failures,
            "degradedCalls": self.degraded_calls,
            "avgLatencyMs": int(self.total_latency_ms / self.calls) if self.calls else None,
            "lastError": self.last_error,
            "circuitOpenForS": max(0, int(self.cooldown_until - time.time())) or None,
        }

    # ---- OpenAI-style chat completions (gateway) ----
    def _chat(self, model: str, system: str, messages: list[dict], max_tokens: int) -> str:
        import httpx

        resp = self._http.post("/v1/chat/completions", json={"model": model, "max_tokens": max_tokens, "messages": [{"role": "system", "content": system}, *messages]})
        if resp.status_code >= 400:
            raise ChatHTTPError(resp.status_code, resp.text[:200])
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(f"unexpected chat response shape: {str(data)[:120]}") from e

    def _call_chat(self, model: str, system: str, user: str, schema: type[T], max_tokens: int) -> T | None:
        schema_json = json.dumps(schema.model_json_schema(), separators=(",", ":"))
        sys_prompt = f"{system}\n\nRespond with ONLY a JSON object (no prose, no markdown fences) that validates against this JSON Schema:\n{schema_json}"
        text = self._chat(model, sys_prompt, [{"role": "user", "content": user}], max_tokens)
        try:
            return schema.model_validate_json(extract_json(text))
        except (ValueError, ValidationError) as e:
            fixed = self._chat(model, sys_prompt, [{"role": "user", "content": user}, {"role": "assistant", "content": text}, {"role": "user", "content": f"That was not valid against the schema ({e!s:.200}). Reply again with ONLY the corrected JSON object."}], max_tokens)
            return schema.model_validate_json(extract_json(fixed))

    # ---- one call, one model ----
    def _call(self, model: str, system: str, user: str, schema: type[T], max_tokens: int) -> T | None:
        if self.api_format == "chat":
            return self._call_chat(model, system, user, schema, max_tokens)
        if self.mode in ("auto", "native"):
            try:
                resp = self._client.messages.parse(model=model, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}], output_format=schema)
                if resp.stop_reason == "refusal":
                    log.warning("LLM refusal (%s)", getattr(resp.stop_details, "category", None))
                    return None
                if resp.parsed_output is not None:
                    return resp.parsed_output
            except ValidationError:
                if self.mode == "native":
                    raise
                log.warning("provider ignored structured outputs; switching to json-instruction mode")
                self.mode = "json"
        schema_json = json.dumps(schema.model_json_schema(), separators=(",", ":"))
        sys_prompt = (
            f"{system}\n\nRespond with ONLY a JSON object (no prose, no markdown fences) that validates against this JSON Schema:\n{schema_json}"
        )
        resp = self._client.messages.create(model=model, max_tokens=max_tokens, system=sys_prompt, messages=[{"role": "user", "content": user}])
        if resp.stop_reason == "refusal":
            return None
        text = "".join(b.text for b in resp.content if b.type == "text")
        try:
            return schema.model_validate_json(extract_json(text))
        except (ValueError, ValidationError) as e:
            log.warning("JSON parse failed (%s): %s", type(e).__name__, text[:200])
            # one repair attempt: ask the same model to fix its own output
            fix = self._client.messages.create(
                model=model, max_tokens=max_tokens, system=sys_prompt,
                messages=[{"role": "user", "content": user}, {"role": "assistant", "content": text}, {"role": "user", "content": f"That was not valid against the schema ({e!s:.200}). Reply again with ONLY the corrected JSON object."}],
            )
            fixed = "".join(b.text for b in fix.content if b.type == "text")
            return schema.model_validate_json(extract_json(fixed))

    def parse(self, system: str, user: str, schema: type[T], max_tokens: int = 2048, tier: str = "primary") -> tuple[T | None, str]:
        """Structured-output call. Returns (parsed_or_None, engine). tier="fast" uses the
        cheaper fast model (if configured) with the primary as its fallback."""
        if not self.enabled or (self._client is None and self._http is None) or time.time() < self.cooldown_until:
            return None, "rules"
        import anthropic
        import httpx

        chain = (self.settings.llm_fast_model, self.model) if tier == "fast" and self.settings.llm_fast_model else (self.model, self.fallback_model)
        for attempt, model in enumerate(chain):
            self.calls += 1
            t0 = time.perf_counter()
            try:
                parsed = self._call(model, system, user, schema, max_tokens)
                ms = int((time.perf_counter() - t0) * 1000)
                self.total_latency_ms += ms
                if parsed is None:
                    self.failures += 1
                    continue
                log.info("llm %s ok in %dms (%s)", model, ms, self.mode)
                self.last_error = None
                self.consecutive_failures = 0
                if attempt == 1 and tier != "fast":
                    self.degraded_calls += 1
                    return parsed, "llm-degraded"
                return parsed, "llm"
            except anthropic.AuthenticationError as e:
                log.error("LLM auth failed, disabling LLM: %s", e)
                self.last_error = "authentication failed"
                self.failures += 1
                self.enabled = False
                return None, "rules"
            except (anthropic.APITimeoutError, anthropic.RateLimitError, anthropic.APIConnectionError, httpx.TimeoutException, httpx.TransportError) as e:
                log.warning("LLM %s transient failure (%s); trying fallback", model, type(e).__name__)
                self.last_error = f"{model}: {type(e).__name__}"
                self.failures += 1
                continue
            except (anthropic.APIStatusError, ChatHTTPError) as e:
                log.warning("LLM %s status %s: %s", model, e.status_code, str(e.message)[:200])
                self.last_error = f"{model}: HTTP {e.status_code} " + ("insufficient balance" if e.status_code == 402 else str(e.message)[:80])
                self.failures += 1
                if e.status_code == 401:
                    self.last_error = "authentication failed"
                    self.enabled = False
                    return None, "rules"
                if e.status_code in (402, 403):
                    self._trip(f"HTTP {e.status_code}")
                    return None, "rules"
                continue
            except (ValueError, ValidationError) as e:
                log.warning("LLM %s unparseable output: %s", model, str(e)[:200])
                self.last_error = f"{model}: unparseable output"
                self.failures += 1
                continue
            except Exception as e:  # noqa: BLE001 — never let the LLM take the pipeline down
                log.exception("LLM unexpected error: %s", e)
                self.last_error = f"{model}: {type(e).__name__}"
                self.failures += 1
                continue
        self.consecutive_failures += 1
        if self.consecutive_failures >= 4:
            self._trip("repeated failures")
        return None, "rules"

    def _trip(self, why: str, seconds: int = 60) -> None:
        """Open the circuit: serve rules mode for `seconds` instead of paying for failing calls."""
        self.cooldown_until = time.time() + seconds
        self.consecutive_failures = 0
        log.warning("LLM circuit opened for %ds (%s); serving rules mode", seconds, why)
