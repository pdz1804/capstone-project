/**
 * Base URL for REST calls and image URLs (must match FastAPI routes under `/api/...`).
 *
 * - Default `/api` — in dev, Vite proxies `/api` → backend (see vite.config.js).
 * - `VITE_API_URL=/api` — same as default.
 * - `VITE_API_URL=http://localhost:8000` — normalized to `http://localhost:8000/api`
 *   so paths like `${base}/upload` hit `POST /api/upload`, not `POST /upload`.
 */
export function getApiBase() {
  const raw = (import.meta.env.VITE_API_URL ?? '').trim()
  if (!raw) return '/api'

  if (raw.startsWith('/')) {
    return raw.replace(/\/+$/, '') || '/api'
  }

  if (/^https?:\/\//i.test(raw)) {
    try {
      const u = new URL(raw)
      const path = u.pathname.replace(/\/+$/, '') || '/'
      if (path === '/') {
        u.pathname = '/api'
      } else if (path === '/api' || path.startsWith('/api/')) {
        u.pathname = path
      } else {
        u.pathname = path.endsWith('/api') ? path : `${path}/api`
      }
      return `${u.origin}${u.pathname}`.replace(/\/+$/, '')
    } catch {
      return '/api'
    }
  }

  return '/api'
}
