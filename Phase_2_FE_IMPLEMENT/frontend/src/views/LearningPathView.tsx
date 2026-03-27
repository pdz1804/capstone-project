import { useState } from 'react';
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
  BarChart3
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

import { cn } from '../lib/utils';
import { ViewType, FileItem, QuizResult } from '../App';
import QuizView from './QuizView';

interface LearningPathViewProps {
  files: FileItem[];
  quizResults: QuizResult[];
  onQuizComplete: (score: number, total: number, fileId: number | null) => void;
}

export default function LearningPathView({ files, quizResults, onQuizComplete }: LearningPathViewProps) {
  const [activeTab, setActiveTab] = useState<'roadmap' | 'priority' | 'analytics' | 'quiz'>('roadmap');
  const [selectedFileIdForQuiz, setSelectedFileIdForQuiz] = useState<number | null>(null);
  const [filterFileId, setFilterFileId] = useState<string>('all');

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

  const skillsData = [
    { subject: 'Neural Networks', A: 85, fullMark: 100 },
    { subject: 'Data Structures', A: 65, fullMark: 100 },
    { subject: 'Algorithms', A: 90, fullMark: 100 },
    { subject: 'Linear Algebra', A: 75, fullMark: 100 },
    { subject: 'Calculus', A: 60, fullMark: 100 },
    { subject: 'Quiz Accuracy', A: averageAccuracy || 0, fullMark: 100 },
  ];

  const roadmap = files.length > 0 ? files.map((file, index) => {
    const fileQuizzes = quizResults.filter(r => r.fileId === file.id);
    const fileAccuracy = fileQuizzes.length > 0
      ? Math.round(fileQuizzes.reduce((acc, curr) => acc + (curr.score / curr.total), 0) / fileQuizzes.length * 100)
      : null;

    return {
      id: file.id,
      title: file.name,
      status: file.status === 'indexed' ? 'completed' : (file.status === 'processing' ? 'in-progress' : 'locked'),
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

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Header & Tabs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Personalized Learning</h2>
          <p className="text-slate-500 mt-1">Track your progress and follow your customized roadmap.</p>
        </div>
        <div className="flex items-center gap-2 bg-slate-100 p-1 rounded-xl">
          <button
            onClick={() => {
              setSelectedFileIdForQuiz(null);
              setActiveTab('roadmap');
            }}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${activeTab === 'roadmap' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <Target className="w-4 h-4 inline-block mr-2" />
            Roadmap
          </button>
          <button
            onClick={() => setActiveTab('priority')}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${activeTab === 'priority' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <Compass className="w-4 h-4 inline-block mr-2" />
            Learning Journey
          </button>
          <button
            onClick={() => {
              setSelectedFileIdForQuiz(null);
              setActiveTab('quiz');
            }}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${activeTab === 'quiz' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <BrainCircuit className="w-4 h-4 inline-block mr-2" />
            Quiz
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${activeTab === 'analytics' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <BarChart3 className="w-4 h-4 inline-block mr-2" />
            Analytics
          </button>
        </div>
      </div>

      {/* Content Area */}
      {(activeTab === 'roadmap' || activeTab === 'priority') && (
        <div className="space-y-8">
          {/* Roadmap Timeline */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8">
            <h3 className="text-lg font-semibold text-slate-900 mb-6 flex items-center gap-2">
              {activeTab === 'priority' ? <Compass className="w-5 h-5 text-indigo-600" /> : <TrendingUp className="w-5 h-5 text-indigo-600" />}
              {activeTab === 'priority' ? 'Learning Journey (Lowest Accuracy First)' : 'Roadmap'}
            </h3>
            <div className="relative border-l-2 border-slate-100 ml-4 space-y-8">
              {displayRoadmap.map((item, index) => (
                <div key={item.id} className="relative pl-8">
                  {/* Timeline Node */}
                  <div className={`absolute w-6 h-6 rounded-full -left-[13px] top-1 flex items-center justify-center border-2 ${item.status === 'completed' ? 'bg-emerald-500 border-emerald-500 text-white' :
                    item.status === 'in-progress' ? 'bg-white border-indigo-500' :
                      'bg-slate-100 border-slate-300'
                    }`}>
                    {item.status === 'completed' && <CheckCircle2 className="w-3 h-3" />}
                    {item.status === 'in-progress' && <div className="w-2 h-2 bg-indigo-500 rounded-full"></div>}
                  </div>

                  {/* Content */}
                  <div className={`bg-white rounded-xl border p-5 transition-all ${item.status === 'in-progress' ? 'border-indigo-200 shadow-md ring-1 ring-indigo-50' :
                    item.status === 'completed' ? 'border-slate-200 hover:border-slate-300' :
                      'border-slate-100 opacity-60'
                    }`}>
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <span className={`text-xs font-bold uppercase tracking-wider mb-1 block ${item.status === 'completed' ? 'text-emerald-600' :
                          item.status === 'in-progress' ? 'text-indigo-600' :
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
                            : 'bg-white text-indigo-600 border border-indigo-200 hover:bg-indigo-50 shadow-sm'
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
            <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm col-span-1 md:col-span-2 flex flex-col justify-center">
              <h3 className="text-lg font-semibold text-slate-900">Performance Analytics</h3>
              <p className="text-sm text-slate-500">Track your progress across all knowledge sources</p>
            </div>
            <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-1">Average Accuracy</span>
              <div className={cn(
                "text-2xl font-bold",
                averageAccuracy === null ? "text-slate-400" : "text-indigo-600"
              )}>
                {averageAccuracy === null ? "Not Taken" : `${averageAccuracy}%`}
              </div>
            </div>
            <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-1">Quizzes Taken</span>
              <div className="text-2xl font-bold text-slate-900">
                {filteredResults.length}
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">Filter View</h3>
              <p className="text-sm text-slate-500">Select a specific file to filter the charts below</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Source:</span>
              <select
                value={filterFileId}
                onChange={(e) => setFilterFileId(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm font-medium text-slate-700 outline-none focus:ring-2 focus:ring-indigo-500/20"
              >
                <option value="all">All Files</option>
                {files.map(f => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
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

            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
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
