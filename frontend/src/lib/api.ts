import type { QueryResponse, QueryFilters, EvalSummary, FeedbackPayload, Property, CompareResponse } from "./types";
import { mockQuery, MOCK_EVAL, PROPERTIES, applyFilters } from "./mock";
import { sleep } from "./utils";

/* ------------------------------------------------------------------
   API client with graceful degradation.
   - If NEXT_PUBLIC_API_URL is set and reachable → live mode.
   - Otherwise (or on timeout / 5xx) → deterministic demo mode so the
     UI never dead-ends. The response carries `mode` so the UI can
     surface a "Demo data" badge honestly.
   ------------------------------------------------------------------ */

export const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";
const TIMEOUT_MS = 120000; // LLM mode makes 3 model calls per query; gateways can take 10-20 s each

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_URL) throw new Error("no-api-url");
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error(`http-${res.status}`);
    return (await res.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

export async function runQuery(query: string, filters: QueryFilters, opts?: { topK?: number }): Promise<QueryResponse> {
  try {
    const data = await request<QueryResponse>("/api/v1/query", {
      method: "POST",
      body: JSON.stringify({ query, filters, top_k: opts?.topK ?? 8 }),
    });
    return { ...data, mode: "live" };
  } catch {
    await sleep(900 + Math.random() * 600); // simulate pipeline latency
    return mockQuery(query, filters);
  }
}

export async function getEvaluation(): Promise<EvalSummary> {
  try {
    return await request<EvalSummary>("/api/v1/evaluation/latest");
  } catch {
    await sleep(300);
    return MOCK_EVAL;
  }
}

export async function listProperties(filters: QueryFilters = {}): Promise<{ items: Property[]; total: number; mode: "live" | "demo" }> {
  try {
    const data = await request<{ items: Property[]; total: number }>("/api/v1/properties", {
      method: "POST",
      body: JSON.stringify(filters),
    });
    return { ...data, mode: "live" };
  } catch {
    await sleep(200);
    const items = applyFilters(PROPERTIES, filters);
    return { items, total: items.length, mode: "demo" };
  }
}

export async function sendFeedback(payload: FeedbackPayload): Promise<{ ok: boolean; mode: "live" | "demo" }> {
  try {
    await request("/api/v1/feedback", { method: "POST", body: JSON.stringify(payload) });
    return { ok: true, mode: "live" };
  } catch {
    await sleep(250);
    return { ok: true, mode: "demo" };
  }
}

export async function compareProperties(a: string, b: string): Promise<CompareResponse | null> {
  try {
    return await request<CompareResponse>("/api/v1/compare", { method: "POST", body: JSON.stringify({ a, b }) });
  } catch {
    return null; // caller falls back to the local hedonic approximation
  }
}

export async function healthcheck(): Promise<{ ok: boolean; mode: "live" | "demo"; latencyMs: number; engine?: string; embedding?: string; records?: number; llmError?: string | null; llmModel?: string | null }> {
  const t0 = performance.now();
  try {
    const h = await request<{ engine: string; embedding: string; records: number; llm: { lastError?: string | null; model?: string | null } }>("/health");
    return { ok: true, mode: "live", latencyMs: Math.round(performance.now() - t0), engine: h.engine, embedding: h.embedding, records: h.records, llmError: h.llm?.lastError ?? null, llmModel: h.llm?.model ?? null };
  } catch {
    return { ok: false, mode: "demo", latencyMs: Math.round(performance.now() - t0) };
  }
}
