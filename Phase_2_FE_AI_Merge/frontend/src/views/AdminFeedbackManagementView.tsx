import { useEffect, useMemo, useState } from 'react';
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

function nf(n: number): string {
  return new Intl.NumberFormat('en-US').format(n || 0);
}

export default function AdminFeedbackManagementView() {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [loading, setLoading] = useState(false);
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
        limit: 1000,
      });
      setItems(data.items || []);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load feedback records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => items, [items]);

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
      <div className="rounded-2xl border border-sky-100 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-sky-600">Admin</p>
            <h2 className="text-xl font-black text-slate-900 tracking-tight">Feedback Management</h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowCreate((v) => !v)}
              className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-3 py-2 text-sm font-semibold text-white hover:bg-sky-700"
            >
              <Plus className="w-4 h-4" /> New feedback
            </button>
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
        </div>

        {showCreate && (
          <div className="mt-4 grid grid-cols-1 lg:grid-cols-6 gap-2 rounded-xl border border-sky-100 bg-sky-50/40 p-3">
            <input
              value={createForm.user_id}
              onChange={(e) => setCreateForm((s) => ({ ...s, user_id: e.target.value }))}
              placeholder="user_id"
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
            <select
              value={createForm.vote}
              onChange={(e) => setCreateForm((s) => ({ ...s, vote: e.target.value as any }))}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
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
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
            <input
              value={createForm.scope}
              onChange={(e) => setCreateForm((s) => ({ ...s, scope: e.target.value }))}
              placeholder="scope"
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={() => void createItem()}
              disabled={saving || !createForm.user_id}
              className="rounded-lg bg-blue-700 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-60"
            >
              Create
            </button>
            <textarea
              value={createForm.feedback_text}
              onChange={(e) => setCreateForm((s) => ({ ...s, feedback_text: e.target.value }))}
              placeholder="feedback text"
              className="lg:col-span-6 rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
            <textarea
              value={createForm.response}
              onChange={(e) => setCreateForm((s) => ({ ...s, response: e.target.value }))}
              placeholder="response"
              className="lg:col-span-6 rounded-lg border border-slate-200 px-3 py-2 text-sm"
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
              className="w-full rounded-lg border border-slate-200 pl-9 pr-3 py-2 text-sm"
            />
          </div>
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="user_id"
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="category"
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
          <select value={vote} onChange={(e) => setVote(e.target.value)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm" title="Vote filter" aria-label="Vote filter">
            <option value="">All votes</option>
            <option value="like">like</option>
            <option value="dislike">dislike</option>
            <option value="general">general</option>
          </select>
          <select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm" title="Activation filter" aria-label="Activation filter">
            <option value="all">All status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>

        <div className="mt-2">
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Apply filters
          </button>
        </div>

        {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-4 min-h-[420px]">
        <div className="rounded-xl border border-sky-100 bg-white overflow-auto">
          {loading ? (
            <div className="p-6 text-slate-500 flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading feedback records...
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-sky-50/60">
                <tr>
                  <th className="px-2 py-2 text-left text-xs text-slate-600">Time</th>
                  <th className="px-2 py-2 text-left text-xs text-slate-600">User</th>
                  <th className="px-2 py-2 text-left text-xs text-slate-600">Vote</th>
                  <th className="px-2 py-2 text-left text-xs text-slate-600">Category</th>
                  <th className="px-2 py-2 text-right text-xs text-slate-600">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((f) => (
                  <tr key={`${f.user_id}:${f.feedback_id}`} className="border-b border-slate-100 hover:bg-slate-50/60">
                    <td className="px-2 py-2 text-xs text-slate-600">{new Date(f.created_at).toLocaleString()}</td>
                    <td className="px-2 py-2 text-xs text-slate-700">{f.user_id}</td>
                    <td className="px-2 py-2 text-xs text-slate-700">{f.vote}</td>
                    <td className="px-2 py-2 text-xs text-slate-700">{f.category}</td>
                    <td className="px-2 py-2 text-right">
                      <div className="inline-flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => void pick(f)}
                          className="rounded-md border border-sky-200 bg-sky-50 px-2 py-1 text-[11px] text-sky-700 hover:bg-sky-100"
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
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-2 py-4 text-sm text-slate-500">No feedback records found.</td>
                  </tr>
                )}
              </tbody>
            </table>
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
                  className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  placeholder="category"
                />
                <input
                  value={selected.sub_category || ''}
                  onChange={(e) => setSelected((s) => (s ? { ...s, sub_category: e.target.value } : s))}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  placeholder="sub category"
                />
              </div>
              <input
                value={selected.scope || ''}
                onChange={(e) => setSelected((s) => (s ? { ...s, scope: e.target.value } : s))}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                placeholder="scope"
              />
              <textarea
                value={selected.suggested_action || ''}
                onChange={(e) => setSelected((s) => (s ? { ...s, suggested_action: e.target.value } : s))}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                placeholder="suggested action"
              />
              <textarea
                value={selected.analysis_summary || ''}
                onChange={(e) => setSelected((s) => (s ? { ...s, analysis_summary: e.target.value } : s))}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                placeholder="analysis summary"
              />
              <textarea
                value={selected.feedback_text || ''}
                onChange={(e) => setSelected((s) => (s ? { ...s, feedback_text: e.target.value } : s))}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
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
                className="w-full rounded-lg bg-blue-700 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-60"
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
