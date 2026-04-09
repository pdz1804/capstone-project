import { useEffect, useState } from 'react';
import { BookOpen, Loader2, Sparkles, X } from 'lucide-react';
import type { UserEntity } from '../database/types';

interface UserProfileModalProps {
  isOpen: boolean;
  profile: UserEntity | null;
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  canEditDisplayName: boolean;
  onClose: () => void;
  onSave: (payload: {
    displayName: string;
    persona: string;
    educationDescription: string;
  }) => void;
}

const PERSONA_OPTIONS = [
  'Friendly mentor',
  'Concise tutor',
  'Formal academic',
  'Motivational coach',
];

export default function UserProfileModal({
  isOpen,
  profile,
  isLoading,
  isSaving,
  error,
  canEditDisplayName,
  onClose,
  onSave,
}: UserProfileModalProps) {
  const [displayName, setDisplayName] = useState('');
  const [persona, setPersona] = useState(PERSONA_OPTIONS[0]);
  const [educationDescription, setEducationDescription] = useState('');

  useEffect(() => {
    if (!isOpen || !profile) return;
    setDisplayName(profile.displayName || '');
    setPersona(profile.persona || PERSONA_OPTIONS[0]);
    setEducationDescription(profile.educationDescription || '');
  }, [isOpen, profile]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl rounded-3xl border border-sky-100 bg-white shadow-[0_30px_80px_-50px_rgba(2,132,199,0.55)] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-5 border-b border-sky-100 bg-sky-50/50 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-sky-600 text-white flex items-center justify-center shadow-sm">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-black text-slate-900 tracking-tight">Profile Settings</p>
              <p className="text-xs text-slate-500">Personalize your learning assistant experience</p>
            </div>
          </div>
          <button
            type="button"
            className="p-2 rounded-lg text-slate-500 hover:bg-sky-100 hover:text-sky-700 transition-colors"
            onClick={onClose}
            aria-label="Close profile settings"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {isLoading ? (
            <div className="h-52 flex flex-col items-center justify-center text-slate-500 gap-3">
              <Loader2 className="w-7 h-7 animate-spin text-sky-600" />
              <p className="text-sm">Loading profile...</p>
            </div>
          ) : (
            <form
              className="space-y-5"
              onSubmit={(e) => {
                e.preventDefault();
                onSave({
                  displayName: displayName.trim(),
                  persona: persona.trim(),
                  educationDescription: educationDescription.trim(),
                });
              }}
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <label className="text-sm text-slate-700">
                  <span className="block text-xs font-bold uppercase tracking-widest text-slate-400 mb-2">Display name</span>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="Your name"
                    readOnly={!canEditDisplayName}
                    className="w-full rounded-xl border border-sky-100 bg-sky-50/50 px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 read-only:bg-slate-100/80 read-only:text-slate-500 read-only:cursor-not-allowed"
                  />
                  {!canEditDisplayName && (
                    <span className="mt-2 block text-[11px] text-slate-500">
                      Student accounts can edit Assistant Tone and Education Background only.
                    </span>
                  )}
                </label>

                <label className="text-sm text-slate-700">
                  <span className="block text-xs font-bold uppercase tracking-widest text-slate-400 mb-2">Assistant tone</span>
                  <select
                    value={persona}
                    onChange={(e) => setPersona(e.target.value)}
                    className="w-full rounded-xl border border-sky-100 bg-sky-50/50 px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                  >
                    {PERSONA_OPTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </label>
              </div>

              <label className="text-sm text-slate-700 block">
                <span className="block text-xs font-bold uppercase tracking-widest text-slate-400 mb-2">Education background</span>
                <textarea
                  value={educationDescription}
                  onChange={(e) => setEducationDescription(e.target.value)}
                  rows={5}
                  placeholder="Describe your current knowledge, subjects studied, and learning goals..."
                  className="w-full rounded-xl border border-sky-100 bg-sky-50/50 px-3.5 py-3 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 resize-y"
                />
              </label>

              <div className="rounded-xl border border-sky-100 bg-sky-50/60 px-4 py-3 text-xs text-slate-600 flex items-start gap-2">
                <Sparkles className="w-4 h-4 text-sky-600 mt-0.5 shrink-0" />
                Your profile context helps BK-MInD adapt explanation style and depth in chat.
              </div>

              <div className="flex justify-end gap-3 pt-1">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2.5 rounded-xl border border-sky-200 text-sky-700 text-sm font-semibold hover:bg-sky-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="px-5 py-2.5 rounded-xl bg-sky-600 text-white text-sm font-semibold hover:bg-sky-700 disabled:opacity-60 inline-flex items-center gap-2 transition-colors"
                >
                  {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  Save changes
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
