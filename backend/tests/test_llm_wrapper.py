"""LLM wrapper tests against fake transports — no network, no real key."""
import json

import httpx
import pytest
from pydantic import BaseModel

from app.agents.llm import LLM, extract_json
from app.config import Settings


class Out(BaseModel):
    intent: str
    bedrooms: int | None = None


def make_llm(handler, fmt="chat", **kw):
    s = Settings(anthropic_api_key="test-key", anthropic_base_url="https://gateway.test", llm_api_format=fmt, llm_model="m-primary", llm_fallback_model="m-fallback", llm_enabled=True, **kw)
    llm = LLM(s)
    llm._http = httpx.Client(base_url="https://gateway.test", transport=httpx.MockTransport(handler), headers={"Authorization": "Bearer test-key"})
    return llm


def chat_reply(content, status=200):
    return httpx.Response(status, json={"choices": [{"message": {"role": "assistant", "content": content}}]} if status == 200 else {"error": {"message": content}})


def test_extract_json_handles_fences_and_prose():
    assert json.loads(extract_json('Sure! ```json\n{"a": 1, "b": {"c": "}"}}\n``` done')) == {"a": 1, "b": {"c": "}"}}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_chat_format_parses_structured_json():
    seen = {}

    def handler(req: httpx.Request):
        seen["path"] = req.url.path
        seen["auth"] = req.headers.get("authorization")
        body = json.loads(req.content)
        seen["model"] = body["model"]
        assert body["messages"][0]["role"] == "system" and "JSON Schema" in body["messages"][0]["content"]
        return chat_reply('```json\n{"intent": "valuation", "bedrooms": 3}\n```')

    out, engine = make_llm(handler).parse("sys", "3 bed house worth?", Out)
    assert engine == "llm" and out.intent == "valuation" and out.bedrooms == 3
    assert seen == {"path": "/v1/chat/completions", "auth": "Bearer test-key", "model": "m-primary"}


def test_chat_format_repairs_invalid_json_once():
    calls = []

    def handler(req):
        calls.append(json.loads(req.content))
        return chat_reply("I think the intent is valuation." if len(calls) == 1 else '{"intent": "valuation"}')

    out, engine = make_llm(handler).parse("sys", "q", Out)
    assert out.intent == "valuation" and len(calls) == 2 and calls[1]["messages"][-1]["role"] == "user"


def test_billing_error_opens_circuit_and_falls_back_to_rules():
    calls = []

    def handler(req):
        calls.append(1)
        return chat_reply("Insufficient Balance", status=402)

    llm = make_llm(handler)
    assert llm.parse("sys", "q", Out) == (None, "rules")
    assert llm.status["circuitOpenForS"] and "insufficient balance" in llm.status["lastError"]
    assert llm.parse("sys", "q", Out) == (None, "rules")
    assert len(calls) == 1  # second call never hit the network


def test_transient_error_uses_fallback_model_and_reports_degraded():
    models = []

    def handler(req):
        models.append(json.loads(req.content)["model"])
        return httpx.Response(503, json={"error": "upstream"}) if len(models) == 1 else chat_reply('{"intent": "similar_properties"}')

    out, engine = make_llm(handler).parse("sys", "q", Out)
    assert engine == "llm-degraded" and out.intent == "similar_properties" and models == ["m-primary", "m-fallback"]


def test_disabled_without_key():
    llm = LLM(Settings(anthropic_api_key=None))
    assert llm.parse("sys", "q", Out) == (None, "rules") and llm.enabled is False
