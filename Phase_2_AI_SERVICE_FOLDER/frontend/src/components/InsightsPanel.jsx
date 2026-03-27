import { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { BarChart2, BookOpen, HelpCircle, Loader2, Map, Sparkles } from 'lucide-react'

/** Minimal exam-style MCQ list (no JSON dump). */
function McqExamView({ questions, hasExplanations }) {
  const [showKey, setShowKey] = useState(false)
  const list = Array.isArray(questions) ? questions.filter((q) => q && typeof q.question === 'string') : []

  if (list.length === 0) {
    return <p className="text-sm text-slate-500">No questions in this response.</p>
  }

  return (
    <div className="max-w-3xl border border-slate-200 rounded-lg bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 border-b border-slate-200 bg-slate-50/90">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          {list.length} question{list.length === 1 ? '' : 's'}
        </span>
        <button
          type="button"
          onClick={() => setShowKey((v) => !v)}
          className="text-xs font-medium text-slate-700 px-2.5 py-1 rounded-md border border-slate-200 bg-white hover:bg-slate-50"
        >
          {showKey ? 'Hide answer key' : 'Show answer key'}
        </button>
      </div>
      <ol className="divide-y divide-slate-100 list-none m-0 p-0">
        {list.map((q, qi) => {
          const opts = Array.isArray(q.options) ? q.options.slice(0, 8) : []
          const correct = Number.isInteger(q.correct_index) ? q.correct_index : -1
          return (
            <li key={qi} className="px-4 py-5 sm:px-5">
              <p className="text-[15px] leading-snug text-slate-900 font-medium mb-3">
                <span className="inline-block min-w-[1.75rem] text-slate-400 font-normal tabular-nums">{qi + 1}.</span>
                {q.question}
              </p>
              <ul className="space-y-0 m-0 p-0 list-none">
                {opts.map((opt, oi) => {
                  const letter = String.fromCharCode(65 + oi)
                  const isCorrect = showKey && oi === correct
                  return (
                    <li
                      key={oi}
                      className={`flex gap-3 text-sm text-slate-800 py-2 px-2 -mx-2 rounded-md border border-transparent ${
                        isCorrect ? 'bg-emerald-50 border-emerald-200/80' : ''
                      }`}
                    >
                      <span className="shrink-0 w-6 font-mono text-xs text-slate-500 pt-0.5">{letter}.</span>
                      <span className="leading-snug">{opt}</span>
                    </li>
                  )
                })}
              </ul>
              {showKey && hasExplanations && q.explanation ? (
                <p className="mt-3 text-xs text-slate-600 leading-relaxed pl-1 border-l-2 border-slate-200 ml-1">{q.explanation}</p>
              ) : null}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

const SUB_TABS = [
  { id: 'summary', label: 'Lecture summary', icon: BookOpen },
  { id: 'mcq', label: 'Practice MCQs', icon: HelpCircle },
  { id: 'roadmap', label: 'Learning roadmap', icon: Map },
  { id: 'analytics', label: 'Analytics', icon: BarChart2 },
]

export default function InsightsPanel({ apiBase, processedLayout }) {
  const [subTab, setSubTab] = useState('summary')

  const documentChoices = useMemo(() => {
    const docs = processedLayout?.documents || []
    const real = docs.filter((d) => d.id && !String(d.id).startsWith('__'))
    return [{ id: '', label: 'All processed documents' }, ...real.map((d) => ({ id: d.id, label: d.display_name || d.id }))]
  }, [processedLayout])

  const [documentId, setDocumentId] = useState('')

  const [summaryQuery, setSummaryQuery] = useState('')
  const [summaryDepth, setSummaryDepth] = useState('detailed')
  const [summaryTone, setSummaryTone] = useState('neutral')
  const [summaryLength, setSummaryLength] = useState('medium')
  const [summaryOut, setSummaryOut] = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(false)

  const [mcqTopic, setMcqTopic] = useState('')
  const [mcqNum, setMcqNum] = useState(5)
  const [mcqDifficulty, setMcqDifficulty] = useState('intermediate')
  const [mcqStyle, setMcqStyle] = useState('exam')
  const [mcqExplain, setMcqExplain] = useState(true)
  const [mcqOut, setMcqOut] = useState(null)
  const [mcqLoading, setMcqLoading] = useState(false)
  const [mcqRenderKey, setMcqRenderKey] = useState(0)

  const [roadProfile, setRoadProfile] = useState('')
  const [roadGoals, setRoadGoals] = useState('')
  const [roadOut, setRoadOut] = useState(null)
  const [roadLoading, setRoadLoading] = useState(false)

  const [analyticsOut, setAnalyticsOut] = useState(null)

  useEffect(() => {
    if (subTab !== 'analytics') return
    let cancelled = false
    axios
      .get(`${apiBase}/insights/analytics`)
      .then((r) => {
        if (!cancelled) setAnalyticsOut(r.data)
      })
      .catch((e) => {
        if (!cancelled) setAnalyticsOut({ error: e.response?.data?.detail || e.message })
      })
    return () => {
      cancelled = true
    }
  }, [subTab, apiBase])

  const payloadDocumentId = documentId.trim() || null

  const runSummary = async () => {
    setSummaryLoading(true)
    setSummaryOut(null)
    try {
      const r = await axios.post(`${apiBase}/insights/summary`, {
        focus_query: summaryQuery,
        depth: summaryDepth,
        top_k: 12,
        document_id: payloadDocumentId,
        tone: summaryTone,
        target_length: summaryLength,
      })
      setSummaryOut(r.data)
    } catch (e) {
      setSummaryOut({ error: e.response?.data?.detail || e.message })
    }
    setSummaryLoading(false)
  }

  const runMcq = async () => {
    if (!mcqTopic.trim()) return
    setMcqLoading(true)
    setMcqOut(null)
    try {
      const r = await axios.post(`${apiBase}/insights/mcq`, {
        topic: mcqTopic,
        num_questions: mcqNum,
        difficulty: mcqDifficulty,
        document_id: payloadDocumentId,
        question_style: mcqStyle,
        include_explanations: mcqExplain,
      })
      setMcqOut(r.data)
    } catch (e) {
      setMcqOut({ error: e.response?.data?.detail || e.message })
    }
    setMcqLoading(false)
  }

  const runRoadmap = async () => {
    if (!roadGoals.trim()) return
    setRoadLoading(true)
    setRoadOut(null)
    try {
      const r = await axios.post(`${apiBase}/insights/learning-roadmap`, {
        student_profile: roadProfile,
        goals: roadGoals,
        document_id: payloadDocumentId,
      })
      setRoadOut(r.data)
    } catch (e) {
      setRoadOut({ error: e.response?.data?.detail || e.message })
    }
    setRoadLoading(false)
  }

  return (
    <div className="flex flex-col min-h-[calc(100vh-13rem)] animate-in fade-in slide-in-from-top-4 duration-500">
      <div className="flex flex-wrap gap-2 mb-4">
        {SUB_TABS.map((t) => {
          const Icon = t.icon
          const on = subTab === t.id
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setSubTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                on ? 'bg-sky-500 text-white shadow-lg shadow-sky-200/40' : 'bg-white/80 text-slate-600 border border-slate-200 hover:border-sky-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          )
        })}
      </div>

      <div className="rounded-2xl border border-slate-200/80 bg-white/90 backdrop-blur-sm shadow-sm p-5 mb-4">
        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Source document (optional)</label>
        <p className="text-xs text-slate-500 mb-2">Match the folder name under stage3/stage4 in Processed Files. Leave as &quot;All&quot; to use all processed documents.</p>
        <select
          className="w-full max-w-xl px-4 py-3 rounded-xl border border-slate-200 bg-white text-slate-800"
          value={documentId}
          onChange={(e) => setDocumentId(e.target.value)}
        >
          {documentChoices.map((o) => (
            <option key={o.id || '__all__'} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div className="flex-1 flex flex-col min-h-0 rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
        {subTab === 'summary' && (
          <div className="flex-1 flex flex-col min-h-0 p-6 lg:p-8 overflow-y-auto">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg">
                <BookOpen className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Lecture summary</h2>
                <p className="text-sm text-slate-500">Uses processed markdown (stage 3), scoped by the document above when set.</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-4xl">
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-2">Focus (optional)</label>
                <input
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-amber-400/40 outline-none"
                  placeholder="e.g. key definitions from week 4"
                  value={summaryQuery}
                  onChange={(e) => setSummaryQuery(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-2">Depth</label>
                <select className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-white" value={summaryDepth} onChange={(e) => setSummaryDepth(e.target.value)}>
                  <option value="brief">brief</option>
                  <option value="detailed">detailed</option>
                  <option value="comprehensive">comprehensive</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-2">Tone</label>
                <select className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-white" value={summaryTone} onChange={(e) => setSummaryTone(e.target.value)}>
                  <option value="neutral">neutral</option>
                  <option value="formal">formal</option>
                  <option value="friendly">friendly</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-2">Target length</label>
                <select className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-white" value={summaryLength} onChange={(e) => setSummaryLength(e.target.value)}>
                  <option value="short">short</option>
                  <option value="medium">medium</option>
                  <option value="long">long</option>
                </select>
              </div>
            </div>
            <button
              type="button"
              onClick={runSummary}
              disabled={summaryLoading}
              className="mt-6 max-w-md py-3.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-white font-semibold shadow-lg shadow-amber-200/50 hover:opacity-95 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {summaryLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
              Generate summary
            </button>
            {summaryOut && (
              <div className="mt-8 flex-1 min-h-[200px] p-6 rounded-2xl bg-slate-50 border border-slate-100 overflow-y-auto max-h-[min(70vh,800px)]">
                {summaryOut.error ? (
                  <p className="text-red-600 text-sm">{summaryOut.error}</p>
                ) : (
                  <div className="prose prose-slate prose-sm max-w-none whitespace-pre-wrap">{summaryOut.summary}</div>
                )}
              </div>
            )}
          </div>
        )}

        {subTab === 'mcq' && (
          <div className="flex-1 flex flex-col min-h-0 p-6 lg:p-8 overflow-y-auto">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg">
                <HelpCircle className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Practice MCQs</h2>
                <p className="text-sm text-slate-500">Questions from processed markdown (document-scoped when selected).</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-4xl">
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-slate-600 mb-2">Topic / focus</label>
                <input
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-violet-400/40 outline-none"
                  placeholder="e.g. gradient descent and learning rate"
                  value={mcqTopic}
                  onChange={(e) => setMcqTopic(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-2">Number of questions</label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  className="w-full px-4 py-3 rounded-xl border border-slate-200"
                  value={mcqNum}
                  onChange={(e) => setMcqNum(Number(e.target.value) || 1)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-2">Difficulty</label>
                <select className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-white" value={mcqDifficulty} onChange={(e) => setMcqDifficulty(e.target.value)}>
                  <option value="basic">basic</option>
                  <option value="intermediate">intermediate</option>
                  <option value="advanced">advanced</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-2">Question style</label>
                <select className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-white" value={mcqStyle} onChange={(e) => setMcqStyle(e.target.value)}>
                  <option value="exam">exam</option>
                  <option value="conceptual">conceptual</option>
                  <option value="mixed">mixed</option>
                </select>
              </div>
              <div className="flex items-center gap-3 pt-8">
                <input id="mcq-explain" type="checkbox" checked={mcqExplain} onChange={(e) => setMcqExplain(e.target.checked)} className="rounded border-slate-300" />
                <label htmlFor="mcq-explain" className="text-sm text-slate-700">
                  Include explanations
                </label>
              </div>
            </div>
            <button
              type="button"
              onClick={runMcq}
              disabled={mcqLoading || !mcqTopic.trim()}
              className="mt-6 max-w-md py-3.5 rounded-xl bg-gradient-to-r from-violet-500 to-purple-600 text-white font-semibold shadow-lg shadow-violet-200/50 hover:opacity-95 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {mcqLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
              Generate questions
            </button>
            {mcqOut && (
              <div className="mt-8 flex-1 min-h-[200px] overflow-y-auto max-h-[min(70vh,800px)] text-sm">
                {mcqOut.error ? (
                  <p className="text-red-600">{mcqOut.error}</p>
                ) : mcqOut.raw ? (
                  <div className="rounded-lg border border-amber-200 bg-amber-50/80 p-4">
                    <p className="text-xs font-medium text-amber-900 mb-2">Could not parse JSON; raw model output:</p>
                    <pre className="text-xs font-mono text-slate-800 whitespace-pre-wrap break-words max-h-[40vh] overflow-y-auto">{mcqOut.raw}</pre>
                  </div>
                ) : (
                  <McqExamView key={mcqRenderKey} questions={mcqOut.questions} hasExplanations={mcqExplain} />
                )}
              </div>
            )}
          </div>
        )}

        {subTab === 'roadmap' && (
          <div className="flex-1 flex flex-col min-h-0 p-6 lg:p-8 overflow-y-auto">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg">
                <Map className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Learning roadmap</h2>
                <p className="text-sm text-slate-500">Goals-driven plan from your processed materials.</p>
              </div>
            </div>
            <div className="max-w-3xl space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-2">Student profile (optional)</label>
                <textarea
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 min-h-[80px]"
                  placeholder="e.g. CS junior, comfortable with Python"
                  value={roadProfile}
                  onChange={(e) => setRoadProfile(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-2">Goals</label>
                <textarea
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 min-h-[100px]"
                  placeholder="e.g. Master transformers and fine-tuning for my thesis"
                  value={roadGoals}
                  onChange={(e) => setRoadGoals(e.target.value)}
                />
              </div>
            </div>
            <button
              type="button"
              onClick={runRoadmap}
              disabled={roadLoading || !roadGoals.trim()}
              className="mt-6 max-w-md py-3.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-semibold shadow-lg disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {roadLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
              Generate roadmap
            </button>
            {roadOut && (
              <div className="mt-8 flex-1 min-h-[200px] p-6 rounded-2xl bg-slate-50 border border-slate-100 overflow-y-auto max-h-[min(70vh,800px)] prose prose-slate prose-sm max-w-none whitespace-pre-wrap">
                {roadOut.error ? <p className="text-red-600 text-sm">{roadOut.error}</p> : roadOut.roadmap}
              </div>
            )}
          </div>
        )}

        {subTab === 'analytics' && (
          <div className="flex-1 flex flex-col min-h-0 p-6 lg:p-8 overflow-y-auto">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-slate-700 flex items-center justify-center shadow-lg">
                <BarChart2 className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-slate-800">Analytics</h2>
                <p className="text-sm text-slate-500">Reserved for future quiz/session metrics (FR-020).</p>
              </div>
            </div>
            <div className="p-6 rounded-2xl bg-slate-50 border border-slate-100 text-slate-700 text-sm max-w-2xl">
              {analyticsOut?.error ? (
                <p className="text-red-600">{analyticsOut.error}</p>
              ) : (
                <pre className="whitespace-pre-wrap font-mono text-xs">{JSON.stringify(analyticsOut ?? { loading: true }, null, 2)}</pre>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
