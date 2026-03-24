import { useState } from 'react'
import { ChevronDown, ChevronUp, Hash } from 'lucide-react'

function MetadataSection({ citation }) {
  return (
    <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-600 space-y-2 bg-slate-50 rounded-lg p-3">
      <div className="flex justify-between items-start">
        <span className="font-semibold text-slate-700">Filename:</span>
        <span className="text-right ml-4 break-words max-w-[60%]">{citation.filename}</span>
      </div>
      <div className="flex justify-between items-start">
        <span className="font-semibold text-slate-700">Hybrid Score:</span>
        <span className="text-right ml-4">{citation.score?.toFixed(4) || 'N/A'}</span>
      </div>

      {/* Uniform Metadata (all chunk types) */}
      {citation.metadata && (
        <div className="border-t border-indigo-200 pt-2 mt-2">
          <div className="font-semibold text-indigo-700 mb-1 flex items-center space-x-1">
            <span>{citation.metadata.document_type === 'media' ? '📹' : '📄'}</span>
            <span>{citation.metadata.document_type === 'media' ? 'Media Info' : 'Document Info'}</span>
          </div>
          {citation.metadata.content_type && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">Content Type:</span>
              <span className="text-right ml-4 font-mono text-indigo-600">{citation.metadata.content_type}</span>
            </div>
          )}
          {citation.metadata.original_file && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">Original File:</span>
              <span className="text-right ml-4 break-words max-w-[60%]">{citation.metadata.original_file}</span>
            </div>
          )}
          {citation.metadata.original_file_format && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">Format:</span>
              <span className="text-right ml-4 font-mono">{citation.metadata.original_file_format}</span>
            </div>
          )}
          {citation.metadata.current_format && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">Current Format:</span>
              <span className="text-right ml-4 font-mono">{citation.metadata.current_format}</span>
            </div>
          )}
          {citation.metadata.uploaded_timestamp && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">Processed:</span>
              <span className="text-right ml-4 text-slate-500">{new Date(citation.metadata.uploaded_timestamp).toLocaleString()}</span>
            </div>
          )}
          {citation.metadata.chunk_index != null && citation.metadata.total_chunks != null && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">Chunk:</span>
              <span className="text-right ml-4 font-mono">{citation.metadata.chunk_index + 1} / {citation.metadata.total_chunks}</span>
            </div>
          )}
          {/* Media-specific fields */}
          {citation.metadata.start_time != null && citation.metadata.end_time != null && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">Time Range:</span>
              <span className="text-right ml-4 font-mono">
                {new Date(citation.metadata.start_time * 1000).toISOString().substr(14, 5)} – {new Date(citation.metadata.end_time * 1000).toISOString().substr(14, 5)}
              </span>
            </div>
          )}
          {citation.metadata.duration != null && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">Duration:</span>
              <span className="text-right ml-4 font-mono">{citation.metadata.duration.toFixed(1)}s</span>
            </div>
          )}
          {citation.metadata.num_associated_frames > 0 && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">Frames:</span>
              <span className="text-right ml-4">{citation.metadata.num_associated_frames} associated</span>
            </div>
          )}
          {citation.metadata.uniform_metadata_version && (
            <div className="flex justify-between items-start mt-1 opacity-50">
              <span className="text-slate-500">Schema Version:</span>
              <span className="text-right ml-4 font-mono text-slate-400">v{citation.metadata.uniform_metadata_version}</span>
            </div>
          )}
        </div>
      )}

      {citation.retrieval_info && (
        <div className="border-t border-slate-200 pt-2 mt-2">
          <div className="font-semibold text-slate-700 mb-1">Raw Scores:</div>
          {citation.retrieval_info.bm25_score !== null && citation.retrieval_info.bm25_score !== undefined && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">BM25 (raw):</span>
              <span className="text-right ml-4 font-mono">{citation.retrieval_info.bm25_score?.toFixed(4) || 'N/A'}</span>
            </div>
          )}
          {citation.retrieval_info.bm25_score_normalized !== null && citation.retrieval_info.bm25_score_normalized !== undefined && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">BM25 (normalized):</span>
              <span className="text-right ml-4 font-mono">{citation.retrieval_info.bm25_score_normalized?.toFixed(4) || 'N/A'}</span>
            </div>
          )}
          {citation.retrieval_info.dense_score !== null && citation.retrieval_info.dense_score !== undefined && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">Dense (raw):</span>
              <span className="text-right ml-4 font-mono">{citation.retrieval_info.dense_score?.toFixed(4) || 'N/A'}</span>
            </div>
          )}
          {citation.retrieval_info.bm25_rank && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">BM25 Rank:</span>
              <span className="text-right ml-4">#{citation.retrieval_info.bm25_rank}</span>
            </div>
          )}
          {citation.retrieval_info.dense_rank && (
            <div className="flex justify-between items-start mt-1">
              <span className="text-slate-600">Dense Rank:</span>
              <span className="text-right ml-4">#{citation.retrieval_info.dense_rank}</span>
            </div>
          )}
        </div>
      )}
      <div className="flex justify-between items-start">
        <span className="font-semibold text-slate-700">Citation ID:</span>
        <span className="font-mono text-right ml-4">{citation.id}</span>
      </div>
    </div>
  )
}

export default function CitationCard({ citationKey, citation, expanded, onToggle, metadataExpanded, onToggleMetadata, contentExpanded, onExpandContent }) {
  return (
    <div
      id={citation.id}
      className="border border-sky-100 rounded-xl overflow-hidden hover:shadow-md transition-all duration-200 bg-white"
    >
      <button
        onClick={(e) => { e.stopPropagation(); onToggle(citationKey) }}
        className="w-full p-4 flex items-center justify-between bg-sky-50 hover:bg-sky-100 transition-colors"
      >
        <div className="flex items-center space-x-3 flex-1 text-left">
          <span className="px-3 py-1 bg-sky-500 text-white rounded-lg font-semibold text-sm flex-shrink-0">
            {citationKey}
          </span>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-slate-800 text-sm truncate">{citation.filename}</p>
            <p className="text-xs text-slate-500 mt-1">Score: {citation.score?.toFixed(4) || 'N/A'}</p>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="w-5 h-5 text-slate-400 flex-shrink-0" />
        ) : (
          <ChevronDown className="w-5 h-5 text-slate-400 flex-shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="p-4 bg-white border-t border-sky-100">
          {/* Content Preview/Full */}
          <div className="mb-4">
            {(() => {
              const fullText = citation.full_text || citation.text || ''
              const previewText = citation.text || ''
              const hasMoreContent = (citation.full_text && citation.full_text.length > previewText.length) ||
                (fullText.length > 200 && previewText.length <= 200) ||
                (previewText.includes('...') && citation.full_text)

              if (contentExpanded || !hasMoreContent) {
                return (
                  <p className="text-slate-700 text-sm whitespace-pre-wrap leading-relaxed">{fullText}</p>
                )
              } else {
                return (
                  <div>
                    <p className="text-slate-700 text-sm whitespace-pre-wrap leading-relaxed">{previewText}</p>
                    <button
                      onClick={(e) => { e.stopPropagation(); onExpandContent(citationKey) }}
                      className="mt-3 text-sky-600 hover:text-sky-700 text-sm font-semibold flex items-center space-x-2 px-3 py-1.5 rounded-lg hover:bg-sky-50 transition-colors border border-sky-200 bg-white"
                    >
                      <span>View More Content</span>
                      <ChevronDown className="w-4 h-4" />
                    </button>
                  </div>
                )
              }
            })()}
          </div>

          {/* Metadata Toggle */}
          <div className="border-t border-slate-200 pt-3 mt-3">
            <button
              onClick={(e) => { e.stopPropagation(); onToggleMetadata(citationKey) }}
              className="w-full flex items-center justify-between text-sm text-slate-600 hover:text-slate-800 py-2.5 px-3 rounded-lg hover:bg-slate-50 transition-colors border border-slate-200 hover:border-sky-300 bg-white"
            >
              <span className="font-semibold flex items-center space-x-2">
                <Hash className="w-4 h-4 text-sky-500" />
                <span>View Metadata</span>
              </span>
              {metadataExpanded ? (
                <ChevronUp className="w-4 h-4 text-slate-500" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-500" />
              )}
            </button>
            {metadataExpanded && <MetadataSection citation={citation} />}
          </div>
        </div>
      )}
    </div>
  )
}
