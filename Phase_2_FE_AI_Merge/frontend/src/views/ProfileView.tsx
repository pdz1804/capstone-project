import { useEffect, useMemo, useState } from 'react';
import { BadgeCheck, BookOpen, CalendarDays, Clock3, Loader2, Mail, Settings, UserCircle2 } from 'lucide-react';
import type { AuthUser } from '../services/auth_service';
import { authService } from '../services/auth_service';
import type { UserEntity } from '../database/types';

interface ProfileViewProps {
  user: AuthUser;
  onEditProfile: () => void;
}

function formatDate(value?: string | null): string {
  if (!value) return 'Not available';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}

export default function ProfileView({ user, onEditProfile }: ProfileViewProps) {
  const [profile, setProfile] = useState<UserEntity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    void authService.getMe().then((me) => {
      if (!active) return;
      setProfile(me);
    }).catch((e) => {
      console.error('Failed to load profile detail', e);
      if (!active) return;
      setError('Unable to load profile details. Please try again.');
    }).finally(() => {
      if (!active) return;
      setLoading(false);
    });

    return () => {
      active = false;
    };
  }, []);

  const effective = profile || {
    uid: user.uid,
    email: user.email || '',
    displayName: user.displayName,
    role: 'student' as const,
    photoURL: user.photoURL,
    persona: user.persona || null,
    educationDescription: user.educationDescription || null,
    authProvider: null,
    createdAt: '',
    lastLogin: null,
  };

  const infoRows = useMemo(() => ([
    { label: 'UID', value: effective.uid || 'Not available' },
    { label: 'Email', value: effective.email || 'Not available' },
    { label: 'Display Name', value: effective.displayName || 'Not set' },
    { label: 'Role', value: effective.role || 'student' },
    { label: 'Auth Provider', value: effective.authProvider || 'google' },
    { label: 'Assistant Tone', value: effective.persona || 'Not set' },
    { label: 'Created At', value: formatDate(effective.createdAt) },
    { label: 'Last Login', value: formatDate(effective.lastLogin) },
  ]), [effective]);

  return (
    <div className="w-full max-w-[1400px] mx-auto space-y-7 pb-12">
      <div className="relative overflow-hidden rounded-3xl border border-sky-100 bg-white p-6 sm:p-7 shadow-[0_20px_45px_-32px_rgba(14,165,233,0.58)]">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.15),transparent_42%)]" />
        <div className="relative flex flex-col md:flex-row md:items-center md:justify-between gap-5">
          <div className="flex items-center gap-4 min-w-0">
            {effective.photoURL ? (
              <img src={effective.photoURL} alt={effective.displayName || 'User'} className="w-16 h-16 rounded-2xl border border-sky-100 object-cover" />
            ) : (
              <div className="w-16 h-16 rounded-2xl bg-sky-100 text-sky-700 font-black text-2xl flex items-center justify-center border border-sky-200">
                {(effective.displayName || 'U').charAt(0).toUpperCase()}
              </div>
            )}
            <div className="min-w-0">
              <p className="text-xs font-black uppercase tracking-widest text-sky-600">User Profile</p>
              <h2 className="text-2xl font-black text-slate-900 tracking-tight truncate">{effective.displayName || 'Unnamed User'}</h2>
              <p className="text-sm text-slate-500 truncate">{effective.email || 'No email'}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onEditProfile}
            className="self-start md:self-center inline-flex items-center gap-2 rounded-xl border border-sky-200 bg-white/85 px-4 py-2.5 text-sm font-semibold text-sky-700 hover:bg-sky-50 transition-colors"
            title="Edit profile settings"
          >
            <Settings className="w-4 h-4" />
            Edit Profile
          </button>
        </div>
      </div>

      {loading ? (
        <div className="rounded-2xl border border-sky-100 bg-white px-6 py-14 text-center text-slate-500">
          <Loader2 className="w-7 h-7 animate-spin text-sky-600 mx-auto mb-3" />
          Loading profile details...
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-6 py-4 text-red-700 text-sm">{error}</div>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="rounded-2xl border border-sky-100 bg-white p-5 shadow-[0_14px_28px_-24px_rgba(14,165,233,0.45)]">
              <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                <UserCircle2 className="w-5 h-5 text-sky-600" />
                Account Details
              </h3>
              <div className="space-y-3">
                {infoRows.map((row) => (
                  <div key={row.label} className="rounded-xl border border-sky-100 bg-sky-50/45 p-3">
                    <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">{row.label}</p>
                    <p className="text-sm text-slate-800 mt-1 break-all">{row.value}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-5">
              <div className="rounded-2xl border border-sky-100 bg-white p-5 shadow-[0_14px_28px_-24px_rgba(14,165,233,0.45)]">
                <h3 className="text-lg font-bold text-slate-900 mb-3 flex items-center gap-2">
                  <BadgeCheck className="w-5 h-5 text-sky-600" />
                  Education Description
                </h3>
                <p className="text-sm text-slate-700 leading-7 whitespace-pre-wrap">
                  {effective.educationDescription || 'No education background provided yet. Add your background in Edit Profile so the chat assistant can personalize support and explanation depth.'}
                </p>
              </div>

              <div className="rounded-2xl border border-sky-100 bg-white p-5 shadow-[0_14px_28px_-24px_rgba(14,165,233,0.45)]">
                <h3 className="text-lg font-bold text-slate-900 mb-3 flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-sky-600" />
                  Profile Summary
                </h3>
                <ul className="space-y-2 text-sm text-slate-700">
                  <li className="flex items-center gap-2"><Mail className="w-4 h-4 text-sky-600" /> {effective.email || 'No email'}</li>
                  <li className="flex items-center gap-2"><CalendarDays className="w-4 h-4 text-sky-600" /> Created: {formatDate(effective.createdAt)}</li>
                  <li className="flex items-center gap-2"><Clock3 className="w-4 h-4 text-sky-600" /> Last login: {formatDate(effective.lastLogin)}</li>
                </ul>
              </div>
            </div>
          </div>

        </>
      )}
    </div>
  );
}
