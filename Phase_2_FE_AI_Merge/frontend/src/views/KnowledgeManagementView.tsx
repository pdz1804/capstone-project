import LibraryView from './LibraryView';
import SearchView from './SearchView';
import KnowledgeDashboardView from './KnowledgeDashboardView';
import { FileItem, ViewType, KnowledgeSubTab } from '../App';

interface KnowledgeManagementViewProps {
  files: FileItem[];
  setFiles: React.Dispatch<React.SetStateAction<FileItem[]>>;
  onNavigate: (view: ViewType) => void;
  activeTab: KnowledgeSubTab;
  onTabChange?: (tab: KnowledgeSubTab) => void;
  onRefreshFiles: () => Promise<void>;
}

export default function KnowledgeManagementView({
  files,
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
      description: 'Index processed content into the vector database to enable semantic search and RAG.',
    },
    explorer: {
      title: 'Knowledge Explorer',
      description: 'Search and explore indexed knowledge with retrieval and answer generation.',
    },
  };

  return (
    <div className="h-full flex flex-col space-y-6">
      <div className="shrink-0 px-1 py-1">
        <div>
          <h2 className="text-base font-semibold text-slate-900">{tabDescription[activeTab].title}</h2>
          <p className="text-sm text-slate-600 mt-1">{tabDescription[activeTab].description}</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {activeTab === 'dashboard' && <KnowledgeDashboardView files={files} />}
        {activeTab === 'upload' && (
          <LibraryView files={files} setFiles={setFiles} onRefreshFiles={onRefreshFiles} controlMode="upload" />
        )}
        {activeTab === 'run-pipeline' && (
          <LibraryView files={files} setFiles={setFiles} onRefreshFiles={onRefreshFiles} controlMode="process" />
        )}
        {activeTab === 'build-index' && (
          <LibraryView files={files} setFiles={setFiles} onRefreshFiles={onRefreshFiles} controlMode="index" />
        )}
        {activeTab === 'explorer' && <SearchView files={files} />}
      </div>
    </div>
  );
}
