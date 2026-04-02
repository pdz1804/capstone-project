import React, { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Search, MessageSquare, RefreshCw, Database, Clock3, Sigma } from 'lucide-react';
import { FileItem } from '../App';
import { getGenerationModels, getSearchImagePreview, searchRag } from '../api/ragApi';

interface SearchViewProps {
  files: FileItem[];
}

type SearchMode = 'retrieval_only' | 'retrieval_generation';
type SearchScope = 'text' | 'image' | 'both';
type RetrieverType = 'bm25' | 'dense' | 'hybrid';

type CitationItem = {
  key: string;
  id?: string;
  type: 'text' | 'image';
  text?: string;
  full_text?: string;
  filename?: string;
  source?: string;
  source_path?: string;
  storage_uri?: string;
  score?: number;
  metadata?: Record<string, unknown>;
  page?: number;
};

export default function SearchView({ files }: SearchViewProps) {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [contents, setContents] = useState<Record<string, unknown>>({});
  const [selectedCitationId, setSelectedCitationId] = useState<string | null>(null);
  const [expandedChunkIds, setExpandedChunkIds] = useState<Record<string, boolean>>({});
  const [imagePreviewUrls, setImagePreviewUrls] = useState<Record<string, string>>({});
  const [imagePreviewLoading, setImagePreviewLoading] = useState<Record<string, boolean>>({});
  const [mode, setMode] = useState<SearchMode>('retrieval_generation');
  const [scope, setScope] = useState<SearchScope>('both');
  const [retrieverType, setRetrieverType] = useState<RetrieverType>('hybrid');
  const [topK, setTopK] = useState<number>(10);
  const [skipReranker, setSkipReranker] = useState<boolean>(true);
  const [showAdvancedConfig, setShowAdvancedConfig] = useState<boolean>(false);
  const [includeImagesForGeneration, setIncludeImagesForGeneration] = useState<boolean>(true);
  const [imagesForGeneration, setImagesForGeneration] = useState<number>(5);
  const [generationModel, setGenerationModel] = useState<string>('');
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [telemetry, setTelemetry] = useState<{
    steps_ms?: Record<string, number>;
    tokens?: {
      input_total?: number;
      output_total?: number;
    };
  } | null>(null);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);

  useEffect(() => {
    const saved = localStorage.getItem('recentSearches');
    if (saved) {
      try {
        setRecentSearches(JSON.parse(saved));
      } catch {
        /* ignore */
      }
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    void getGenerationModels()
      .then((data) => {
        if (!mounted) return;
        const models = (data.models || []).filter(Boolean);
        setModelOptions(models);
        if (models.length > 0) {
          setGenerationModel(models[0]);
        }
      })
      .catch(() => {
        if (!mounted) return;
        setModelOptions([]);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    return () => {
      Object.values(imagePreviewUrls).forEach((url) => URL.revokeObjectURL(url));
    };
  }, [imagePreviewUrls]);

  const saveRecentSearch = (searchQuery: string) => {
    const updated = [searchQuery, ...recentSearches.filter((q) => q !== searchQuery)].slice(0, 5);
    setRecentSearches(updated);
    localStorage.setItem('recentSearches', JSON.stringify(updated));
  };

  const removeRecentSearch = (searchQuery: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = recentSearches.filter((q) => q !== searchQuery);
    setRecentSearches(updated);
    localStorage.setItem('recentSearches', JSON.stringify(updated));
  };

  const runSearch = async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    setError(null);
    setIsSearching(true);
    setAnswer(null);
    setContents({});
    setSelectedCitationId(null);
    setExpandedChunkIds({});
    setTelemetry(null);
    saveRecentSearch(trimmed);
    try {
      const data = await searchRag({
        query: trimmed,
        top_k: showAdvancedConfig ? topK : 10,
        retriever_type: showAdvancedConfig ? retrieverType : 'hybrid',
        include_images: includeImagesForGeneration,
        images_for_generation: imagesForGeneration,
        mode,
        search_scope: showAdvancedConfig ? scope : 'text',
        generation_model: mode === 'retrieval_generation' ? generationModel || null : null,
        skip_reranker: showAdvancedConfig ? skipReranker : true,
      });
      setAnswer(data.answer || null);
      setContents((data.contents as Record<string, unknown>) || {});
      setTelemetry(data.telemetry || null);
    } catch (e: unknown) {
      const msg =
        e && typeof e === 'object' && 'response' in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || '')
          : e instanceof Error
            ? e.message
            : 'Search failed';
      setError(msg || 'Search failed');
    } finally {
      setIsSearching(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    void runSearch(query);
  };

  const handleRecentSearchClick = (searchQuery: string) => {
    setQuery(searchQuery);
    void runSearch(searchQuery);
  };

  const totalFiles = files.length;
  const citations: CitationItem[] = useMemo(() => {
    const rows = Object.entries(contents || {}).map(([key, raw]) => {
      const c = (raw || {}) as Record<string, unknown>;
      return {
        key,
        id: String(c.id || ''),
        type: (String(c.type || 'text') === 'image' ? 'image' : 'text') as 'text' | 'image',
        text: String(c.text || ''),
        full_text: String(c.full_text || ''),
        filename: String(c.filename || ''),
        source: String(c.source || ''),
        source_path: String(c.source_path || ''),
        storage_uri: String(c.storage_uri || ''),
        score: Number(c.score || 0),
        metadata: (c.metadata || {}) as Record<string, unknown>,
        page: Number(c.page || 0),
      };
    });
    return rows.sort((a, b) => a.key.localeCompare(b.key, undefined, { numeric: true }));
  }, [contents]);

  const handleCitationClick = (href: string) => {
    const target = href.replace(/^#/, '');
    setSelectedCitationId(target);
    const el = document.getElementById(target);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const toggleChunk = (id: string) => {
    setExpandedChunkIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const loadImagePreview = async (row: Record<string, unknown>, key: string) => {
    if (imagePreviewUrls[key] || imagePreviewLoading[key]) return;
    const storageUri = String(row.storage_uri || '');
    const sourcePath = String(row.source_path || '');
    const page = Number(row.page || 1);
    try {
      setImagePreviewLoading((prev) => ({ ...prev, [key]: true }));
      const { body } = await getSearchImagePreview(
        storageUri || undefined,
        storageUri ? undefined : sourcePath || undefined,
        page,
      );
      const url = URL.createObjectURL(body);
      setImagePreviewUrls((prev) => ({ ...prev, [key]: url }));
    } catch {
      // keep quiet; user can still inspect metadata
    } finally {
      setImagePreviewLoading((prev) => ({ ...prev, [key]: false }));
    }
  };

  return (
    <div className="w-full h-full flex flex-col space-y-6 pb-12">
      <div className="bg-white/90 backdrop-blur-sm rounded-2xl p-6 border border-slate-200 shadow-sm shrink-0 space-y-2">
        <p className="text-xs text-slate-500">
          Retrieval + generation use your FastAPI backend <code className="bg-slate-100 px-1 rounded">POST /api/search</code>{' '}
          (Qdrant + configured LLM). Indexed sources in workspace: <strong>{totalFiles}</strong> input file(s) listed.
        </p>
      </div>

      <div className="bg-white/90 backdrop-blur-sm rounded-2xl p-6 border border-slate-200 shadow-sm shrink-0">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center text-blue-600">
            <MessageSquare className="w-5 h-5 fill-blue-600/20" />
          </div>
          <label className="text-sm font-bold text-slate-700 uppercase tracking-tight">Your Query</label>
          <button
            type="button"
            onClick={() => setShowAdvancedConfig((v) => !v)}
            className="ml-auto text-xs px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
          >
            {showAdvancedConfig ? 'Hide config' : 'Show config'}
          </button>
        </div>
        {!showAdvancedConfig && (
          <div className="mb-4 rounded-xl border border-sky-100 bg-sky-50/70 px-4 py-3 text-sm text-sky-800">
            Default for students: <strong>Text retrieval</strong> + <strong>Hybrid</strong> + <strong>Top K = 10</strong> + <strong>Skip reranker</strong>.
          </div>
        )}
        {showAdvancedConfig && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
          <label className="text-xs text-slate-600">
            Mode
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as SearchMode)}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
            >
              <option value="retrieval_only">Retrieval only</option>
              <option value="retrieval_generation">Retrieval + generation</option>
            </select>
          </label>
          <label className="text-xs text-slate-600">
            Search scope
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value as SearchScope)}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
            >
              <option value="text">Text index only</option>
              <option value="image">Image index only</option>
              <option value="both">Both text + image</option>
            </select>
          </label>
          <label className="text-xs text-slate-600">
            Text retrieval
            <select
              value={retrieverType}
              onChange={(e) => setRetrieverType(e.target.value as RetrieverType)}
              disabled={scope === 'image'}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm disabled:opacity-50"
            >
              <option value="hybrid">Hybrid</option>
              <option value="dense">Dense (Qdrant)</option>
              <option value="bm25">BM25</option>
            </select>
          </label>
          <label className="text-xs text-slate-600">
            Top K
            <input
              type="number"
              min={1}
              max={100}
              value={topK}
              onChange={(e) => setTopK(Math.max(1, Math.min(100, Number(e.target.value || 10))))}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
            />
          </label>
          <label className="text-xs text-slate-600 flex items-end gap-2 pb-2">
            <input
              type="checkbox"
              checked={skipReranker}
              onChange={(e) => setSkipReranker(e.target.checked)}
              className="rounded border-slate-300"
            />
            Skip reranker
          </label>
          </div>
        )}
        {showAdvancedConfig && mode === 'retrieval_generation' && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
            <label className="text-xs text-slate-600">
              Generation model (AWS)
              <select
                value={generationModel}
                onChange={(e) => setGenerationModel(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              >
                {(modelOptions.length ? modelOptions : ['']).map((m) => (
                  <option key={m || 'default'} value={m}>
                    {m || 'Configured default'}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-600 flex items-end gap-2 pb-2">
              <input
                type="checkbox"
                checked={includeImagesForGeneration}
                onChange={(e) => setIncludeImagesForGeneration(e.target.checked)}
                className="rounded border-slate-300"
              />
              Include image hits in generation
            </label>
            <label className="text-xs text-slate-600">
              Images for generation
              <input
                type="number"
                min={0}
                max={20}
                value={imagesForGeneration}
                onChange={(e) => setImagesForGeneration(Math.max(0, Math.min(20, Number(e.target.value || 5))))}
                className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              />
            </label>
          </div>
        )}
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="relative">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask a question over your indexed documents…"
              className="w-full px-4 py-4 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-lg min-h-[120px] resize-none"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap gap-2 flex-1">
              {[
                'What is Retrieval-Augmented Generation (RAG)?',
                'Summarize the main topics in my materials.',
                'What formulas or definitions appear in the lecture notes?',
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
              {isSearching ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              Ask
            </button>
          </div>
        </form>
      </div>

      {recentSearches.length > 0 && (
        <div className="flex flex-wrap gap-2 items-center text-sm text-slate-600">
          <span className="font-medium">Recent:</span>
          {recentSearches.map((q) => (
            <span key={q} className="inline-flex items-center gap-1 bg-slate-100 rounded-full pl-3 pr-1 py-0.5">
              <button type="button" className="hover:text-indigo-600" onClick={() => handleRecentSearchClick(q)}>
                {q.slice(0, 40)}
                {q.length > 40 ? '…' : ''}
              </button>
              <button
                type="button"
                className="text-slate-400 hover:text-red-500 px-1"
                onClick={(e) => removeRecentSearch(q, e)}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 text-red-800 text-sm px-4 py-3">{error}</div>
      )}

      {!isSearching && telemetry && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 flex items-center gap-2">
            <Clock3 className="w-4 h-4 text-sky-600" />
            <span className="text-sm text-slate-700">
              Retrieval: {(telemetry.steps_ms?.text_retrieval || 0) + (telemetry.steps_ms?.image_retrieval || 0)} ms
            </span>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 flex items-center gap-2">
            <Clock3 className="w-4 h-4 text-indigo-600" />
            <span className="text-sm text-slate-700">Generation: {telemetry.steps_ms?.generation || 0} ms</span>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 flex items-center gap-2">
            <Sigma className="w-4 h-4 text-emerald-600" />
            <span className="text-sm text-slate-700">
              Tokens in/out: {telemetry.tokens?.input_total || 0} / {telemetry.tokens?.output_total || 0}
            </span>
          </div>
        </div>
      )}

      {!isSearching && (answer != null || citations.length > 0) && (
        <div className="space-y-6">
          {answer != null && (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2 bg-slate-50/50">
                <div className="w-2.5 h-2.5 rounded-full bg-blue-600 shadow-[0_0_8px_rgba(37,99,235,0.5)]" />
                <h3 className="font-bold text-slate-800 uppercase tracking-tight text-sm">Answer</h3>
              </div>
              <div className="p-8 prose prose-slate max-w-none text-slate-700 leading-7 prose-headings:my-3 prose-p:my-2 prose-li:my-1">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: ({ children }) => <h1 className="text-3xl font-bold text-slate-900 mt-2 mb-4">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-2xl font-semibold text-slate-900 mt-6 mb-3">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-xl font-semibold text-slate-900 mt-5 mb-2">{children}</h3>,
                    p: ({ children }) => <p className="text-base leading-7 text-slate-700 my-2">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-6 my-3 space-y-1">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-6 my-3 space-y-1">{children}</ol>,
                    li: ({ children }) => <li className="text-base leading-7 text-slate-700">{children}</li>,
                    table: ({ children }) => <table className="w-full border-collapse text-sm my-4">{children}</table>,
                    th: ({ children }) => <th className="border border-slate-300 bg-slate-50 px-2 py-1 text-left">{children}</th>,
                    td: ({ children }) => <td className="border border-slate-300 px-2 py-1 align-top">{children}</td>,
                    a: ({ href, children }) => {
                      const link = String(href || '');
                      if (link.startsWith('#')) {
                        return (
                          <button
                            type="button"
                            onClick={() => handleCitationClick(link)}
                            className="text-blue-700 hover:text-blue-900 underline underline-offset-2"
                          >
                            {children}
                          </button>
                        );
                      }
                      return (
                        <a href={link} target="_blank" rel="noreferrer" className="text-blue-700 hover:text-blue-900">
                          {children}
                        </a>
                      );
                    },
                  }}
                >
                  {answer}
                </ReactMarkdown>
              </div>
            </div>
          )}

          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center text-emerald-600">
                <Database className="w-5 h-5 fill-emerald-600/20" />
              </div>
              <h3 className="font-bold text-slate-800 uppercase tracking-tight text-sm">Citations + chunks</h3>
            </div>
            <div className="space-y-3">
              {citations.map((c) => {
                const cid = c.id || '';
                const active = !!cid && selectedCitationId === cid;
                const longText = c.full_text || c.text || '';
                const expanded = !!expandedChunkIds[cid];
                const metadataForDisplay =
                  c.metadata && Object.keys(c.metadata).length > 0
                    ? c.metadata
                    : {
                        source: c.source || '',
                        source_path: c.source_path || '',
                        storage_uri: c.storage_uri || '',
                        page: c.page || 0,
                        score: c.score ?? 0,
                      };
                return (
                  <div
                    id={cid || undefined}
                    key={`${c.key}-${cid}`}
                    className={`rounded-xl border p-4 transition-all ${active ? 'border-blue-400 bg-blue-50/60' : 'border-slate-200 bg-white'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-800">
                        {c.key} · {c.type === 'text' ? (c.filename || c.source || 'chunk') : `${c.source || 'image'} (page ${c.page || '-'})`}
                      </p>
                      {typeof c.score === 'number' && !Number.isNaN(c.score) && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                          {c.score.toFixed(4)}
                        </span>
                      )}
                    </div>
                    {c.type === 'text' ? (
                      <>
                        <p className="mt-2 text-sm text-slate-700">
                          {(expanded ? longText : (c.text || '')).slice(0, expanded ? undefined : 500)}
                          {!expanded && (longText || '').length > 500 ? '...' : ''}
                        </p>
                        {(longText || '').length > 500 && (
                          <button
                            type="button"
                            onClick={() => toggleChunk(cid)}
                            className="mt-1 text-xs text-blue-600 hover:text-blue-800"
                          >
                            {expanded ? 'Load less' : 'Load more...'}
                          </button>
                        )}
                      </>
                    ) : (
                      <div className="mt-2">
                        {!imagePreviewUrls[cid] ? (
                          <button
                            type="button"
                            disabled={!!imagePreviewLoading[cid]}
                            onClick={() =>
                              void loadImagePreview(
                                {
                                  storage_uri: c.storage_uri,
                                  source_path: c.source_path,
                                  page: c.page,
                                },
                                cid
                              )
                            }
                            className="text-xs px-2 py-1 rounded border border-indigo-200 text-indigo-700 bg-indigo-50 hover:bg-indigo-100 disabled:opacity-60"
                          >
                            {imagePreviewLoading[cid] ? 'Loading...' : 'Load image'}
                          </button>
                        ) : (
                          <img src={imagePreviewUrls[cid]} alt={c.source || 'citation image'} className="w-full max-h-80 object-contain rounded border border-slate-200 bg-slate-50" />
                        )}
                      </div>
                    )}
                    <details className="mt-2">
                      <summary className="text-xs text-slate-500 cursor-pointer">Metadata</summary>
                      <pre className="mt-2 text-[11px] bg-slate-50 border border-slate-200 rounded-lg p-2 overflow-auto">
                        {JSON.stringify(metadataForDisplay, null, 2)}
                      </pre>
                    </details>
                  </div>
                );
              })}
              {citations.length === 0 && (
                <p className="text-sm text-slate-500">No citation map returned for this run.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
