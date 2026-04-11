import React, { useEffect, useMemo, useState } from 'react';
import { Eye, RefreshCw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import { createFeedback, FeedbackItem, getFeedback, listFeedback } from '../api/ragApi';

const CATEGORIES = [
  'All categories',
  'Content Quality',
  'Feature & Scope',
  'Model Intelligence',
  'Safety & Security',
  'Uncategorized',
  'User Experience',
];

const APP_FEATURE_SCOPES = [
  'Dashboard',
  'Knowledge Management',
  'Upload Files',
  'Run Pipeline',
  'Build Index',
  'Knowledge Explorer',
  'Knowledge Dashboard',
  'Lecture Viewer',
  'Learning Path',
  'Chat Assistant',
  'Feedbacks',
  'Profile',
  'Authentication',
  'Search & Generation',
  'File Processing',
];

export default function FeedbacksView() {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<FeedbackItem | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [category, setCategory] = useState<string>('All categories');
  const [generalScope, setGeneralScope] = useState<string>('');
  const [generalText, setGeneralText] = useState<string>('');
  const [submittingGeneral, setSubmittingGeneral] = useState(false);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [generalSuccess, setGeneralSuccess] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listFeedback({
        limit: 80,
        ...(category !== 'All categories' ? { category } : {}),
      });
      setItems(data.items || []);
      if (!data.items?.length) {
        setSelectedId(null);
        setDetail(null);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to load feedback';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    setLoadingDetail(true);
    void getFeedback(selectedId)
      .then((x) => {
        if (!active) return;
        setDetail(x);
      })
      .catch(() => {
        if (!active) return;
        setDetail(null);
      })
      .finally(() => {
        if (!active) return;
        setLoadingDetail(false);
      });

    return () => {
      active = false;
    };
  }, [selectedId]);

  const submitGeneralFeedback = async () => {
    const text = generalText.trim();
    if (!text) {
      setGeneralError('Please write your feedback before submitting.');
      setGeneralSuccess(null);
      return;
    }

    setSubmittingGeneral(true);
    setGeneralError(null);
    setGeneralSuccess(null);
    try {
      const created = await createFeedback({
        vote: 'general',
        scope: generalScope || undefined,
        feedback_text: text,
        query: text,
        response: '',
        reason_code: 'general_feedback',
      });
      setGeneralText('');
      setGeneralScope('');
      setSelectedId(created.feedback_id);
      setGeneralSuccess('Thanks! Your feedback has been submitted.');
      await refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to submit general feedback';
      setGeneralError(msg);
    } finally {
      setSubmittingGeneral(false);
    }
  };

  const counts = useMemo(() => {
    const like = items.filter((x) => x.vote === 'like').length;
    const dislike = items.filter((x) => x.vote === 'dislike').length;
    const general = items.filter((x) => x.vote === 'general').length;
    return { total: items.length, like, dislike, general };
  }, [items]);

  return (
    <div className="w-full h-full min-h-0 flex flex-col space-y-4">
      <div className="rounded-2xl border border-sky-100 bg-white p-4 sm:p-5 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[220px]">
          <label className="text-xs font-semibold text-slate-600">Category</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            title="Feedback category"
            aria-label="Feedback category"
            className="mt-1 w-full rounded-lg border border-sky-100 bg-sky-50/60 px-3 py-2 text-sm"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      <div className="rounded-2xl border border-emerald-100 bg-white p-4 sm:p-5">
        <p className="text-sm font-semibold text-slate-800">Send General Feedback</p>
        <p className="text-xs text-slate-500 mt-1">
          Share any suggestion, issue, or idea about the app. Scope is optional.
        </p>
        <div className="mt-3 grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)_auto] gap-3 items-start">
          <select
            value={generalScope}
            onChange={(e) => setGeneralScope(e.target.value)}
            title="Feedback scope"
            aria-label="Feedback scope"
            className="rounded-lg border border-emerald-100 bg-emerald-50/50 px-3 py-2 text-sm"
          >
            <option value="">Scope (optional)</option>
            {APP_FEATURE_SCOPES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <textarea
            value={generalText}
            onChange={(e) => setGeneralText(e.target.value)}
            placeholder="Tell us what should be improved, what is confusing, or what new feature you want..."
            className="min-h-[84px] rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={() => void submitGeneralFeedback()}
            disabled={submittingGeneral}
            className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700 hover:bg-emerald-100 disabled:opacity-60"
          >
            {submittingGeneral ? 'Submitting...' : 'Submit feedback'}
          </button>
        </div>
        {!!generalError && <p className="mt-2 text-xs text-rose-600">{generalError}</p>}
        {!!generalSuccess && <p className="mt-2 text-xs text-emerald-700">{generalSuccess}</p>}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="rounded-xl border border-sky-100 bg-white p-4">
          <p className="text-xs text-slate-500">Feedback count</p>
          <p className="text-3xl font-black text-blue-600 mt-1">{counts.total}</p>
        </div>
        <div className="rounded-xl border border-sky-100 bg-white p-4">
          <p className="text-xs text-slate-500">Like count</p>
          <p className="text-3xl font-black text-emerald-600 mt-1">{counts.like}</p>
        </div>
        <div className="rounded-xl border border-sky-100 bg-white p-4">
          <p className="text-xs text-slate-500">Dislike count</p>
          <p className="text-3xl font-black text-rose-600 mt-1">{counts.dislike}</p>
        </div>
        <div className="rounded-xl border border-sky-100 bg-white p-4">
          <p className="text-xs text-slate-500">General count</p>
          <p className="text-3xl font-black text-amber-600 mt-1">{counts.general}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-4 min-h-0 flex-1">
        <div className="rounded-2xl border border-sky-100 bg-white overflow-auto min-h-[280px]">
          {loading ? (
            <div className="p-4 text-sm text-slate-500">Loading feedback...</div>
          ) : error ? (
            <div className="p-4 text-sm text-red-600">{error}</div>
          ) : items.length === 0 ? (
            <div className="p-4 text-sm text-slate-500">No feedback found for your account yet.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-sky-50/70 border-b border-sky-100">
                <tr>
                  <th className="px-3 py-2 text-left text-xs text-slate-600">Time</th>
                  <th className="px-3 py-2 text-left text-xs text-slate-600">Vote</th>
                  <th className="px-3 py-2 text-left text-xs text-slate-600">Scope</th>
                  <th className="px-3 py-2 text-left text-xs text-slate-600">Category</th>
                  <th className="px-3 py-2 text-left text-xs text-slate-600">Sub category</th>
                  <th className="px-3 py-2 text-right text-xs text-slate-600">View</th>
                </tr>
              </thead>
              <tbody>
                {items.map((x) => (
                  <tr key={x.feedback_id} className="border-b border-slate-100 hover:bg-slate-50/70">
                    <td className="px-3 py-2 text-xs text-slate-600">{new Date(x.created_at).toLocaleString()}</td>
                    <td className="px-3 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        x.vote === 'like'
                          ? 'bg-emerald-100 text-emerald-700'
                          : x.vote === 'dislike'
                            ? 'bg-rose-100 text-rose-700'
                            : 'bg-amber-100 text-amber-700'
                      }`}>
                        {x.vote}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-600">{x.scope || '-'}</td>
                    <td className="px-3 py-2 text-slate-700">{x.category}</td>
                    <td className="px-3 py-2 text-slate-600">{x.sub_category || '-'}</td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => setSelectedId(x.feedback_id)}
                        className="inline-flex items-center gap-1 rounded-lg border border-sky-200 bg-sky-50 px-2 py-1 text-xs text-sky-700 hover:bg-sky-100"
                      >
                        <Eye className="w-3.5 h-3.5" /> View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="rounded-2xl border border-sky-100 bg-white p-4 overflow-auto min-h-[280px]">
          {!selectedId ? (
            <p className="text-sm text-slate-500">Select one feedback row to view detail.</p>
          ) : loadingDetail ? (
            <p className="text-sm text-slate-500">Loading detail...</p>
          ) : !detail ? (
            <p className="text-sm text-slate-500">Feedback detail not available.</p>
          ) : (
            <div className="space-y-4 text-sm">
              <div>
                <p className="text-xs text-slate-500">Time</p>
                <p className="text-slate-800">{new Date(detail.created_at).toLocaleString()}</p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <p className="text-xs text-slate-500">Category</p>
                  <p className="text-slate-800">{detail.category}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Sub category</p>
                  <p className="text-slate-800">{detail.sub_category || '-'}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <p className="text-xs text-slate-500">Vote type</p>
                  <p className="text-slate-800">{detail.vote}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Scope</p>
                  <p className="text-slate-800">{detail.scope || '-'}</p>
                </div>
              </div>
              {!!detail.feedback_text && (
                <div>
                  <p className="text-xs text-slate-500">General feedback note</p>
                  <div className="mt-1 rounded-xl border border-amber-100 bg-amber-50/50 p-3 prose prose-sm max-w-none prose-p:my-2 prose-headings:my-2 prose-li:my-1 prose-code:text-amber-700">
                    <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                      {detail.feedback_text}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
              <div>
                <p className="text-xs text-slate-500">Suggested action</p>
                <div className="mt-1 rounded-xl border border-emerald-100 bg-emerald-50/50 p-3 prose prose-sm max-w-none prose-p:my-2 prose-headings:my-2 prose-li:my-1 prose-code:text-emerald-700">
                  <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                    {detail.suggested_action || '-'}
                  </ReactMarkdown>
                </div>
              </div>
              <div>
                <p className="text-xs text-slate-500">User query</p>
                <div className="mt-1 rounded-xl border border-slate-200 bg-slate-50/70 p-3 prose prose-sm max-w-none prose-p:my-2 prose-headings:my-2 prose-li:my-1 prose-code:text-sky-700">
                  <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                    {detail.query || '-'}
                  </ReactMarkdown>
                </div>
              </div>
              <div>
                <p className="text-xs text-slate-500">AI response</p>
                <div className="mt-1 rounded-xl border border-sky-100 bg-sky-50/40 p-3 prose prose-sm max-w-none prose-p:my-2 prose-headings:my-2 prose-li:my-1 prose-code:text-sky-700">
                  <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                    {detail.response || '-'}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
