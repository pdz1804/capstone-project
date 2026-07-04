export const adminUi = {
  panel:
    'rounded-2xl border border-slate-200/70 bg-gradient-to-r from-transparent via-slate-50/60 to-sky-50/50 p-4 shadow-none',
  tableShell:
    'rounded-2xl border border-slate-200 bg-white/90 shadow-[0_20px_38px_-30px_rgba(15,23,42,0.45)] overflow-auto backdrop-blur-[1px]',
  table: 'min-w-full text-sm',
  thead:
    'sticky top-0 z-10 bg-gradient-to-r from-slate-100 via-slate-50 to-sky-50/85 backdrop-blur supports-[backdrop-filter]:bg-slate-50/85',
  th: 'px-3 py-2.5 text-left text-[11px] font-bold uppercase tracking-wide text-slate-600',
  thRight: 'px-3 py-2.5 text-right text-[11px] font-bold uppercase tracking-wide text-slate-600',
  td: 'px-3 py-2.5 text-xs text-slate-700 align-top',
  tdRight: 'px-3 py-2.5 text-right text-xs text-slate-700 align-top',
  input:
    'rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100',
  select:
    'rounded-xl border border-slate-200 bg-white/95 px-3 py-2 text-sm text-slate-700 shadow-sm outline-none transition hover:border-slate-300 focus:border-sky-300 focus:ring-2 focus:ring-sky-100 cursor-pointer',
  buttonPrimary:
    'rounded-xl bg-sky-700 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-800 disabled:opacity-60',
  buttonSoft:
    'rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50',
  buttonSubtle:
    'rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100',
};

export function adminRowClass(index: number): string {
  return [
    'border-b border-slate-100/90 transition-colors hover:bg-sky-50/55',
    index % 2 === 1 ? 'bg-slate-50/45' : '',
  ].join(' ');
}

const badgeBase = 'inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide';

function normalizeToken(value?: string): string {
  return String(value || '').trim().toLowerCase();
}

export function roleBadgeClass(role?: string): string {
  const token = normalizeToken(role);
  if (token === 'admin') return `${badgeBase} bg-indigo-100 text-indigo-700 ring-1 ring-indigo-200`;
  if (token === 'instructor') return `${badgeBase} bg-cyan-100 text-cyan-700 ring-1 ring-cyan-200`;
  return `${badgeBase} bg-slate-100 text-slate-700 ring-1 ring-slate-200`;
}

export function statusBadgeClass(status?: string): string {
  const token = normalizeToken(status);
  if (token === 'active' || token === 'success' || token === 'indexed') {
    return `${badgeBase} bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200`;
  }
  if (token === 'inactive' || token === 'failed' || token === 'error') {
    return `${badgeBase} bg-rose-100 text-rose-700 ring-1 ring-rose-200`;
  }
  if (token === 'processing' || token === 'uploaded') {
    return `${badgeBase} bg-amber-100 text-amber-700 ring-1 ring-amber-200`;
  }
  return `${badgeBase} bg-slate-100 text-slate-700 ring-1 ring-slate-200`;
}

export function voteBadgeClass(vote?: string): string {
  const token = normalizeToken(vote);
  if (token === 'like') return `${badgeBase} bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200`;
  if (token === 'dislike') return `${badgeBase} bg-rose-100 text-rose-700 ring-1 ring-rose-200`;
  return `${badgeBase} bg-sky-100 text-sky-700 ring-1 ring-sky-200`;
}

export function categoryBadgeClass(category?: string): string {
  const token = normalizeToken(category);
  if (token.includes('quality')) return `${badgeBase} bg-violet-100 text-violet-700 ring-1 ring-violet-200`;
  if (token.includes('latency') || token.includes('performance')) return `${badgeBase} bg-cyan-100 text-cyan-700 ring-1 ring-cyan-200`;
  if (token.includes('cost')) return `${badgeBase} bg-amber-100 text-amber-700 ring-1 ring-amber-200`;
  return `${badgeBase} bg-slate-100 text-slate-700 ring-1 ring-slate-200`;
}

export function typeBadgeClass(kind?: string): string {
  const token = normalizeToken(kind);
  if (token === 'video') return `${badgeBase} bg-blue-100 text-blue-700 ring-1 ring-blue-200`;
  if (token === 'document' || token === 'spreadsheet') return `${badgeBase} bg-indigo-100 text-indigo-700 ring-1 ring-indigo-200`;
  if (token === 'audio') return `${badgeBase} bg-fuchsia-100 text-fuchsia-700 ring-1 ring-fuchsia-200`;
  if (token === 'image') return `${badgeBase} bg-orange-100 text-orange-700 ring-1 ring-orange-200`;
  return `${badgeBase} bg-slate-100 text-slate-700 ring-1 ring-slate-200`;
}
