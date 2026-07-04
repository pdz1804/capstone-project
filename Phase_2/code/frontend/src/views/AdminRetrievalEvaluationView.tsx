import { useEffect } from 'react';
import { Beaker, RefreshCw } from 'lucide-react';

import type { FileItem } from '../App';
import { adminUi } from '../lib/adminUi';
import SearchView from './SearchView';

interface AdminRetrievalEvaluationViewProps {
  files: FileItem[];
  onRefreshFiles: () => Promise<{ count: number } | void>;
}

export default function AdminRetrievalEvaluationView({
  files,
  onRefreshFiles,
}: AdminRetrievalEvaluationViewProps) {
  useEffect(() => {
    void onRefreshFiles();
  }, [onRefreshFiles]);

  return (
    <div className="space-y-4">
      <div className={adminUi.panel}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-emerald-600">Admin</p>
            <h2 className="text-xl font-black tracking-tight text-slate-900">Retrieval Evaluation</h2>
            <p className="mt-1 text-xs text-slate-500">
              Run the existing retrieval evaluation flow on one uploaded file at a time, then review and save human labels.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void onRefreshFiles()}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh files
          </button>
        </div>
      </div>

      <div className="rounded-2xl border border-emerald-100 bg-white/95 p-4 shadow-[0_20px_38px_-30px_rgba(15,23,42,0.35)]">
        <div className="mb-4 flex items-center gap-2 text-emerald-700">
          <Beaker className="h-5 w-5" />
          <p className="text-sm font-bold uppercase tracking-tight">Evaluation Workspace</p>
        </div>
        <SearchView files={files} showRetrievalEval showSearch={false} />
      </div>
    </div>
  );
}
