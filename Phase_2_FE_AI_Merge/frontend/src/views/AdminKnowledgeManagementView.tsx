import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Database,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-react';
import {
  activateAdminKnowledge,
  deactivateAdminKnowledge,
  deleteAdminKnowledge,
  getAdminKnowledge,
  listAdminKnowledge,
  syncAdminKnowledge,
  updateAdminKnowledge,
  type AdminKnowledgeItem,
} from '../api/ragApi';
import type { UserEntity } from '../database/types';
import { userRepo } from '../repositories/user_repository';
import { adminRowClass, adminUi, statusBadgeClass, typeBadgeClass } from '../lib/adminUi';
import { AdminSortHeader, AdminTablePagination, type SortDirection } from '../components/admin/AdminTableControls';

function nf(n: number): string {
  return new Intl.NumberFormat('en-US').format(n || 0);
}

function fmtDate(iso?: string): string {
  if (!iso) return '-';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function metadataPathForSource(sourcePath?: string): string {
  if (!sourcePath) return '-';
  return `${sourcePath}.metadata.json`;
}

type KnowledgeDetail = AdminKnowledgeItem & { usage_summary?: Record<string, unknown> };

type KnowledgeSortKey = 'title' | 'uploaded' | 'user' | 'type' | 'status';

export default function AdminKnowledgeManagementView() {
  const [items, setItems] = useState<AdminKnowledgeItem[]>([]);
  const [users, setUsers] = useState<UserEntity[]>([]);
  const [loading, setLoading] = useState(false);
  const [usersLoading, setUsersLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState('');
  const [userId, setUserId] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState<string>('all');

  const [selected, setSelected] = useState<KnowledgeDetail | null>(null);
  const [editableTags, setEditableTags] = useState('');
  const [editableNotes, setEditableNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const initializedRef = useRef(false);

  const [sortKey, setSortKey] = useState<KnowledgeSortKey>('uploaded');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const loadUsers = async () => {
    setUsersLoading(true);
    try {
      const data = await userRepo.listAdminUsers();
      setUsers(data.items || []);
    } catch {
      setUsers([]);
    } finally {
      setUsersLoading(false);
    }
  };

  const load = async (sync = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAdminKnowledge({
        query: query || undefined,
        user_id: userId || undefined,
        knowledge_type: typeFilter || undefined,
        is_active: activeFilter === 'all' ? undefined : activeFilter === 'active',
        sync_with_storage: sync,
        include_usage: false,
      });
      setItems(data.items || []);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load knowledge data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;
    void Promise.all([loadUsers(), load(false)]);
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
      const an = (a.displayName || a.username || a.email || a.uid || '').toLowerCase();
      const bn = (b.displayName || b.username || b.email || b.uid || '').toLowerCase();
      return an.localeCompare(bn);
    });
    return arr;
  }, [users]);

  const userLabel = (uid: string): string => {
    const u = userMap.get(uid);
    if (!u) return 'Unknown user';
    return u.displayName || u.username || u.email || 'Unknown user';
  };

  const sorted = useMemo(() => {
    const rows = [...filtered];
    rows.sort((a, b) => {
      let compare = 0;
      if (sortKey === 'title') {
        compare = String(a.title || '').toLowerCase().localeCompare(String(b.title || '').toLowerCase());
      }
      if (sortKey === 'uploaded') {
        compare = new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
      }
      if (sortKey === 'user') {
        compare = userLabel(a.user_id).toLowerCase().localeCompare(userLabel(b.user_id).toLowerCase());
      }
      if (sortKey === 'type') {
        compare = String(a.knowledge_type || '').toLowerCase().localeCompare(String(b.knowledge_type || '').toLowerCase());
      }
      if (sortKey === 'status') {
        const aStatus = `${a.is_active ? 'active' : 'inactive'}-${a.status || ''}`;
        const bStatus = `${b.is_active ? 'active' : 'inactive'}-${b.status || ''}`;
        compare = aStatus.localeCompare(bStatus);
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

  const setSort = (next: KnowledgeSortKey, defaultDirection: SortDirection = 'asc') => {
    setPage(1);
    if (sortKey === next) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(next);
    setSortDirection(defaultDirection);
  };

  const pick = async (knowledgeId: string) => {
    try {
      const detail = await getAdminKnowledge(knowledgeId);
      setSelected(detail as KnowledgeDetail);
      setEditableTags(((detail.tags || []) as string[]).join(', '));
      setEditableNotes(detail.notes || '');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load knowledge detail');
    }
  };

  const saveItem = async () => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateAdminKnowledge(selected.knowledge_id, {
        tags: editableTags
          .split(',')
          .map((x) => x.trim())
          .filter(Boolean),
        notes: editableNotes,
      });
      const next = updated as KnowledgeDetail;
      setSelected(next);
      setEditableTags(((next.tags || []) as string[]).join(', '));
      setEditableNotes(next.notes || '');
      await load(false);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to update knowledge metadata');
    } finally {
      setSaving(false);
    }
  };

  const deactivate = async (knowledgeId: string) => {
    try {
      await deactivateAdminKnowledge(knowledgeId);
      await load(false);
      if (selected?.knowledge_id === knowledgeId) {
        await pick(knowledgeId);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to deactivate knowledge item');
    }
  };

  const activate = async (knowledgeId: string) => {
    try {
      await activateAdminKnowledge(knowledgeId);
      await load(false);
      if (selected?.knowledge_id === knowledgeId) {
        await pick(knowledgeId);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to activate knowledge item');
    }
  };

  const remove = async (knowledgeId: string) => {
    if (!window.confirm('Remove this uploaded file completely? This deletes source file, sidecar metadata, and attempts index cleanup.')) return;
    try {
      const result = await deleteAdminKnowledge(knowledgeId);
      await load(false);
      if (selected?.knowledge_id === knowledgeId) setSelected(null);
      const removedText = Number(result.removed_text_vectors || 0);
      const removedImage = Number(result.removed_image_vectors || 0);
      window.alert(`Removed file successfully. Qdrant cleanup: text=${removedText}, image=${removedImage}`);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to remove knowledge item');
    }
  };

  return (
    <div className="space-y-4">
      <div className={adminUi.panel}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-sky-600">Admin</p>
            <h2 className="text-xl font-black text-slate-900 tracking-tight">Knowledge Management</h2>
            <p className="mt-1 text-xs text-slate-500">Tip: use Detail in each row to open full information and edit tags/notes.</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void syncAdminKnowledge().then(() => load(false))}
              className="inline-flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-100"
            >
              <Database className="w-4 h-4" /> Sync from storage
            </button>
            <button
              type="button"
              onClick={() => void load(false)}
              className={`inline-flex items-center gap-2 ${adminUi.buttonSoft}`}
            >
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-5 gap-2">
          <div className="relative md:col-span-2">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="search title/path/user/id"
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
              <option key={u.uid} value={u.uid}>
                {u.displayName || u.username || u.email || 'Unknown user'}
              </option>
            ))}
          </select>
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className={adminUi.select} title="Type filter" aria-label="Type filter">
            <option value="">All types</option>
            <option value="document">document</option>
            <option value="video">video</option>
            <option value="audio">audio</option>
            <option value="image">image</option>
            <option value="spreadsheet">spreadsheet</option>
            <option value="other">other</option>
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
            onClick={() => void load(false)}
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
              <Loader2 className="w-4 h-4 animate-spin" /> Loading knowledge records...
            </div>
          ) : (
            <>
              <table className={adminUi.table}>
                <thead className={adminUi.thead}>
                  <tr>
                    <th className={adminUi.th}>
                      <AdminSortHeader
                        label="Knowledge"
                        active={sortKey === 'title'}
                        direction={sortDirection}
                        onClick={() => setSort('title', 'asc')}
                      />
                    </th>
                    <th className={adminUi.th}>
                      <AdminSortHeader
                        label="Uploaded"
                        active={sortKey === 'uploaded'}
                        direction={sortDirection}
                        onClick={() => setSort('uploaded', 'desc')}
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
                        label="Type"
                        active={sortKey === 'type'}
                        direction={sortDirection}
                        onClick={() => setSort('type', 'asc')}
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
                  {paged.map((k, idx) => (
                    <tr key={k.knowledge_id} className={adminRowClass((page - 1) * pageSize + idx)}>
                      <td className={adminUi.td}>
                        <p className="text-xs font-semibold text-slate-800">{k.title}</p>
                      </td>
                      <td className={adminUi.td}>{fmtDate(k.created_at)}</td>
                      <td className={adminUi.td}>
                        <p className="font-semibold text-slate-800">{userLabel(k.user_id)}</p>
                      </td>
                      <td className={adminUi.td}><span className={typeBadgeClass(k.knowledge_type)}>{k.knowledge_type || 'other'}</span></td>
                      <td className={adminUi.td}>
                        <div className="flex flex-wrap gap-1">
                          <span className={statusBadgeClass(k.status)}>{k.status || 'unknown'}</span>
                          {k.is_active ? (
                            <span className={statusBadgeClass('active')}>active</span>
                          ) : (
                            <span className={statusBadgeClass('inactive')}>inactive</span>
                          )}
                        </div>
                      </td>
                      <td className={adminUi.tdRight}>
                        <div className="inline-flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => void pick(k.knowledge_id)}
                            className="rounded-lg border border-sky-200 bg-sky-50 px-2 py-1 text-[11px] font-semibold text-sky-700 hover:bg-sky-100"
                          >
                            Detail
                          </button>
                          {k.is_active ? (
                            <button type="button" onClick={() => void deactivate(k.knowledge_id)} className="rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-[11px] text-rose-700 hover:bg-rose-100">Deactivate</button>
                          ) : (
                            <button type="button" onClick={() => void activate(k.knowledge_id)} className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700 hover:bg-emerald-100">Activate</button>
                          )}
                          <button
                            type="button"
                            onClick={() => void remove(k.knowledge_id)}
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
                      <td colSpan={6} className="px-2 py-4 text-sm text-slate-500">No knowledge records found.</td>
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
                  itemLabel="knowledge records"
                />
              </div>
            </>
          )}
        </div>

        <div className="rounded-xl border border-sky-100 bg-white p-4 overflow-auto">
          {!selected ? (
            <p className="text-sm text-slate-500">Use Detail in a row to open full information.</p>
          ) : (
            <div className="space-y-3">
              <div>
                <p className="text-xs text-slate-500">Knowledge ID</p>
                <p className="text-sm font-bold text-slate-900 break-all">{selected.knowledge_id}</p>
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">File Information (Read-only)</p>
                <input
                  value={selected.title}
                  readOnly
                  className="w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-700"
                  title="Knowledge title"
                  aria-label="Knowledge title"
                />
                <input
                  value={selected.source_path || ''}
                  readOnly
                  className="w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-700"
                  title="Knowledge source path"
                  aria-label="Knowledge source path"
                />
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
                    <p className="text-slate-500">User</p>
                    <p className="font-semibold text-slate-800">{userLabel(selected.user_id)}</p>
                    <p className="text-slate-500 break-all">{selected.user_id}</p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
                    <p className="text-slate-500">Uploaded at</p>
                    <p className="font-semibold text-slate-800">{fmtDate(selected.created_at)}</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
                    <p className="text-slate-500">Type</p>
                    <p className="font-semibold text-slate-800">{selected.knowledge_type}</p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
                    <p className="text-slate-500">Status</p>
                    <p className="font-semibold text-slate-800">{selected.status}</p>
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
                  <p className="text-slate-500">Metadata sidecar path</p>
                  <p className="font-semibold text-slate-800 break-all">{metadataPathForSource(selected.source_path)}</p>
                </div>
              </div>

              <div className="rounded-xl border border-sky-100 bg-sky-50/40 p-3 space-y-2">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Editable Metadata</p>
                <textarea
                  value={editableTags}
                  onChange={(e) => setEditableTags(e.target.value)}
                  className={`w-full ${adminUi.input}`}
                  placeholder="tags (comma separated)"
                />
                <textarea
                  value={editableNotes}
                  onChange={(e) => setEditableNotes(e.target.value)}
                  className={`w-full ${adminUi.input}`}
                  placeholder="notes"
                />
                <button
                  type="button"
                  onClick={() => void saveItem()}
                  disabled={saving}
                  className={`w-full ${adminUi.buttonPrimary}`}
                >
                  Save tags and notes
                </button>
                <p className="text-xs text-slate-600">Tags and notes are stored in the metadata sidecar next to the uploaded file.</p>
              </div>

              <div className="rounded-xl border border-amber-100 bg-amber-50/40 p-3">
                <p className="text-xs font-bold uppercase tracking-widest text-amber-700">Action Behavior</p>
                <p className="mt-1 text-xs text-slate-700">Deactivate keeps file + index data and marks this knowledge as inactive only.</p>
                <p className="mt-1 text-xs text-slate-700">Remove deletes uploaded file + sidecar metadata and tries cleaning matching text/image vectors in Qdrant.</p>
                <p className="mt-1 text-xs text-slate-700">Knowledge ID formula: kg_ + first 16 hex chars of sha1(user_id|source_path).</p>
              </div>

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
