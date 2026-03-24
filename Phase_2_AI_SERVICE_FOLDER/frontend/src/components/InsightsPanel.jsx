import { useState } from 'react'
import axios from 'axios'
import { BookOpen, HelpCircle, Loader2, Sparkles } from 'lucide-react'

export default function InsightsPanel({ apiBase }) {
  const [summaryQuery, setSummaryQuery] = useState('')
  const [summaryDepth, setSummaryDepth] = useState('detailed')
  const [summaryOut, setSummaryOut] = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(false)

  const [mcqTopic, setMcqTopic] = useState('')
  const [mcqOut, setMcqOut] = useState(null)
  const [mcqLoading, setMcqLoading] = useState(false)

  const runSummary = async () => {
    setSummaryLoading(true)
    setSummaryOut(null)
    try {
      const r = await axios.post(`${apiBase}/insights/summary`, {
        focus_query: summaryQuery,
        depth: summaryDepth,
        top_k: 12,
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
        num_questions: 5,
        difficulty: 'intermediate',
      })
      setMcqOut(r.data)
    } catch (e) {
      setMcqOut({ error: e.response?.data?.detail || e.message })
    }
    setMcqLoading(false)
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-top-4 duration-500">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="glass-strong rounded-3xl card-shadow p-8 border border-slate-100/80">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg">
              <BookOpen className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-800">Lecture summary</h2>
              <p className="text-sm text-slate-500">FR-016 — uses retrieved chunks from your index</p>
            </div>
          </div>
          <label className="block text-sm font-medium text-slate-600 mb-2">Focus (optional)</label>
          <input
            className="w-full px-4 py-3 rounded-xl border border-slate-200 mb-4 focus:ring-2 focus:ring-amber-400/50 focus:border-amber-400 outline-none transition-all"
            placeholder="e.g. key definitions from week 4"
            value={summaryQuery}
            onChange={(e) => setSummaryQuery(e.target.value)}
          />
          <label className="block text-sm font-medium text-slate-600 mb-2">Depth</label>
          <select
            className="w-full px-4 py-3 rounded-xl border border-slate-200 mb-6 bg-white"
            value={summaryDepth}
            onChange={(e) => setSummaryDepth(e.target.value)}
          >
            <option value="brief">brief</option>
            <option value="detailed">detailed</option>
            <option value="comprehensive">comprehensive</option>
          </select>
          <button
            onClick={runSummary}
            disabled={summaryLoading}
            className="w-full py-3.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-white font-semibold shadow-lg shadow-amber-200/50 hover:opacity-95 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {summaryLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
            Generate summary
          </button>
          {summaryOut && (
            <div className="mt-6 p-5 rounded-2xl bg-slate-50 border border-slate-100 max-h-[420px] overflow-y-auto">
              {summaryOut.error ? (
                <p className="text-red-600 text-sm">{summaryOut.error}</p>
              ) : (
                <div className="prose prose-slate prose-sm max-w-none whitespace-pre-wrap">{summaryOut.summary}</div>
              )}
            </div>
          )}
        </div>

        <div className="glass-strong rounded-3xl card-shadow p-8 border border-slate-100/80">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg">
              <HelpCircle className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-800">Practice MCQs</h2>
              <p className="text-sm text-slate-500">FR-019 — JSON questions from indexed content</p>
            </div>
          </div>
          <label className="block text-sm font-medium text-slate-600 mb-2">Topic</label>
          <input
            className="w-full px-4 py-3 rounded-xl border border-slate-200 mb-6 focus:ring-2 focus:ring-violet-400/50 outline-none"
            placeholder="e.g. gradient descent and learning rate"
            value={mcqTopic}
            onChange={(e) => setMcqTopic(e.target.value)}
          />
          <button
            onClick={runMcq}
            disabled={mcqLoading || !mcqTopic.trim()}
            className="w-full py-3.5 rounded-xl bg-gradient-to-r from-violet-500 to-purple-600 text-white font-semibold shadow-lg shadow-violet-200/50 hover:opacity-95 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {mcqLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
            Generate questions
          </button>
          {mcqOut && (
            <div className="mt-6 p-5 rounded-2xl bg-slate-50 border border-slate-100 max-h-[420px] overflow-y-auto text-sm">
              {mcqOut.error ? (
                <p className="text-red-600">{mcqOut.error}</p>
              ) : (
                <pre className="text-xs font-mono text-slate-700 whitespace-pre-wrap break-words">
                  {JSON.stringify(mcqOut.questions ?? mcqOut, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
