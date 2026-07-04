import { useState, useMemo } from 'react';
import {
  TrendingUp,
  Target,
  Award,
  BookOpen,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  Compass,
  BrainCircuit,
  BarChart3,
  Loader2,
  Sparkles
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend
} from 'recharts';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import type { Components } from 'react-markdown';

import { cn } from '../lib/utils';
import { ViewType, FileItem, QuizResult } from '../App';
import QuizView from './QuizView';
import { postRoadmap } from '../api/ragApi';
import learningRobot from '../../robot_1.png';

interface LearningPathViewProps {
  files: FileItem[];
  quizResults: QuizResult[];
  onQuizComplete: (score: number, total: number, fileId: number | null) => void;
}

const ROADMAP_MARKDOWN_COMPONENTS: Components = {
  h1: ({ children }) => <h1 className="text-2xl font-bold text-slate-900 mt-2 mb-3">{children}</h1>,
  h2: ({ children }) => <h2 className="text-xl font-semibold text-slate-900 mt-4 mb-2">{children}</h2>,
  h3: ({ children }) => <h3 className="text-lg font-semibold text-slate-900 mt-4 mb-2">{children}</h3>,
  p: ({ children }) => <p className="text-sm leading-7 text-slate-700 my-2">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-5 my-3 space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-5 my-3 space-y-1">{children}</ol>,
  li: ({ children }) => <li className="text-sm leading-7 text-slate-700">{children}</li>,
  table: ({ children }) => <table className="w-full border-collapse text-sm my-4">{children}</table>,
  th: ({ children }) => <th className="border border-slate-300 bg-slate-50 px-2 py-1 text-left">{children}</th>,
  td: ({ children }) => <td className="border border-slate-300 px-2 py-1 align-top">{children}</td>,
  a: ({ href, children }) => {
    const link = String(href || '');
    return (
      <a href={link} target="_blank" rel="noreferrer" className="text-blue-700 hover:text-blue-900 underline underline-offset-2">
        {children}
      </a>
    );
  },
};

export default function LearningPathView({ files, quizResults, onQuizComplete }: LearningPathViewProps) {
  const [activeTab, setActiveTab] = useState<'roadmap' | 'priority' | 'analytics' | 'quiz'>('roadmap');
  const [selectedFileIdForQuiz, setSelectedFileIdForQuiz] = useState<number | null>(null);
  const [filterFileId, setFilterFileId] = useState<string>('all');
  const [roadmapGoals, setRoadmapGoals] = useState('');
  const [studentProfile, setStudentProfile] = useState('');
  const [roadmapDocScope, setRoadmapDocScope] = useState<string>('all');
  const [aiRoadmapText, setAiRoadmapText] = useState<string | null>(null);
  const [roadmapLoading, setRoadmapLoading] = useState(false);
  const [roadmapError, setRoadmapError] = useState<string | null>(null);

  const filteredResults = filterFileId === 'all'
    ? quizResults
    : quizResults.filter(r => r.fileId?.toString() === filterFileId);

  const averageAccuracy = filteredResults.length > 0
    ? Math.round(filteredResults.reduce((acc, curr) => acc + (curr.score / curr.total), 0) / filteredResults.length * 100)
    : null;

  const performanceData = [...filteredResults].reverse().map((result, index, arr) => {
    const cumulativeScore = arr.slice(0, index + 1).reduce((acc, curr) => acc + (curr.score / curr.total), 0);
    const averageAccuracy = Math.round((cumulativeScore / (index + 1)) * 100);
    return {
      name: `${index + 1}`,
      score: averageAccuracy
    };
  });

  const skillsData = useMemo(() => {
    const fromFiles = files.slice(0, 8).map((f) => {
      const fileQuizzes = quizResults.filter((r) => r.fileId === f.id);
      const A =
        fileQuizzes.length > 0
          ? Math.round(
            (fileQuizzes.reduce((acc, curr) => acc + curr.score / Math.max(curr.total, 1), 0) / fileQuizzes.length) *
            100
          )
          : 0;
      const label = f.name.replace(/\.[^/.]+$/, '').slice(0, 22) || 'Source';
      return { subject: label, A, fullMark: 100 };
    });
    if (fromFiles.length > 0) return fromFiles;
    if (averageAccuracy !== null) {
      return [{ subject: 'Quiz average', A: averageAccuracy, fullMark: 100 }];
    }
    return [{ subject: 'Complete a quiz', A: 0, fullMark: 100 }];
  }, [files, quizResults, averageAccuracy]);

  const roadmap = files.length > 0 ? files.map((file, index) => {
    const fileQuizzes = quizResults.filter(r => r.fileId === file.id);
    const fileAccuracy = fileQuizzes.length > 0
      ? Math.round(fileQuizzes.reduce((acc, curr) => acc + (curr.score / curr.total), 0) / fileQuizzes.length * 100)
      : null;

    return {
      id: file.id,
      title: file.name,
      status:
        file.status === 'indexed'
          ? 'completed'
          : file.status === 'processing' || file.status === 'uploaded' || file.status === 'processed'
            ? 'in-progress'
            : 'locked',
      date: file.date,
      score: file.status === 'indexed' ? (fileAccuracy !== null ? `${fileAccuracy}%` : 'Not Taken') : '--',
      accuracy: fileAccuracy
    };
  }) : [
    { id: 1, title: 'No files uploaded yet', status: 'locked', date: 'N/A', score: '--', accuracy: null }
  ];

  const priorityRoadmap = [...roadmap].sort((a, b) => {
    const accA = a.accuracy === null ? -1 : a.accuracy;
    const accB = b.accuracy === null ? -1 : b.accuracy;
    return accA - accB;
  });

  const displayRoadmap = activeTab === 'priority' ? priorityRoadmap : roadmap;

  const handleGenerateAiRoadmap = async () => {
    const goals = roadmapGoals.trim();
    if (!goals) {
      setRoadmapError('Enter your learning goals first.');
      return;
    }
    setRoadmapLoading(true);
    setRoadmapError(null);
    setAiRoadmapText(null);
    try {
      let documentId: string | null = null;
      if (roadmapDocScope !== 'all') {
        const f = files.find((x) => String(x.id) === roadmapDocScope);
        documentId = f?.documentFolder ?? null;
      }
      const res = await postRoadmap({
        goals,
        student_profile: studentProfile.trim(),
        document_id: documentId,
      });
      if (res.error) {
        setRoadmapError(res.error);
        return;
      }
      const text = (res.roadmap || '').trim();
      setAiRoadmapText(text || 'Empty response from learning-roadmap API.');
    } catch (e) {
      setRoadmapError(e instanceof Error ? e.message : 'Roadmap request failed');
    } finally {
      setRoadmapLoading(false);
    }
  };

  return (
    <div className="w-full max-w-[1720px] mx-auto space-y-7 px-1 sm:px-2">
      {/* Header & Tabs */}
      <div className="relative overflow-hidden rounded-3xl border border-sky-100 bg-white p-5 sm:p-6 shadow-[0_18px_34px_-28px_rgba(14,165,233,0.6)]">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_100%_10%,rgba(56,189,248,0.14),transparent_40%)]" />
        <div className="relative grid grid-cols-1 xl:grid-cols-[1fr_auto_auto] xl:items-center gap-5 xl:gap-4">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Personalized Learning</h2>
            <p className="text-slate-500 mt-1">Track your progress and follow your customized roadmap.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2 bg-sky-50/70 border border-sky-100 p-1 rounded-xl w-full xl:w-auto xl:max-w-[640px]">
            <button
              onClick={() => {
                setSelectedFileIdForQuiz(null);
                setActiveTab('roadmap');
              }}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${activeTab === 'roadmap' ? 'bg-white text-sky-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
            >
              <Target className="w-4 h-4 inline-block mr-2" />
              Roadmap
            </button>
            <button
              onClick={() => setActiveTab('priority')}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${activeTab === 'priority' ? 'bg-white text-sky-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
            >
              <Compass className="w-4 h-4 inline-block mr-2" />
              Learning Journey
            </button>
            <button
              onClick={() => {
                setSelectedFileIdForQuiz(null);
                setActiveTab('quiz');
              }}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${activeTab === 'quiz' ? 'bg-white text-sky-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
            >
              <BrainCircuit className="w-4 h-4 inline-block mr-2" />
              Quiz
            </button>
            <button
              onClick={() => setActiveTab('analytics')}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${activeTab === 'analytics' ? 'bg-white text-sky-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
            >
              <BarChart3 className="w-4 h-4 inline-block mr-2" />
              Analytics
            </button>
          </div>
          <div className="hidden xl:flex items-center gap-3">
            <div className="rounded-2xl border border-sky-100 bg-gradient-to-br from-sky-50 to-white px-4 py-3 min-w-[190px] shadow-sm">
              <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">AI Learning Companion</p>
              <div className="flex items-center justify-between gap-3 mt-2">
                <p className="text-xs text-slate-500 leading-5 max-w-[86px]">Adaptive roadmap and quiz guidance</p>
                <img src={learningRobot} alt="AI learning companion" className="h-20 w-auto object-contain animate-float-delayed" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Content Area */}
      {(activeTab === 'roadmap' || activeTab === 'priority') && (
        <div className="space-y-8">
          <div className="bg-white rounded-2xl border border-sky-100 shadow-[0_16px_32px_-26px_rgba(14,165,233,0.55)] p-8 space-y-6">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-sky-600" />
              <h3 className="text-lg font-semibold text-slate-900">AI learning roadmap</h3>
            </div>
            <p className="text-sm text-slate-500">
              Uses <code className="bg-slate-100 px-1 rounded text-xs">POST /api/insights/learning-roadmap</code> over your
              processed materials (same as the AI service backend).
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Goals (required)</label>
                <textarea
                  value={roadmapGoals}
                  onChange={(e) => setRoadmapGoals(e.target.value)}
                  placeholder="e.g. Pass the ML midterm and understand backpropagation"
                  rows={3}
                  className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 focus:ring-2 focus:ring-sky-500/30 outline-none"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Student profile (optional)</label>
                <textarea
                  value={studentProfile}
                  onChange={(e) => setStudentProfile(e.target.value)}
                  placeholder="Year level, prior courses, time per week…"
                  rows={3}
                  className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 focus:ring-2 focus:ring-sky-500/30 outline-none"
                />
              </div>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-end gap-4">
              <div className="flex-1">
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Scope</label>
                <select
                  value={roadmapDocScope}
                  onChange={(e) => setRoadmapDocScope(e.target.value)}
                  aria-label="Roadmap document scope"
                  className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm font-medium text-slate-700 bg-white"
                >
                  <option value="all">All processed documents</option>
                  {files.map((f) => (
                    <option key={f.id} value={String(f.id)}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                onClick={() => void handleGenerateAiRoadmap()}
                disabled={roadmapLoading}
                className="px-6 py-3 rounded-xl bg-sky-600 text-white text-sm font-bold hover:bg-sky-700 disabled:opacity-60 flex items-center justify-center gap-2 shrink-0"
              >
                {roadmapLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                Generate
              </button>
            </div>
            {roadmapError && <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl p-4">{roadmapError}</p>}
            {aiRoadmapText && (
              <article className="border border-slate-100 rounded-xl p-6 bg-slate-50/80 max-h-96 overflow-y-auto">
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={ROADMAP_MARKDOWN_COMPONENTS}>
                  {aiRoadmapText}
                </ReactMarkdown>
              </article>
            )}
          </div>

          <div className="bg-white rounded-2xl border border-sky-100 shadow-[0_16px_32px_-26px_rgba(14,165,233,0.55)] p-8">
            <h3 className="text-lg font-semibold text-slate-900 mb-6 flex items-center gap-2">
              {activeTab === 'priority' ? <Compass className="w-5 h-5 text-sky-600" /> : <TrendingUp className="w-5 h-5 text-sky-600" />}
              {activeTab === 'priority' ? 'Learning Journey (Lowest Accuracy First)' : 'Roadmap'}
            </h3>
            <div className="relative border-l-2 border-slate-100 ml-4 space-y-8">
              {displayRoadmap.map((item, index) => (
                <div key={item.id} className="relative pl-8">
                  {/* Timeline Node */}
                  <div className={`absolute w-6 h-6 rounded-full -left-[13px] top-1 flex items-center justify-center border-2 ${item.status === 'completed' ? 'bg-emerald-500 border-emerald-500 text-white' :
                    item.status === 'in-progress' ? 'bg-white border-sky-500' :
                      'bg-slate-100 border-slate-300'
                    }`}>
                    {item.status === 'completed' && <CheckCircle2 className="w-3 h-3" />}
                    {item.status === 'in-progress' && <div className="w-2 h-2 bg-sky-500 rounded-full"></div>}
                  </div>

                  {/* Content */}
                  <div className={`bg-white rounded-xl border p-5 transition-all ${item.status === 'in-progress' ? 'border-sky-200 shadow-md ring-1 ring-sky-50' :
                    item.status === 'completed' ? 'border-slate-200 hover:border-slate-300' :
                      'border-slate-100 opacity-60'
                    }`}>
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <span className={`text-xs font-bold uppercase tracking-wider mb-1 block ${item.status === 'completed' ? 'text-emerald-600' :
                          item.status === 'in-progress' ? 'text-sky-600' :
                            'text-slate-400'
                          }`}>
                          File {index + 1}
                        </span>
                        <h4 className={`font-semibold text-lg ${item.status === 'locked' ? 'text-slate-500' : 'text-slate-900'}`}>
                          {item.title}
                        </h4>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-medium text-slate-500 block">{item.date}</span>
                        {item.status === 'completed' && (
                          <span className={cn(
                            "inline-flex items-center gap-1 text-sm font-bold mt-1",
                            item.score === 'Not Taken' ? 'text-slate-400' : 'text-emerald-600'
                          )}>
                            {item.score !== 'Not Taken' && <Award className="w-4 h-4" />} {item.score}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="mt-4 pt-4 border-t border-slate-100">
                      <div className="flex gap-3">
                        <button
                          onClick={() => {
                            setSelectedFileIdForQuiz(item.id);
                            setActiveTab('quiz');
                          }}
                          disabled={item.status === 'locked'}
                          className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${item.status === 'locked'
                            ? 'bg-slate-50 text-slate-400 cursor-not-allowed border border-slate-100'
                            : 'bg-white text-sky-600 border border-sky-200 hover:bg-sky-50 shadow-sm'
                            }`}
                        >
                          <BrainCircuit className="w-4 h-4" />
                          Take Practice Quiz
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'quiz' && (
        <QuizView
          files={files}
          onComplete={onQuizComplete}
          initialFileId={selectedFileIdForQuiz}
        />
      )}

      {activeTab === 'analytics' && (
        <div className="space-y-8">
          {/* Analytics Filter & Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-2xl p-6 border border-sky-100 shadow-[0_16px_32px_-26px_rgba(14,165,233,0.55)] col-span-1 md:col-span-2 flex flex-col justify-center">
              <h3 className="text-lg font-semibold text-slate-900">Performance Analytics</h3>
              <p className="text-sm text-slate-500">Track your progress across all knowledge sources</p>
            </div>
            <div className="bg-white rounded-2xl p-6 border border-sky-100 shadow-[0_16px_32px_-26px_rgba(14,165,233,0.55)]">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-1">Average Accuracy</span>
              <div className={cn(
                "text-2xl font-bold",
                averageAccuracy === null ? "text-slate-400" : "text-sky-600"
              )}>
                {averageAccuracy === null ? "Not Taken" : `${averageAccuracy}%`}
              </div>
            </div>
            <div className="bg-white rounded-2xl p-6 border border-sky-100 shadow-[0_16px_32px_-26px_rgba(14,165,233,0.55)]">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-1">Quizzes Taken</span>
              <div className="text-2xl font-bold text-slate-900">
                {filteredResults.length}
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 border border-sky-100 shadow-[0_16px_32px_-26px_rgba(14,165,233,0.55)] flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">Filter View</h3>
              <p className="text-sm text-slate-500">Select a specific file to filter the charts below</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Source:</span>
              <select
                value={filterFileId}
                onChange={(e) => setFilterFileId(e.target.value)}
                aria-label="Filter analytics by source file"
                className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm font-medium text-slate-700 outline-none focus:ring-2 focus:ring-sky-500/20"
              >
                <option value="all">All Files</option>
                {files.map(f => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="bg-white rounded-2xl border border-sky-100 shadow-[0_16px_32px_-26px_rgba(14,165,233,0.55)] p-6">
              <h3 className="text-lg font-semibold text-slate-900 mb-6">Performance Trend</h3>
              <div className="h-80 w-full">
                {performanceData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={performanceData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                      <XAxis
                        dataKey="name"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: '#64748b', fontSize: 12 }}
                        dy={10}
                        label={{ value: 'Quiz Attempt', position: 'insideBottom', offset: -5, fill: '#64748b', fontSize: 11 }}
                      />
                      <YAxis
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: '#64748b', fontSize: 12 }}
                        dx={-10}
                        label={{ value: 'Avg Accuracy (%)', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: 11 }}
                      />
                      <Tooltip
                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                        cursor={{ stroke: '#cbd5e1', strokeWidth: 1, strokeDasharray: '3 3' }}
                        formatter={(value: number) => [`${value}%`, 'Average Accuracy']}
                        labelFormatter={(label) => `Attempt ${label}`}
                      />
                      <Line type="monotone" dataKey="score" stroke="#4f46e5" strokeWidth={3} dot={{ r: 4, fill: '#4f46e5', strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 6 }} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-slate-400">
                    <TrendingUp className="w-12 h-12 mb-2 opacity-20" />
                    <p>No quiz data available for this selection</p>
                  </div>
                )}
              </div>
            </div>

            <div className="bg-white rounded-2xl border border-sky-100 shadow-[0_16px_32px_-26px_rgba(14,165,233,0.55)] p-6">
              <h3 className="text-lg font-semibold text-slate-900 mb-6">Skill Matrix</h3>
              <div className="h-80 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart cx="50%" cy="50%" outerRadius="70%" data={skillsData}>
                    <PolarGrid stroke="#e2e8f0" />
                    <PolarAngleAxis dataKey="subject" tick={{ fill: '#475569', fontSize: 11, fontWeight: 500 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                    <Radar name="Student" dataKey="A" stroke="#4f46e5" fill="#4f46e5" fillOpacity={0.4} />
                    <Tooltip />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
