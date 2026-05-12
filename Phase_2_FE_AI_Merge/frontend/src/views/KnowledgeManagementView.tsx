import LibraryView from './LibraryView';
import SearchView from './SearchView';
import KnowledgeDashboardView from './KnowledgeDashboardView';
import { FileItem, KnowledgeSubTab } from '../App';

interface KnowledgeManagementViewProps {
  files: FileItem[];
  filesTotal: number;
  filesLoading: boolean;
  setFiles: React.Dispatch<React.SetStateAction<FileItem[]>>;
  activeTab: KnowledgeSubTab;
  onRefreshFiles: (params?: {
    skip?: number;
    limit?: number;
    query?: string;
    type?: string;
    status?: string;
    sort_by?: 'name' | 'size' | 'date' | 'status' | 'type';
    sort_dir?: 'asc' | 'desc';
    cache_bust?: boolean;
  }) => Promise<{ count: number } | void>;
}

export default function KnowledgeManagementView({
  files,
  filesTotal,
  filesLoading,
  setFiles,
  activeTab,
  onRefreshFiles,
}: KnowledgeManagementViewProps) {
  const tabDescription: Record<KnowledgeSubTab, { title: string; description: string }> = {
    dashboard: {
      title: 'Knowledge Dashboard',
      description: 'Overview of indexing status, storage usage, and processed artifacts by file.',
    },
    upload: {
      title: 'Upload Content',
      description: 'Upload your educational materials to the server. These files will be staged for processing.',
    },
    'run-pipeline': {
      title: 'Run Pipeline',
      description: 'Run the pipeline to transcribe videos and extract structured insights from documents.',
    },
    'build-index': {
      title: 'Build Index',
      description: 'Index processed content into the Vector Database to enable semantic search and RAG.',
    },
    explorer: {
      title: 'Knowledge Explorer',
      description: 'Search and explore indexed knowledge with retrieval and answer generation.',
    },
  };

  return (
    <div className="h-full flex flex-col space-y-5">
      <div className="shrink-0">
        <div className="relative overflow-hidden rounded-3xl border border-sky-100 bg-white px-6 py-5 shadow-[0_14px_30px_-24px_rgba(14,165,233,0.5)]">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.13),transparent_42%)]" />
          <div className="relative">
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">{tabDescription[activeTab].title}</h2>
            <p className="text-sm text-slate-600 mt-1 max-w-3xl">{tabDescription[activeTab].description}</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {activeTab === 'dashboard' && <KnowledgeDashboardView files={files} />}
        {activeTab === 'upload' && (
          <LibraryView files={files} filesTotal={filesTotal} filesLoading={filesLoading} setFiles={setFiles} onRefreshFiles={onRefreshFiles} controlMode="upload" />
        )}
        {activeTab === 'run-pipeline' && (
          <LibraryView files={files} filesTotal={filesTotal} filesLoading={filesLoading} setFiles={setFiles} onRefreshFiles={onRefreshFiles} controlMode="process" />
        )}
        {activeTab === 'build-index' && (
          <LibraryView files={files} filesTotal={filesTotal} filesLoading={filesLoading} setFiles={setFiles} onRefreshFiles={onRefreshFiles} controlMode="index" />
        )}
        {activeTab === 'explorer' && <SearchView files={files} />}
      </div>
    </div>
  );
}
