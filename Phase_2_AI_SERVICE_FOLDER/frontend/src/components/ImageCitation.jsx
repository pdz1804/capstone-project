import { Image, ChevronDown, ChevronUp, Hash } from 'lucide-react'

export default function ImageCitation({ citationKey, citation, expanded, onToggle, metadataExpanded, onToggleMetadata, apiBase }) {
  return (
    <div
      id={citation.id}
      className="border border-indigo-100 rounded-xl overflow-hidden hover:shadow-lg transition-all duration-200 bg-white"
    >
      <button
        onClick={(e) => { e.stopPropagation(); onToggle(citationKey) }}
        className="w-full"
      >
        <div className="aspect-[4/3] bg-indigo-50 relative overflow-hidden">
          <img
            src={`${apiBase}/pdf-page-image?pdf_name=${encodeURIComponent(citation.source)}&page=${citation.page}`}
            alt={`Page ${citation.page} of ${citation.source}`}
            className="w-full h-full object-cover"
            onError={(e) => {
              e.target.style.display = 'none'
              if (e.target.nextSibling) {
                e.target.nextSibling.style.display = 'flex'
              }
            }}
          />
          <div className="hidden items-center justify-center w-full h-full absolute inset-0">
            <div className="text-center">
              <Image className="w-10 h-10 text-indigo-300 mb-2 mx-auto" />
              <p className="text-sm text-indigo-400 font-medium">Page {citation.page}</p>
            </div>
          </div>
          <div className="absolute top-2 right-2 px-2 py-1 bg-indigo-500 text-white rounded text-xs font-semibold">
            {citationKey}
          </div>
        </div>
      </button>

      {expanded && (
        <div className="p-4 bg-white border-t border-indigo-100">
          <div className="mb-3">
            <p className="text-sm font-medium text-slate-800 mb-1">{citation.source}</p>
            <p className="text-xs text-slate-500">Page {citation.page}</p>
          </div>

          {/* Metadata Toggle */}
          <div className="border-t border-slate-200 pt-3 mt-3">
            <button
              onClick={(e) => { e.stopPropagation(); onToggleMetadata(citationKey) }}
              className="w-full flex items-center justify-between text-sm text-slate-600 hover:text-slate-800 py-2.5 px-3 rounded-lg hover:bg-slate-50 transition-colors border border-slate-200 hover:border-indigo-300"
            >
              <span className="font-semibold flex items-center space-x-2">
                <Hash className="w-4 h-4 text-indigo-500" />
                <span>View Metadata</span>
              </span>
              {metadataExpanded ? (
                <ChevronUp className="w-4 h-4 text-slate-500" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-500" />
              )}
            </button>

            {metadataExpanded && (
              <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-600 space-y-2 bg-slate-50 rounded-lg p-3">
                <div className="flex justify-between items-start">
                  <span className="font-semibold text-slate-700">Source:</span>
                  <span className="text-right ml-4 truncate max-w-[60%]">{citation.source}</span>
                </div>
                <div className="flex justify-between items-start">
                  <span className="font-semibold text-slate-700">Page:</span>
                  <span className="text-right ml-4">{citation.page}</span>
                </div>
                <div className="flex justify-between items-start">
                  <span className="font-semibold text-slate-700">Score:</span>
                  <span className="text-right ml-4">{citation.score?.toFixed(4) || 'N/A'}</span>
                </div>
                <div className="flex justify-between items-start">
                  <span className="font-semibold text-slate-700">Citation ID:</span>
                  <span className="font-mono text-right ml-4">{citation.id}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
