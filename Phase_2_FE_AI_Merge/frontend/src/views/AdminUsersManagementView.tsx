import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Shield,
  Trash2,
  UserCheck,
  UserMinus,
} from 'lucide-react';
import { userRepo } from '../repositories/user_repository';
import type { UserEntity } from '../database/types';
import { adminRowClass, adminUi, roleBadgeClass, statusBadgeClass } from '../lib/adminUi';

function nf(n: number): string {
  return new Intl.NumberFormat('en-US').format(n || 0);
}

function fmtDate(iso?: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

type Editable = {
  displayName: string;
  role: string;
  isActive: boolean;
};

type UserDetail = UserEntity & { usage_summary?: Record<string, unknown> };

export default function AdminUsersManagementView() {
  const [users, setUsers] = useState<UserEntity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState('');
  const [role, setRole] = useState('');
  const [activeFilter, setActiveFilter] = useState<string>('all');

  const [selected, setSelected] = useState<UserDetail | null>(null);
  const [saving, setSaving] = useState(false);
  const [edit, setEdit] = useState<Editable>({ displayName: '', role: 'student', isActive: true });
  const initializedRef = useRef(false);

  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    email: '',
    password: '',
    username: '',
    displayName: '',
    role: 'student',
  });

  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await userRepo.listAdminUsers({
        limit: 1000,
        query: query || undefined,
        role: role || undefined,
        is_active: activeFilter === 'all' ? undefined : activeFilter === 'active',
      });
      setUsers(data.items || []);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;
    void loadUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => users, [users]);

  const loadDetail = async (uid: string) => {
    try {
      const item = await userRepo.getAdminUser(uid);
      const next = item as UserDetail;
      setSelected(next);
      setEdit({
        displayName: next.displayName || '',
        role: next.role || 'student',
        isActive: next.isActive ?? true,
      });
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load user detail');
    }
  };

  const saveUser = async () => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await userRepo.updateAdminUser(selected.uid, {
        displayName: edit.displayName,
        role: edit.role as any,
        isActive: edit.isActive,
      });
      setSelected({ ...selected, ...updated });
      await loadUsers();
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to update user');
    } finally {
      setSaving(false);
    }
  };

  const createUser = async () => {
    setSaving(true);
    setError(null);
    try {
      await userRepo.createAdminUser({
        email: createForm.email,
        password: createForm.password,
        username: createForm.username || undefined,
        displayName: createForm.displayName || undefined,
        role: createForm.role,
      });
      setShowCreate(false);
      setCreateForm({ email: '', password: '', username: '', displayName: '', role: 'student' });
      await loadUsers();
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to create user');
    } finally {
      setSaving(false);
    }
  };

  const deactivate = async (uid: string) => {
    try {
      await userRepo.deactivateAdminUser(uid);
      await loadUsers();
      if (selected?.uid === uid) {
        await loadDetail(uid);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to deactivate user');
    }
  };

  const activate = async (uid: string) => {
    try {
      await userRepo.activateAdminUser(uid);
      await loadUsers();
      if (selected?.uid === uid) {
        await loadDetail(uid);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to activate user');
    }
  };

  const removeUser = async (uid: string) => {
    if (!window.confirm('Delete this user permanently?')) return;
    try {
      await userRepo.deleteAdminUser(uid);
      await loadUsers();
      if (selected?.uid === uid) setSelected(null);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to delete user');
    }
  };

  return (
    <div className="space-y-4">
      <div className={adminUi.panel}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-sky-600">Admin</p>
            <h2 className="text-xl font-black text-slate-900 tracking-tight">User Management</h2>
            <p className="mt-1 text-xs text-slate-500">Tip: use Detail in each row to open the full user profile panel.</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowCreate((v) => !v)}
              className={`inline-flex items-center gap-2 ${adminUi.buttonPrimary}`}
            >
              <Plus className="w-4 h-4" /> New user
            </button>
            <button
              type="button"
              onClick={() => void loadUsers()}
              className={`inline-flex items-center gap-2 ${adminUi.buttonSoft}`}
            >
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
        </div>

        {showCreate && (
          <div className="mt-4 grid grid-cols-1 lg:grid-cols-6 gap-2 rounded-xl border border-sky-100 bg-sky-50/40 p-3">
            <input
              value={createForm.email}
              onChange={(e) => setCreateForm((s) => ({ ...s, email: e.target.value }))}
              placeholder="email"
              className={adminUi.input}
            />
            <input
              value={createForm.password}
              onChange={(e) => setCreateForm((s) => ({ ...s, password: e.target.value }))}
              placeholder="password"
              className={adminUi.input}
            />
            <input
              value={createForm.username}
              onChange={(e) => setCreateForm((s) => ({ ...s, username: e.target.value }))}
              placeholder="username (optional)"
              className={adminUi.input}
            />
            <input
              value={createForm.displayName}
              onChange={(e) => setCreateForm((s) => ({ ...s, displayName: e.target.value }))}
              placeholder="display name"
              className={adminUi.input}
            />
            <select
              value={createForm.role}
              onChange={(e) => setCreateForm((s) => ({ ...s, role: e.target.value }))}
              className={adminUi.select}
              title="Role"
              aria-label="Role"
            >
              <option value="student">student</option>
              <option value="instructor">instructor</option>
              <option value="admin">admin</option>
            </select>
            <button
              type="button"
              onClick={() => void createUser()}
              disabled={saving || !createForm.email || !createForm.password}
              className={adminUi.buttonPrimary}
            >
              Create
            </button>
          </div>
        )}

        <div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-2">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="search uid/email/name"
              className={`w-full pl-9 pr-3 ${adminUi.input}`}
            />
          </div>
          <select value={role} onChange={(e) => setRole(e.target.value)} className={adminUi.select} title="Role filter" aria-label="Role filter">
            <option value="">All roles</option>
            <option value="student">student</option>
            <option value="instructor">instructor</option>
            <option value="admin">admin</option>
          </select>
          <select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)} className={adminUi.select} title="Activation filter" aria-label="Activation filter">
            <option value="all">All status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          <button
            type="button"
            onClick={() => void loadUsers()}
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
              <Loader2 className="w-4 h-4 animate-spin" /> Loading users...
            </div>
          ) : (
            <table className={adminUi.table}>
              <thead className={adminUi.thead}>
                <tr>
                  <th className={adminUi.th}>User</th>
                  <th className={adminUi.th}>Role</th>
                  <th className={adminUi.th}>Status</th>
                  <th className={adminUi.thRight}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((u, idx) => (
                  <tr key={u.uid} className={adminRowClass(idx)}>
                    <td className={adminUi.td}>
                      <p className="text-xs font-semibold text-slate-800">{u.displayName || u.username || u.email}</p>
                      <p className="text-[11px] text-slate-500">{u.email}</p>
                    </td>
                    <td className={adminUi.td}><span className={roleBadgeClass(u.role)}>{u.role || 'student'}</span></td>
                    <td className={adminUi.td}>
                      {(u.isActive ?? true) ? (
                        <span className={statusBadgeClass('active')}>active</span>
                      ) : (
                        <span className={statusBadgeClass('inactive')}>inactive</span>
                      )}
                    </td>
                    <td className={adminUi.tdRight}>
                      <div className="inline-flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => void loadDetail(u.uid)}
                          className="rounded-lg border border-sky-200 bg-sky-50 px-2 py-1 text-[11px] font-semibold text-sky-700 hover:bg-sky-100"
                        >
                          Detail
                        </button>
                        {(u.isActive ?? true) ? (
                          <button
                            type="button"
                            onClick={() => void deactivate(u.uid)}
                            className="rounded-md border border-rose-200 bg-rose-50 p-1.5 text-rose-700 hover:bg-rose-100"
                            title="Deactivate"
                          >
                            <UserMinus className="w-3.5 h-3.5" />
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => void activate(u.uid)}
                            className="rounded-md border border-emerald-200 bg-emerald-50 p-1.5 text-emerald-700 hover:bg-emerald-100"
                            title="Activate"
                          >
                            <UserCheck className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => void removeUser(u.uid)}
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
                    <td colSpan={4} className="px-2 py-4 text-sm text-slate-500">No users found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        <div className="rounded-xl border border-sky-100 bg-white p-4 overflow-auto">
          {!selected ? (
            <p className="text-sm text-slate-500">Use Detail on a row to open user information and controls.</p>
          ) : (
            <div className="space-y-4">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs font-bold uppercase tracking-widest text-slate-500">User Profile</p>
                <div className="mt-2 grid grid-cols-1 gap-2 text-xs text-slate-700">
                  <div className="rounded-lg border border-slate-200 bg-white p-2">
                    <p className="text-slate-500">UID</p>
                    <p className="font-semibold break-all">{selected.uid}</p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-white p-2">
                    <p className="text-slate-500">Email</p>
                    <p className="font-semibold">{selected.email}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="rounded-lg border border-slate-200 bg-white p-2">
                      <p className="text-slate-500">Username</p>
                      <p className="font-semibold">{selected.username || '-'}</p>
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-white p-2">
                      <p className="text-slate-500">Auth provider</p>
                      <p className="font-semibold">{selected.authProvider || '-'}</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="rounded-lg border border-slate-200 bg-white p-2">
                      <p className="text-slate-500">Created</p>
                      <p className="font-semibold">{fmtDate(selected.createdAt)}</p>
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-white p-2">
                      <p className="text-slate-500">Last login</p>
                      <p className="font-semibold">{fmtDate(selected.lastLogin)}</p>
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-white p-2">
                    <p className="text-slate-500">Persona</p>
                    <p className="font-semibold">{selected.persona || '-'}</p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-white p-2">
                    <p className="text-slate-500">Education description</p>
                    <p className="font-semibold whitespace-pre-wrap">{selected.educationDescription || '-'}</p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-white p-2">
                    <p className="text-slate-500">Photo URL</p>
                    <p className="font-semibold break-all">{selected.photoURL || '-'}</p>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-sky-100 bg-sky-50/40 p-3">
                <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Access Controls</p>
                <div className="mt-2 grid grid-cols-1 gap-2">
                  <input
                    value={edit.displayName}
                    onChange={(e) => setEdit((s) => ({ ...s, displayName: e.target.value }))}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    placeholder="display name"
                  />
                  <select
                    value={edit.role}
                    onChange={(e) => setEdit((s) => ({ ...s, role: e.target.value }))}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    title="Role"
                    aria-label="Role"
                  >
                    <option value="student">student</option>
                    <option value="instructor">instructor</option>
                    <option value="admin">admin</option>
                  </select>
                  <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={edit.isActive}
                      onChange={(e) => setEdit((s) => ({ ...s, isActive: e.target.checked }))}
                    />
                    Active account
                  </label>
                  <button
                    type="button"
                    onClick={() => void saveUser()}
                    disabled={saving}
                    className={adminUi.buttonPrimary}
                  >
                    Save changes
                  </button>
                </div>
              </div>

              <div className="rounded-xl border border-sky-100 bg-sky-50/40 p-3">
                <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Usage Summary</p>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-lg border border-sky-100 bg-white p-2">
                    <p className="text-slate-500">Requests</p>
                    <p className="text-sm font-bold text-slate-800">{nf(Number(selected.usage_summary?.total_requests || 0))}</p>
                  </div>
                  <div className="rounded-lg border border-sky-100 bg-white p-2">
                    <p className="text-slate-500">Estimated Cost</p>
                    <p className="text-sm font-bold text-amber-700">${Number(selected.usage_summary?.estimated_cost_usd || 0).toFixed(4)}</p>
                  </div>
                  <div className="rounded-lg border border-sky-100 bg-white p-2">
                    <p className="text-slate-500">Token In</p>
                    <p className="text-sm font-bold text-slate-800">{nf(Number(selected.usage_summary?.token_in || 0))}</p>
                  </div>
                  <div className="rounded-lg border border-sky-100 bg-white p-2">
                    <p className="text-slate-500">Token Out</p>
                    <p className="text-sm font-bold text-slate-800">{nf(Number(selected.usage_summary?.token_out || 0))}</p>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-sky-100 bg-slate-50 p-3 text-xs text-slate-600">
                <p className="inline-flex items-center gap-1 font-semibold text-slate-700">
                  <Shield className="w-3.5 h-3.5" /> Admin action note
                </p>
                <p className="mt-1">Deactivate blocks account access while keeping records. Delete removes user account permanently.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
