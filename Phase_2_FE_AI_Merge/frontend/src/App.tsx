/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect, useCallback } from 'react';
import {
  LayoutDashboard,
  Database,
  BookOpen,
  TrendingUp,
  Bell,
  LogOut,
  Loader2,
  ChevronDown,
  UploadCloud,
  Search,
  BarChart3,
  MessageSquare,
  ChevronsLeft,
  ChevronsRight,
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
import AppFooter from './components/AppFooter';
import { authService } from './services/auth_service';
import type { AuthUser } from './services/auth_service';
import {
  getFilesWithMetadata,
  getQuizResults,
  mapFilesWithMetadataToFileItems,
  postQuizResult,
} from './api/ragApi';

export type ViewType = 'dashboard' | 'knowledge' | 'lecture' | 'learning' | 'chat';
export type KnowledgeSubTab = 'dashboard' | 'upload' | 'explorer';

export interface FileItem {
  id: number;
  name: string;
  type: 'video' | 'document' | 'image' | 'spreadsheet' | 'audio' | 'pdf';
  size: string;
  rawSize: number;
  /** uploaded = on server input/ but not in vector index (not “actively processing”) */
  status: 'indexed' | 'processed' | 'uploaded' | 'processing' | 'failed' | 'uploading';
  indexStatus?: 'none' | 'text' | 'image' | 'all';
  date: string;
  duration?: string;
  pages?: number;
  resolution?: string;
  rows?: number;
  progress?: number;
  uploadedBytes?: number;
  timeRemaining?: number;
  originalFile?: File;
  /** Backend absolute path or URI — required for DELETE /api/files */
  storagePath?: string;
  /** Folder name under stage3/stage4 for /api/insights/* document_id */
  documentFolder?: string;
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isAuthReady, setIsAuthReady] = useState(false);
  
  const [files, setFiles] = useState<FileItem[]>([]);
  const [quizResults, setQuizResults] = useState<QuizResult[]>([]);

  const refreshQuizResultsFromApi = useCallback(async () => {
    try {
      const { items } = await getQuizResults(300);
      const mapped: QuizResult[] = (items || []).map((r) => ({
        id: r.attempt_id,
        score: Number(r.score || 0),
        total: Number(r.total || 0),
        date: String(r.created_at || '').slice(0, 10) || new Date().toISOString().slice(0, 10),
        fileId: r.file_id ?? null,
      }));
      setQuizResults(mapped);
    } catch (e) {
      console.error('Failed to load quiz results from API', e);
      setQuizResults([]);
    }
  }, []);

  const addQuizResult = (score: number, total: number, fileId: number | null) => {
    const newResult: QuizResult = {
      id: Math.random().toString(36).substr(2, 9),
      score,
      total,
      date: new Date().toLocaleDateString(),
      fileId
    };
    setQuizResults(prev => [newResult, ...prev]);

    // Persist attempt per user (best-effort; UI already updated optimistically).
    const selected = files.find((f) => f.id === fileId);
    void postQuizResult({
      score,
      total,
      file_id: fileId,
      document_id: selected?.documentFolder ?? null,
      quiz_topic: undefined,
    }).catch((e) => {
      console.error('Failed to store quiz result', e);
    });
  };

  const refreshFilesFromApi = useCallback(async () => {
    try {
      const data = await getFilesWithMetadata();
      const mappedFiles = mapFilesWithMetadataToFileItems(data);
      setFiles(mappedFiles);
    } catch (e) {
      console.error('Failed to load files from API', e);
      setFiles([]);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const unsubscribe = authService.onAuthStateChanged((currentUser) => {
      if (!active) return;
      setUser(currentUser);
    });
    void authService.getInitialUser().then((initialUser) => {
      if (!active) return;
      setUser(initialUser);
      setIsAuthReady(true);
    });
    return () => {
      active = false;
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!user) {
      setFiles([]);
      setQuizResults([]);
      return;
    }
    refreshFilesFromApi();
    refreshQuizResultsFromApi();
  }, [user?.uid, refreshFilesFromApi, refreshQuizResultsFromApi]);

  if (!isAuthReady) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col">
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
        </div>
        <AppFooter />
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
        { id: 'upload', label: 'Upload', icon: UploadCloud },
        { id: 'explorer', label: 'Knowledge Explorer', icon: Search },
        { id: 'dashboard', label: 'Knowledge Dashboard', icon: BarChart3 },
      ]
    },
    { id: 'lecture', label: 'Lecture Viewer', icon: BookOpen },
    { id: 'learning', label: 'Learning Path', icon: TrendingUp },
    { id: 'chat', label: 'Chat Assistant', icon: MessageSquare },
  ] as const;

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Sidebar */}
      <aside
        className={cn(
          'bg-white border-r border-slate-200 flex flex-col shrink-0 transition-[width] duration-200 ease-out overflow-hidden',
          sidebarCollapsed ? 'w-[4.5rem]' : 'w-80'
        )}
      >
        <div className={cn('border-b border-slate-200', sidebarCollapsed ? 'p-3 flex justify-center' : 'p-6')}>
          <div className={cn('flex items-center gap-2', sidebarCollapsed && 'justify-center')}>
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0">
              <BookOpen className="w-5 h-5 text-white" />
            </div>
            {!sidebarCollapsed && (
              <span className="text-xl font-bold text-slate-900 tracking-tight whitespace-nowrap">BK-MInD</span>
            )}
          </div>
          {!sidebarCollapsed && <p className="text-xs text-slate-500 mt-1">Educational RAG System</p>}
        </div>

        <nav className="flex-1 p-2 sm:p-4 space-y-1 overflow-y-auto overflow-x-hidden">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.id;
            const hasSubItems = 'subItems' in item;

            return (
              <div key={item.id} className="space-y-1">
                <button
                  type="button"
                  title={sidebarCollapsed ? item.label : undefined}
                  onClick={() => {
                    if (hasSubItems) {
                      if (sidebarCollapsed) {
                        setSidebarCollapsed(false);
                        setCurrentView(item.id as ViewType);
                        setIsKnowledgeExpanded(true);
                        return;
                      }
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
                    'w-full flex items-center rounded-lg text-sm font-medium transition-colors text-left',
                    sidebarCollapsed ? 'justify-center px-2 py-3' : 'justify-between px-3 py-2.5',
                    isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  )}
                >
                  <div className={cn('flex items-center min-w-0', sidebarCollapsed ? '' : 'gap-3')}>
                    <Icon className={cn('w-5 h-5 shrink-0', isActive ? 'text-indigo-600' : 'text-slate-400')} />
                    {!sidebarCollapsed && <span className="whitespace-nowrap truncate">{item.label}</span>}
                  </div>
                  {hasSubItems && !sidebarCollapsed && (
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
                  {hasSubItems && isKnowledgeExpanded && !sidebarCollapsed && (
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

        <div className={cn('border-t border-slate-200 space-y-1', sidebarCollapsed ? 'p-2' : 'p-4')}>
          <button
            type="button"
            title={sidebarCollapsed ? 'Sign out' : undefined}
            onClick={() => authService.logout()}
            className={cn(
              'w-full flex items-center rounded-lg text-sm font-medium text-red-600 hover:bg-red-50 transition-colors',
              sidebarCollapsed ? 'justify-center px-2 py-3' : 'gap-3 px-3 py-2.5'
            )}
          >
            <LogOut className="w-5 h-5 text-red-400 shrink-0" />
            {!sidebarCollapsed && 'Sign Out'}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-4 sm:px-8 shrink-0 gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <button
              type="button"
              onClick={() => setSidebarCollapsed((c) => !c)}
              className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors shrink-0"
              aria-expanded={!sidebarCollapsed}
              aria-label={sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'}
            >
              {sidebarCollapsed ? <ChevronsRight className="w-5 h-5" /> : <ChevronsLeft className="w-5 h-5" />}
            </button>
            <h1 className="text-lg font-semibold text-slate-800 truncate">
              {navItems.find((i) => i.id === currentView)?.label || currentView}
            </h1>
          </div>
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

        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <div className="flex-1 overflow-y-auto p-8 min-h-0">
            {currentView === 'dashboard' && <DashboardView onNavigate={setCurrentView} user={user} files={files} />}
            {currentView === 'knowledge' && (
              <KnowledgeManagementView
                files={files}
                setFiles={setFiles}
                onNavigate={setCurrentView}
                activeTab={knowledgeSubTab}
                onTabChange={setKnowledgeSubTab}
                onRefreshFiles={refreshFilesFromApi}
              />
            )}
            {currentView === 'lecture' && <LectureView files={files} />}
            {currentView === 'learning' && (
              <LearningPathView files={files} quizResults={quizResults} onQuizComplete={addQuizResult} />
            )}
            {currentView === 'chat' && <ChatAssistantView />}
          </div>
          <AppFooter />
        </div>
      </main>
    </div>
  );
}
