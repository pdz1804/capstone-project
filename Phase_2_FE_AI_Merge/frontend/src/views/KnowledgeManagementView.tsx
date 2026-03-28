import React from 'react';
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
      title: 'Upload',
      description: 'Upload files, manage items, preview content, and run remove actions with confirmation.',
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

      {/* Subtab Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'dashboard' && <KnowledgeDashboardView files={files} />}
        {activeTab === 'upload' && (
          <LibraryView files={files} setFiles={setFiles} onRefreshFiles={onRefreshFiles} />
        )}
        {activeTab === 'explorer' && <SearchView files={files} />}
      </div>
    </div>
  );
}
