import React, { useState, useEffect } from 'react';
import {
  Search,
  FileText,
  MessageSquare,
  RefreshCw,
  Database
} from 'lucide-react';
import { cn } from '../lib/utils';
import { ViewType, FileItem } from '../App';

interface SearchViewProps {
  onNavigate: (view: ViewType) => void;
  files: FileItem[];
}

export default function SearchView({ onNavigate, files }: SearchViewProps) {
  const [selectedModel, setSelectedModel] = useState('Gemini 1.5 Flash');
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [showResults, setShowResults] = useState(true);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);

  // Load recent searches from local storage on mount
  useEffect(() => {
    const saved = localStorage.getItem('recentSearches');
    if (saved) {
      try {
        setRecentSearches(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to parse recent searches', e);
      }
    }
  }, []);

  const saveRecentSearch = (searchQuery: string) => {
    const updated = [searchQuery, ...recentSearches.filter(q => q !== searchQuery)].slice(0, 5);
    setRecentSearches(updated);
    localStorage.setItem('recentSearches', JSON.stringify(updated));
  };

  const removeRecentSearch = (searchQuery: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = recentSearches.filter(q => q !== searchQuery);
    setRecentSearches(updated);
    localStorage.setItem('recentSearches', JSON.stringify(updated));
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    saveRecentSearch(query.trim());
    setIsSearching(true);

    setTimeout(() => {
      setIsSearching(false);
      setShowResults(true);
    }, 1500);
  };

  const handleRecentSearchClick = (searchQuery: string) => {
    setQuery(searchQuery);
    saveRecentSearch(searchQuery);
    setIsSearching(true);
    setShowResults(false);

    setTimeout(() => {
      setIsSearching(false);
      setShowResults(true);
    }, 1500);
  };

  const totalFiles = files.length;

  const scrollToChunk = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      element.classList.add('ring-2', 'ring-blue-500', 'ring-offset-2');
      setTimeout(() => {
        element.classList.remove('ring-2', 'ring-blue-500', 'ring-offset-2');
      }, 2000);
    }
  };

  return (
    <div className="max-w-5xl mx-auto h-full flex flex-col space-y-6 pb-12">
      {/* Configuration Section */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm shrink-0 space-y-4">
        <div className="grid grid-cols-1 gap-4">
          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">AI Model (Generation)</label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-slate-700 font-medium flex items-center justify-between cursor-pointer hover:border-sky-300 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 appearance-none"
            >
              <option value="Gemini 1.5 Flash">Gemini 1.5 Flash (Default)</option>
              <option value="Gemini 1.5 Pro">Gemini 1.5 Pro</option>
              <option value="Gemma 2 9B">Gemma 2 9B</option>
              <option value="Gemma 2 27B">Gemma 2 27B</option>
              <option value="Claude 3.5 Sonnet">Claude 3.5 Sonnet</option>
              <option value="GPT-4o">GPT-4o</option>
            </select>
          </div>
        </div>
      </div>

      {/* Query Input Section */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm shrink-0">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center text-blue-600">
            <MessageSquare className="w-5 h-5 fill-blue-600/20" />
          </div>
          <label className="text-sm font-bold text-slate-700 uppercase tracking-tight">Your Query</label>
        </div>
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="relative">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your question here..."
              className="w-full px-4 py-4 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-lg min-h-[120px] resize-none"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap gap-2 flex-1">
              {[
                "What is Retrieval-Augmented Generation (RAG)?",
                "How does RAG improve AI accuracy?",
                "What are the key components of a RAG system?"
              ].map((q, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setQuery(q)}
                  className="px-3 py-1.5 rounded-full border border-slate-200 hover:border-blue-300 hover:bg-blue-50 transition-all text-[11px] font-medium text-slate-500 hover:text-blue-600"
                >
                  {q}
                </button>
              ))}
            </div>

            <button
              type="submit"
              disabled={!query.trim() || isSearching}
              className="px-6 py-2.5 bg-blue-600 text-white rounded-xl font-bold hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-md shrink-0"
            >
              {isSearching ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Search className="w-4 h-4" />
              )}
              Ask
            </button>
          </div>
        </form>
      </div>

      {/* Results Area */}
      {showResults && !isSearching && (
        <div className="space-y-6">
          {/* AI Response */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2 bg-slate-50/50">
              <div className="w-2.5 h-2.5 rounded-full bg-blue-600 shadow-[0_0_8px_rgba(37,99,235,0.5)]"></div>
              <h3 className="font-bold text-slate-800 uppercase tracking-tight text-sm">AI Response</h3>
            </div>
            <div className="p-8">
              <div className="prose prose-slate max-w-none text-slate-700 leading-relaxed mb-8">
                <p>
                  Retrieval-Augmented Generation (RAG) is a technique that enhances Large Language Models (LLMs) by providing them with relevant external data <span onClick={() => scrollToChunk('chunk-1')} className="text-blue-600 font-bold cursor-pointer hover:underline">[1]</span>. This process involves retrieving documents from a knowledge base <span onClick={() => scrollToChunk('chunk-2')} className="text-blue-600 font-bold cursor-pointer hover:underline">[2]</span> and using them as context for the model's response <span onClick={() => scrollToChunk('chunk-3')} className="text-blue-600 font-bold cursor-pointer hover:underline">[3]</span>. RAG significantly reduces hallucinations and ensures that the AI provides up-to-date information based on specific datasets <span onClick={() => scrollToChunk('chunk-1')} className="text-blue-600 font-bold cursor-pointer hover:underline">[1]</span>, <span onClick={() => scrollToChunk('chunk-2')} className="text-blue-600 font-bold cursor-pointer hover:underline">[2]</span>.
                </p>
              </div>

              <div className="flex items-center gap-4 mb-8 text-sm">
                <span className="text-slate-400 font-medium">Citations:</span>
                <div className="flex gap-2">
                  {[1, 2, 3].map(n => (
                    <span
                      key={n}
                      onClick={() => scrollToChunk(`chunk-${n}`)}
                      className="text-blue-600 font-bold cursor-pointer hover:underline"
                    >
                      [{n}]
                    </span>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 py-4 border-t border-slate-100">
                {[
                  { label: 'Model', value: selectedModel, color: 'text-fuchsia-600' },
                  { label: 'Input', value: '12,877 tokens' },
                  { label: 'Output', value: '143 tokens' },
                  { label: 'Cost', value: '$0.000527', color: 'text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded' },
                  { label: 'Retrieval', value: '2502.9 ms' },
                  { label: 'Generation', value: '2101.2 ms' },
                  { label: 'Total', value: '4604.2 ms' }
                ].map((stat, i) => (
                  <div key={i} className="flex flex-col gap-1">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{stat.label}</span>
                    <span className={cn("text-xs font-bold whitespace-nowrap", stat.color || "text-slate-700")}>{stat.value}</span>
                  </div>
                ))}
              </div>

            </div>
          </div>

          {/* Matching Chunks */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center text-blue-600">
                <Database className="w-5 h-5 fill-blue-600/20" />
              </div>
              <h3 className="font-bold text-slate-800 uppercase tracking-tight text-sm">Matching Chunks (13 Found)</h3>
            </div>

            <div className="space-y-3">
              {[
                { id: 'chunk-1', name: 'Introduction to RAG.pdf', score: '0.95', text: 'RAG combines the power of pre-trained language models with a retrieval mechanism that accesses a large corpus of documents.' },
                { id: 'chunk-2', name: 'Vector Database Basics.pdf', score: '0.88', text: 'Vector databases store document embeddings, allowing for efficient similarity search during the retrieval phase of RAG.' },
                { id: 'chunk-3', name: 'Prompt Engineering for RAG.pdf', score: '0.82', text: 'Effective prompt engineering is crucial for guiding the LLM to use the retrieved context accurately and concisely.' }
              ].map((chunk, i) => (
                <div
                  key={i}
                  id={chunk.id}
                  className="bg-white rounded-xl border border-slate-200 p-4 flex flex-col gap-3 hover:border-blue-300 transition-all group cursor-pointer"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <FileText className="w-5 h-5 text-slate-400" />
                      <span className="font-medium text-slate-700">{chunk.name}</span>
                      <span className="text-[10px] font-bold px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full uppercase tracking-wider">Score: {chunk.score}</span>
                    </div>
                    <button className="text-xs font-bold text-blue-600 hover:underline">View More</button>
                  </div>
                  <p className="text-xs text-slate-500 italic line-clamp-2">"{chunk.text}"</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
