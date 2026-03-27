import React, { useState, useEffect } from 'react';
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

interface Question {
  id: number;
  text: string;
  options: string[];
  correctAnswer: number;
}

const MOCK_QUESTIONS: Question[] = [
  {
    id: 1,
    text: "What is the primary purpose of a Loss Function in Machine Learning?",
    options: [
      "To measure how well the model is performing",
      "To increase the speed of training",
      "To store the weights of the model",
      "To visualize the data distribution"
    ],
    correctAnswer: 0
  },
  {
    id: 2,
    text: "Which activation function is commonly used in the hidden layers of Deep Neural Networks?",
    options: ["Sigmoid", "ReLU", "Softmax", "Linear"],
    correctAnswer: 1
  },
  {
    id: 3,
    text: "What does 'RAG' stand for in the context of AI?",
    options: [
      "Random Access Generation",
      "Retrieval-Augmented Generation",
      "Rapid AI Growth",
      "Recurrent Analysis Group"
    ],
    correctAnswer: 1
  },
  {
    id: 4,
    text: "In a Convolutional Neural Network (CNN), what is the purpose of a Pooling layer?",
    options: [
      "To increase the number of parameters",
      "To reduce the spatial dimensions of the input",
      "To apply non-linearity",
      "To normalize the weights"
    ],
    correctAnswer: 1
  },
  {
    id: 5,
    text: "What is 'Overfitting' in Machine Learning?",
    options: [
      "When a model performs well on training data but poorly on new data",
      "When a model is too simple to capture the underlying pattern",
      "When the training process takes too long",
      "When the dataset is too large for the model"
    ],
    correctAnswer: 0
  }
];

type QuizState = 'config' | 'playing' | 'results';

interface QuizViewProps {
  files: FileItem[];
  standalone?: boolean;
  onComplete?: (score: number, total: number, fileId: number | null) => void;
  initialFileId?: number | null;
}

export default function QuizView({ files, standalone = false, onComplete, initialFileId }: QuizViewProps) {
  const [state, setState] = useState<QuizState>('config');
  const [config, setConfig] = useState({
    numQuestions: 5,
    duration: 10, // minutes
    selectedFileId: (initialFileId !== null && initialFileId !== undefined) ? initialFileId : (files.length > 0 ? files[0].id : null)
  });
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [isAnswered, setIsAnswered] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const [score, setScore] = useState(0);

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

  const startQuiz = () => {
    setCurrentQuestionIndex(0);
    setAnswers({});
    setIsAnswered(false);
    setTimeLeft(config.duration * 60);
    setState('playing');
  };

  const handleAnswer = (optionIndex: number) => {
    if (isAnswered) return;
    setAnswers({ ...answers, [currentQuestionIndex]: optionIndex });
    setIsAnswered(true);
  };

  const nextQuestion = () => {
    setIsAnswered(false);
    if (currentQuestionIndex < config.numQuestions - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    } else {
      calculateScore();
      setState('results');
    }
  };

  const calculateScore = () => {
    let correct = 0;
    MOCK_QUESTIONS.slice(0, config.numQuestions).forEach((q, idx) => {
      if (answers[idx] === q.correctAnswer) {
        correct++;
      }
    });
    setScore(correct);
    if (onComplete) {
      onComplete(correct, config.numQuestions, config.selectedFileId);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className={cn("max-w-3xl mx-auto min-h-[600px] flex flex-col w-full", !standalone && "py-4")}>
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
              {/* File Selection */}
              <div className="space-y-3">
                <label className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-widest">
                  <FileText className="w-3 h-3" />
                  Select Knowledge Source
                </label>
                <select
                  value={config.selectedFileId || ''}
                  onChange={(e) => setConfig({ ...config, selectedFileId: Number(e.target.value) })}
                  className="w-full p-4 rounded-xl border-2 border-slate-100 bg-slate-50 font-bold text-slate-700 focus:border-indigo-500 focus:ring-0 transition-all outline-none"
                >
                  {files.length > 0 ? (
                    files.map(f => (
                      <option key={f.id} value={f.id}>{f.name}</option>
                    ))
                  ) : (
                    <option disabled value="">No files available</option>
                  )}
                </select>
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
                onClick={startQuiz}
                disabled={!config.selectedFileId}
                className="w-full py-4 bg-slate-900 text-white rounded-xl font-black uppercase tracking-widest hover:bg-slate-800 disabled:opacity-50 transition-all shadow-xl shadow-slate-200 flex items-center justify-center gap-3 group mt-2"
              >
                Start Quiz
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
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="px-3 py-1.5 bg-white border border-slate-200 rounded-xl shadow-sm">
                  <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block leading-none">Question</span>
                  <p className="text-sm font-black text-slate-900 mt-1">{currentQuestionIndex + 1} / {config.numQuestions}</p>
                </div>
                <div className="px-3 py-1.5 bg-white border border-slate-200 rounded-xl shadow-sm flex items-center gap-2">
                  <Timer className={cn("w-4 h-4", timeLeft < 60 ? "text-red-500 animate-pulse" : "text-indigo-600")} />
                  <div>
                    <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block leading-none">Time Left</span>
                    <p className={cn("text-sm font-black leading-none mt-1", timeLeft < 60 ? "text-red-600" : "text-slate-900")}>
                      {formatTime(timeLeft)}
                    </p>
                  </div>
                </div>
              </div>
              <div className="w-24 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-600 transition-all duration-500"
                  style={{ width: `${((currentQuestionIndex + 1) / config.numQuestions) * 100}%` }}
                />
              </div>
            </div>

            {/* Question Card */}
            <div className="bg-white rounded-[2.5rem] border border-slate-200 p-8 md:p-12 shadow-xl shadow-slate-200/50 flex-1 flex flex-col">
              <h3 className="text-xl font-bold text-slate-900 mb-8 leading-tight">
                {MOCK_QUESTIONS[currentQuestionIndex].text}
              </h3>

              <div className="space-y-3 flex-1">
                {MOCK_QUESTIONS[currentQuestionIndex].options.map((option, idx) => {
                  const isCorrect = idx === MOCK_QUESTIONS[currentQuestionIndex].correctAnswer;
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
                {currentQuestionIndex === config.numQuestions - 1 ? 'Finish Quiz' : 'Next Question'}
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
                <p className="text-2xl font-black text-indigo-600">{score} / {config.numQuestions}</p>
              </div>
              <div className="p-6 bg-slate-50 rounded-2xl border border-slate-100">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-1">Accuracy</span>
                <p className="text-2xl font-black text-emerald-600">{Math.round((score / config.numQuestions) * 100)}%</p>
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
