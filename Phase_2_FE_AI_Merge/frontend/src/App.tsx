/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect, useCallback, useMemo, lazy, Suspense } from 'react';
import {
  Activity,
  LayoutDashboard,
  Database,
  BookOpen,
  TrendingUp,
  LogOut,
  Loader2,
  ChevronDown,
  UploadCloud,
  Search,
  BarChart3,
  MessageSquare,
  Menu,
  Play,
  Layers,
  UserCircle2,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { cn } from './lib/utils';
import LoginView from './views/LoginView';
import AppFooter from './components/AppFooter';
import UserProfileModal from './components/UserProfileModal';
import { authService } from './services/auth_service';
import type { AuthUser } from './services/auth_service';
import type { UserEntity } from './database/types';
import {
  getFilesWithMetadata,
  getQuizResults,
  mapFilesWithMetadataToFileItems,
  postQuizResult,
} from './api/ragApi';

export type ViewType =
  | 'dashboard'
  | 'knowledge'
  | 'lecture'
  | 'learning'
  | 'chat'
  | 'feedbacks'
  | 'profile'
  | 'adminDashboard'
  | 'adminInvocations'
  | 'adminUsers'
  | 'adminKnowledge'
  | 'adminFeedback';
export type KnowledgeSubTab = 'dashboard' | 'upload' | 'run-pipeline' | 'build-index' | 'explorer';

const VIEW_PATHS: Record<ViewType, string> = {
  dashboard: '/dashboard',
  knowledge: '/knowledge/dashboard',
  lecture: '/lecture',
  learning: '/learning',
  chat: '/chat',
  feedbacks: '/feedbacks',
  profile: '/profile',
  adminDashboard: '/admin/dashboard',
  adminInvocations: '/admin/invocations',
  adminUsers: '/admin/users',
  adminKnowledge: '/admin/knowledge',
  adminFeedback: '/admin/feedback',
};

const KNOWLEDGE_PATHS: Record<KnowledgeSubTab, string> = {
  dashboard: '/knowledge/dashboard',
  upload: '/knowledge/upload',
  'run-pipeline': '/knowledge/run-pipeline',
  'build-index': '/knowledge/build-index',
  explorer: '/knowledge/explorer',
};

const DashboardView = lazy(() => import('./views/DashboardView'));
const KnowledgeManagementView = lazy(() => import('./views/KnowledgeManagementView'));
const LectureView = lazy(() => import('./views/LectureView'));
const LearningPathView = lazy(() => import('./views/LearningPathView'));
const ChatAssistantView = lazy(() => import('./views/ChatAssistantView'));
const FeedbacksView = lazy(() => import('./views/FeedbacksView'));
const ProfileView = lazy(() => import('./views/ProfileView'));
const AdminDashboardView = lazy(() => import('./views/AdminDashboardView'));
const AdminInvocationsView = lazy(() => import('./views/AdminInvocationsView'));
const AdminUsersManagementView = lazy(() => import('./views/AdminUsersManagementView'));
const AdminKnowledgeManagementView = lazy(() => import('./views/AdminKnowledgeManagementView'));
const AdminFeedbackManagementView = lazy(() => import('./views/AdminFeedbackManagementView'));

function routeToState(pathname: string): {
  view: ViewType;
  knowledgeSubTab: KnowledgeSubTab;
  isKnown: boolean;
} {
  const clean = pathname.replace(/\/+$/, '') || '/';
  if (clean === '/' || clean === '/dashboard') {
    return { view: 'dashboard', knowledgeSubTab: 'dashboard', isKnown: true };
  }
  if (clean.startsWith('/knowledge')) {
    const seg = clean.split('/')[2] || 'dashboard';
    const valid: KnowledgeSubTab[] = ['dashboard', 'upload', 'run-pipeline', 'build-index', 'explorer'];
    if (valid.includes(seg as KnowledgeSubTab)) {
      return { view: 'knowledge', knowledgeSubTab: seg as KnowledgeSubTab, isKnown: true };
    }
    return { view: 'knowledge', knowledgeSubTab: 'dashboard', isKnown: false };
  }
  if (clean === '/lecture') return { view: 'lecture', knowledgeSubTab: 'dashboard', isKnown: true };
  if (clean === '/learning') return { view: 'learning', knowledgeSubTab: 'dashboard', isKnown: true };
  if (clean === '/chat') return { view: 'chat', knowledgeSubTab: 'dashboard', isKnown: true };
  if (clean === '/feedbacks') return { view: 'feedbacks', knowledgeSubTab: 'dashboard', isKnown: true };
  if (clean === '/profile') return { view: 'profile', knowledgeSubTab: 'dashboard', isKnown: true };
  if (clean === '/admin/dashboard') return { view: 'adminDashboard', knowledgeSubTab: 'dashboard', isKnown: true };
  if (clean === '/admin/invocations') return { view: 'adminInvocations', knowledgeSubTab: 'dashboard', isKnown: true };
  if (clean === '/admin/users') return { view: 'adminUsers', knowledgeSubTab: 'dashboard', isKnown: true };
  if (clean === '/admin/knowledge') return { view: 'adminKnowledge', knowledgeSubTab: 'dashboard', isKnown: true };
  if (clean === '/admin/feedback') return { view: 'adminFeedback', knowledgeSubTab: 'dashboard', isKnown: true };
  return { view: 'dashboard', knowledgeSubTab: 'dashboard', isKnown: false };
}

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
  const navigate = useNavigate();
  const location = useLocation();
  const routeState = useMemo(() => routeToState(location.pathname), [location.pathname]);
  const currentView = routeState.view;
  const knowledgeSubTab = routeState.knowledgeSubTab;
  const [isKnowledgeExpanded, setIsKnowledgeExpanded] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isAuthReady, setIsAuthReady] = useState(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [profile, setProfile] = useState<UserEntity | null>(null);
  const [currentRole, setCurrentRole] = useState<'student' | 'admin' | 'instructor'>('student');
  const [adminViewMode, setAdminViewMode] = useState<'admin' | 'user'>('admin');
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  const [files, setFiles] = useState<FileItem[]>([]);
  const [quizResults, setQuizResults] = useState<QuizResult[]>([]);

  const navigateToView = useCallback((view: ViewType) => {
    navigate(VIEW_PATHS[view]);
    if (view === 'knowledge') {
      setIsKnowledgeExpanded(true);
    }
  }, [navigate]);

  const navigateToKnowledgeTab = useCallback((tab: KnowledgeSubTab) => {
    navigate(KNOWLEDGE_PATHS[tab]);
    setIsKnowledgeExpanded(true);
  }, [navigate]);

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

  const loadProfile = useCallback(async () => {
    setProfileLoading(true);
    setProfileError(null);
    try {
      const me = await authService.getMe();
      setProfile(me);
    } catch (e) {
      console.error('Failed to load profile', e);
      setProfileError('Unable to load your profile right now.');
    } finally {
      setProfileLoading(false);
    }
  }, []);

  const handleSaveProfile = useCallback(async (payload: { displayName: string; persona: string; educationDescription: string }) => {
    setProfileSaving(true);
    setProfileError(null);
    const isStudent = (profile?.role ?? 'student') === 'student';
    try {
      const updated = await authService.updateProfile({
        displayName: isStudent ? undefined : (payload.displayName || undefined),
        persona: payload.persona || undefined,
        educationDescription: payload.educationDescription || undefined,
      });
      setProfile(updated);
      setUser((prev) => (prev ? {
        ...prev,
        displayName: updated.displayName,
        persona: updated.persona,
        educationDescription: updated.educationDescription,
      } : prev));
      setIsProfileModalOpen(false);
    } catch (e) {
      console.error('Failed to save profile', e);
      setProfileError('Could not save profile changes. Please try again.');
    } finally {
      setProfileSaving(false);
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
      setProfile(null);
      setCurrentRole('student');
      return;
    }
    refreshFilesFromApi();
    refreshQuizResultsFromApi();
    void authService.getMe().then((me) => {
      if ((me.isActive ?? true) === false) {
        void authService.logout();
        return;
      }
      setProfile(me);
      setCurrentRole((me.role as any) || 'student');
      setUser((prev) => (prev ? {
        ...prev,
        username: me.username,
        role: me.role,
        isActive: me.isActive,
        displayName: me.displayName ?? prev.displayName,
        persona: me.persona,
        educationDescription: me.educationDescription,
      } : prev));
    }).catch((e) => {
      console.error('Failed to resolve role profile', e);
      setCurrentRole((user.role as any) || 'student');
    });
  }, [user?.uid, refreshFilesFromApi, refreshQuizResultsFromApi]);

  useEffect(() => {
    if (!isProfileModalOpen || !user) return;
    void loadProfile();
  }, [isProfileModalOpen, user?.uid, loadProfile]);

  useEffect(() => {
    // Non-admin accounts always stay in user view mode.
    if (currentRole !== 'admin') {
      setAdminViewMode('user');
    }
  }, [currentRole]);

  const isAdminUser = currentRole === 'admin';
  const isAdminView = isAdminUser && adminViewMode === 'admin';
  const canUseRetrievalEval = currentRole === 'admin' || currentRole === 'student';

  useEffect(() => {
    if (!isAuthReady || !user) return;
    if (!isAdminView && location.pathname.startsWith('/admin')) {
      navigate('/dashboard', { replace: true });
      return;
    }
    if (isAdminView && !location.pathname.startsWith('/admin') && location.pathname !== '/profile') {
      navigate('/admin/dashboard', { replace: true });
      return;
    }

    if (!routeState.isKnown || location.pathname === '/') {
      navigate(isAdminView ? '/admin/dashboard' : '/dashboard', { replace: true });
    }
  }, [isAuthReady, user?.uid, routeState.isKnown, location.pathname, navigate, isAdminView]);

  if (!isAuthReady) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col">
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
        </div>
        <AppFooter />
      </div>
    );
  }

  if (!user) {
    return <LoginView />;
  }

  const studentNavItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    {
      id: 'knowledge',
      label: 'Knowledge Management',
      icon: Database,
      subItems: [
        { id: 'upload', label: 'Upload Files', icon: UploadCloud },
        { id: 'run-pipeline', label: 'Run Pipeline', icon: Play },
        { id: 'build-index', label: 'Build Index', icon: Layers },
        { id: 'explorer', label: 'Knowledge Explorer', icon: Search },
        { id: 'dashboard', label: 'Knowledge Dashboard', icon: BarChart3 },
      ]
    },
    { id: 'lecture', label: 'Lecture Viewer', icon: BookOpen },
    { id: 'learning', label: 'Learning Path', icon: TrendingUp },
    { id: 'chat', label: 'Chat Assistant', icon: MessageSquare },
    { id: 'feedbacks', label: 'Feedbacks', icon: BarChart3 },
  ] as const;

  const adminNavItems = [
    { id: 'adminDashboard', label: 'Application Dashboard', icon: LayoutDashboard },
    { id: 'adminInvocations', label: 'API Invocations', icon: Activity },
    { id: 'adminUsers', label: 'User Management', icon: UserCircle2 },
    { id: 'adminKnowledge', label: 'Knowledge Management', icon: Database },
    { id: 'adminFeedback', label: 'Feedback Management', icon: BarChart3 },
    { id: 'profile', label: 'Profile', icon: UserCircle2 },
  ] as const;

  const navItems = (isAdminView ? adminNavItems : studentNavItems) as ReadonlyArray<any>;
  const viewLoadingFallback = (
    <div className="h-full w-full flex items-center justify-center">
      <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
    </div>
  );

  return (
    <div className="relative flex h-screen overflow-hidden bg-slate-50 text-slate-900 font-sans">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_100%_0%,rgba(56,189,248,0.12),transparent_35%),radial-gradient(circle_at_0%_100%,rgba(14,165,233,0.08),transparent_40%)]" />
      {/* Sidebar */}
      <aside
        className={cn(
          'bg-white/95 border-r border-sky-100 flex flex-col shrink-0 transition-[width] duration-200 ease-out overflow-hidden backdrop-blur-sm',
          sidebarCollapsed ? 'w-[4.5rem]' : 'w-72'
        )}
      >
        <div className={cn('border-b border-sky-100', sidebarCollapsed ? 'p-3 flex justify-center' : 'p-6')}>

          <div className={cn('flex items-center gap-2', sidebarCollapsed && 'justify-center')}>
            <div className="w-8 h-8 rounded-md bg-blue-600 flex items-center justify-center shrink-0">
              <BookOpen className="w-5 h-5 text-white" />
            </div>
            {!sidebarCollapsed && (
              <span className="text-xl font-bold text-slate-900 tracking-tight whitespace-nowrap">BK-MInD</span>
            )}
          </div>
          {!sidebarCollapsed && <p className="text-xs text-slate-500 mt-1">Educational RAG System</p>}
        </div>
        <div className={cn("p-2 flex", sidebarCollapsed ? "justify-center" : "px-4 py-2 border-b border-sky-100")}>
          <button
            type="button"
            onClick={() => setSidebarCollapsed((c) => !c)}
            className="p-2 rounded-lg text-slate-500 hover:bg-sky-50 hover:text-sky-700 transition-colors shrink-0"
            aria-label={sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'}
          >
            {<Menu className='w-5 h-5' />}
          </button>
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
                      if (currentView === item.id) {
                        setIsKnowledgeExpanded(!isKnowledgeExpanded);
                      } else {
                        navigateToView(item.id as ViewType);
                      }
                    } else {
                      navigateToView(item.id as ViewType);
                    }
                  }}
                  className={cn(
                    'w-full flex items-center rounded-lg text-sm font-medium transition-colors text-left',
                    sidebarCollapsed ? 'justify-center px-2 py-3' : 'justify-between px-3 py-2.5',
                    isActive ? 'bg-sky-50 text-sky-700 border border-sky-100' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 border border-transparent'
                  )}
                >
                  <div className={cn('flex items-center min-w-0', sidebarCollapsed ? '' : 'gap-3')}>
                    <Icon className={cn('w-5 h-5 shrink-0', isActive ? 'text-sky-600' : 'text-slate-400')} />
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
                  {hasSubItems && isKnowledgeExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2, ease: "easeInOut" }}
                      className="overflow-hidden"
                    >
                      <div className={cn("py-1 space-y-1", sidebarCollapsed ? "px-0" : "pl-4")}>
                        {item.subItems.map((sub) => {
                          const SubIcon = sub.icon;
                          const isSubActive = isActive && knowledgeSubTab === sub.id;
                          return (
                            <button
                              key={sub.id}
                              title={sidebarCollapsed ? sub.label : undefined}
                              onMouseEnter={() => {
                                if (sub.id === 'upload') {
                                  refreshFilesFromApi();
                                }
                              }}
                              onClick={() => {
                                navigateToKnowledgeTab(sub.id as KnowledgeSubTab);
                              }}
                              className={cn(
                                "w-full flex items-center rounded-lg text-sm font-medium transition-colors text-left",
                                sidebarCollapsed ? "justify-center px-2 py-2.5" : "gap-2 px-3 py-2",
                                isSubActive
                                  ? "bg-sky-50 text-sky-700 border border-sky-100"
                                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
                              )}
                            >
                              <SubIcon className={cn("w-5 h-5 shrink-0", isSubActive ? "text-sky-600" : "text-slate-400")} />
                              {!sidebarCollapsed && <span className="whitespace-nowrap">{sub.label}</span>}
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

        <div className={cn('border-t border-sky-100 space-y-1 bg-white/80', sidebarCollapsed ? 'p-2' : 'p-4')}>
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
        <header className="h-16 bg-white/95 border-b border-sky-100 flex items-center justify-between px-4 sm:px-8 shrink-0 gap-3 backdrop-blur-sm">
          <div className="flex items-center gap-2 min-w-0">
            {/* <button
              type="button"
              onClick={() => setSidebarCollapsed((c) => !c)}
              className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors shrink-0"
              aria-label={sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'}
            >
              {sidebarCollapsed ? <ChevronsRight className="w-5 h-5" /> : <ChevronsLeft className="w-5 h-5" />}
            </button> */}
            <h1 className="text-lg font-semibold text-slate-800 truncate">
              {currentView === 'knowledge' && !isAdminView
                ? studentNavItems
                    .find((i) => i.id === 'knowledge')
                    ?.subItems?.find((s) => s.id === knowledgeSubTab)?.label || 'Knowledge Management'
                : currentView === 'profile'
                  ? 'Profile'
                  : navItems.find((i) => i.id === currentView)?.label || currentView}
            </h1>
          </div>
          <div className="flex items-center gap-4">
            {isAdminUser && (
              <div className="inline-flex items-center rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
                <span className="px-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">View as</span>
                <button
                  type="button"
                  onClick={() => setAdminViewMode('user')}
                  className={cn(
                    'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                    adminViewMode === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-600 hover:bg-slate-100'
                  )}
                  aria-label="Switch to user view"
                >
                  User
                </button>
                <button
                  type="button"
                  onClick={() => setAdminViewMode('admin')}
                  className={cn(
                    'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
                    adminViewMode === 'admin'
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-600 hover:bg-slate-100'
                  )}
                  aria-label="Switch to admin view"
                >
                  Admin
                </button>
              </div>
            )}
            {/* <button className="p-2 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-100 transition-colors relative">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
            </button> */}
            <Link
              to="/profile"
              className="flex items-center gap-3 pl-4 border-l border-sky-100 rounded-lg hover:bg-sky-50/70 pr-2 py-1.5 transition-colors"
              title="Open detailed profile page"
            >
              {user.photoURL ? (
                <img src={user.photoURL} alt={user.displayName || 'User'} className="w-8 h-8 rounded-full border border-sky-100" referrerPolicy="no-referrer" />
              ) : (
                <div className="w-8 h-8 rounded-full bg-sky-100 flex items-center justify-center text-sky-700 font-semibold text-sm">
                  {user.displayName ? user.displayName.charAt(0).toUpperCase() : 'U'}
                </div>
              )}
              <div className="hidden md:block text-sm text-left">
                <p className="font-semibold text-slate-700 leading-none">{user.displayName || 'User'}</p>
                <p className="text-slate-500 text-xs mt-1 truncate max-w-[150px]">{user.email}</p>
              </div>
              <span className="hidden md:inline-flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-sky-700">
                <UserCircle2 className="w-3 h-3" />
                Profile
              </span>
            </Link>
          </div>
        </header>

        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <div className="flex-1 overflow-y-auto p-3 sm:p-5 lg:p-6 xl:p-8 2xl:px-10 min-h-0">
            <Suspense fallback={viewLoadingFallback}>
              {currentView === 'dashboard' && <DashboardView onNavigate={navigateToView} user={user} files={files} />}
              {currentView === 'knowledge' && (
                <KnowledgeManagementView
                  files={files}
                  setFiles={setFiles}
                  activeTab={knowledgeSubTab}
                  onRefreshFiles={refreshFilesFromApi}
                  canUseRetrievalEval={canUseRetrievalEval}
                />
              )}
              {currentView === 'lecture' && <LectureView files={files} />}
              {currentView === 'learning' && (
                <LearningPathView files={files} quizResults={quizResults} onQuizComplete={addQuizResult} />
              )}
              {currentView === 'chat' && <ChatAssistantView />}
              {currentView === 'feedbacks' && <FeedbacksView />}
              {currentView === 'adminDashboard' && <AdminDashboardView />}
              {currentView === 'adminInvocations' && <AdminInvocationsView />}
              {currentView === 'adminUsers' && <AdminUsersManagementView />}
              {currentView === 'adminKnowledge' && <AdminKnowledgeManagementView />}
              {currentView === 'adminFeedback' && <AdminFeedbackManagementView />}
              {currentView === 'profile' && <ProfileView user={user} onEditProfile={() => setIsProfileModalOpen(true)} />}
            </Suspense>
          </div>
          <AppFooter />
        </div>
      </main>

      <UserProfileModal
        isOpen={isProfileModalOpen}
        profile={profile}
        isLoading={profileLoading}
        isSaving={profileSaving}
        error={profileError}
        canEditDisplayName={(profile?.role ?? 'student') !== 'student'}
        onClose={() => {
          setIsProfileModalOpen(false);
          setProfileError(null);
        }}
        onSave={(payload) => {
          void handleSaveProfile(payload);
        }}
      />
    </div>
  );
}
