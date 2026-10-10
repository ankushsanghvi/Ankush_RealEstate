import type { QueryResponse, QueryFilters, EvalSummary, FeedbackPayload, Property, CompareResponse } from "./types";
import { mockQuery, MOCK_EVAL, PROPERTIES, applyFilters } from "./mock";
import { sleep } from "./utils";

/* ------------------------------------------------------------------
   API client.
   - NEXT_PUBLIC_API_URL set → live mode. A failed request (network,
     timeout, 4xx/5xx) is surfaced as an error for valuations,
     evaluation metrics and feedback: never replaced by invented
     numbers that could pass for a real result.
   - NEXT_PUBLIC_API_URL empty → explicit demo mode with deterministic
     mock data, labelled "demo" throughout the UI.
   The property browser and compare view keep a labelled fallback
   ("demo subset" / "local approx.") because they show records, not
   valuations.
   ------------------------------------------------------------------ */

export const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";
export const DEMO_MODE = !API_URL;

export class ApiError extends Error {
  constructor(public status: number | null, message: string) {
    super(message);
  }
}
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
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new ApiError(res.status, typeof body?.detail === "string" ? body.detail : `Request failed with HTTP ${res.status}`);
    }
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(null, ctrl.signal.aborted ? `No response from the API within ${TIMEOUT_MS / 1000}s` : "Could not reach the API");
  } finally {
    clearTimeout(t);
  }
}

/** Throws ApiError when the configured backend fails; mock data only in demo mode. */
export async function runQuery(query: string, filters: QueryFilters, opts?: { topK?: number }): Promise<QueryResponse> {
  if (DEMO_MODE) {
    await sleep(900 + Math.random() * 600); // simulate pipeline latency
    return mockQuery(query, filters);
  }
  const data = await request<QueryResponse>("/api/v1/query", {
    method: "POST",
    body: JSON.stringify({ query, filters, top_k: opts?.topK ?? 8 }),
  });
  return { ...data, mode: "live" };
}

/** Throws ApiError when the configured backend fails; mock metrics only in demo mode. */
export async function getEvaluation(): Promise<EvalSummary> {
  if (DEMO_MODE) {
    await sleep(300);
    return MOCK_EVAL;
  }
  return request<EvalSummary>("/api/v1/evaluation/latest");
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

/** Throws ApiError when the configured backend rejects or misses the feedback. */
export async function sendFeedback(payload: FeedbackPayload): Promise<{ ok: boolean; mode: "live" | "demo" }> {
  if (DEMO_MODE) {
    await sleep(250);
    return { ok: true, mode: "demo" };
  }
  await request("/api/v1/feedback", { method: "POST", body: JSON.stringify(payload) });
  return { ok: true, mode: "live" };
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
    // A configured-but-unreachable backend is still live mode (queries will error), not demo mode.
    return { ok: false, mode: DEMO_MODE ? "demo" : "live", latencyMs: Math.round(performance.now() - t0) };
  }
}
