import { useEffect, useMemo, useState, useRef } from 'react';
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
import { AdminSortHeader, AdminTablePagination, type SortDirection } from '../components/admin/AdminTableControls';

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

type StatusFilter = 'all' | '2xx' | '4xx' | '5xx';
type MethodFilter = 'ALL' | 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'OPTIONS';

function normalizeDays(v: number): number {
  if (DAY_OPTIONS.includes(v as (typeof DAY_OPTIONS)[number])) return v;
  return 30;
}

export default function AdminInvocationsView() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [days, setDays] = useState<number>(() => normalizeDays(Number(searchParams.get('days') || 30)));
  const [userId, setUserId] = useState<string>(() => searchParams.get('user_id') || '');
  const [feature, setFeature] = useState<string>(() => searchParams.get('feature') || '');
  const [modelId, setModelId] = useState<string>(() => searchParams.get('model_id') || '');

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [methodFilter, setMethodFilter] = useState<MethodFilter>('ALL');
  const [pathFilter, setPathFilter] = useState('');
  const [keyword, setKeyword] = useState('');

  const [items, setItems] = useState<AdminInvocationRecord[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [facets, setFacets] = useState<{ features?: string[]; models?: string[] }>({});
  const [users, setUsers] = useState<UserEntity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [sortKey, setSortKey] = useState<
    'time' | 'methodPath' | 'feature' | 'user' | 'model' | 'status' | 'latency' | 'in' | 'out' | 'cost'
  >('time');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const mounted = useRef(true);
  useEffect(() => {
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = async (nextPage = page, cacheBust = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAdminInvocations({
        days,
        user_id: userId || undefined,
        feature: feature || undefined,
        model_id: modelId || undefined,
        method: methodFilter === 'ALL' ? undefined : methodFilter,
        status_family: statusFilter === 'all' ? undefined : statusFilter,
        path_query: pathFilter || undefined,
        query: keyword || undefined,
        skip: (nextPage - 1) * pageSize,
        limit: pageSize,
        sort_by: sortKey,
        sort_dir: sortDirection,
        cache_bust: cacheBust,
      });

      if (!mounted.current) return;

      setItems(data.items || []);
      setTotalItems(Number(data.count || 0));
      setFacets(data.facets || {});

      const nextParams = new URLSearchParams();
      nextParams.set('days', String(days));
      if (userId) nextParams.set('user_id', userId);
      if (feature) nextParams.set('feature', feature);
      if (modelId) nextParams.set('model_id', modelId);
      setSearchParams(nextParams, { replace: true });
    } catch (e: any) {
      if (!mounted.current) return;
      setError(e?.response?.data?.detail || e?.message || 'Failed to load invocation logs');
    } finally {
      if (mounted.current) setLoading(false);
    }
  };

  useEffect(() => {
    void Promise.all([
      load(1),
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

  const featureOptions = useMemo(() => (facets.features || []).slice(0, 200), [facets.features]);

  const modelOptions = useMemo(() => (facets.models || []).slice(0, 200), [facets.models]);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(totalItems / Math.max(1, pageSize))), [pageSize, totalItems]);

  useEffect(() => {
    setPage((current) => Math.min(Math.max(1, current), totalPages));
  }, [totalPages]);

  const paged = items;

  useEffect(() => {
    void load(page);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, sortDirection, sortKey]);

  const setSort = (
    next:
      | 'time'
      | 'methodPath'
      | 'feature'
      | 'user'
      | 'model'
      | 'status'
      | 'latency'
      | 'in'
      | 'out'
      | 'cost',
    defaultDirection: SortDirection = 'asc',
  ) => {
    setPage(1);
    if (sortKey === next) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(next);
    setSortDirection(defaultDirection);
  };

  return (
    <div className="space-y-4">
      <div className={adminUi.panel}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-sky-600">Admin</p>
            <h2 className="text-xl font-black text-slate-900 tracking-tight">All API Invocation Logs</h2>
            <p className="mt-1 text-xs text-slate-500">Showing {nf(items.length)} of {nf(totalItems)} matching records</p>
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
              onClick={() => void load(page, true)}
              className={`inline-flex items-center gap-2 ${adminUi.buttonSoft}`}
            >
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 xl:grid-cols-5 gap-2">
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
            onClick={() => {
              setPage(1);
              void load(1, true);
            }}
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
              setPage(1);
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
          <>
            <table className={adminUi.table}>
              <thead className={adminUi.thead}>
                <tr>
                  <th className={adminUi.th}>
                    <AdminSortHeader
                      label="Time"
                      active={sortKey === 'time'}
                      direction={sortDirection}
                      onClick={() => setSort('time', 'desc')}
                    />
                  </th>
                  <th className={adminUi.th}>
                    <AdminSortHeader
                      label="Method / Path"
                      active={sortKey === 'methodPath'}
                      direction={sortDirection}
                      onClick={() => setSort('methodPath', 'asc')}
                    />
                  </th>
                  <th className={adminUi.th}>
                    <AdminSortHeader
                      label="Feature"
                      active={sortKey === 'feature'}
                      direction={sortDirection}
                      onClick={() => setSort('feature', 'asc')}
                    />
                  </th>
                  <th className={adminUi.th}>
                    <AdminSortHeader
                      label="User"
                      active={sortKey === 'user'}
                      direction={sortDirection}
                      onClick={() => setSort('user', 'asc')}
                    />
                  </th>
                  <th className={adminUi.th}>
                    <AdminSortHeader
                      label="Model"
                      active={sortKey === 'model'}
                      direction={sortDirection}
                      onClick={() => setSort('model', 'asc')}
                    />
                  </th>
                  <th className={adminUi.thRight}>
                    <AdminSortHeader
                      label="Status"
                      active={sortKey === 'status'}
                      direction={sortDirection}
                      onClick={() => setSort('status', 'desc')}
                      align="right"
                    />
                  </th>
                  <th className={adminUi.thRight}>
                    <AdminSortHeader
                      label="Latency"
                      active={sortKey === 'latency'}
                      direction={sortDirection}
                      onClick={() => setSort('latency', 'desc')}
                      align="right"
                    />
                  </th>
                  <th className={adminUi.thRight}>
                    <AdminSortHeader
                      label="In"
                      active={sortKey === 'in'}
                      direction={sortDirection}
                      onClick={() => setSort('in', 'desc')}
                      align="right"
                    />
                  </th>
                  <th className={adminUi.thRight}>
                    <AdminSortHeader
                      label="Out"
                      active={sortKey === 'out'}
                      direction={sortDirection}
                      onClick={() => setSort('out', 'desc')}
                      align="right"
                    />
                  </th>
                  <th className={adminUi.thRight}>
                    <AdminSortHeader
                      label="Cost"
                      active={sortKey === 'cost'}
                      direction={sortDirection}
                      onClick={() => setSort('cost', 'desc')}
                      align="right"
                    />
                  </th>
                </tr>
              </thead>
              <tbody>
                {paged.map((row, idx) => (
                  <tr key={row.usage_id} className={adminRowClass((page - 1) * pageSize + idx)}>
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
                {items.length === 0 && (
                  <tr>
                    <td colSpan={10} className="px-3 py-6 text-sm text-slate-500 text-center">
                      No invocation logs match the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            <div className="border-t border-slate-100 px-3 py-2">
              <AdminTablePagination
                page={page}
                pageSize={pageSize}
                totalItems={totalItems}
                onPageChange={(next) => setPage(Math.min(Math.max(1, next), totalPages))}
                onPageSizeChange={(nextSize) => {
                  setPageSize(nextSize);
                  setPage(1);
                }}
                itemLabel="invocations"
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
