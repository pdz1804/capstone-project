import {
  FileText,
  Video,
  Image as ImageIcon,
  Search,
  TrendingUp,
  Clock,
  CheckCircle2,
  Music,
  Loader2,
  AlertCircle,
  UploadCloud,
  ChevronRight,
  Database,
  BarChart3,
  Layers,
  ArrowRight,
  ShieldCheck,
  FileCode,
  BookOpen,
} from 'lucide-react';
import { motion } from 'motion/react';
import { ViewType, FileItem } from '../App';

interface DashboardViewProps {
  onNavigate: (view: ViewType) => void;
  user?: { displayName?: string | null };
  files: FileItem[];
}

export default function DashboardView({ onNavigate, user, files }: DashboardViewProps) {
  const totalFiles = files.length;
  const processedFiles = files.filter(f => f.status === 'processed').length;
  const indexedFiles = files.filter(f => f.status === 'indexed').length;
  const totalSize = files.reduce((acc, f) => acc + (f.rawSize || 0), 0);

  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  };

  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: { y: 0, opacity: 1 },
  };

  const stats = [
    { label: 'Total Files', value: totalFiles.toString(), icon: Database, color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-100' },
    { label: 'Indexed Assets', value: indexedFiles.toString(), icon: ShieldCheck, color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-100' },
    { label: 'Processed', value: processedFiles.toString(), icon: Layers, color: 'text-sky-600', bg: 'bg-sky-50', border: 'border-sky-100' },
    { label: 'Storage Used', value: formatSize(totalSize), icon: BarChart3, color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-100' },
  ];

  const quickActions = [
    { id: 'search', label: 'Ask AI Assistant', desc: 'Query your knowledge base', icon: Search, color: 'bg-sky-600', view: 'chat' },
    { id: 'upload', label: 'Import Content', desc: 'Add new lecture materials', icon: UploadCloud, color: 'bg-blue-600', view: 'knowledge' },
    { id: 'lecture', label: 'Lecture Viewer', desc: 'Comprehensive material library', icon: BookOpen, color: 'bg-cyan-600', view: 'lecture' },
  ];

  const recentActivity = files.slice(0, 5).map((f) => ({
    id: f.id,
    title: f.name,
    type: f.type,
    status: f.status,
    time: f.date,
    indexStatus: f.indexStatus,
  }));

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="max-w-7xl mx-auto space-y-10 pb-20 px-4"
    >
      {/* Premium Hero Section */}
      <motion.div
        variants={itemVariants}
        className="relative overflow-hidden rounded-[2.5rem] bg-gradient-to-br from-sky-400 via-blue-500 to-sky-500 text-white shadow-2xl shadow-sky-200/50 p-8 lg:p-12 mb-12"
      >
        <div className="absolute inset-0 bg-white/10 opacity-30 mix-blend-overlay pointer-events-none" />
        <div className="absolute top-0 right-0 w-1/2 h-full opacity-90 mix-blend-screen pointer-events-none hidden lg:block">
          <img
            src="C:\Users\nam\.gemini\antigravity\brain\ea4abc8e-8bdd-4a60-912d-86596658c15c\bright_welcome_illustration_1775564857932.png"
            alt="Hero"
            className="w-full h-full object-cover transform scale-110 translate-x-12"
          />
        </div>

        <div className="relative z-10 max-w-2xl">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="inline-flex items-center gap-2 px-3 py-1 bg-white/30 backdrop-blur-md rounded-full text-white text-xs font-black uppercase tracking-widest mb-6 border border-white/30"
          >
            <Sparkles className="w-3.5 h-3.5" stroke="white" /> AI-Powered Learning Hub
          </motion.div>
          <h2 className="text-4xl lg:text-5xl font-black mb-4 tracking-tight leading-tight">
            Elevate study with <span className="text-sky-100">BK-MInD</span>
          </h2>
          <p className="text-lg text-white/90 mb-8 font-medium leading-relaxed max-w-xl">
            Welcome back, <span className="text-white font-black underline decoration-sky-300 underline-offset-4">{user?.displayName || 'Scholar'}</span>! Your knowledge base is ready with {totalFiles} assets processed and indexed for deep search.
          </p>

          <div className="flex flex-wrap gap-4">
            <button
              onClick={() => onNavigate('chat' as ViewType)}
              className="px-8 py-4 bg-white text-sky-600 rounded-2xl font-black text-sm uppercase tracking-wider hover:bg-slate-50 hover:scale-105 transition-all shadow-xl shadow-sky-900/10 active:scale-95 flex items-center gap-2 group"
            >
              Start Chatting <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
            <button
              onClick={() => onNavigate('learning')}
              className="px-8 py-4 bg-sky-700/30 hover:bg-sky-700/50 backdrop-blur-md text-white rounded-2xl font-black text-sm uppercase tracking-wider transition-all border border-white/20 active:scale-95"
            >
              Study Roadmap
            </button>
          </div>
        </div>
      </motion.div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <motion.div
              key={i}
              variants={itemVariants}
              whileHover={{ y: -5, transition: { duration: 0.2 } }}
              className="bg-white rounded-3xl p-6 border border-slate-200 shadow-xl shadow-slate-100/50 flex flex-col justify-between group h-full"
            >
              <div className="flex items-center justify-between mb-4">
                <div className={`p-4 rounded-[1.25rem] ${stat.bg} ${stat.color} transition-colors group-hover:bg-slate-900 group-hover:text-white`}>
                  <Icon className="w-6 h-6" />
                </div>
                <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest border border-slate-100 rounded-full px-2 py-0.5">Live</div>
              </div>
              <div>
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">{stat.label}</p>
                <div className="flex items-baseline gap-2">
                  <p className="text-3xl font-black text-slate-900 tracking-tighter">{stat.value}</p>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
        {/* Quick Actions */}
        <div className="lg:col-span-1 space-y-6">
          <div className="flex items-center justify-between px-2">
            <h3 className="text-xl font-black text-slate-900 tracking-tight">Quick Actions</h3>
          </div>
          <div className="space-y-4">
            {quickActions.map((action, i) => {
              const ActionIcon = action.icon;
              return (
                <motion.button
                  key={i}
                  variants={itemVariants}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => onNavigate(action.view as ViewType)}
                  className="w-full flex items-center gap-5 p-5 bg-white border border-slate-200 rounded-[1.75rem] shadow-lg shadow-slate-100/50 hover:border-sky-200 text-left group"
                >
                  <div className={`w-14 h-14 rounded-2xl ${action.color} text-white flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform`}>
                    <ActionIcon className="w-6 h-6" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-bold text-slate-900 truncate">{action.label}</p>
                    <p className="text-xs text-slate-500 truncate mt-0.5 font-medium">{action.desc}</p>
                  </div>
                  <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-sky-500 group-hover:translate-x-1 transition-all" />
                </motion.button>
              );
            })}
          </div>
        </div>

        {/* Enhanced Recent Activity */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between px-2">
            <h3 className="text-xl font-black text-slate-900 tracking-tight">Recent Insights</h3>
            <button
              onClick={() => onNavigate('knowledge' as ViewType)}
              className="text-xs font-black text-sky-600 hover:text-sky-800 uppercase tracking-widest flex items-center gap-1.5 group"
            >
              Analyze Library <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </button>
          </div>

          <motion.div
            variants={itemVariants}
            className="bg-white rounded-[2rem] border border-slate-200 shadow-xl overflow-hidden"
          >
            <div className="divide-y divide-slate-100">
              {recentActivity.length === 0 ? (
                <div className="p-20 text-center text-slate-400">
                  <FileCode className="w-12 h-12 mx-auto mb-4 opacity-20" />
                  <p className="text-sm font-bold uppercase tracking-widest opacity-50">Pulse quiet — Start by uploading content</p>
                </div>
              ) : (
                recentActivity.map((activity) => (
                  <div
                    key={activity.id}
                    className="p-5 flex items-center justify-between hover:bg-slate-50 transition-colors cursor-pointer group"
                    onClick={() => onNavigate('lecture' as ViewType)}
                  >
                    <div className="flex items-center gap-5 min-w-0">
                      <div className={`w-12 h-12 rounded-2xl flex items-center justify-center shadow-sm shrink-0 ${activity.type === 'video' ? 'bg-sky-100 text-sky-600' :
                        activity.type === 'document' ? 'bg-blue-100 text-blue-600' :
                          activity.type === 'spreadsheet' ? 'bg-emerald-100 text-emerald-600' :
                            activity.type === 'audio' ? 'bg-purple-100 text-purple-600' :
                              'bg-amber-100 text-amber-600'
                        }`}>
                        {activity.type === 'video' ? <Video className="w-5 h-5" /> :
                          activity.type === 'document' ? <FileText className="w-5 h-5" /> :
                            activity.type === 'spreadsheet' ? <FileText className="w-5 h-5" /> :
                              activity.type === 'audio' ? <Music className="w-5 h-5" /> :
                                <ImageIcon className="w-5 h-5" />}
                      </div>
                      <div className="min-w-0">
                        <p className="font-bold text-slate-900 group-hover:text-sky-600 transition-colors truncate max-w-md" title={activity.title}>{activity.title}</p>
                        <div className="flex items-center gap-3 mt-1.5">
                          <span className="flex items-center gap-1 text-[10px] font-bold text-slate-400">
                            <Clock className="w-3 h-3" />
                            {activity.time}
                          </span>
                          <span className="w-1 h-1 bg-slate-300 rounded-full" />
                          <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{activity.type}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="hidden sm:block">
                        {activity.status === 'indexed' && (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest bg-emerald-100/80 text-emerald-700">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            {activity.indexStatus === 'all'
                              ? 'Indexed (All)'
                              : activity.indexStatus === 'text'
                                ? 'Indexed (Text)'
                                : activity.indexStatus === 'image'
                                  ? 'Indexed (Image)'
                                  : 'Indexed'}
                          </span>
                        )}
                        {activity.status === 'uploaded' && (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest bg-slate-100 text-slate-700">
                            Uploaded
                          </span>
                        )}
                        {activity.status === 'processed' && (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest bg-sky-100 text-sky-700">
                            Processed
                          </span>
                        )}
                        {activity.status === 'processing' && (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest bg-sky-100 text-sky-700">
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            Syncing
                          </span>
                        )}
                        {activity.status === 'failed' && (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest bg-red-100 text-red-700">
                            <AlertCircle className="w-3.5 h-3.5" />
                            Error
                          </span>
                        )}
                      </div>
                      <ChevronRight className="w-5 h-5 text-slate-200 group-hover:text-sky-400 transition-colors" />
                    </div>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        </div>
      </div>
    </motion.div>
  );
}

function Sparkles({ className, stroke }: { className?: string; stroke?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke={stroke || "currentColor"}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
      <path d="M5 3v4" />
      <path d="M19 17v4" />
      <path d="M3 5h4" />
      <path d="M17 19h4" />
    </svg>
  );
}
