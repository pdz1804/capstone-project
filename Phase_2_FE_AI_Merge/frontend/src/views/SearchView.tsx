import React, { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { Search, MessageSquare, RefreshCw, Database, Clock3, Sigma, Copy, FileDown } from 'lucide-react';
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
  start_time?: number;
  end_time?: number;
  time_range_label?: string;
};

const SEARCH_REMARK_PLUGINS = [remarkGfm, remarkBreaks, remarkMath];
const SEARCH_REHYPE_PLUGINS = [rehypeKatex];

function formatSecondsToClock(seconds?: number): string {
  if (typeof seconds !== 'number' || Number.isNaN(seconds) || seconds < 0) return '-';
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) {
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function getCitationTimeRange(citation: CitationItem): string {
  const explicit = String(citation.time_range_label || '').trim();
  if (explicit) return explicit;

  const md = (citation.metadata || {}) as Record<string, unknown>;
  const startRaw = citation.start_time ?? Number(md.start_time ?? NaN);
  const endRaw = citation.end_time ?? Number(md.end_time ?? NaN);
  const hasStart = typeof startRaw === 'number' && !Number.isNaN(startRaw);
  const hasEnd = typeof endRaw === 'number' && !Number.isNaN(endRaw);
  if (hasStart && hasEnd) return `${formatSecondsToClock(startRaw)} - ${formatSecondsToClock(endRaw)}`;
  if (hasStart) return `from ${formatSecondsToClock(startRaw)}`;
  if (hasEnd) return `until ${formatSecondsToClock(endRaw)}`;
  return '';
}

function toDisplayDocName(raw: string): string {
  const normalized = String(raw || '').trim().replace(/\\/g, '/');
  if (!normalized) return '';
  const last = normalized.split('/').pop() || normalized;
  const clean = last.split('?')[0].split('#')[0];
  return clean.replace(/\.[a-z0-9]{1,6}$/i, '');
}

function getCitationDisplayName(citation: CitationItem): string {
  const md = (citation.metadata || {}) as Record<string, unknown>;
  const docId = String(md.doc_id || '').trim();
  if (docId) return docId;

  const fromFilename = toDisplayDocName(String(citation.filename || ''));
  if (fromFilename) return fromFilename;

  const fromSource = toDisplayDocName(String(citation.source || citation.storage_uri || citation.source_path || ''));
  if (fromSource) return fromSource;

  return citation.type === 'text' ? 'chunk' : 'image';
}

function isLikelyMediaPath(value: string): boolean {
  const v = String(value || '').toLowerCase();
  if (!v) return false;
  return ['.mp4', '.mov', '.mkv', '.webm', '.avi', '.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'].some((ext) =>
    v.includes(ext)
  );
}

function isLocalHostRuntime(): boolean {
  const host = (window?.location?.hostname || '').toLowerCase();
  return host === 'localhost' || host === '127.0.0.1' || host === '::1';
}

export default function SearchView({ files }: SearchViewProps) {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [contents, setContents] = useState<Record<string, unknown>>({});
  const [rawTextResults, setRawTextResults] = useState<Array<Record<string, unknown>>>([]);
  const [rawImageResults, setRawImageResults] = useState<Array<Record<string, unknown>>>([]);
  const [selectedCitationId, setSelectedCitationId] = useState<string | null>(null);
  const [expandedChunkIds, setExpandedChunkIds] = useState<Record<string, boolean>>({});
  const [imagePreviewUrls, setImagePreviewUrls] = useState<Record<string, string>>({});
  const [previewMediaTypes, setPreviewMediaTypes] = useState<Record<string, string>>({});
  const [imagePreviewLoading, setImagePreviewLoading] = useState<Record<string, boolean>>({});
  const [mode, setMode] = useState<SearchMode>('retrieval_generation');
  const [scope, setScope] = useState<SearchScope>('both');
  const [retrieverType, setRetrieverType] = useState<RetrieverType>('hybrid');
  const [topK, setTopK] = useState<number>(10);
  const [showAdvancedConfig, setShowAdvancedConfig] = useState<boolean>(false);
  const [includeImagesForGeneration, setIncludeImagesForGeneration] = useState<boolean>(true);
  const [imagesForGeneration, setImagesForGeneration] = useState<number>(5);
  const [generationModel, setGenerationModel] = useState<string>('');
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [copyStatus, setCopyStatus] = useState<'idle' | 'ok' | 'err'>('idle');
  const [isPreparingPdf, setIsPreparingPdf] = useState<boolean>(false);
  const [telemetry, setTelemetry] = useState<{
    steps_ms?: Record<string, number>;
    tokens?: {
      input_total?: number;
      output_total?: number;
    };
  } | null>(null);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const answerRenderRef = useRef<HTMLDivElement | null>(null);

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
    setRawTextResults([]);
    setRawImageResults([]);
    setSelectedCitationId(null);
    setExpandedChunkIds({});
    setTelemetry(null);
    setCopyStatus('idle');
    setImagePreviewUrls((prev) => {
      Object.values(prev).forEach((u) => URL.revokeObjectURL(u));
      return {};
    });
    setPreviewMediaTypes({});
    setImagePreviewLoading({});
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
      });
      setAnswer(data.answer || null);
      setContents((data.contents as Record<string, unknown>) || {});
      setRawTextResults((data.text_results as Array<Record<string, unknown>>) || []);
      setRawImageResults((data.image_results as Array<Record<string, unknown>>) || []);
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

  const handleCopyAnswer = async () => {
    const text = String(answer || '').trim();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus('ok');
      window.setTimeout(() => setCopyStatus('idle'), 1800);
    } catch {
      setCopyStatus('err');
      window.setTimeout(() => setCopyStatus('idle'), 2200);
    }
  };

  const handleDownloadAnswerPdf = () => {
    const rendered = answerRenderRef.current;
    if (!rendered) return;
    setIsPreparingPdf(true);
    try {
      const titleBase = (query || 'knowledge-explorer-answer').trim().slice(0, 80) || 'knowledge-explorer-answer';
      const safeTitle = titleBase.replace(/[\\/:*?"<>|]+/g, '-');
      const popup = window.open('', '_blank', 'width=960,height=720');
      if (!popup) {
        throw new Error('Popup blocked');
      }
      popup.document.open();
      popup.document.write(`<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>${safeTitle}</title>
    <style>
      body { font-family: "Segoe UI", Arial, sans-serif; margin: 28px; color: #0f172a; }
      h1,h2,h3 { color: #0f172a; margin: 14px 0 8px; }
      p, li { line-height: 1.65; font-size: 14px; }
      code { background: #f1f5f9; padding: 1px 4px; border-radius: 4px; }
      pre { background: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; border-radius: 8px; overflow: auto; }
      table { width: 100%; border-collapse: collapse; margin-top: 10px; }
      th, td { border: 1px solid #cbd5e1; padding: 6px; text-align: left; vertical-align: top; }
      .meta { margin-bottom: 14px; font-size: 12px; color: #475569; }
      @media print { body { margin: 16mm; } }
    </style>
  </head>
  <body>
    <h1>Knowledge Explorer Answer</h1>
    <div class="meta">Query: ${query.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
    <div>${rendered.innerHTML}</div>
  </body>
</html>`);
      popup.document.close();
      popup.focus();
      window.setTimeout(() => {
        popup.print();
      }, 180);
    } catch {
      setError('Could not open PDF export. Please allow popups and try again.');
    } finally {
      window.setTimeout(() => setIsPreparingPdf(false), 250);
    }
  };

  const totalFiles = files.length;
  const citations: CitationItem[] = useMemo(() => {
    const contentRows = Object.entries(contents || {}).map(([key, raw]) => {
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
        start_time: c.start_time != null ? Number(c.start_time) : undefined,
        end_time: c.end_time != null ? Number(c.end_time) : undefined,
        time_range_label: String(c.time_range_label || ''),
      };
    });
    if (contentRows.length > 0) {
      return contentRows.sort((a, b) => a.key.localeCompare(b.key, undefined, { numeric: true }));
    }

    const textRows: CitationItem[] = rawTextResults.map((raw, idx) => {
      const c = (raw || {}) as Record<string, unknown>;
      const md = (c.metadata || {}) as Record<string, unknown>;
      return {
        key: `[1.${idx + 1}]`,
        id: String(c.id || `retrieval-text-${idx + 1}`),
        type: 'text',
        text: String(c.text || ''),
        full_text: String(c.full_text || c.text || ''),
        filename: String(md.doc_id || c.filename || c.source || ''),
        source: String(c.source || ''),
        source_path: String(c.source_path || md.original_file || ''),
        storage_uri: String(c.storage_uri || md.storage_uri || ''),
        score: Number(c.score || 0),
        metadata: md,
        page: Number(c.page || 0),
        start_time: c.start_time != null ? Number(c.start_time) : undefined,
        end_time: c.end_time != null ? Number(c.end_time) : undefined,
        time_range_label: String(c.time_range_label || ''),
      };
    });

    const imageRows: CitationItem[] = rawImageResults.map((raw, idx) => {
      const c = (raw || {}) as Record<string, unknown>;
      return {
        key: `[2.${idx + 1}]`,
        id: String(c.id || `retrieval-image-${idx + 1}`),
        type: 'image',
        text: String(c.text || ''),
        full_text: String(c.full_text || c.text || ''),
        filename: String(c.filename || c.source || ''),
        source: String(c.source || ''),
        source_path: String(c.source_path || ''),
        storage_uri: String(c.storage_uri || ''),
        score: Number(c.score || 0),
        metadata: (c.metadata || {}) as Record<string, unknown>,
        page: Number(c.page || 0),
      };
    });

    return [...textRows, ...imageRows].sort((a, b) => a.key.localeCompare(b.key, undefined, { numeric: true }));
  }, [contents, rawTextResults, rawImageResults]);

  const citationsById = useMemo(() => {
    const map: Record<string, CitationItem> = {};
    citations.forEach((item) => {
      if (item.id) map[item.id] = item;
    });
    return map;
  }, [citations]);

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

  const loadSourcePreview = async (row: Record<string, unknown>, key: string) => {
    if (imagePreviewUrls[key] || imagePreviewLoading[key]) return;
    const storageUri = String(row.storage_uri || '');
    const sourcePath = String(row.source_path || '');
    const page = Number(row.page || 1);
    try {
      setImagePreviewLoading((prev) => ({ ...prev, [key]: true }));
      const { body, mediaType } = await getSearchImagePreview(
        storageUri || undefined,
        storageUri ? undefined : sourcePath || undefined,
        page,
      );
      const url = URL.createObjectURL(body);
      setImagePreviewUrls((prev) => ({ ...prev, [key]: url }));
      setPreviewMediaTypes((prev) => ({ ...prev, [key]: mediaType || '' }));
    } catch {
      // keep quiet; user can still inspect metadata
    } finally {
      setImagePreviewLoading((prev) => ({ ...prev, [key]: false }));
    }
  };

  function AnswerImage({ src, alt }: { src?: string; alt?: string }) {
    const rawSrc = String(src || '');
    const citationId = rawSrc.startsWith('#image-') ? rawSrc.slice(1) : '';
    const citation = citationId ? citationsById[citationId] : undefined;
    const previewUrl = citationId ? imagePreviewUrls[citationId] : '';
    const isLoading = citationId ? imagePreviewLoading[citationId] : false;

    useEffect(() => {
      if (!citationId || !citation || previewUrl || isLoading) return;
      void loadImagePreview(
        {
          storage_uri: citation.storage_uri,
          source_path: citation.source_path,
          page: citation.page,
        },
        citationId
      );
    }, [citation, citationId, isLoading, previewUrl]);

    if (citationId) {
      if (previewUrl) {
        return (
          <img
            src={previewUrl}
            alt={alt || citation?.source || 'answer image'}
            className="w-full max-h-[28rem] object-contain rounded-xl border border-sky-100 bg-sky-50/50 my-3"
          />
        );
      }
      return (
        <div className="my-3 rounded-xl border border-sky-100 bg-sky-50/50 px-4 py-3 text-sm text-slate-500">
          {isLoading ? 'Loading cited image…' : 'Image preview unavailable.'}
        </div>
      );
    }

    if (!rawSrc) return null;

    return (
      <img
        src={rawSrc}
        alt={alt || 'answer image'}
        className="w-full max-h-[28rem] object-contain rounded-xl border border-sky-100 bg-sky-50/50 my-3"
      />
    );
  }

  return (
    <div className="w-full h-full flex flex-col space-y-6 pb-12">
      <div className="bg-white/95 backdrop-blur-sm rounded-2xl p-6 border border-sky-100 shadow-[0_12px_26px_-22px_rgba(14,165,233,0.5)] shrink-0 space-y-2">
        <p className="text-xs text-slate-500">
          Retrieval + generation use your FastAPI backend <code className="bg-slate-100 px-1 rounded">POST /api/search</code>{' '}
          (Qdrant + configured LLM). Indexed sources in workspace: <strong>{totalFiles}</strong> input file(s) listed.
        </p>
      </div>

      <div className="bg-white/95 backdrop-blur-sm rounded-2xl p-6 border border-sky-100 shadow-[0_12px_26px_-22px_rgba(14,165,233,0.5)] shrink-0">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center text-blue-600">
            <MessageSquare className="w-5 h-5 fill-blue-600/20" />
          </div>
          <label className="text-sm font-bold text-slate-700 uppercase tracking-tight">Your Query</label>
          <button
            type="button"
            onClick={() => setShowAdvancedConfig((v) => !v)}
            className="ml-auto text-xs px-3 py-1.5 rounded-lg border border-sky-100 bg-sky-50/70 text-slate-700 hover:bg-sky-100/60"
          >
            {showAdvancedConfig ? 'Hide config' : 'Show config'}
          </button>
        </div>
        {!showAdvancedConfig && (
          <div className="mb-4 rounded-xl border border-sky-100 bg-sky-50/70 px-4 py-3 text-sm text-sky-800">
            Default for students: <strong>Text retrieval</strong> + <strong>Hybrid</strong> + <strong>Top K = 10</strong>.
          </div>
        )}
        {showAdvancedConfig && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
            <label className="text-xs text-slate-600">
              Mode
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as SearchMode)}
                className="mt-1 w-full rounded-lg border border-sky-100 bg-sky-50/60 px-3 py-2 text-sm"
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
                className="mt-1 w-full rounded-lg border border-sky-100 bg-sky-50/60 px-3 py-2 text-sm"
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
                className="mt-1 w-full rounded-lg border border-sky-100 bg-sky-50/60 px-3 py-2 text-sm disabled:opacity-50"
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
                className="mt-1 w-full rounded-lg border border-sky-100 bg-sky-50/60 px-3 py-2 text-sm"
              />
            </label>
          </div>
        )}
        {mode === 'retrieval_generation' && (
          <div className="mb-4 rounded-xl border border-sky-100 bg-sky-50/60 p-3">
            <label className="text-xs text-slate-700 block">
              Generation model (Bedrock - Knowledge Explorer)
              <select
                value={generationModel}
                onChange={(e) => setGenerationModel(e.target.value)}
                className="mt-1 w-full rounded-lg border border-sky-100 bg-white px-3 py-2 text-sm"
              >
                {(modelOptions.length ? modelOptions : ['']).map((m) => (
                  <option key={m || 'default'} value={m}>
                    {m || 'Configured default'}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
        {showAdvancedConfig && mode === 'retrieval_generation' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
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
                className="mt-1 w-full rounded-lg border border-sky-100 bg-sky-50/60 px-3 py-2 text-sm"
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
              className="w-full px-4 py-4 bg-sky-50/60 border border-sky-100 rounded-xl text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 transition-all text-lg min-h-[120px] resize-none"
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
              <button type="button" className="hover:text-sky-600" onClick={() => handleRecentSearchClick(q)}>
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
          <div className="rounded-xl border border-sky-100 bg-white px-4 py-3 flex items-center gap-2 shadow-[0_10px_24px_-20px_rgba(14,165,233,0.45)]">
            <Clock3 className="w-4 h-4 text-sky-600" />
            <span className="text-sm text-slate-700">
              Retrieval: {telemetry.steps_ms?.retrieval_total ?? ((telemetry.steps_ms?.text_retrieval || 0) + (telemetry.steps_ms?.image_retrieval || 0))} ms
            </span>
          </div>
          <div className="rounded-xl border border-sky-100 bg-white px-4 py-3 flex items-center gap-2 shadow-[0_10px_24px_-20px_rgba(14,165,233,0.45)]">
            <Clock3 className="w-4 h-4 text-sky-600" />
            <span className="text-sm text-slate-700">Generation: {telemetry.steps_ms?.generation || 0} ms</span>
          </div>
          <div className="rounded-xl border border-sky-100 bg-white px-4 py-3 flex items-center gap-2 shadow-[0_10px_24px_-20px_rgba(14,165,233,0.45)]">
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
            <div className="bg-white rounded-2xl border border-sky-100 shadow-[0_14px_28px_-22px_rgba(14,165,233,0.45)] overflow-hidden">
              <div className="px-6 py-4 border-b border-sky-100 flex items-center gap-2 bg-sky-50/50">
                <div className="w-2.5 h-2.5 rounded-full bg-blue-600 shadow-[0_0_8px_rgba(37,99,235,0.5)]" />
                <h3 className="font-bold text-slate-800 uppercase tracking-tight text-sm">Answer</h3>
              </div>
              <div ref={answerRenderRef} className="p-8 prose prose-slate max-w-none text-slate-700 leading-7 prose-headings:my-3 prose-p:my-2 prose-li:my-1">
                <ReactMarkdown
                  remarkPlugins={SEARCH_REMARK_PLUGINS}
                  rehypePlugins={SEARCH_REHYPE_PLUGINS}
                  components={{
                    h1: ({ children }) => <h1 className="text-3xl font-bold text-slate-900 mt-2 mb-4">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-2xl font-semibold text-slate-900 mt-6 mb-3">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-xl font-semibold text-slate-900 mt-5 mb-2">{children}</h3>,
                    p: ({ children }) => <p className="text-base leading-7 text-slate-700 my-2">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-6 my-3 space-y-1">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-6 my-3 space-y-1">{children}</ol>,
                    table: ({ children }) => <table className="w-full border-collapse text-sm my-4">{children}</table>,
                    th: ({ children }) => <th className="border border-slate-300 bg-slate-50 px-2 py-1 text-left">{children}</th>,
                    td: ({ children }) => <td className="border border-slate-300 px-2 py-1 align-top">{children}</td>,
                    img: ({ src, alt }) => <AnswerImage src={typeof src === 'string' ? src : undefined} alt={alt} />,
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

          {answer != null && (
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => void handleCopyAnswer()}
                className="inline-flex items-center gap-2 rounded-lg border border-sky-200 bg-white px-3 py-2 text-xs font-semibold text-sky-700 hover:bg-sky-50"
              >
                <Copy className="w-4 h-4" />
                {copyStatus === 'ok' ? 'Copied' : copyStatus === 'err' ? 'Copy failed' : 'Copy answer'}
              </button>
              <button
                type="button"
                onClick={handleDownloadAnswerPdf}
                disabled={isPreparingPdf}
                className="inline-flex items-center gap-2 rounded-lg border border-emerald-200 bg-white px-3 py-2 text-xs font-semibold text-emerald-700 hover:bg-emerald-50 disabled:opacity-60"
              >
                <FileDown className="w-4 h-4" />
                {isPreparingPdf ? 'Preparing PDF...' : 'Download rendered PDF'}
              </button>
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
                const timeRange = c.type === 'text' ? getCitationTimeRange(c) : '';
                const md = (c.metadata || {}) as Record<string, unknown>;
                const isMediaChunk = c.type === 'text' && String(md.document_type || '').toLowerCase() === 'media';
                const mediaStorageUri = (() => {
                  const original = String(md.original_storage_uri || '').trim();
                  if (original) return original;
                  const fallback = String(c.storage_uri || '').trim();
                  return isLikelyMediaPath(fallback) ? fallback : '';
                })();
                const mediaSourcePath = String(md.preview_source_path || md.original_file || c.source_path || '');
                const mediaFormat = String(md.original_file_format || '').toLowerCase();
                const mediaStart = Number(c.start_time ?? Number(md.start_time ?? 0));
                const mediaType = String(previewMediaTypes[cid] || '');
                const isAudio = mediaType.startsWith('audio/') || ['mp3', 'wav', 'm4a', 'aac', 'flac', 'ogg'].includes(mediaFormat);
                const isVideo = mediaType.startsWith('video/') || ['mp4', 'mov', 'mkv', 'webm', 'avi'].includes(mediaFormat);
                const canLoadOriginalMedia = Boolean(mediaStorageUri || mediaSourcePath);
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
                    className={`rounded-xl border p-4 transition-all ${active ? 'border-sky-400 bg-sky-50/60' : 'border-sky-100 bg-white'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-800">
                        {c.key} · {c.type === 'text' ? getCitationDisplayName(c) : `${getCitationDisplayName(c)} (page ${c.page || '-'})`}
                      </p>
                      {typeof c.score === 'number' && !Number.isNaN(c.score) && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                          {c.score.toFixed(4)}
                        </span>
                      )}
                    </div>
                    {timeRange && (
                      <div className="mt-1 text-[11px] inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                        <Clock3 className="w-3 h-3" />
                        <span>{timeRange}</span>
                      </div>
                    )}
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
                        {isMediaChunk && (
                          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50/60 p-3">
                            {!imagePreviewUrls[cid] ? (
                              canLoadOriginalMedia ? (
                              <button
                                type="button"
                                disabled={!!imagePreviewLoading[cid]}
                                onClick={() =>
                                  void loadSourcePreview(
                                    {
                                      storage_uri: mediaStorageUri,
                                      source_path: mediaStorageUri ? '' : (isLocalHostRuntime() ? mediaSourcePath : ''),
                                      page: 1,
                                    },
                                    cid
                                  )
                                }
                                className="text-xs px-2 py-1 rounded border border-amber-300 text-amber-800 bg-amber-100 hover:bg-amber-200 disabled:opacity-60"
                              >
                                {imagePreviewLoading[cid] ? 'Loading media...' : `Load original media${mediaStart > 0 ? ` @ ${formatSecondsToClock(mediaStart)}` : ''}`}
                              </button>
                              ) : (
                                <p className="text-xs text-amber-800">Original media source is unavailable for this chunk in current index metadata.</p>
                              )
                            ) : isAudio ? (
                              <audio
                                controls
                                preload="metadata"
                                src={imagePreviewUrls[cid]}
                                className="w-full"
                                onLoadedMetadata={(e) => {
                                  if (mediaStart > 0) {
                                    try {
                                      e.currentTarget.currentTime = mediaStart;
                                    } catch {
                                      // ignore seek failures on some formats
                                    }
                                  }
                                }}
                              />
                            ) : isVideo ? (
                              <video
                                controls
                                preload="metadata"
                                src={imagePreviewUrls[cid]}
                                className="w-full max-h-80 rounded border border-amber-200 bg-black"
                                onLoadedMetadata={(e) => {
                                  if (mediaStart > 0) {
                                    try {
                                      e.currentTarget.currentTime = mediaStart;
                                    } catch {
                                      // ignore seek failures on some formats
                                    }
                                  }
                                }}
                              />
                            ) : (
                              <p className="text-xs text-amber-800">Original media loaded, but the browser cannot preview this media type inline.</p>
                            )}
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="mt-2">
                        {!imagePreviewUrls[cid] ? (
                          <button
                            type="button"
                            disabled={!!imagePreviewLoading[cid]}
                            onClick={() =>
                              void loadSourcePreview(
                                {
                                  storage_uri: c.storage_uri,
                                  source_path: c.source_path,
                                  page: c.page,
                                },
                                cid
                              )
                            }
                            className="text-xs px-2 py-1 rounded border border-sky-200 text-sky-700 bg-sky-50 hover:bg-sky-100 disabled:opacity-60"
                          >
                            {imagePreviewLoading[cid] ? 'Loading...' : 'Load image'}
                          </button>
                        ) : (
                          <img src={imagePreviewUrls[cid]} alt={c.source || 'citation image'} className="w-full max-h-80 object-contain rounded border border-sky-100 bg-sky-50/50" />
                        )}
                      </div>
                    )}
                    <details className="mt-2">
                      <summary className="text-xs text-slate-500 cursor-pointer">Metadata</summary>
                      <pre className="mt-2 text-[11px] bg-sky-50/60 border border-sky-100 rounded-lg p-2 overflow-auto">
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
