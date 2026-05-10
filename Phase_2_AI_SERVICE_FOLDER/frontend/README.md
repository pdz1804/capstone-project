# Phase 2 AI Service   Frontend

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

- **Processed** loads **`GET /api/processed-documents`** (stage-ordered document groups + pipeline-wide metadata). If the API fails or returns an empty layout, the UI falls back to flat **`GET /api/files`** `processed` rows and shows a warning banner.
- **Preview** on a file row calls **`GET /api/processed-file?rel_path=…`** (same axios defaults as other calls). **`ProcessedFilePreviewModal`** renders by type: markdown (`react-markdown` + GFM), JSON (pretty-printed), plain text, PDF (`iframe` + blob URL), images, video (`<video controls>`), or download prompt for unknown binary.
- **Status** polling uses **`GET /api/status`** without **`fresh`** on an interval; after uploads/process/index or manual refresh, the app requests **`fresh=true`** so Qdrant-backed counts update immediately while routine polling avoids hammering the backend cache window.
- **Multi-user:** axios is configured (see `src/main.jsx`) to send **`X-User-Id`** when set (e.g. localStorage), matching backend storage isolation.
