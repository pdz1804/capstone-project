import React, { useState, useEffect } from 'react';
import { ArrowRight, AlertCircle, Eye, ChevronDown, ChevronUp } from 'lucide-react';
import { FileItem } from '../App';

interface StageInfo {
  [key: string]: {
    label: string;
    color: 'sky' | 'cyan' | 'blue' | 'indigo';
    step: number;
  };
}

type StageTone = {
  card: string;
  detail: string;
  dot: string;
};

interface ProcessingPipelineProps {
  files: FileItem[];
  processingStats?: Record<string, any>;
}

const stageInfo: StageInfo = {
  stage1_normalized: { label: 'Normalized', color: 'sky', step: 1 },
  stage2_extracted: { label: 'Media Extract', color: 'cyan', step: 2 },
  stage3_docling: { label: 'Docling', color: 'blue', step: 3 },
  stage4_rag_ready: { label: 'RAG Ready', color: 'indigo', step: 4 },
};

export const ProcessingPipeline: React.FC<ProcessingPipelineProps> = ({ files, processingStats }) => {
  const [processedFilter, setProcessedFilter] = useState<string>('all');
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [expandedStages, setExpandedStages] = useState<Record<string, boolean>>({});

  const stageTone: Record<'sky' | 'cyan' | 'blue' | 'indigo', StageTone> = {
    sky: {
      card: 'bg-sky-100 text-sky-700 border-sky-200',
      detail: 'bg-sky-50 border-sky-200 text-sky-800',
      dot: 'bg-sky-200',
    },
    cyan: {
      card: 'bg-cyan-100 text-cyan-700 border-cyan-200',
      detail: 'bg-cyan-50 border-cyan-200 text-cyan-800',
      dot: 'bg-cyan-200',
    },
    blue: {
      card: 'bg-blue-100 text-blue-700 border-blue-200',
      detail: 'bg-blue-50 border-blue-200 text-blue-800',
      dot: 'bg-blue-200',
    },
    indigo: {
      card: 'bg-indigo-100 text-indigo-700 border-indigo-200',
      detail: 'bg-indigo-50 border-indigo-200 text-indigo-800',
      dot: 'bg-indigo-200',
    },
  };

  // Group files by status
  const indexedFiles = files.filter(f => f.status === 'indexed');
  const processedFiles = files.filter(f => f.status === 'processed');
  const processingFiles = files.filter(f => f.status === 'processing');
  const uploadedFiles = files.filter(f => f.status === 'uploaded' || f.status === 'processed');
  const failedFiles = files.filter(f => f.status === 'failed');

  // Get stage counts from processingStats or calculate from files
  const stageCounts: Record<string, number> = processingStats?.stage_totals || {
    stage1_normalized: files.length - uploadedFiles.length - failedFiles.length,
    stage2_extracted: Math.max(0, Math.floor((files.length - uploadedFiles.length - failedFiles.length) * 0.8)),
    stage3_docling: Math.max(0, Math.floor((files.length - uploadedFiles.length - failedFiles.length) * 0.6)),
    stage4_rag_ready: indexedFiles.length,
  };

  // Filter documents based on selected filter
  const filteredFiles = processedFilter === 'all'
    ? files
    : processedFilter === 'indexed'
      ? indexedFiles
      : processedFilter === 'processed'
        ? processedFiles
        : processedFilter === 'processing'
          ? processingFiles
          : processedFilter === 'uploaded'
            ? uploadedFiles
            : failedFiles;

  const selectedFile = files.find(f => f.id === selectedDocId) || (filteredFiles.length > 0 ? filteredFiles[0] : null);

  // Toggle stage expansion
  const toggleStage = (stage: string) => {
    setExpandedStages(prev => ({
      ...prev,
      [stage]: !prev[stage]
    }));
  };

  return (
    <div className="space-y-6">
      {/* Stage Progress Visualization */}
      <div className="bg-white rounded-xl shadow-[0_16px_30px_-24px_rgba(14,165,233,0.5)] border border-sky-100 p-6">
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-slate-800">Processing Pipeline</h3>
          <p className="text-xs text-slate-500 mt-1 leading-relaxed">
            Documents flow through stages: <code className="bg-slate-100 px-1 rounded font-mono text-[11px]">normalized</code>
            {' → '}<code className="bg-slate-100 px-1 rounded font-mono text-[11px]">rag_ready</code>
          </p>
        </div>

        {/* Stage Cards with Progress */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          {Object.entries(stageInfo).map(([stageKey, info]) => {
            const count = stageCounts[stageKey] || 0;
            const tone = stageTone[info.color];

            return (
              <div key={stageKey} className={`${tone.card} border p-4 rounded-xl text-center relative`}>
                <div className="text-3xl font-bold mb-1">{count}</div>
                <div className="text-xs font-medium">{info.label}</div>
                {info.step < 4 && (
                  <ArrowRight className="hidden sm:block absolute -right-5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-300" />
                )}
              </div>
            );
          })}
        </div>

        {/* Filter Buttons */}
        <div className="flex items-center space-x-2 flex-wrap gap-2 mb-6">
          <span className="text-sm font-medium text-slate-600">Filter by status:</span>
          {[
            { id: 'all', label: 'All', count: files.length },
            { id: 'indexed', label: 'Indexed', count: indexedFiles.length },
            { id: 'processed', label: 'Processed', count: processedFiles.length },
            { id: 'processing', label: 'Processing', count: processingFiles.length },
            { id: 'uploaded', label: 'Not Indexed', count: uploadedFiles.length },
            { id: 'failed', label: 'Failed', count: failedFiles.length },
          ].map(filter => (
            <button
              key={filter.id}
              onClick={() => setProcessedFilter(filter.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${processedFilter === filter.id
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'bg-white text-slate-600 border border-sky-100 hover:bg-sky-50'
                }`}
            >
              {filter.label} ({filter.count})
            </button>
          ))}
        </div>

        {filteredFiles.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Document List - Left Side */}
            <div className="lg:col-span-4 space-y-2 max-h-[min(560px,70vh)] overflow-y-auto pr-2">
              <p className="text-sm font-semibold text-slate-600 mb-2">Your documents</p>
              {filteredFiles.map(file => {
                const isActive = selectedFile?.id === file.id;
                return (
                  <button
                    key={file.id}
                    onClick={() => setSelectedDocId(file.id)}
                    className={`w-full text-left p-4 rounded-xl border transition-all ${isActive
                        ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-300 shadow-sm'
                        : 'border-slate-200 bg-white hover:border-sky-200 hover:shadow-sm'
                      }`}
                  >
                    <p className="font-semibold text-slate-800 truncate">{file.name}</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {file.type} • {file.size}
                    </p>
                    <div className="flex flex-wrap gap-1 mt-2">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-medium ${file.status === 'indexed'
                            ? 'bg-green-100 text-green-800'
                            : file.status === 'processing'
                              ? 'bg-yellow-100 text-yellow-800'
                              : file.status === 'failed'
                                ? 'bg-red-100 text-red-800'
                                : 'bg-slate-100 text-slate-800'
                          }`}
                      >
                        {file.status.charAt(0).toUpperCase() + file.status.slice(1)}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Document Details - Right Side */}
            <div className="lg:col-span-8 min-h-[320px]">
              {selectedFile ? (
                <div className="space-y-5 bg-white p-6 rounded-lg border border-sky-100 shadow-[0_10px_24px_-20px_rgba(14,165,233,0.45)]">
                  <div className="flex items-center justify-between gap-2 border-b border-sky-100 pb-3">
                    <h4 className="text-lg font-bold text-slate-800 truncate">{selectedFile.name}</h4>
                    <span className="text-sm text-slate-500 shrink-0">{selectedFile.type.toUpperCase()}</span>
                  </div>

                  {/* File Info */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-sky-50 p-3 rounded-lg border border-sky-100">
                      <p className="text-xs text-sky-600 font-medium">Size</p>
                      <p className="text-lg font-bold text-sky-700">{selectedFile.size}</p>
                    </div>
                    <div className="bg-blue-50 p-3 rounded-lg border border-blue-100">
                      <p className="text-xs text-blue-600 font-medium">Upload Date</p>
                      <p className="text-lg font-bold text-blue-700">{selectedFile.date}</p>
                    </div>
                  </div>

                  {/* Processing Stages */}
                  <div className="space-y-2">
                    <h5 className="text-sm font-semibold text-slate-700">Processing Stages</h5>
                    {Object.entries(stageInfo).map(([stageKey, info]) => {
                      const isProcessed = selectedFile.status === 'indexed' ||
                        (stageKey === 'stage1_normalized' && selectedFile.status !== 'uploaded');

                      return (
                        <button
                          key={stageKey}
                          onClick={() => toggleStage(stageKey)}
                          className={`w-full text-left p-3 rounded-lg border transition-all ${isProcessed
                              ? stageTone[info.color].detail
                              : 'bg-slate-50 border-slate-200 text-slate-500'
                            }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2">
                              <div
                                className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${isProcessed ? stageTone[info.color].dot : 'bg-slate-200'
                                  }`}
                              >
                                {isProcessed ? '✓' : '○'}
                              </div>
                              <span className="text-sm font-medium">{info.label}</span>
                            </div>
                            {expandedStages[stageKey] ? (
                              <ChevronUp className="w-4 h-4" />
                            ) : (
                              <ChevronDown className="w-4 h-4" />
                            )}
                          </div>
                          {expandedStages[stageKey] && (
                            <p className="text-xs mt-2 text-slate-600">
                              {stageKey === 'stage1_normalized' && 'Converting to standard format (PDF/Markdown)'}
                              {stageKey === 'stage2_extracted' && 'Extracting media files (video/audio)'}
                              {stageKey === 'stage3_docling' && 'Running OCR, VLM, and ASR analysis'}
                              {stageKey === 'stage4_rag_ready' && 'Creating chunks and indexing in Qdrant'}
                            </p>
                          )}
                        </button>
                      );
                    })}
                  </div>

                  {/* Storage Path */}
                  <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                    <p className="text-xs text-slate-600 font-mono break-all">
                      <span className="font-semibold">Path:</span> {selectedFile.storagePath || 'N/A'}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-slate-400">
                  <AlertCircle className="w-10 h-10 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No document selected</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="text-center py-12 text-slate-400">
            <AlertCircle className="w-12 h-12 mx-auto mb-3 opacity-20" />
            <p>No documents in this view</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProcessingPipeline;
