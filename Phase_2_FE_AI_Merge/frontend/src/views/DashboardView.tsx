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
} from 'lucide-react';
import { ViewType, FileItem } from '../App';

interface DashboardViewProps {
  onNavigate: (view: ViewType) => void;
  user?: { displayName?: string | null };
  files: FileItem[];
}

export default function DashboardView({ onNavigate, user, files }: DashboardViewProps) {
  const totalFiles = files.length;
  const videoFiles = files.filter(f => f.type === 'video').length;

  const stats = [
    { label: 'Total Files', value: totalFiles.toString(), icon: FileText, color: 'text-blue-600', bg: 'bg-blue-100' },
    { label: 'Video Lectures', value: videoFiles.toString(), icon: Video, color: 'text-indigo-600', bg: 'bg-indigo-100' },
  ];

  const recentActivity = files.slice(0, 4).map((f) => ({
    id: f.id,
    title: f.name,
    type: f.type,
    status: f.status,
    time: f.date,
  }));

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Welcome Section */}
      <div className="bg-white rounded-2xl p-8 border border-slate-200 shadow-sm flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Welcome back, {user?.displayName || 'User'}!</h2>
          <div className="mt-6 flex gap-3">
            <button 
              onClick={() => onNavigate('knowledge')}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors flex items-center gap-2"
            >
              <Search className="w-4 h-4" />
              Ask a Question
            </button>
            <button 
              onClick={() => onNavigate('learning')}
              className="px-4 py-2 bg-white text-slate-700 border border-slate-300 rounded-lg font-medium hover:bg-slate-50 transition-colors flex items-center gap-2"
            >
              <TrendingUp className="w-4 h-4" />
              View Learning Path
            </button>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <div key={i} className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex items-start gap-4">
              <div className={`p-3 rounded-xl ${stat.bg}`}>
                <Icon className={`w-6 h-6 ${stat.color}`} />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-500">{stat.label}</p>
                <p className="text-2xl font-bold text-slate-900 mt-1">{stat.value}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Recent Activity */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-900">Recent Activity</h3>
          <button 
            onClick={() => onNavigate('knowledge')}
            className="text-sm font-medium text-indigo-600 hover:text-indigo-700"
          >
            View all files
          </button>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="divide-y divide-slate-100">
            {recentActivity.map((activity) => (
              <div key={activity.id} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors cursor-pointer">
                <div className="flex items-center gap-4">
                  <div className={`p-2 rounded-lg ${
                    activity.type === 'video' ? 'bg-indigo-100 text-indigo-600' :
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
                  <div>
                    <p className="font-medium text-slate-900">{activity.title}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Clock className="w-3 h-3 text-slate-400" />
                      <span className="text-xs text-slate-500">{activity.time}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {activity.status === 'indexed' && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                      <CheckCircle2 className="w-3 h-3" />
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
                    <span
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700"
                      title="Run pipeline (process), then Build index under Knowledge → Upload"
                    >
                      Not indexed
                    </span>
                  )}
                  {activity.status === 'processed' && (
                    <span
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-sky-100 text-sky-700"
                      title="Processed completed. Build index to make searchable."
                    >
                      Processed
                    </span>
                  )}
                  {activity.status === 'processing' && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Processing
                    </span>
                  )}
                  {activity.status === 'uploading' && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                      <UploadCloud className="w-3 h-3" />
                      Uploading
                    </span>
                  )}
                  {activity.status === 'failed' && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
                      <AlertCircle className="w-3 h-3" />
                      Failed
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
