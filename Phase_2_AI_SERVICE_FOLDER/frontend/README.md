# Phase 2 AI Service — Frontend

Vite + React 18 + Tailwind. The dev server proxies `/api` to `http://localhost:8000` (see `vite.config.js`).

## Scripts

```bash
npm install
npm run dev      # http://localhost:3000
npm run build
npm run preview
```

## Environment

| Variable | Purpose |
|----------|---------|
| `VITE_API_URL` | API prefix for axios (default `/api` — works with Vite proxy in dev) |

In production behind nginx or another host, set `VITE_API_URL` to the full public API base if needed.

## UX

Tabs: **Upload**, **Processed**, **Indexed**, **Search**, **Insights** (summaries & MCQs against indexed content).
