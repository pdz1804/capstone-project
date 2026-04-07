import React, { useState } from 'react';
import { RefreshCw, FileText, Image, AlertCircle, Loader2, Trash2, Database } from 'lucide-react';

interface IndexStats {
  text_index?: {
    chunks: number;
    docs: number;
    retrievers?: string[];
  };
  image_index?: {
    pages: number;
    vector_store?: string;
  };
}

interface IndexManagementProps {
  stats: IndexStats | null;
  loading: boolean;
  onRebuildAll: () => Promise<void>;
  onRebuildText: () => Promise<void>;
  onRebuildImage: () => Promise<void>;
  onClearTextIndex: () => Promise<void>;
  onClearImageIndex: () => Promise<void>;
}

export const IndexManagement: React.FC<IndexManagementProps> = ({
  stats,
  loading,
  onRebuildAll,
  onRebuildText,
  onRebuildImage,
  onClearTextIndex,
  onClearImageIndex,
}) => {
  const [confirmType, setConfirmType] = useState<'text' | 'image' | null>(null);

  const handleAction = async (action: () => Promise<void>) => {
    try {
      await action();
    } catch (error) {
      console.error('Action failed:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Index Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Text Index */}
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-8 hover:shadow-lg hover:border-sky-200 transition-all duration-300">
          <div className="flex items-center space-x-4 mb-6">
            <div className="w-12 h-12 bg-sky-100 rounded-xl flex items-center justify-center">
              <FileText className="w-6 h-6 text-sky-600" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-800">Text Index</h3>
              <p className="text-sm text-slate-400">BM25 + Qdrant dense + hybrid</p>
            </div>
          </div>
          {stats?.text_index ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-sky-50 rounded-xl border border-sky-100">
                  <div className="text-sm text-sky-600 font-medium mb-1">Chunks</div>
                  <p className="text-3xl font-bold text-sky-700">{stats.text_index.chunks || 0}</p>
                </div>
                <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
                  <div className="text-sm text-blue-600 font-medium mb-1">Documents</div>
                  <p className="text-3xl font-bold text-blue-700">{stats.text_index.docs || 0}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {stats.text_index.retrievers?.map((r, i) => (
                  <span key={i} className="px-3 py-1.5 bg-sky-100 text-sky-700 rounded-lg text-sm font-medium">
                    {r}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-6">
              <AlertCircle className="w-8 h-8 mx-auto mb-2 text-slate-300" />
              <p className="text-slate-400 text-sm">No text index available</p>
            </div>
          )}
        </div>

        {/* Image Index */}
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-8 hover:shadow-lg hover:border-sky-200 transition-all duration-300">
          <div className="flex items-center space-x-4 mb-6">
            <div className="w-12 h-12 bg-sky-100 rounded-xl flex items-center justify-center">
              <Image className="w-6 h-6 text-sky-600" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-800">Image Index</h3>
              <p className="text-sm text-slate-400">ColQwen → Qdrant (MaxSim)</p>
            </div>
          </div>
          {stats?.image_index ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-sky-50 rounded-xl border border-sky-100">
                  <div className="text-sm text-sky-600 font-medium mb-1">Pages</div>
                  <p className="text-3xl font-bold text-sky-700">{stats.image_index.pages || 0}</p>
                </div>
                <div className="p-4 bg-purple-50 rounded-xl border border-purple-100">
                  <div className="text-sm text-purple-600 font-medium mb-1">Vector DB</div>
                  <p className="text-lg font-bold text-purple-700 leading-tight">
                    {stats.image_index.vector_store || 'qdrant'}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="px-3 py-1.5 bg-sky-100 text-sky-700 rounded-lg text-sm font-medium">
                  ColQwen
                </span>
                <span className="px-3 py-1.5 bg-purple-100 text-purple-700 rounded-lg text-sm font-medium">
                  MaxSim
                </span>
              </div>
            </div>
          ) : (
            <div className="text-center py-6">
              <AlertCircle className="w-8 h-8 mx-auto mb-2 text-slate-300" />
              <p className="text-slate-400 text-sm">No image index available</p>
            </div>
          )}
        </div>
      </div>

      {/* Index Management Buttons */}
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-slate-100 p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-slate-800 flex items-center space-x-3">
            <Database className="w-5 h-5 text-sky-500" />
            <span>Index Management</span>
          </h3>
        </div>

        <div className="space-y-4">
          {/* Rebuild Section */}
          <div className="bg-sky-50 rounded-xl p-4 border border-sky-100">
            <h4 className="font-medium text-slate-800 mb-3 flex items-center space-x-2">
              <RefreshCw className="w-4 h-4 text-sky-600" />
              <span>Rebuild Indexes</span>
            </h4>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => handleAction(onRebuildText)}
                disabled={loading}
                className="px-4 py-2.5 bg-sky-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-sky-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95"
                title="Rebuild text index only"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                <span>Rebuild Text</span>
              </button>

              <button
                onClick={() => handleAction(onRebuildImage)}
                disabled={loading}
                className="px-4 py-2.5 bg-sky-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-sky-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95"
                title="Rebuild image index only"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                <span>Rebuild Image</span>
              </button>

              <button
                onClick={() => handleAction(onRebuildAll)}
                disabled={loading}
                className="px-4 py-2.5 bg-slate-600 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-slate-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95"
                title="Rebuild all indexes"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                <span>Rebuild All</span>
              </button>
            </div>
          </div>

          {/* Delete Section */}
          <div className="bg-red-50 rounded-xl p-4 border border-red-100">
            <h4 className="font-medium text-slate-800 mb-3 flex items-center space-x-2">
              <Trash2 className="w-4 h-4 text-red-600" />
              <span>Clear Indexes</span>
            </h4>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => setConfirmType('text')}
                disabled={loading}
                className="px-4 py-2.5 rounded-lg font-medium flex items-center space-x-2 transition-all duration-200 active:scale-95 bg-rose-100 text-rose-700 hover:bg-rose-200 disabled:opacity-50"
                title="Clear all text index vectors and BM25 data"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                <span>Clear Text Index</span>
              </button>
              <button
                onClick={() => setConfirmType('image')}
                disabled={loading}
                className="px-4 py-2.5 rounded-lg font-medium flex items-center space-x-2 transition-all duration-200 active:scale-95 bg-red-100 text-red-700 hover:bg-red-200 disabled:opacity-50"
                title="Clear all vision index (ColQwen pages)"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                <span>Clear Image Index</span>
              </button>
            </div>
            <p className="text-sm text-red-600 mt-2">⚠️ Clear actions are destructive and cannot be undone.</p>
          </div>

          {/* Info Section */}
          <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
            <p className="text-sm text-slate-600">
              <span className="font-semibold">Rebuild Text Index:</span> Re-processes documents → chunks → text embeddings (BM25 + Qdrant dense)
            </p>
            <p className="text-sm text-slate-600 mt-2">
              <span className="font-semibold">Rebuild Image Index:</span> Re-processes images → ColQwen embeddings → Qdrant vision index
            </p>
            <p className="text-sm text-slate-600 mt-2">
              <span className="font-semibold">Rebuild All:</span> Rebuilds both text and image indexes from scratch
            </p>
          </div>
        </div>
      </div>

      {confirmType && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[1px] flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white rounded-2xl border border-slate-200 shadow-2xl p-6">
            <h4 className="text-lg font-semibold text-slate-900">
              {confirmType === 'text' ? 'Clear text index?' : 'Clear image index?'}
            </h4>
            <p className="text-sm text-slate-600 mt-2">
              {confirmType === 'text'
                ? 'This will remove all text vectors and BM25 documents/chunks from the text index. This action cannot be undone.'
                : 'This will remove all image pages from the vision index (ColQwen/Qdrant). This action cannot be undone.'}
            </p>
            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setConfirmType(null)}
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={async () => {
                  if (confirmType === 'text') {
                    await handleAction(onClearTextIndex);
                  } else {
                    await handleAction(onClearImageIndex);
                  }
                  setConfirmType(null);
                }}
                className="px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
              >
                {loading ? 'Clearing...' : 'Yes, clear index'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IndexManagement;
