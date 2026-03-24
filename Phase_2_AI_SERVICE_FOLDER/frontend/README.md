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
| `VITE_API_URL` | API base for axios. Default `/api` (Vite dev proxy). If you set a full URL like `http://localhost:8000`, `src/apiBase.js` appends `/api` so routes match `POST /api/upload`, etc. |

Use `http://host:8000/api` explicitly if you already include the path.

## UX

Tabs: **Upload**, **Processed**, **Indexed**, **Search**, **Insights** (summaries & MCQs against indexed content).
