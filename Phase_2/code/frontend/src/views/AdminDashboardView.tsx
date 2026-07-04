import { useEffect, useMemo, useState, useRef } from 'react';
import {
  Activity,
  Coins,
  Database,
  DollarSign,
  Loader2,
  RefreshCw,
  Users,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  getAdminCostDashboard,
  getAdminDashboard,
  listAdminInvocations,
  type AdminCostDashboardResponse,
  type AdminDashboardResponse,
  type AdminInvocationRecord,
} from '../api/ragApi';
import { useNavigate } from 'react-router-dom';
import { userRepo } from '../repositories/user_repository';
import type { UserEntity } from '../database/types';
import { adminRowClass, adminUi } from '../lib/adminUi';

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

const COST_STACK_COLORS = ['#0ea5e9', '#14b8a6', '#8b5cf6', '#f97316', '#84cc16', '#06b6d4'];

function compactServiceLabel(service: string): string {
  const s = String(service || '').trim();
  if (!s) return 'Unknown';
  if (s.length <= 28) return s;
  return `${s.slice(0, 26)}...`;
}

export default function AdminDashboardView() {
  const navigate = useNavigate();
  const [selectedRange, setSelectedRange] = useState<DashboardRange>('1h');
  const [activeTab, setActiveTab] = useState<'usage' | 'costs'>('usage');
  const [serviceFilter, setServiceFilter] = useState<string>('ALL');
  const [dashboard, setDashboard] = useState<AdminDashboardResponse | null>(null);
  const [costDashboard, setCostDashboard] = useState<AdminCostDashboardResponse | null>(null);
  const [users, setUsers] = useState<UserEntity[]>([]);
  const [invocations, setInvocations] = useState<AdminInvocationRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const activeRange = DASHBOARD_RANGES[selectedRange];

  const mounted = useRef(true);
  useEffect(() => {
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = async (targetDays: number) => {
    setLoading(true);
    setError(null);
    try {
      const [dashRes, logsRes, costsRes] = await Promise.allSettled([
        getAdminDashboard(targetDays),
        listAdminInvocations({ days: targetDays, limit: 8 }),
        getAdminCostDashboard(targetDays),
      ]);
      
      if (!mounted.current) return;

      const failedSources: string[] = [];

      if (dashRes.status === 'fulfilled') {
        setDashboard(dashRes.value);
      } else {
        setDashboard(null);
        failedSources.push('usage dashboard');
      }

      if (logsRes.status === 'fulfilled') {
        setInvocations(logsRes.value.items || []);
      } else {
        setInvocations([]);
        failedSources.push('invocations');
      }

      if (costsRes.status === 'fulfilled') {
        setCostDashboard(costsRes.value);
      } else {
        setCostDashboard(null);
        failedSources.push('cost dashboard');
      }

      if (failedSources.length > 0) {
        setError(`Some admin data sources failed: ${failedSources.join(', ')}`);
      }
    } catch (e: any) {
      if (!mounted.current) return;
      setError(e?.response?.data?.detail || e?.message || 'Failed to load admin dashboard');
    } finally {
      if (mounted.current) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void load(activeRange.days);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRange.days]);

  useEffect(() => {
    void userRepo.listAdminUsers()
      .then((res) => setUsers(res.items || []))
      .catch(() => setUsers([]));
  }, []);

  const userMap = useMemo(() => {
    const m = new Map<string, UserEntity>();
    for (const u of users) m.set(u.uid, u);
    return m;
  }, [users]);

  const userLabel = (uid: string): string => {
    const u = userMap.get(uid);
    if (!u) return 'Unknown user';
    return u.displayName || u.username || u.email || 'Unknown user';
  };

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
    () => topUsers.map((x) => ({ ...x, user_short: compactUserId(userLabel(x.user_id || 'anonymous')) })),
    [topUsers, userMap],
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

  const cloudCostSummary = costDashboard?.summary || {
    total_cost_usd: 0,
    avg_daily_cost_usd: 0,
    services_count: 0,
    records_count: 0,
    latest_day: null,
    latest_day_total_cost_usd: 0,
    parse_errors: 0,
  };

  const hasCloudCostData = (costDashboard?.cost_by_day || []).length > 0;

  const serviceOptions = useMemo(
    () => ['ALL', ...(costDashboard?.service_options || [])],
    [costDashboard],
  );

  useEffect(() => {
    if (!serviceOptions.includes(serviceFilter)) {
      setServiceFilter('ALL');
    }
  }, [serviceFilter, serviceOptions]);

  const filteredDailyCloudCost = useMemo(() => {
    const dayRows = costDashboard?.cost_by_day || [];
    if (serviceFilter === 'ALL') {
      return dayRows.map((x) => ({ day: x.day, cost_usd: Number(x.total_cost_usd || 0) }));
    }
    const byDay = new Map<string, number>();
    for (const row of costDashboard?.cost_by_day_service || []) {
      if (row.service !== serviceFilter) continue;
      byDay.set(row.day, (byDay.get(row.day) || 0) + Number(row.cost_usd || 0));
    }
    return dayRows.map((x) => ({
      day: x.day,
      cost_usd: Number((byDay.get(x.day) || 0).toFixed(6)),
    }));
  }, [costDashboard, serviceFilter]);

  const filteredServiceTotals = useMemo(() => {
    const rows = costDashboard?.cost_by_service || [];
    if (serviceFilter === 'ALL') return rows;
    return rows.filter((x) => x.service === serviceFilter);
  }, [costDashboard, serviceFilter]);

  const latestDayBreakdown = useMemo(() => {
    const rows = costDashboard?.latest_day_breakdown || [];
    if (serviceFilter === 'ALL') return rows;
    return rows.filter((x) => x.service === serviceFilter);
  }, [costDashboard, serviceFilter]);

  const topServiceCostRows = useMemo(
    () => filteredServiceTotals.slice(0, 10).map((row) => ({
      ...row,
      service_short: compactServiceLabel(row.service),
    })),
    [filteredServiceTotals],
  );

  const dailyCloudCostStacked = useMemo(() => {
    const dayRows = costDashboard?.cost_by_day || [];
    const dayServiceRows = costDashboard?.cost_by_day_service || [];

    if (dayRows.length === 0) {
      return {
        data: [] as Array<Record<string, string | number>>,
        stackKeys: [] as string[],
      };
    }

    const serviceTotals = new Map<string, number>();
    const byDayService = new Map<string, number>();

    for (const row of dayServiceRows) {
      const day = String(row.day || '');
      const service = String(row.service || 'Unknown Service');
      const cost = Number(row.cost_usd || 0);
      if (!day || cost <= 0) continue;
      const k = `${day}|||${service}`;
      byDayService.set(k, (byDayService.get(k) || 0) + cost);
      serviceTotals.set(service, (serviceTotals.get(service) || 0) + cost);
    }

    const orderedServices = Array.from(serviceTotals.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([service]) => service);

    const focusServices =
      serviceFilter === 'ALL'
        ? orderedServices.slice(0, 5)
        : orderedServices.includes(serviceFilter)
          ? [serviceFilter]
          : [];

    const data = dayRows.map((row) => {
      const day = String(row.day || '');
      const total = Number(row.total_cost_usd || 0);
      let known = 0;

      const out: Record<string, string | number> = {
        day,
        total_cost_usd: Number(total.toFixed(6)),
      };

      for (const service of focusServices) {
        const value = Number((byDayService.get(`${day}|||${service}`) || 0).toFixed(6));
        out[service] = value;
        known += value;
      }

      const others = Math.max(0, Number((total - known).toFixed(6)));
      if (others > 0 || focusServices.length === 0) {
        out.Others = others;
      }

      return out;
    });

    const hasOthers = data.some((x) => Number(x.Others || 0) > 0);
    return {
      data,
      stackKeys: [
        ...focusServices,
        ...(hasOthers ? ['Others'] : []),
      ],
    };
  }, [costDashboard, serviceFilter]);

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-200/70 bg-gradient-to-r from-transparent via-slate-50/60 to-sky-50/55 p-5 shadow-none">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-sky-600">Admin Dashboard</p>
            <h2 className="text-2xl font-black text-slate-900 tracking-tight">Application Usage and Cost Control</h2>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={selectedRange}
              onChange={(e) => setSelectedRange(e.target.value as DashboardRange)}
              className={adminUi.select}
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
              className={`inline-flex items-center gap-2 ${adminUi.buttonSoft}`}
            >
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
        </div>
        {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
      </div>

      <div className="rounded-2xl border border-slate-200/70 bg-gradient-to-r from-transparent via-slate-50/55 to-sky-50/45 p-2">
        <div className="inline-flex rounded-xl bg-slate-100/90 p-1">
          <button
            type="button"
            onClick={() => setActiveTab('usage')}
            className={`rounded-lg px-4 py-2 text-xs font-black uppercase tracking-widest transition-colors ${activeTab === 'usage'
              ? 'bg-white text-sky-700 border border-sky-100'
              : 'text-slate-500 hover:text-slate-700'
              }`}
          >
            Usage and Performance
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('costs')}
            className={`rounded-lg px-4 py-2 text-xs font-black uppercase tracking-widest transition-colors ${activeTab === 'costs'
              ? 'bg-white text-sky-700 border border-sky-100'
              : 'text-slate-500 hover:text-slate-700'
              }`}
          >
            Costs and Billing
          </button>
        </div>
      </div>

      {activeTab === 'usage' ? (
        <>
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
              <p className="text-xs text-slate-500">Estimated LLM cost</p>
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
                <div className="h-[300px] flex items-center justify-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin" /></div>
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
                <div className="h-[300px] flex items-center justify-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin" /></div>
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
                <div className="h-[300px] flex items-center justify-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin" /></div>
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
                <div className="h-[300px] flex items-center justify-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin" /></div>
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
                <div className="h-[300px] flex items-center justify-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin" /></div>
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
                <div className="h-[300px] flex items-center justify-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin" /></div>
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

          <div className={`${adminUi.tableShell} p-4`}>
            <h3 className="text-sm font-bold text-slate-800 mb-3">Per-user API Request Detail</h3>
            <table className={adminUi.table}>
              <thead className={adminUi.thead}>
                <tr>
                  <th className={adminUi.th}>User</th>
                  <th className={adminUi.thRight}>Requests</th>
                  <th className={adminUi.thRight}>Token In</th>
                  <th className={adminUi.thRight}>Token Out</th>
                  <th className={adminUi.thRight}>Cost</th>
                </tr>
              </thead>
              <tbody>
                {topUsers.map((u, idx) => (
                  <tr key={u.user_id} className={adminRowClass(idx)}>
                    <td className={`${adminUi.td} break-all`} title={u.user_id || 'anonymous'}>{userLabel(u.user_id || 'anonymous')}</td>
                    <td className={adminUi.tdRight}>{nf(u.requests)}</td>
                    <td className={adminUi.tdRight}>{nf(u.token_in)}</td>
                    <td className={adminUi.tdRight}>{nf(u.token_out)}</td>
                    <td className={`${adminUi.tdRight} font-semibold text-amber-700`}>{usd(u.estimated_cost_usd)}</td>
                  </tr>
                ))}
                {topUsers.length === 0 && (
                  <tr>
                    <td className="px-3 py-6 text-sm text-slate-500 text-center" colSpan={5}>No per-user usage found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className={`${adminUi.tableShell} p-4`}>
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
            <table className={adminUi.table}>
              <thead className={adminUi.thead}>
                <tr>
                  <th className={adminUi.th}>Time</th>
                  <th className={adminUi.th}>Feature</th>
                  <th className={adminUi.th}>Model</th>
                  <th className={adminUi.thRight}>In</th>
                  <th className={adminUi.thRight}>Out</th>
                </tr>
              </thead>
              <tbody>
                {invocations.map((log, idx) => (
                  <tr key={log.usage_id} className={adminRowClass(idx)}>
                    <td className={`${adminUi.td} text-slate-600`}>{new Date(log.invoked_at).toLocaleString()}</td>
                    <td className={adminUi.td}>{log.feature}</td>
                    <td className={`${adminUi.td} break-all`}>{log.model_id || '-'}</td>
                    <td className={adminUi.tdRight}>{nf(log.token_in || 0)}</td>
                    <td className={adminUi.tdRight}>{nf(log.token_out || 0)}</td>
                  </tr>
                ))}
                {invocations.length === 0 && (
                  <tr>
                    <td className="px-3 py-6 text-sm text-slate-500 text-center" colSpan={5}>No invocation logs found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <>
          {costDashboard?.error && (
            <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              Failed to load cloud cost report: {costDashboard.error}
            </p>
          )}

          {!loading && !hasCloudCostData && !costDashboard?.error && (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              No cloud cost CSV data found. Configure AWS cost report source via `AWS_COST_REPORT_S3_BUCKET` and `AWS_COST_REPORT_S3_PREFIX`.
            </p>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4">
              <p className="text-xs text-slate-500">Cloud cost ({activeRange.title})</p>
              <p className="mt-2 text-3xl font-black text-emerald-700">{usd(cloudCostSummary.total_cost_usd)}</p>
              <DollarSign className="w-5 h-5 text-emerald-500 mt-2" />
            </div>
            <div className="rounded-xl border border-sky-200 bg-sky-50/40 p-4">
              <p className="text-xs text-slate-500">Latest day ({cloudCostSummary.latest_day || '-'})</p>
              <p className="mt-2 text-3xl font-black text-sky-700">{usd(cloudCostSummary.latest_day_total_cost_usd)}</p>
              <Coins className="w-5 h-5 text-sky-500 mt-2" />
            </div>
            <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-4">
              <p className="text-xs text-slate-500">Average daily cloud cost</p>
              <p className="mt-2 text-3xl font-black text-indigo-700">{usd(cloudCostSummary.avg_daily_cost_usd)}</p>
              <Activity className="w-5 h-5 text-indigo-500 mt-2" />
            </div>
            <div className="rounded-xl border border-violet-200 bg-violet-50/40 p-4">
              <p className="text-xs text-slate-500">Tracked services / rows</p>
              <p className="mt-2 text-3xl font-black text-violet-700">{nf(cloudCostSummary.services_count)}</p>
              <p className="mt-1 text-xs text-violet-700">{nf(cloudCostSummary.records_count)} records</p>
            </div>
          </div>

          <div className="rounded-xl border border-sky-100 bg-white p-4">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-xs font-semibold text-slate-500">Filter by service</p>
              <select
                value={serviceFilter}
                onChange={(e) => setServiceFilter(e.target.value)}
                className={`${adminUi.select} min-w-[280px]`}
                title="Service filter"
                aria-label="Service filter"
              >
                {serviceOptions.map((svc) => (
                  <option key={svc} value={svc}>{svc === 'ALL' ? 'All services' : svc}</option>
                ))}
              </select>
              <p className="text-xs text-slate-500">Source: {costDashboard?.bucket || '-'} / {costDashboard?.prefix || 'detailed/'}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="rounded-xl border border-sky-100 bg-white p-4 h-[360px]">
              <h3 className="text-sm font-bold text-slate-800 mb-3">
                Daily Cloud Cost by Service ({serviceFilter === 'ALL' ? 'top services + Others' : `${serviceFilter} + Others`})
              </h3>
              <p className="text-[11px] text-slate-500 mb-3">
                Stacked bars show per-day service split. Remaining cost is grouped as Others.
              </p>
              {loading ? (
                <div className="h-[300px] flex items-center justify-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin" /></div>
              ) : dailyCloudCostStacked.data.length === 0 || dailyCloudCostStacked.stackKeys.length === 0 ? (
                <div className="h-[300px] flex items-center justify-center text-sm text-slate-500">No data</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dailyCloudCostStacked.data}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="day" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip
                      formatter={(v: any, name: any) => [usd(Number(v || 0)), compactServiceLabel(String(name || ''))]}
                      labelFormatter={(label: any) => `Date: ${label}`}
                    />
                    <Legend
                      verticalAlign="top"
                      align="left"
                      formatter={(value: any) => compactServiceLabel(String(value || ''))}
                    />
                    {dailyCloudCostStacked.stackKeys.map((k, idx) => (
                      <Bar
                        key={k}
                        dataKey={k}
                        stackId="daily-cost"
                        fill={k === 'Others' ? '#94a3b8' : COST_STACK_COLORS[idx % COST_STACK_COLORS.length]}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="rounded-xl border border-sky-100 bg-white p-4 h-[360px]">
              <h3 className="text-sm font-bold text-slate-800 mb-1">Top Services by Cloud Cost</h3>
              <p className="text-[11px] text-slate-500 mb-3">Horizontal rank view for easier service-name reading.</p>
              {loading ? (
                <div className="h-[300px] flex items-center justify-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin" /></div>
              ) : topServiceCostRows.length === 0 ? (
                <div className="h-[300px] flex items-center justify-center text-sm text-slate-500">No data</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    layout="vertical"
                    data={topServiceCostRows}
                    margin={{ top: 8, right: 20, left: 8, bottom: 8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis
                      type="number"
                      tick={{ fill: '#64748b', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(v: any) => `$${Number(v || 0).toFixed(1)}`}
                    />
                    <YAxis
                      type="category"
                      dataKey="service_short"
                      width={180}
                      tick={{ fill: '#64748b', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      formatter={(v: any) => usd(Number(v || 0))}
                      labelFormatter={(_label: any, payload: any) => {
                        const p = payload?.[0]?.payload;
                        return String(p?.service || _label || 'Service');
                      }}
                    />
                    <Bar dataKey="cost_usd" fill="#0284c7" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className={`${adminUi.tableShell} p-4`}>
              <h3 className="text-sm font-bold text-slate-800 mb-3">Service Cost Totals ({activeRange.title})</h3>
              <table className={adminUi.table}>
                <thead className={adminUi.thead}>
                  <tr>
                    <th className={adminUi.th}>Service</th>
                    <th className={adminUi.thRight}>Cost (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredServiceTotals.map((row, idx) => (
                    <tr key={row.service} className={adminRowClass(idx)}>
                      <td className={`${adminUi.td} break-all`}>{row.service}</td>
                      <td className={`${adminUi.tdRight} font-semibold text-emerald-700`}>{usd(row.cost_usd)}</td>
                    </tr>
                  ))}
                  {filteredServiceTotals.length === 0 && (
                    <tr>
                      <td className="px-3 py-6 text-sm text-slate-500 text-center" colSpan={2}>No service cost rows found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className={`${adminUi.tableShell} p-4`}>
              <h3 className="text-sm font-bold text-slate-800 mb-3">Latest Day Detailed Breakdown</h3>
              <table className={adminUi.table}>
                <thead className={adminUi.thead}>
                  <tr>
                    <th className={adminUi.th}>Service</th>
                    <th className={adminUi.th}>Usage Type</th>
                    <th className={adminUi.thRight}>Cost (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  {latestDayBreakdown.map((row, idx) => (
                    <tr key={`${row.service}-${row.usage_type}-${idx}`} className={adminRowClass(idx)}>
                      <td className={`${adminUi.td} break-all`}>{row.service}</td>
                      <td className={`${adminUi.td} break-all`}>{row.usage_type}</td>
                      <td className={`${adminUi.tdRight} font-semibold text-emerald-700`}>{usd(row.cost_usd)}</td>
                    </tr>
                  ))}
                  {latestDayBreakdown.length === 0 && (
                    <tr>
                      <td className="px-3 py-6 text-sm text-slate-500 text-center" colSpan={3}>No detailed rows for latest day.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className={`${adminUi.tableShell} p-4`}>
              <h3 className="text-sm font-bold text-slate-800 mb-3">Model Usage and Cost Estimation</h3>
              <table className={adminUi.table}>
                <thead className={adminUi.thead}>
                  <tr>
                    <th className={adminUi.th}>Model ID</th>
                    <th className={adminUi.thRight}>Req</th>
                    <th className={adminUi.thRight}>Token In</th>
                    <th className={adminUi.thRight}>Token Out</th>
                    <th className={adminUi.thRight}>Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {(dashboard?.model_usage || []).map((m, idx) => (
                    <tr key={m.model_id} className={adminRowClass(idx)}>
                      <td className={`${adminUi.td} break-all`}>{m.model_id}</td>
                      <td className={adminUi.tdRight}>{nf(m.requests)}</td>
                      <td className={adminUi.tdRight}>{nf(m.token_in)}</td>
                      <td className={adminUi.tdRight}>{nf(m.token_out)}</td>
                      <td className={`${adminUi.tdRight} font-semibold text-amber-700`}>{usd(m.estimated_cost_usd)}</td>
                    </tr>
                  ))}
                  {(dashboard?.model_usage || []).length === 0 && (
                    <tr>
                      <td className="px-3 py-6 text-sm text-slate-500 text-center" colSpan={5}>No model usage found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className={`${adminUi.tableShell} p-4`}>
              <h3 className="text-sm font-bold text-slate-800 mb-3">Pricing Catalog by Model ID</h3>
              <table className={adminUi.table}>
                <thead className={adminUi.thead}>
                  <tr>
                    <th className={adminUi.th}>Model ID</th>
                    <th className={adminUi.th}>Display Name</th>
                    <th className={adminUi.thRight}>Input / 1M</th>
                    <th className={adminUi.thRight}>Output / 1M</th>
                  </tr>
                </thead>
                <tbody>
                  {(dashboard?.pricing_catalog || []).map((p, idx) => (
                    <tr key={p.model_id} className={adminRowClass(idx)}>
                      <td className={`${adminUi.td} break-all`}>{p.model_id}</td>
                      <td className={adminUi.td}>{p.display_name}</td>
                      <td className={adminUi.tdRight}>${p.input_price_per_million.toFixed(2)}</td>
                      <td className={adminUi.tdRight}>${p.output_price_per_million.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
