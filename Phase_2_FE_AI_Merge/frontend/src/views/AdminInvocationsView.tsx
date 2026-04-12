import { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  Loader2,
  RefreshCw,
  Search,
  X,
} from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { listAdminInvocations, type AdminInvocationRecord } from '../api/ragApi';
import { userRepo } from '../repositories/user_repository';
import type { UserEntity } from '../database/types';
import { adminRowClass, adminUi } from '../lib/adminUi';

function nf(n: number): string {
  return new Intl.NumberFormat('en-US').format(n || 0);
}

function usd(n: number): string {
  return `$${(n || 0).toFixed(4)}`;
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function compact(v: string, max = 26): string {
  if (!v) return '-';
  if (v.length <= max) return v;
  return `${v.slice(0, Math.max(8, max - 10))}...${v.slice(-6)}`;
}

const DAY_OPTIONS = [1, 7, 30, 90, 180, 365] as const;
const LIMIT_OPTIONS = [100, 300, 1000, 5000] as const;

type StatusFilter = 'all' | '2xx' | '4xx' | '5xx';
type MethodFilter = 'ALL' | 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'OPTIONS';

function normalizeDays(v: number): number {
  if (DAY_OPTIONS.includes(v as (typeof DAY_OPTIONS)[number])) return v;
  return 30;
}

function normalizeLimit(v: number): number {
  if (LIMIT_OPTIONS.includes(v as (typeof LIMIT_OPTIONS)[number])) return v;
  return 1000;
}

export default function AdminInvocationsView() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [days, setDays] = useState<number>(() => normalizeDays(Number(searchParams.get('days') || 30)));
  const [limit, setLimit] = useState<number>(() => normalizeLimit(Number(searchParams.get('limit') || 1000)));
  const [userId, setUserId] = useState<string>(() => searchParams.get('user_id') || '');
  const [feature, setFeature] = useState<string>(() => searchParams.get('feature') || '');
  const [modelId, setModelId] = useState<string>(() => searchParams.get('model_id') || '');

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [methodFilter, setMethodFilter] = useState<MethodFilter>('ALL');
  const [pathFilter, setPathFilter] = useState('');
  const [keyword, setKeyword] = useState('');

  const [items, setItems] = useState<AdminInvocationRecord[]>([]);
  const [users, setUsers] = useState<UserEntity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAdminInvocations({
        days,
        limit,
        user_id: userId || undefined,
        feature: feature || undefined,
        model_id: modelId || undefined,
      });
      setItems(data.items || []);

      const nextParams = new URLSearchParams();
      nextParams.set('days', String(days));
      nextParams.set('limit', String(limit));
      if (userId) nextParams.set('user_id', userId);
      if (feature) nextParams.set('feature', feature);
      if (modelId) nextParams.set('model_id', modelId);
      setSearchParams(nextParams, { replace: true });
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load invocation logs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void Promise.all([
      load(),
      userRepo.listAdminUsers({ limit: 1000 }).then((res) => setUsers(res.items || [])).catch(() => setUsers([])),
    ]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const userMap = useMemo(() => {
    const m = new Map<string, UserEntity>();
    for (const u of users) m.set(u.uid, u);
    return m;
  }, [users]);

  const userOptions = useMemo(() => {
    const arr = [...users];
    arr.sort((a, b) => {
      const an = (a.displayName || a.username || a.email || '').toLowerCase();
      const bn = (b.displayName || b.username || b.email || '').toLowerCase();
      return an.localeCompare(bn);
    });
    return arr;
  }, [users]);

  const userLabel = (uid: string): string => {
    const u = userMap.get(uid);
    if (!u) return 'Unknown user';
    return u.displayName || u.username || u.email || 'Unknown user';
  };

  const featureOptions = useMemo(
    () => Array.from(new Set(items.map((x) => x.feature).filter((x) => !!x))).slice(0, 200),
    [items],
  );

  const modelOptions = useMemo(
    () => Array.from(new Set(items.map((x) => x.model_id || '').filter((x) => !!x))).slice(0, 200),
    [items],
  );

  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    const pathKw = pathFilter.trim().toLowerCase();

    return items.filter((row) => {
      if (methodFilter !== 'ALL' && String(row.method || '').toUpperCase() !== methodFilter) return false;
      if (statusFilter === '2xx' && !(row.status_code >= 200 && row.status_code < 300)) return false;
      if (statusFilter === '4xx' && !(row.status_code >= 400 && row.status_code < 500)) return false;
      if (statusFilter === '5xx' && !(row.status_code >= 500 && row.status_code < 600)) return false;
      if (pathKw && !String(row.path || '').toLowerCase().includes(pathKw)) return false;
      if (!kw) return true;

      const searchHaystack = [
        row.usage_id,
        row.user_id,
        row.feature,
        row.path,
        row.model_id || '',
        row.method,
        String(row.status_code),
      ]
        .join(' ')
        .toLowerCase();

      return searchHaystack.includes(kw);
    });
  }, [items, keyword, methodFilter, pathFilter, statusFilter]);

  return (
    <div className="space-y-4">
      <div className={adminUi.panel}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-sky-600">Admin</p>
            <h2 className="text-xl font-black text-slate-900 tracking-tight">All API Invocation Logs</h2>
            <p className="mt-1 text-xs text-slate-500">Showing {nf(filtered.length)} of {nf(items.length)} loaded records</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => navigate('/admin/dashboard')}
              className={`inline-flex items-center gap-2 ${adminUi.buttonSoft}`}
            >
              <ArrowLeft className="w-4 h-4" /> Dashboard
            </button>
            <button
              type="button"
              onClick={() => void load()}
              className={`inline-flex items-center gap-2 ${adminUi.buttonSoft}`}
            >
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-2">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className={adminUi.select}
            title="Time window"
            aria-label="Time window"
          >
            <option value={1}>Last 1 day</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={180}>Last 180 days</option>
            <option value={365}>Last 365 days</option>
          </select>

          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className={adminUi.select}
            title="Load limit"
            aria-label="Load limit"
          >
            <option value={100}>Load 100 rows</option>
            <option value={300}>Load 300 rows</option>
            <option value={1000}>Load 1000 rows</option>
            <option value={5000}>Load 5000 rows</option>
          </select>

          <select
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className={adminUi.select}
            title="User filter"
            aria-label="User filter"
          >
            <option value="">All users</option>
            {userOptions.map((u) => (
              <option key={u.uid} value={u.uid}>{u.displayName || u.username || u.email || 'Unknown user'}</option>
            ))}
          </select>

          <select
            value={feature}
            onChange={(e) => setFeature(e.target.value)}
            className={adminUi.select}
            title="Feature filter"
            aria-label="Feature filter"
          >
            <option value="">All features</option>
            {featureOptions.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>

          <select
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            className={adminUi.select}
            title="Model filter"
            aria-label="Model filter"
          >
            <option value="">All models</option>
            {modelOptions.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>

          <button
            type="button"
            onClick={() => void load()}
            className={adminUi.buttonPrimary}
          >
            Apply server filters
          </button>
        </div>

        <div className="mt-2 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-2">
          <div className="relative xl:col-span-2">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="Quick search: usage_id, user, feature, path, model, status"
              className={`w-full pl-9 pr-3 ${adminUi.input}`}
            />
          </div>

          <input
            value={pathFilter}
            onChange={(e) => setPathFilter(e.target.value)}
            placeholder="Path contains (e.g. /api/search)"
            className={adminUi.input}
          />

          <select
            value={methodFilter}
            onChange={(e) => setMethodFilter(e.target.value as MethodFilter)}
            className={adminUi.select}
            title="Method filter"
            aria-label="Method filter"
          >
            <option value="ALL">All methods</option>
            <option value="GET">GET</option>
            <option value="POST">POST</option>
            <option value="PUT">PUT</option>
            <option value="PATCH">PATCH</option>
            <option value="DELETE">DELETE</option>
            <option value="OPTIONS">OPTIONS</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            className={adminUi.select}
            title="Status filter"
            aria-label="Status filter"
          >
            <option value="all">All status</option>
            <option value="2xx">2xx Success</option>
            <option value="4xx">4xx Client errors</option>
            <option value="5xx">5xx Server errors</option>
          </select>
        </div>

        <div className="mt-2">
          <button
            type="button"
            onClick={() => {
              setStatusFilter('all');
              setMethodFilter('ALL');
              setPathFilter('');
              setKeyword('');
            }}
            className={`inline-flex items-center gap-2 ${adminUi.buttonSubtle}`}
          >
            <X className="w-4 h-4" /> Clear local filters
          </button>
        </div>

        {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
      </div>

      <div className={adminUi.tableShell}>
        {loading ? (
          <div className="p-6 text-slate-500 flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading invocation logs...
          </div>
        ) : (
          <table className={adminUi.table}>
            <thead className={adminUi.thead}>
              <tr>
                <th className={adminUi.th}>Time</th>
                <th className={adminUi.th}>Method / Path</th>
                <th className={adminUi.th}>Feature</th>
                <th className={adminUi.th}>User</th>
                <th className={adminUi.th}>Model</th>
                <th className={adminUi.thRight}>Status</th>
                <th className={adminUi.thRight}>Latency</th>
                <th className={adminUi.thRight}>In</th>
                <th className={adminUi.thRight}>Out</th>
                <th className={adminUi.thRight}>Cost</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, idx) => (
                <tr key={row.usage_id} className={adminRowClass(idx)}>
                  <td className={`${adminUi.td} whitespace-nowrap text-slate-600`}>{fmtDate(row.invoked_at)}</td>
                  <td className={adminUi.td}>
                    <p className="font-semibold text-slate-800">{row.method}</p>
                    <p className="text-[11px] text-slate-500" title={row.path}>{compact(row.path, 38)}</p>
                  </td>
                  <td className={adminUi.td}>{row.feature || '-'}</td>
                  <td className={adminUi.td}><span className="font-semibold text-slate-800">{userLabel(row.user_id)}</span></td>
                  <td className={adminUi.td} title={row.model_id || '-'}>{compact(row.model_id || '-', 24)}</td>
                  <td className={adminUi.tdRight}>
                    <span
                      className={[
                        'rounded-full px-2 py-0.5',
                        row.status_code >= 200 && row.status_code < 300
                          ? 'bg-emerald-100 text-emerald-700'
                          : row.status_code >= 500
                            ? 'bg-rose-100 text-rose-700'
                            : 'bg-amber-100 text-amber-700',
                      ].join(' ')}
                    >
                      {row.status_code}
                    </span>
                  </td>
                  <td className={adminUi.tdRight}>{nf(row.duration_ms)} ms</td>
                  <td className={adminUi.tdRight}>{nf(row.token_in)}</td>
                  <td className={adminUi.tdRight}>{nf(row.token_out)}</td>
                  <td className={`${adminUi.tdRight} font-semibold text-amber-700`}>{usd(row.estimated_cost_usd)}</td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={10} className="px-3 py-6 text-sm text-slate-500 text-center">
                    No invocation logs match the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
