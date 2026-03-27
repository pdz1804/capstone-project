/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect } from 'react';
import { 
  LayoutDashboard, 
  Database, 
  BookOpen, 
  TrendingUp, 
  Bell,
  User,
  LogOut,
  Loader2,
  ChevronDown, 
  UploadCloud, 
  Search,
  BarChart3,
  MessageSquare
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from './lib/utils';
import DashboardView from './views/DashboardView';
import KnowledgeManagementView from './views/KnowledgeManagementView';
import LectureView from './views/LectureView';
import LearningPathView from './views/LearningPathView';
import ChatAssistantView from './views/ChatAssistantView';
import QuizView from './views/QuizView';
import LoginView from './views/LoginView';
import { authService } from './services/auth_service';
import { User as FirebaseUser } from 'firebase/auth';

export type ViewType = 'dashboard' | 'knowledge' | 'lecture' | 'learning' | 'chat';
export type KnowledgeSubTab = 'dashboard' | 'upload' | 'explorer';

export interface FileItem {
  id: number;
  name: string;
  type: 'video' | 'document' | 'image' | 'spreadsheet' | 'audio' | 'pdf';
  size: string;
  rawSize: number;
  status: 'indexed' | 'processing' | 'failed' | 'uploading';
  date: string;
  duration?: string;
  pages?: number;
  resolution?: string;
  rows?: number;
  progress?: number;
  uploadedBytes?: number;
  timeRemaining?: number;
  originalFile?: File;
}

export interface QuizResult {
  id: string;
  score: number;
  total: number;
  date: string;
  fileId: number | null;
}

export default function App() {
  const [currentView, setCurrentView] = useState<ViewType>('dashboard');
  const [knowledgeSubTab, setKnowledgeSubTab] = useState<KnowledgeSubTab>('dashboard');
  const [isKnowledgeExpanded, setIsKnowledgeExpanded] = useState(true);
  const [user, setUser] = useState<FirebaseUser | null>(null);
  const [isAuthReady, setIsAuthReady] = useState(false);
  
  const [files, setFiles] = useState<FileItem[]>([]);
  const [quizResults, setQuizResults] = useState<QuizResult[]>([]);

  const addQuizResult = (score: number, total: number, fileId: number | null) => {
    const newResult: QuizResult = {
      id: Math.random().toString(36).substr(2, 9),
      score,
      total,
      date: new Date().toLocaleDateString(),
      fileId
    };
    setQuizResults(prev => [newResult, ...prev]);
  };

  useEffect(() => {
    const unsubscribe = authService.onAuthStateChanged((currentUser) => {
      setUser(currentUser);
      setIsAuthReady(true);
    });
    return () => unsubscribe();
  }, []);

  if (!isAuthReady) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <LoginView />;
  }

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { 
      id: 'knowledge', 
      label: 'Knowledge Management', 
      icon: Database,
      subItems: [
        { id: 'dashboard', label: 'Knowledge Dashboard', icon: BarChart3 },
        { id: 'upload', label: 'Upload', icon: UploadCloud },
        { id: 'explorer', label: 'Knowledge Explorer', icon: Search },
      ]
    },
    { id: 'lecture', label: 'Lecture Viewer', icon: BookOpen },
    { id: 'learning', label: 'Learning Path', icon: TrendingUp },
    { id: 'chat', label: 'Chat Assistant', icon: MessageSquare },
  ] as const;

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Sidebar */}
      <aside className="w-80 bg-white border-r border-slate-200 flex flex-col shrink-0">
        <div className="p-6 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
              <BookOpen className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-slate-900 tracking-tight">BK-MInD</span>
          </div>
          <p className="text-xs text-slate-500 mt-1">Educational RAG System</p>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.id;
            const hasSubItems = 'subItems' in item;
            
            return (
              <div key={item.id} className="space-y-1">
                <button
                  onClick={() => {
                    if (hasSubItems) {
                      if (currentView === item.id) {
                        setIsKnowledgeExpanded(!isKnowledgeExpanded);
                      } else {
                        setCurrentView(item.id as ViewType);
                        setIsKnowledgeExpanded(true);
                      }
                    } else {
                      setCurrentView(item.id as ViewType);
                    }
                  }}
                  className={cn(
                    "w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-left",
                    isActive 
                      ? "bg-indigo-50 text-indigo-700" 
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={cn("w-5 h-5 shrink-0", isActive ? "text-indigo-600" : "text-slate-400")} />
                    <span className="whitespace-nowrap">{item.label}</span>
                  </div>
                  {hasSubItems && (
                    <motion.div
                      animate={{ rotate: isKnowledgeExpanded ? 0 : -90 }}
                      transition={{ duration: 0.2 }}
                      className="shrink-0"
                    >
                      <ChevronDown className="w-4 h-4 text-slate-400" />
                    </motion.div>
                  )}
                </button>

                <AnimatePresence initial={false}>
                  {hasSubItems && isKnowledgeExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2, ease: "easeInOut" }}
                      className="overflow-hidden"
                    >
                      <div className="pl-10 py-1 space-y-1">
                        {item.subItems.map((sub) => {
                          const SubIcon = sub.icon;
                          const isSubActive = isActive && knowledgeSubTab === sub.id;
                          return (
                            <button
                              key={sub.id}
                              onClick={() => {
                                setCurrentView(item.id as ViewType);
                                setKnowledgeSubTab(sub.id as KnowledgeSubTab);
                              }}
                              className={cn(
                                "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left",
                                isSubActive 
                                  ? "bg-indigo-50/50 text-indigo-700" 
                                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
                              )}
                            >
                              <SubIcon className={cn("w-4 h-4 shrink-0", isSubActive ? "text-indigo-600" : "text-slate-400")} />
                              <span className="whitespace-nowrap">{sub.label}</span>
                            </button>
                          );
                        })}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-200 space-y-1">
          <button 
            onClick={() => authService.logout()}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
          >
            <LogOut className="w-5 h-5 text-red-400" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8 shrink-0">
          <h1 className="text-lg font-semibold text-slate-800 capitalize">
            {navItems.find(i => i.id === currentView)?.label || currentView}
          </h1>
          <div className="flex items-center gap-4">
            <button className="p-2 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-100 transition-colors relative">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
            </button>
            <div className="flex items-center gap-3 pl-4 border-l border-slate-200">
              {user.photoURL ? (
                <img src={user.photoURL} alt={user.displayName || 'User'} className="w-8 h-8 rounded-full border border-slate-200" referrerPolicy="no-referrer" />
              ) : (
                <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-semibold text-sm">
                  {user.displayName ? user.displayName.charAt(0).toUpperCase() : 'U'}
                </div>
              )}
              <div className="hidden md:block text-sm">
                <p className="font-medium text-slate-700 leading-none">{user.displayName || 'User'}</p>
                <p className="text-slate-500 text-xs mt-1 truncate max-w-[150px]">{user.email}</p>
              </div>
            </div>
          </div>
        </header>

        {/* View Content */}
        <div className="flex-1 overflow-y-auto p-8">
          {currentView === 'dashboard' && <DashboardView onNavigate={setCurrentView} user={user} files={files} />}
          {currentView === 'knowledge' && (
            <KnowledgeManagementView 
              files={files} 
              setFiles={setFiles} 
              onNavigate={setCurrentView} 
              activeTab={knowledgeSubTab}
              onTabChange={setKnowledgeSubTab}
            />
          )}
          {currentView === 'lecture' && <LectureView files={files} />}
          {currentView === 'learning' && (
            <LearningPathView 
              files={files} 
              quizResults={quizResults} 
              onQuizComplete={addQuizResult} 
            />
          )}
          {currentView === 'chat' && <ChatAssistantView />}
        </div>
      </main>
    </div>
  );
}
