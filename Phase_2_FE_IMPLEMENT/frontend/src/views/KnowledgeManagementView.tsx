import React, { useState } from 'react';
import { UploadCloud, Search, Database, BarChart3 } from 'lucide-react';
import { cn } from '../lib/utils';
import LibraryView from './LibraryView';
import SearchView from './SearchView';
import KnowledgeDashboardView from './KnowledgeDashboardView';
import { FileItem, ViewType, KnowledgeSubTab } from '../App';

interface KnowledgeManagementViewProps {
  files: FileItem[];
  setFiles: React.Dispatch<React.SetStateAction<FileItem[]>>;
  onNavigate: (view: ViewType) => void;
  activeTab: KnowledgeSubTab;
  onTabChange: (tab: KnowledgeSubTab) => void;
}

export default function KnowledgeManagementView({
  files,
  setFiles,
  onNavigate,
  activeTab,
  onTabChange
}: KnowledgeManagementViewProps) {
  const tabs = [
    { id: 'dashboard', label: 'Knowledge Dashboard', icon: BarChart3 },
    { id: 'upload', label: 'Upload', icon: UploadCloud },
    { id: 'explorer', label: 'Knowledge Explorer', icon: Search },
  ] as const;

  return (
    <div className="h-full flex flex-col space-y-6">
      {/* <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center text-indigo-600">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Knowledge Management</h2>
            <p className="text-sm text-slate-500">Manage your educational content and explore knowledge</p>
          </div>
        </div>
      </div> */}

      {/* Subtabs Navigation */}
      <div className="flex border-b border-slate-200 shrink-0">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id as KnowledgeSubTab)}
              className={cn(
                "flex items-center gap-2 px-6 py-3 text-sm font-medium transition-all relative",
                isActive
                  ? "text-indigo-600"
                  : "text-slate-500 hover:text-slate-700 hover:bg-slate-50"
              )}
            >
              <Icon className={cn("w-4 h-4", isActive ? "text-indigo-600" : "text-slate-400")} />
              {tab.label}
              {isActive && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-600 rounded-t-full" />
              )}
            </button>
          );
        })}
      </div>

      {/* Subtab Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'dashboard' && <KnowledgeDashboardView files={files} />}
        {activeTab === 'upload' && <LibraryView files={files} setFiles={setFiles} />}
        {activeTab === 'explorer' && <SearchView onNavigate={onNavigate} files={files} />}
      </div>
    </div>
  );
}
