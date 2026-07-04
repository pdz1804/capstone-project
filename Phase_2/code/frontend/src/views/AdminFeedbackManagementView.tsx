import { useEffect, useMemo, useState, useRef } from 'react';
import {
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-react';
import {
  activateAdminFeedback,
  createAdminFeedback,
  deactivateAdminFeedback,
  deleteAdminFeedback,
  getAdminFeedback,
  listAdminFeedback,
  updateAdminFeedback,
  type FeedbackItem,
} from '../api/ragApi';
import { userRepo } from '../repositories/user_repository';
import type { UserEntity } from '../database/types';
import { adminRowClass, adminUi, categoryBadgeClass, statusBadgeClass, voteBadgeClass } from '../lib/adminUi';
import { AdminSortHeader, AdminTablePagination, type SortDirection } from '../components/admin/AdminTableControls';

function nf(n: number): string {
  return new Intl.NumberFormat('en-US').format(n || 0);
}

export default function AdminFeedbackManagementView() {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [users, setUsers] = useState<UserEntity[]>([]);
  const [loading, setLoading] = useState(false);
  const [usersLoading, setUsersLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState('');
  const [userId, setUserId] = useState('');
  const [category, setCategory] = useState('');
  const [vote, setVote] = useState('');
  const [activeFilter, setActiveFilter] = useState<string>('all');

  const [selected, setSelected] = useState<(FeedbackItem & { usage_summary?: Record<string, any> }) | null>(null);
  const [saving, setSaving] = useState(false);

  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    user_id: '',
    vote: 'general' as 'like' | 'dislike' | 'general',
    query: '',
    response: '',
    scope: '',
    feedback_text: '',
  });

  const [sortKey, setSortKey] = useState<'time' | 'user' | 'vote' | 'category' | 'status'>('time');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const mounted = useRef(true);
  useEffect(() => {
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAdminFeedback({
        query: query || undefined,
        user_id: userId || undefined,
        category: category || undefined,
        vote: vote || undefined,
        is_active: activeFilter === 'all' ? undefined : activeFilter === 'active',
        include_usage: true,
      });
      if (!mounted.current) return;
      setItems(data.items || []);
    } catch (e: any) {
      if (!mounted.current) return;
      setError(e?.response?.data?.detail || e?.message || 'Failed to load feedback records');
    } finally {
      if (mounted.current) setLoading(false);
    }
  };

  const loadUsers = async () => {
    setUsersLoading(true);
    try {
      const data = await userRepo.listAdminUsers();
      if (!mounted.current) return;
      setUsers(data.items || []);
    } catch {
      if (!mounted.current) return;
      setUsers([]);
    } finally {
      if (mounted.current) setUsersLoading(false);
    }
  };

  useEffect(() => {
    void Promise.all([load(), loadUsers()]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => items, [items]);

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

  const categoryOptions = useMemo(() => {
    const values = new Set<string>();
    for (const item of items) {
      const v = String(item.category || '').trim();
      if (v) values.add(v);
    }
    if (values.size === 0) {
      values.add('Content Quality');
      values.add('Answer Quality');
      values.add('Hallucination');
      values.add('Relevance');
      values.add('Formatting');
    }
    return Array.from(values).sort((a, b) => a.localeCompare(b));
  }, [items]);

  const userLabel = (uid: string): string => {
    const u = userMap.get(uid);
    if (!u) return 'Unknown user';
    return u.displayName || u.username || u.email || 'Unknown user';
  };

  const sorted = useMemo(() => {
    const rows = [...filtered];
    rows.sort((a, b) => {
      let compare = 0;
      if (sortKey === 'time') {
        compare = new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
      }
      if (sortKey === 'user') {
        compare = userLabel(a.user_id).toLowerCase().localeCompare(userLabel(b.user_id).toLowerCase());
      }
      if (sortKey === 'vote') {
        compare = String(a.vote || '').toLowerCase().localeCompare(String(b.vote || '').toLowerCase());
      }
      if (sortKey === 'category') {
        compare = String(a.category || '').toLowerCase().localeCompare(String(b.category || '').toLowerCase());
      }
      if (sortKey === 'status') {
        compare = Number(a.is_active ?? true) - Number(b.is_active ?? true);
      }
      return sortDirection === 'asc' ? compare : -compare;
    });
    return rows;
  }, [filtered, sortDirection, sortKey]);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(sorted.length / Math.max(1, pageSize))), [pageSize, sorted.length]);

  useEffect(() => {
    setPage((current) => Math.min(Math.max(1, current), totalPages));
  }, [totalPages]);

  const paged = useMemo(() => {
    const start = (page - 1) * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [page, pageSize, sorted]);

  const setSort = (
    next: 'time' | 'user' | 'vote' | 'category' | 'status',
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

  const pick = async (item: FeedbackItem) => {
    try {
      const detail = await getAdminFeedback(item.user_id, item.feedback_id);
      setSelected(detail);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load feedback detail');
    }
  };

  const createItem = async () => {
    setSaving(true);
    setError(null);
    try {
      await createAdminFeedback({
        user_id: createForm.user_id,
        vote: createForm.vote,
        query: createForm.query || undefined,
        response: createForm.response || undefined,
        scope: createForm.scope || undefined,
        feedback_text: createForm.feedback_text || undefined,
      });
      setShowCreate(false);
      setCreateForm({ user_id: '', vote: 'general', query: '', response: '', scope: '', feedback_text: '' });
      await load();
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to create feedback');
    } finally {
      setSaving(false);
    }
  };

  const saveItem = async () => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateAdminFeedback(selected.user_id, selected.feedback_id, {
        category: selected.category,
        sub_category: selected.sub_category,
        suggested_action: selected.suggested_action,
        analysis_summary: selected.analysis_summary,
        reason_code: selected.reason_code || undefined,
        reason_text: selected.reason_text || undefined,
        scope: selected.scope || undefined,
        feedback_text: selected.feedback_text || undefined,
        is_active: selected.is_active,
      });
      setSelected(updated as any);
      await load();
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to update feedback');
    } finally {
      setSaving(false);
    }
  };

  const deactivate = async (item: FeedbackItem) => {
    try {
      await deactivateAdminFeedback(item.user_id, item.feedback_id);
      await load();
      if (selected?.feedback_id === item.feedback_id) {
        await pick(item);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to deactivate feedback');
    }
  };

  const activate = async (item: FeedbackItem) => {
    try {
      await activateAdminFeedback(item.user_id, item.feedback_id);
      await load();
      if (selected?.feedback_id === item.feedback_id) {
        await pick(item);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to activate feedback');
    }
  };

  const remove = async (item: FeedbackItem) => {
    if (!window.confirm('Delete this feedback record?')) return;
    try {
      await deleteAdminFeedback(item.user_id, item.feedback_id);
      await load();
      if (selected?.feedback_id === item.feedback_id) setSelected(null);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to delete feedback');
    }
  };

  return (
    <div className="space-y-4">
      <div className={adminUi.panel}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-sky-600">Admin</p>
            <h2 className="text-xl font-black text-slate-900 tracking-tight">Feedback Management</h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowCreate((v) => !v)}
              className={`inline-flex items-center gap-2 ${adminUi.buttonPrimary}`}
            >
              <Plus className="w-4 h-4" /> New feedback
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

        {showCreate && (
          <div className="mt-4 grid grid-cols-1 lg:grid-cols-6 gap-2 rounded-xl border border-sky-100 bg-sky-50/40 p-3">
            <select
              value={createForm.user_id}
              onChange={(e) => setCreateForm((s) => ({ ...s, user_id: e.target.value }))}
              className={adminUi.select}
              title="User"
              aria-label="User"
              disabled={usersLoading}
            >
              <option value="">Select user</option>
              {userOptions.map((u) => (
                <option key={u.uid} value={u.uid}>{u.displayName || u.username || u.email || 'Unknown user'}</option>
              ))}
            </select>
            <select
              value={createForm.vote}
              onChange={(e) => setCreateForm((s) => ({ ...s, vote: e.target.value as any }))}
              className={adminUi.select}
              title="Vote"
              aria-label="Vote"
            >
              <option value="general">general</option>
              <option value="like">like</option>
              <option value="dislike">dislike</option>
            </select>
            <input
              value={createForm.query}
              onChange={(e) => setCreateForm((s) => ({ ...s, query: e.target.value }))}
              placeholder="query"
              className={adminUi.input}
            />
            <input
              value={createForm.scope}
              onChange={(e) => setCreateForm((s) => ({ ...s, scope: e.target.value }))}
              placeholder="scope"
              className={adminUi.input}
            />
            <button
              type="button"
              onClick={() => void createItem()}
              disabled={saving || !createForm.user_id}
              className={adminUi.buttonPrimary}
            >
              Create
            </button>
            <textarea
              value={createForm.feedback_text}
              onChange={(e) => setCreateForm((s) => ({ ...s, feedback_text: e.target.value }))}
              placeholder="feedback text"
              className={`lg:col-span-6 ${adminUi.input}`}
            />
            <textarea
              value={createForm.response}
              onChange={(e) => setCreateForm((s) => ({ ...s, response: e.target.value }))}
              placeholder="response"
              className={`lg:col-span-6 ${adminUi.input}`}
            />
          </div>
        )}

        <div className="mt-4 grid grid-cols-1 md:grid-cols-6 gap-2">
          <div className="relative md:col-span-2">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="search query/response/user"
              className={`w-full pl-9 pr-3 ${adminUi.input}`}
            />
          </div>
          <select
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className={adminUi.select}
            title="User filter"
            aria-label="User filter"
            disabled={usersLoading}
          >
            <option value="">All users</option>
            {userOptions.map((u) => (
              <option key={u.uid} value={u.uid}>{u.displayName || u.username || u.email || 'Unknown user'}</option>
            ))}
          </select>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className={adminUi.select}
            title="Category filter"
            aria-label="Category filter"
          >
            <option value="">All categories</option>
            {categoryOptions.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select value={vote} onChange={(e) => setVote(e.target.value)} className={adminUi.select} title="Vote filter" aria-label="Vote filter">
            <option value="">All votes</option>
            <option value="like">like</option>
            <option value="dislike">dislike</option>
            <option value="general">general</option>
          </select>
          <select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)} className={adminUi.select} title="Activation filter" aria-label="Activation filter">
            <option value="all">All status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>

        <div className="mt-2">
          <button
            type="button"
            onClick={() => void load()}
            className={adminUi.buttonSubtle}
          >
            Apply filters
          </button>
        </div>

        {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-4 min-h-[420px]">
        <div className={adminUi.tableShell}>
          {loading ? (
            <div className="p-6 text-slate-500 flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading feedback records...
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
                        label="User"
                        active={sortKey === 'user'}
                        direction={sortDirection}
                        onClick={() => setSort('user', 'asc')}
                      />
                    </th>
                    <th className={adminUi.th}>
                      <AdminSortHeader
                        label="Vote"
                        active={sortKey === 'vote'}
                        direction={sortDirection}
                        onClick={() => setSort('vote', 'asc')}
                      />
                    </th>
                    <th className={adminUi.th}>
                      <AdminSortHeader
                        label="Category"
                        active={sortKey === 'category'}
                        direction={sortDirection}
                        onClick={() => setSort('category', 'asc')}
                      />
                    </th>
                    <th className={adminUi.th}>
                      <AdminSortHeader
                        label="Status"
                        active={sortKey === 'status'}
                        direction={sortDirection}
                        onClick={() => setSort('status', 'desc')}
                      />
                    </th>
                    <th className={adminUi.thRight}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {paged.map((f, idx) => (
                    <tr key={`${f.user_id}:${f.feedback_id}`} className={adminRowClass((page - 1) * pageSize + idx)}>
                      <td className={`${adminUi.td} text-slate-600`}>{new Date(f.created_at).toLocaleString()}</td>
                      <td className={adminUi.td}><span className="font-semibold text-slate-800">{userLabel(f.user_id)}</span></td>
                      <td className={adminUi.td}><span className={voteBadgeClass(f.vote)}>{f.vote || 'general'}</span></td>
                      <td className={adminUi.td}><span className={categoryBadgeClass(f.category)}>{f.category || 'Uncategorized'}</span></td>
                      <td className={adminUi.td}><span className={statusBadgeClass((f.is_active ?? true) ? 'active' : 'inactive')}>{(f.is_active ?? true) ? 'active' : 'inactive'}</span></td>
                      <td className={adminUi.tdRight}>
                        <div className="inline-flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => void pick(f)}
                            className="rounded-lg border border-sky-200 bg-sky-50 px-2 py-1 text-[11px] font-semibold text-sky-700 hover:bg-sky-100"
                          >
                            Detail
                          </button>
                          {(f.is_active ?? true) ? (
                            <button type="button" onClick={() => void deactivate(f)} className="rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-[11px] text-rose-700 hover:bg-rose-100">Deactivate</button>
                          ) : (
                            <button type="button" onClick={() => void activate(f)} className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700 hover:bg-emerald-100">Activate</button>
                          )}
                          <button
                            type="button"
                            onClick={() => void remove(f)}
                            className="rounded-md border border-slate-200 bg-slate-50 p-1.5 text-slate-700 hover:bg-slate-100"
                            title="Delete"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {sorted.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-2 py-4 text-sm text-slate-500">No feedback records found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
              <div className="border-t border-slate-100 px-3 py-2">
                <AdminTablePagination
                  page={page}
                  pageSize={pageSize}
                  totalItems={sorted.length}
                  onPageChange={(next) => setPage(Math.min(Math.max(1, next), totalPages))}
                  onPageSizeChange={(nextSize) => {
                    setPageSize(nextSize);
                    setPage(1);
                  }}
                  itemLabel="feedback records"
                />
              </div>
            </>
          )}
        </div>

        <div className="rounded-xl border border-sky-100 bg-white p-4 overflow-auto">
          {!selected ? (
            <p className="text-sm text-slate-500">Select a feedback record to view and edit detail.</p>
          ) : (
            <div className="space-y-3">
              <div>
                <p className="text-xs text-slate-500">Feedback ID</p>
                <p className="text-sm font-bold text-slate-900 break-all">{selected.feedback_id}</p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <input
                  value={selected.category || ''}
                  onChange={(e) => setSelected((s) => (s ? { ...s, category: e.target.value } : s))}
                  className={adminUi.input}
                  placeholder="category"
                />
                <input
                  value={selected.sub_category || ''}
                  onChange={(e) => setSelected((s) => (s ? { ...s, sub_category: e.target.value } : s))}
                  className={adminUi.input}
                  placeholder="sub category"
                />
              </div>
              <input
                value={selected.scope || ''}
                onChange={(e) => setSelected((s) => (s ? { ...s, scope: e.target.value } : s))}
                className={`w-full ${adminUi.input}`}
                placeholder="scope"
              />
              <textarea
                value={selected.suggested_action || ''}
                onChange={(e) => setSelected((s) => (s ? { ...s, suggested_action: e.target.value } : s))}
                className={`w-full ${adminUi.input}`}
                placeholder="suggested action"
              />
              <textarea
                value={selected.analysis_summary || ''}
                onChange={(e) => setSelected((s) => (s ? { ...s, analysis_summary: e.target.value } : s))}
                className={`w-full ${adminUi.input}`}
                placeholder="analysis summary"
              />
              <textarea
                value={selected.feedback_text || ''}
                onChange={(e) => setSelected((s) => (s ? { ...s, feedback_text: e.target.value } : s))}
                className={`w-full ${adminUi.input}`}
                placeholder="feedback text"
              />
              <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={selected.is_active ?? true}
                  onChange={(e) => setSelected((s) => (s ? { ...s, is_active: e.target.checked } : s))}
                />
                Active
              </label>
              <button
                type="button"
                onClick={() => void saveItem()}
                disabled={saving}
                className={`w-full ${adminUi.buttonPrimary}`}
              >
                Save changes
              </button>

              <div className="rounded-xl border border-sky-100 bg-sky-50/40 p-3">
                <p className="text-xs font-bold uppercase tracking-widest text-slate-500">User Usage Snapshot</p>
                <p className="mt-1 text-xs text-slate-700">Requests: {nf(Number(selected.usage_summary?.total_requests || 0))}</p>
                <p className="text-xs text-slate-700">Token In: {nf(Number(selected.usage_summary?.token_in || 0))}</p>
                <p className="text-xs text-slate-700">Token Out: {nf(Number(selected.usage_summary?.token_out || 0))}</p>
                <p className="text-xs text-amber-700 font-semibold">Estimated Cost: ${Number(selected.usage_summary?.estimated_cost_usd || 0).toFixed(4)}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
