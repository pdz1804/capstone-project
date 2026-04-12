import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  Coins,
  Database,
  Loader2,
  RefreshCw,
  Users,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  getAdminDashboard,
  listAdminInvocations,
  type AdminDashboardResponse,
  type AdminInvocationRecord,
} from '../api/ragApi';
import { useNavigate } from 'react-router-dom';

function nf(n: number): string {
  return new Intl.NumberFormat('en-US').format(n || 0);
}

function usd(n: number): string {
  return `$${(n || 0).toFixed(4)}`;
}

function compactUserId(userId: string): string {
  if (!userId) return 'anonymous';
  if (userId.length <= 16) return userId;
  return `${userId.slice(0, 6)}...${userId.slice(-4)}`;
}

function parseTime(raw: string): number {
  const t = Date.parse(raw);
  return Number.isFinite(t) ? t : 0;
}

function filterByHourWindow<T extends { hour: string }>(rows: T[], hours: number): T[] {
  if (!rows.length) return [];
  const sorted = [...rows].sort((a, b) => parseTime(a.hour) - parseTime(b.hour));
  const lastTs = parseTime(sorted[sorted.length - 1]?.hour || '');
  if (!lastTs) return sorted.slice(-Math.max(1, hours));
  const cutoff = lastTs - (Math.max(1, hours) - 1) * 60 * 60 * 1000;
  return sorted.filter((x) => parseTime(x.hour) >= cutoff);
}

function toHourLabel(hour: string): string {
  const d = new Date(hour);
  if (Number.isNaN(d.getTime())) return hour;
  const hh = String(d.getHours()).padStart(2, '0');
  return `${d.getMonth() + 1}/${d.getDate()} ${hh}:00`;
}

type DashboardRange = '1h' | '3h' | '6h' | '12h' | '1d' | '7d' | '30d' | '90d';

const DASHBOARD_RANGES: Record<DashboardRange, {
  label: string;
  title: string;
  days: number;
  useHourly: boolean;
  hours?: number;
}> = {
  '1h': { label: 'Last 1 hour', title: 'last 1h', days: 1, useHourly: true, hours: 1 },
  '3h': { label: 'Last 3 hours', title: 'last 3h', days: 1, useHourly: true, hours: 3 },
  '6h': { label: 'Last 6 hours', title: 'last 6h', days: 1, useHourly: true, hours: 6 },
  '12h': { label: 'Last 12 hours', title: 'last 12h', days: 1, useHourly: true, hours: 12 },
  '1d': { label: 'Last 1 day', title: 'last 24h', days: 1, useHourly: true, hours: 24 },
  '7d': { label: 'Last 7 days', title: 'last 7d', days: 7, useHourly: false },
  '30d': { label: 'Last 30 days', title: 'last 30d', days: 30, useHourly: false },
  '90d': { label: 'Last 90 days', title: 'last 90d', days: 90, useHourly: false },
};

const DASHBOARD_RANGE_OPTIONS: DashboardRange[] = ['1h', '3h', '6h', '12h', '1d', '7d', '30d', '90d'];

export default function AdminDashboardView() {
  const navigate = useNavigate();
  const [selectedRange, setSelectedRange] = useState<DashboardRange>('1h');
  const [dashboard, setDashboard] = useState<AdminDashboardResponse | null>(null);
  const [invocations, setInvocations] = useState<AdminInvocationRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const activeRange = DASHBOARD_RANGES[selectedRange];

  const load = async (targetDays: number) => {
    setLoading(true);
    setError(null);
    try {
      const [dash, logs] = await Promise.all([
        getAdminDashboard(targetDays),
        listAdminInvocations({ days: targetDays, limit: 8 }),
      ]);
      setDashboard(dash);
      setInvocations(logs.items || []);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load admin dashboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(activeRange.days);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRange.days]);

  const featureChart = useMemo(
    () => (dashboard?.requests_by_feature || []).slice(0, 12),
    [dashboard],
  );

  const tokenChart = useMemo(
    () => {
      const hourly = dashboard?.tokens_by_hour || [];
      if (activeRange.useHourly && hourly.length > 0) {
        return filterByHourWindow(hourly, activeRange.hours || 24).map((x) => ({ ...x, label: toHourLabel(x.hour) }));
      }
      return (dashboard?.tokens_by_day || []).slice(-activeRange.days).map((x) => ({ ...x, hour: x.day, label: x.day }));
    },
    [dashboard, activeRange.days, activeRange.hours, activeRange.useHourly],
  );

  const requestChart = useMemo(
    () => {
      const hourly = dashboard?.requests_by_hour || [];
      if (activeRange.useHourly && hourly.length > 0) {
        return filterByHourWindow(hourly, activeRange.hours || 24).map((x) => ({ ...x, label: toHourLabel(x.hour) }));
      }
      return (dashboard?.requests_by_day || []).slice(-activeRange.days).map((x) => ({ ...x, hour: x.day, label: x.day }));
    },
    [dashboard, activeRange.days, activeRange.hours, activeRange.useHourly],
  );

  const activeUserChart = useMemo(
    () => {
      const hourly = dashboard?.active_users_by_hour || [];
      if (activeRange.useHourly && hourly.length > 0) {
        return filterByHourWindow(hourly, activeRange.hours || 24).map((x) => ({ ...x, label: toHourLabel(x.hour) }));
      }
      return (dashboard?.active_users_by_day || []).slice(-activeRange.days).map((x) => ({ ...x, hour: x.day, label: x.day }));
    },
    [dashboard, activeRange.days, activeRange.hours, activeRange.useHourly],
  );

  const statusChart = useMemo(
    () => (dashboard?.requests_by_status || []).slice(0, 10),
    [dashboard],
  );

  const topUsers = useMemo(
    () => (dashboard?.requests_by_user || []).slice(0, 10),
    [dashboard],
  );

  const topUsersChart = useMemo(
    () => topUsers.map((x) => ({ ...x, user_short: compactUserId(x.user_id) })),
    [topUsers],
  );

  const summary = dashboard?.summary || {
    total_requests: 0,
    unique_users: 0,
    token_in: 0,
    token_out: 0,
    estimated_cost_usd: 0,
    avg_duration_ms: 0,
    error_requests: 0,
    error_rate_percent: 0,
  };

  const feedbackCoverage = dashboard?.feedback_coverage || {
    chat_requests: 0,
    feedback_requests: 0,
    coverage_ratio: 0,
    coverage_percent: 0,
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-sky-100 bg-white p-5 shadow-[0_16px_30px_-24px_rgba(14,165,233,0.5)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-sky-600">Admin Dashboard</p>
            <h2 className="text-2xl font-black text-slate-900 tracking-tight">Application Usage and Cost Control</h2>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={selectedRange}
              onChange={(e) => setSelectedRange(e.target.value as DashboardRange)}
              className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm"
              title="Dashboard range"
              aria-label="Dashboard range"
            >
              {DASHBOARD_RANGE_OPTIONS.map((rangeKey) => (
                <option key={rangeKey} value={rangeKey}>{DASHBOARD_RANGES[rangeKey].label}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => void load(activeRange.days)}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
        </div>
        {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="rounded-xl border border-sky-100 bg-white p-4">
          <p className="text-xs text-slate-500">Total API requests</p>
          <p className="mt-2 text-3xl font-black text-blue-700">{nf(summary.total_requests)}</p>
          <Activity className="w-5 h-5 text-blue-500 mt-2" />
        </div>
        <div className="rounded-xl border border-sky-100 bg-white p-4">
          <p className="text-xs text-slate-500">Unique users</p>
          <p className="mt-2 text-3xl font-black text-emerald-700">{nf(summary.unique_users || 0)}</p>
          <Users className="w-5 h-5 text-emerald-500 mt-2" />
        </div>
        <div className="rounded-xl border border-sky-100 bg-white p-4">
          <p className="text-xs text-slate-500">Token in</p>
          <p className="mt-2 text-3xl font-black text-indigo-700">{nf(summary.token_in)}</p>
          <Database className="w-5 h-5 text-indigo-500 mt-2" />
        </div>
        <div className="rounded-xl border border-sky-100 bg-white p-4">
          <p className="text-xs text-slate-500">Token out</p>
          <p className="mt-2 text-3xl font-black text-violet-700">{nf(summary.token_out)}</p>
          <Database className="w-5 h-5 text-violet-500 mt-2" />
        </div>
        <div className="rounded-xl border border-amber-200 bg-amber-50/40 p-4">
          <p className="text-xs text-slate-500">Estimated cost</p>
          <p className="mt-2 text-3xl font-black text-amber-700">{usd(summary.estimated_cost_usd)}</p>
          <Coins className="w-5 h-5 text-amber-500 mt-2" />
        </div>
        <div className="rounded-xl border border-rose-100 bg-rose-50/40 p-4">
          <p className="text-xs text-slate-500">Error rate</p>
          <p className="mt-2 text-3xl font-black text-rose-700">{(summary.error_rate_percent || 0).toFixed(2)}%</p>
          <p className="mt-1 text-xs text-rose-700">{nf(summary.error_requests || 0)} failed calls</p>
        </div>
        <div className="rounded-xl border border-cyan-100 bg-cyan-50/40 p-4">
          <p className="text-xs text-slate-500">Avg latency</p>
          <p className="mt-2 text-3xl font-black text-cyan-700">{nf(summary.avg_duration_ms || 0)} ms</p>
          <p className="mt-1 text-xs text-cyan-700">Across all API invocations</p>
        </div>
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4">
          <p className="text-xs text-slate-500">Feedback coverage / chat</p>
          <p className="mt-2 text-3xl font-black text-emerald-700">{(feedbackCoverage.coverage_percent || 0).toFixed(2)}%</p>
          <p className="mt-1 text-xs text-emerald-700">
            {nf(feedbackCoverage.feedback_requests)} feedback / {nf(feedbackCoverage.chat_requests)} chat
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="rounded-xl border border-sky-100 bg-white p-4 h-[360px]">
          <h3 className="text-sm font-bold text-slate-800 mb-3">API Requests by Feature</h3>
          {loading ? (
            <div className="h-[300px] flex items-center justify-center text-slate-500">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          ) : featureChart.length === 0 ? (
            <div className="h-[300px] flex items-center justify-center text-sm text-slate-500">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={featureChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="feature" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip />
                <Bar dataKey="requests" fill="#2563eb" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="rounded-xl border border-sky-100 bg-white p-4 h-[360px]">
          <h3 className="text-sm font-bold text-slate-800 mb-3">Token Usage Trend ({activeRange.title})</h3>
          {loading ? (
            <div className="h-[300px] flex items-center justify-center text-slate-500">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          ) : tokenChart.length === 0 ? (
            <div className="h-[300px] flex items-center justify-center text-sm text-slate-500">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={tokenChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip />
                <Line type="monotone" dataKey="token_in" stroke="#1d4ed8" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="token_out" stroke="#7c3aed" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="rounded-xl border border-sky-100 bg-white p-4 h-[360px]">
          <h3 className="text-sm font-bold text-slate-800 mb-3">API Requests Trend ({activeRange.title})</h3>
          {loading ? (
            <div className="h-[300px] flex items-center justify-center text-slate-500">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          ) : requestChart.length === 0 ? (
            <div className="h-[300px] flex items-center justify-center text-sm text-slate-500">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={requestChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip />
                <Line type="monotone" dataKey="requests" stroke="#0ea5e9" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="rounded-xl border border-sky-100 bg-white p-4 h-[360px]">
          <h3 className="text-sm font-bold text-slate-800 mb-3">Active Users Trend ({activeRange.title})</h3>
          {loading ? (
            <div className="h-[300px] flex items-center justify-center text-slate-500">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          ) : activeUserChart.length === 0 ? (
            <div className="h-[300px] flex items-center justify-center text-sm text-slate-500">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={activeUserChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip />
                <Line type="monotone" dataKey="users" stroke="#16a34a" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="rounded-xl border border-sky-100 bg-white p-4 h-[360px]">
          <h3 className="text-sm font-bold text-slate-800 mb-3">Top Users by API Requests</h3>
          {loading ? (
            <div className="h-[300px] flex items-center justify-center text-slate-500">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          ) : topUsersChart.length === 0 ? (
            <div className="h-[300px] flex items-center justify-center text-sm text-slate-500">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topUsersChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="user_short" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip />
                <Bar dataKey="requests" fill="#059669" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="rounded-xl border border-sky-100 bg-white p-4 h-[360px]">
          <h3 className="text-sm font-bold text-slate-800 mb-3">Requests by HTTP Status</h3>
          {loading ? (
            <div className="h-[300px] flex items-center justify-center text-slate-500">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          ) : statusChart.length === 0 ? (
            <div className="h-[300px] flex items-center justify-center text-sm text-slate-500">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={statusChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="status_code" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip />
                <Bar dataKey="requests" fill="#dc2626" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-sky-100 bg-white p-4 overflow-auto">
        <h3 className="text-sm font-bold text-slate-800 mb-3">Per-user API Request Detail</h3>
        <table className="w-full text-sm">
          <thead className="bg-sky-50/60 sticky top-0">
            <tr>
              <th className="px-2 py-2 text-left text-xs text-slate-600">User</th>
              <th className="px-2 py-2 text-right text-xs text-slate-600">Requests</th>
              <th className="px-2 py-2 text-right text-xs text-slate-600">Token In</th>
              <th className="px-2 py-2 text-right text-xs text-slate-600">Token Out</th>
              <th className="px-2 py-2 text-right text-xs text-slate-600">Cost</th>
            </tr>
          </thead>
          <tbody>
            {topUsers.map((u) => (
              <tr key={u.user_id} className="border-b border-slate-100">
                <td className="px-2 py-2 text-xs text-slate-700 break-all">{u.user_id || 'anonymous'}</td>
                <td className="px-2 py-2 text-right text-xs">{nf(u.requests)}</td>
                <td className="px-2 py-2 text-right text-xs">{nf(u.token_in)}</td>
                <td className="px-2 py-2 text-right text-xs">{nf(u.token_out)}</td>
                <td className="px-2 py-2 text-right text-xs font-semibold text-amber-700">{usd(u.estimated_cost_usd)}</td>
              </tr>
            ))}
            {topUsers.length === 0 && (
              <tr>
                <td className="px-2 py-3 text-sm text-slate-500" colSpan={5}>No per-user usage found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="rounded-xl border border-sky-100 bg-white p-4 overflow-auto">
          <h3 className="text-sm font-bold text-slate-800 mb-3">Model Usage and Cost Estimation</h3>
          <table className="w-full text-sm">
            <thead className="bg-sky-50/60 sticky top-0">
              <tr>
                <th className="px-2 py-2 text-left text-xs text-slate-600">Model ID</th>
                <th className="px-2 py-2 text-right text-xs text-slate-600">Req</th>
                <th className="px-2 py-2 text-right text-xs text-slate-600">Token In</th>
                <th className="px-2 py-2 text-right text-xs text-slate-600">Token Out</th>
                <th className="px-2 py-2 text-right text-xs text-slate-600">Cost</th>
              </tr>
            </thead>
            <tbody>
              {(dashboard?.model_usage || []).map((m) => (
                <tr key={m.model_id} className="border-b border-slate-100">
                  <td className="px-2 py-2 text-xs text-slate-700 break-all">{m.model_id}</td>
                  <td className="px-2 py-2 text-right text-xs">{nf(m.requests)}</td>
                  <td className="px-2 py-2 text-right text-xs">{nf(m.token_in)}</td>
                  <td className="px-2 py-2 text-right text-xs">{nf(m.token_out)}</td>
                  <td className="px-2 py-2 text-right text-xs font-semibold text-amber-700">{usd(m.estimated_cost_usd)}</td>
                </tr>
              ))}
              {(dashboard?.model_usage || []).length === 0 && (
                <tr>
                  <td className="px-2 py-3 text-sm text-slate-500" colSpan={5}>No model usage found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="rounded-xl border border-sky-100 bg-white p-4 overflow-auto">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-bold text-slate-800">Recent API Invocations</h3>
              <p className="text-[11px] text-slate-500">Showing latest 8 records</p>
            </div>
            <button
              type="button"
              onClick={() => navigate(`/admin/invocations?days=${activeRange.days}`)}
              className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-1.5 text-xs font-semibold text-sky-700 hover:bg-sky-100"
            >
              Show all
            </button>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-sky-50/60 sticky top-0">
              <tr>
                <th className="px-2 py-2 text-left text-xs text-slate-600">Time</th>
                <th className="px-2 py-2 text-left text-xs text-slate-600">Feature</th>
                <th className="px-2 py-2 text-left text-xs text-slate-600">Model</th>
                <th className="px-2 py-2 text-right text-xs text-slate-600">In</th>
                <th className="px-2 py-2 text-right text-xs text-slate-600">Out</th>
              </tr>
            </thead>
            <tbody>
              {invocations.map((log) => (
                <tr key={log.usage_id} className="border-b border-slate-100">
                  <td className="px-2 py-2 text-xs text-slate-600">{new Date(log.invoked_at).toLocaleString()}</td>
                  <td className="px-2 py-2 text-xs text-slate-700">{log.feature}</td>
                  <td className="px-2 py-2 text-xs text-slate-700 break-all">{log.model_id || '-'}</td>
                  <td className="px-2 py-2 text-right text-xs">{nf(log.token_in || 0)}</td>
                  <td className="px-2 py-2 text-right text-xs">{nf(log.token_out || 0)}</td>
                </tr>
              ))}
              {invocations.length === 0 && (
                <tr>
                  <td className="px-2 py-3 text-sm text-slate-500" colSpan={5}>No invocation logs found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-xl border border-sky-100 bg-white p-4 overflow-auto">
        <h3 className="text-sm font-bold text-slate-800 mb-3">Pricing Catalog by Model ID</h3>
        <table className="w-full text-sm">
          <thead className="bg-sky-50/60">
            <tr>
              <th className="px-2 py-2 text-left text-xs text-slate-600">Model ID</th>
              <th className="px-2 py-2 text-left text-xs text-slate-600">Display Name</th>
              <th className="px-2 py-2 text-right text-xs text-slate-600">Input / 1M</th>
              <th className="px-2 py-2 text-right text-xs text-slate-600">Output / 1M</th>
            </tr>
          </thead>
          <tbody>
            {(dashboard?.pricing_catalog || []).map((p) => (
              <tr key={p.model_id} className="border-b border-slate-100">
                <td className="px-2 py-2 text-xs text-slate-700 break-all">{p.model_id}</td>
                <td className="px-2 py-2 text-xs text-slate-700">{p.display_name}</td>
                <td className="px-2 py-2 text-right text-xs">${p.input_price_per_million.toFixed(2)}</td>
                <td className="px-2 py-2 text-right text-xs">${p.output_price_per_million.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
