# Valora workspace (frontend)

Next.js 16 · React 19 · Tailwind v4 · motion · Recharts. Deploys to Vercel.

```bash
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local   # omit for demo mode
npm run dev            # http://localhost:3000
npm run build && npm start
```

| Route | Purpose |
|---|---|
| `/` | Homepage: pipeline, capabilities, agent graph, reliability |
| `/app` | Valuation console — query + filters → valuation, judge, risk, comparables, ML prediction, impact, guardrails, agent trace, feedback |
| `/app/compare` | Explain the price gap between two records (hedonic attribution via `/api/v1/compare`) |
| `/app/properties` | Neighborhood medians + sortable index of records |
| `/app/evaluation` | Latest evaluation run, trend, feedback counts |
| `/app/docs` | API reference |

`src/lib/types.ts` holds the API contracts (mirrored by `backend/app/schemas.py`);
`src/lib/api.ts` is the client with a 20 s timeout and a labelled demo-data fallback.
