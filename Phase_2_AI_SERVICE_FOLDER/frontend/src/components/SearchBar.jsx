import { Search, Loader2, Sparkles } from 'lucide-react'

export default function SearchBar({ query, setQuery, onSearch, searchLoading }) {
  return (
    <div className="glass-strong rounded-3xl card-shadow p-10">
      <div className="flex items-center space-x-3 mb-8">
        <div className="w-12 h-12 bg-sky-500 rounded-2xl flex items-center justify-center shadow-lg shadow-sky-200/50">
          <Search className="w-6 h-6 text-white" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Query Knowledge Base</h2>
          <p className="text-sm text-slate-500 mt-0.5">Search across your indexed documents</p>
        </div>
      </div>
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onSearch()}
            placeholder="Ask a question about your documents..."
            className="w-full px-6 py-4 bg-white border-2 border-slate-200 rounded-2xl focus:outline-none focus:ring-4 focus:ring-sky-200/50 focus:border-sky-400 text-slate-700 placeholder-slate-400 font-medium transition-all duration-200 shadow-sm"
          />
          <div className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300">
            <Search className="w-5 h-5" />
          </div>
        </div>
        <button
          onClick={onSearch}
          disabled={searchLoading || !query.trim()}
          className="px-10 py-4 bg-sky-500 text-white rounded-2xl font-bold hover:shadow-xl hover:shadow-sky-200/50 disabled:opacity-50 flex items-center space-x-2.5 transition-all duration-300 hover:scale-105 active:scale-95 disabled:hover:scale-100"
        >
          {searchLoading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Searching...</span>
            </>
          ) : (
            <>
              <Search className="w-5 h-5" />
              <span>Search</span>
            </>
          )}
        </button>
      </div>
    </div>
  )
}
