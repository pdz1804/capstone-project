import React, { useState, useEffect, useMemo } from 'react';
import {
  Timer,
  CheckCircle2,
  XCircle,
  ArrowRight,
  RotateCcw,
  Settings,
  BrainCircuit,
  Award,
  ChevronRight,
  Clock,
  ListOrdered,
  FileText
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '../lib/utils';
import { FileItem } from '../App';
import { postMcq } from '../api/ragApi';

interface Question {
  id: number;
  text: string;
  options: string[];
  correctAnswer: number;
}

function normalizeMcqFromApi(raw: unknown[]): Question[] {
  const out: Question[] = [];
  raw.forEach((item, i) => {
    const q = item as {
      question?: string;
      options?: string[];
      correct_index?: number;
    };
    const opts = Array.isArray(q.options) ? q.options.filter(Boolean) : [];
    if (opts.length < 2) return;
    const ci =
      typeof q.correct_index === 'number' && q.correct_index >= 0 && q.correct_index < opts.length
        ? q.correct_index
        : 0;
    out.push({
      id: i + 1,
      text: q.question || `Question ${i + 1}`,
      options: opts,
      correctAnswer: ci,
    });
  });
  return out;
}

type QuizState = 'config' | 'playing' | 'results';

interface QuizViewProps {
  files: FileItem[];
  standalone?: boolean;
  onComplete?: (score: number, total: number, fileId: number | null) => void;
  initialFileId?: number | null;
}

export default function QuizView({ files, standalone = false, onComplete, initialFileId }: QuizViewProps) {
  const quizScopes = useMemo(
    () => files.filter((f) => !!f.documentFolder && (f.status === 'processed' || f.status === 'indexed')),
    [files]
  );

  const [state, setState] = useState<QuizState>('config');
  const [config, setConfig] = useState({
    numQuestions: 5,
    duration: 10, // minutes
    topic: 'Key concepts from the uploaded materials',
    selectedFileId: (initialFileId !== null && initialFileId !== undefined) ? initialFileId : null
  });
  const [questions, setQuestions] = useState<Question[]>([]);
  const [quizLoading, setQuizLoading] = useState(false);
  const [quizLoadError, setQuizLoadError] = useState<string | null>(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [isAnswered, setIsAnswered] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const [score, setScore] = useState(0);

  useEffect(() => {
    if (config.selectedFileId === null) return;
    if (!quizScopes.some((f) => f.id === config.selectedFileId)) {
      setConfig((prev) => ({ ...prev, selectedFileId: null }));
    }
  }, [quizScopes, config.selectedFileId]);

  // Timer logic
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (state === 'playing' && timeLeft > 0) {
      timer = setInterval(() => {
        setTimeLeft((prev) => {
          if (prev <= 1) {
            calculateScore();
            setState('results');
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [state, timeLeft]);

  const startQuiz = async () => {
    if (quizLoading) return;
    const topic = config.topic.trim();
    if (!topic) {
      setQuizLoadError('Enter a quiz topic first.');
      return;
    }
    setQuizLoading(true);
    setQuizLoadError(null);
    try {
      const scopeFile = config.selectedFileId ? quizScopes.find((f) => f.id === config.selectedFileId) : undefined;
      const documentId = scopeFile?.documentFolder ?? null;
      const res = await postMcq({
        topic,
        num_questions: config.numQuestions,
        difficulty: 'intermediate',
        document_id: documentId,
        question_style: 'exam',
        include_explanations: true,
      });
      if (res.error) {
        setQuizLoadError(res.error);
        return;
      }
      const normalized = normalizeMcqFromApi((res.questions || []) as unknown[]);
      if (normalized.length === 0) {
        setQuizLoadError(
          'No quiz questions were generated from processed markdown. Run Process first, then try again.'
        );
        return;
      }
      setQuestions(normalized);
      setCurrentQuestionIndex(0);
      setAnswers({});
      setIsAnswered(false);
      setTimeLeft(config.duration * 60);
      setState('playing');
    } catch (e) {
      setQuizLoadError(e instanceof Error ? e.message : 'Quiz generation failed.');
    } finally {
      setQuizLoading(false);
    }
  };

  const handleAnswer = (optionIndex: number) => {
    if (isAnswered) return;
    setAnswers({ ...answers, [currentQuestionIndex]: optionIndex });
    setIsAnswered(true);
  };

  const nextQuestion = () => {
    setIsAnswered(false);
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    } else {
      calculateScore();
      setState('results');
    }
  };

  const calculateScore = () => {
    let correct = 0;
    const total = questions.length || config.numQuestions;
    questions.forEach((q, idx) => {
      if (answers[idx] === q.correctAnswer) correct++;
    });
    setScore(correct);
    if (onComplete) {
      onComplete(correct, total, config.selectedFileId);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className={cn("w-full min-h-[600px] flex flex-col", !standalone && "py-4")}>
      <AnimatePresence mode="wait">
        {state === 'config' && (
          <motion.div
            key="config"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="bg-white rounded-[2.5rem] border border-slate-200 p-8 md:p-12 shadow-xl shadow-slate-200/50 flex-1 flex flex-col justify-center"
          >
            <div className="text-center mb-10">
              <div className="w-16 h-16 bg-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-indigo-100">
                <BrainCircuit className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-2xl font-black text-slate-900 tracking-tight">Quiz Configuration</h2>
              <p className="text-slate-500 mt-2 font-medium text-sm">Customize your practice session</p>
            </div>

            <div className="space-y-6 max-w-md mx-auto w-full">
              {quizLoadError && (
                <div className="rounded-xl border border-red-200 bg-red-50 text-red-800 text-xs px-3 py-2">
                  {quizLoadError}
                </div>
              )}
              <div className="space-y-3">
                <label className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-widest">
                  Quiz topic
                </label>
                <input
                  type="text"
                  value={config.topic}
                  onChange={(e) => setConfig({ ...config, topic: e.target.value })}
                  className="w-full p-4 rounded-xl border-2 border-slate-100 bg-slate-50 font-medium text-slate-700 focus:border-indigo-500 outline-none"
                  placeholder="What should questions focus on?"
                />
                <p className="text-[10px] text-slate-400">
                  Uses <code className="bg-slate-100 px-1 rounded">POST /api/insights/mcq</code> over processed markdown.
                </p>
              </div>
              {/* File Selection */}
              <div className="space-y-3">
                <label className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-widest">
                  <FileText className="w-3 h-3" />
                  Scope to document (optional)
                </label>
                <select
                  value={config.selectedFileId ?? ''}
                  onChange={(e) => {
                    const v = e.target.value;
                    setConfig({
                      ...config,
                      selectedFileId: v === '' ? null : Number(v),
                    });
                  }}
                  className="w-full p-4 rounded-xl border-2 border-slate-100 bg-slate-50 font-bold text-slate-700 focus:border-indigo-500 focus:ring-0 transition-all outline-none"
                >
                  <option value="">All processed materials</option>
                  {quizScopes.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name}
                    </option>
                  ))}
                </select>
                {quizScopes.length === 0 && (
                  <p className="text-[10px] text-amber-600">
                    No processed/indexed documents available yet. Run Process (and Index) first.
                  </p>
                )}
              </div>

              <div className="space-y-3">
                <label className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-widest">
                  <ListOrdered className="w-3 h-3" />
                  Number of Questions
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {[3, 5, 10].map((n) => (
                    <button
                      key={n}
                      onClick={() => setConfig({ ...config, numQuestions: n })}
                      className={cn(
                        "py-3 rounded-xl font-bold transition-all border-2 text-sm",
                        config.numQuestions === n
                          ? "bg-indigo-600 border-indigo-600 text-white shadow-lg shadow-indigo-100"
                          : "bg-white border-slate-100 text-slate-600 hover:border-indigo-200"
                      )}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <label className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-widest">
                  <Clock className="w-3 h-3" />
                  Duration (Minutes)
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {[5, 10, 20].map((m) => (
                    <button
                      key={m}
                      onClick={() => setConfig({ ...config, duration: m })}
                      className={cn(
                        "py-3 rounded-xl font-bold transition-all border-2 text-sm",
                        config.duration === m
                          ? "bg-indigo-600 border-indigo-600 text-white shadow-lg shadow-indigo-100"
                          : "bg-white border-slate-100 text-slate-600 hover:border-indigo-200"
                      )}
                    >
                      {m}m
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="button"
                onClick={() => void startQuiz()}
                disabled={quizLoading || !config.topic.trim()}
                className="w-full py-4 bg-slate-900 text-white rounded-xl font-black uppercase tracking-widest hover:bg-slate-800 disabled:opacity-50 transition-all shadow-xl shadow-slate-200 flex items-center justify-center gap-3 group mt-2"
              >
                {quizLoading ? 'Loading questions…' : 'Start Quiz'}
                <ChevronRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </button>
            </div>
          </motion.div>
        )}

        {state === 'playing' && (
          <motion.div
            key="playing"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="flex-1 flex flex-col"
          >
            {/* Quiz Header */}
            <div className="mb-6 bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
              <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-4">
                <div className="md:flex-1 min-w-0">
                  <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Progress</p>
                  <div className="flex items-center justify-between gap-3 mb-2">
                    <p className="text-sm font-bold text-slate-700">
                      Question <span className="text-indigo-600">{currentQuestionIndex + 1}</span> of {questions.length}
                    </p>
                    <p className="text-xs font-semibold text-slate-500">
                      {Math.round(((currentQuestionIndex + 1) / Math.max(questions.length, 1)) * 100)}%
                    </p>
                  </div>
                  <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-600 transition-all duration-500"
                      style={{ width: `${((currentQuestionIndex + 1) / Math.max(questions.length, 1)) * 100}%` }}
                    />
                  </div>
                </div>
                <div className={cn(
                  "md:w-[220px] rounded-xl border px-4 py-3 flex items-center gap-3",
                  timeLeft < 60 ? "border-red-200 bg-red-50" : "border-indigo-100 bg-indigo-50/60"
                )}>
                  <Timer className={cn("w-5 h-5 shrink-0", timeLeft < 60 ? "text-red-500 animate-pulse" : "text-indigo-600")} />
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Time left</p>
                    <p className={cn("text-lg font-black leading-none mt-1", timeLeft < 60 ? "text-red-600" : "text-slate-900")}>
                      {formatTime(timeLeft)}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Question Card */}
            <div className="bg-white rounded-[2.5rem] border border-slate-200 p-8 md:p-10 lg:p-12 shadow-xl shadow-slate-200/50 flex-1 flex flex-col">
              <h3 className="text-xl font-bold text-slate-900 mb-8 leading-tight">
                {questions[currentQuestionIndex].text}
              </h3>

              <div className="space-y-3 flex-1">
                {questions[currentQuestionIndex].options.map((option, idx) => {
                  const isCorrect = idx === questions[currentQuestionIndex].correctAnswer;
                  const isSelected = answers[currentQuestionIndex] === idx;

                  let buttonClass = "bg-white border-slate-100 text-slate-600 hover:border-indigo-200 hover:bg-slate-50";
                  if (isAnswered) {
                    if (isCorrect) {
                      buttonClass = "bg-emerald-50 border-emerald-500 text-emerald-700";
                    } else if (isSelected) {
                      buttonClass = "bg-red-50 border-red-500 text-red-700";
                    } else {
                      buttonClass = "bg-white border-slate-100 text-slate-400 opacity-50";
                    }
                  } else if (isSelected) {
                    buttonClass = "bg-indigo-50 border-indigo-600 text-indigo-700";
                  }

                  return (
                    <button
                      key={idx}
                      onClick={() => handleAnswer(idx)}
                      disabled={isAnswered}
                      className={cn(
                        "w-full p-5 rounded-xl text-left font-bold transition-all border-2 flex items-center justify-between group text-sm",
                        buttonClass
                      )}
                    >
                      <span>{option}</span>
                      <div className={cn(
                        "w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all",
                        isAnswered
                          ? (isCorrect ? "border-emerald-500 bg-emerald-500 text-white" : (isSelected ? "border-red-500 bg-red-500 text-white" : "border-slate-200"))
                          : (isSelected ? "border-indigo-600 bg-indigo-600 text-white" : "border-slate-200 group-hover:border-indigo-300")
                      )}>
                        {isAnswered && isCorrect && <CheckCircle2 className="w-3 h-3" />}
                        {isAnswered && isSelected && !isCorrect && <XCircle className="w-3 h-3" />}
                        {!isAnswered && isSelected && <CheckCircle2 className="w-3 h-3" />}
                      </div>
                    </button>
                  );
                })}
              </div>

              <button
                onClick={nextQuestion}
                disabled={answers[currentQuestionIndex] === undefined}
                className="mt-8 w-full py-4 bg-slate-900 text-white rounded-xl font-black uppercase tracking-widest hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-xl shadow-slate-200 flex items-center justify-center gap-3 group"
              >
                {currentQuestionIndex === questions.length - 1 ? 'Finish Quiz' : 'Next Question'}
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </button>
            </div>
          </motion.div>
        )}

        {state === 'results' && (
          <motion.div
            key="results"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white rounded-[2.5rem] border border-slate-200 p-8 md:p-12 shadow-xl shadow-slate-200/50 flex-1 flex flex-col items-center justify-center text-center"
          >
            <div className="w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center mb-6">
              <Award className="w-10 h-10 text-emerald-600" />
            </div>
            <h2 className="text-3xl font-black text-slate-900 tracking-tight mb-2">Quiz Completed!</h2>
            <p className="text-slate-500 font-medium mb-10 text-sm">Great job! Here's how you performed:</p>

            <div className="grid grid-cols-2 gap-4 w-full max-w-sm mb-10">
              <div className="p-6 bg-slate-50 rounded-2xl border border-slate-100">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-1">Score</span>
                <p className="text-2xl font-black text-indigo-600">{score} / {questions.length || config.numQuestions}</p>
              </div>
              <div className="p-6 bg-slate-50 rounded-2xl border border-slate-100">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-1">Accuracy</span>
                <p className="text-2xl font-black text-emerald-600">
                  {questions.length ? Math.round((score / questions.length) * 100) : 0}%
                </p>
              </div>
            </div>

            <div className="flex gap-3 w-full max-w-sm">
              <button
                onClick={() => setState('config')}
                className="flex-1 py-4 bg-white border-2 border-slate-200 text-slate-700 rounded-xl font-black uppercase tracking-widest hover:bg-slate-50 transition-all flex items-center justify-center gap-2 text-xs"
              >
                <RotateCcw className="w-4 h-4" />
                Retry
              </button>
              {standalone && (
                <button
                  onClick={() => window.close()}
                  className="flex-1 py-4 bg-slate-900 text-white rounded-xl font-black uppercase tracking-widest hover:bg-slate-800 transition-all shadow-xl shadow-slate-200 text-xs"
                >
                  Close Tab
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
