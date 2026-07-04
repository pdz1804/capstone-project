import React, { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { Search, MessageSquare, RefreshCw, Database, Clock3, Sigma, Copy, FileDown, Beaker, Save, ThumbsDown, ThumbsUp } from 'lucide-react';
import { FileItem } from '../App';
import apiClient from '../api/client';
import {
  createRetrievalEvalRun,
  getRetrievalEvalRun,
  getGenerationModels,
  getSearchImagePreview,
  recomputeRetrievalEvalRun,
  saveRetrievalEvalAnswerLabels,
  saveRetrievalEvalLabels,
  searchRag,
  type RetrievalEvalEvidence,
  type RetrievalEvalRun,
} from '../api/ragApi';

interface SearchViewProps {
  files: FileItem[];
  showRetrievalEval?: boolean;
  showSearch?: boolean;
}

type SearchMode = 'retrieval_only' | 'retrieval_generation';
type SearchScope = 'text' | 'image' | 'both';
type RetrieverType = 'bm25' | 'dense' | 'hybrid';
const DEFAULT_KNOWLEDGE_EXPLORER_MODEL = 'us.anthropic.claude-haiku-4-5-20251001-v1:0';

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

type EvalModality = 'text' | 'image';

function getMetricMean(metrics: Record<string, any> | undefined, source: 'llm' | 'human', modality: EvalModality, key: string): string {
  const value = metrics?.[source]?.[modality]?.aggregate?.[key]?.mean;
  return typeof value === 'number' ? value.toFixed(3) : '-';
}

function evalModalitiesForScope(scope: string | undefined): EvalModality[] {
  if (scope === 'text') return ['text'];
  if (scope === 'image') return ['image'];
  return ['text', 'image'];
}

function evalScopeFromRun(run: RetrievalEvalRun | null, fallback: SearchScope = 'both'): SearchScope {
  const scope = String(run?.config?.search_scope || fallback);
  return scope === 'text' || scope === 'image' || scope === 'both' ? scope : fallback;
}

function evalKValuesFromRun(run: RetrievalEvalRun | null): number[] {
  const raw = run?.config?.k_values;
  if (!Array.isArray(raw)) return [1, 3, 5, 7, 10];
  const values = raw.map((value) => Number(value)).filter((value) => Number.isFinite(value) && value > 0);
  return values.length > 0 ? values : [1, 3, 5, 7, 10];
}

function RetrievalMetricTable({
  title,
  metrics,
  source,
  modalities,
  kValues,
}: {
  title: string;
  metrics?: Record<string, any>;
  source: 'llm' | 'human';
  modalities: EvalModality[];
  kValues: number[];
}) {
  const ks = kValues.map((k) => `@${k}`);
  const rows = [
    { label: 'Text recall', modality: 'text' as EvalModality, metric: 'recall' },
    { label: 'Text nDCG', modality: 'text' as EvalModality, metric: 'ndcg' },
    { label: 'Image recall', modality: 'image' as EvalModality, metric: 'recall' },
    { label: 'Image nDCG', modality: 'image' as EvalModality, metric: 'ndcg' },
  ].filter((row) => modalities.includes(row.modality));
  return (
    <div className="overflow-hidden rounded-lg border border-emerald-100 bg-white">
      <div className="border-b border-emerald-100 bg-emerald-50/50 px-3 py-2 text-xs font-black uppercase tracking-tight text-emerald-800">{title}</div>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-50 text-left text-[10px] uppercase tracking-tight text-slate-500">
            <th className="px-3 py-2">Metric</th>
            {ks.map((k) => <th key={k} className="px-3 py-2">{k}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-t border-slate-100">
              <td className="px-3 py-2 font-semibold text-slate-700">{row.label}</td>
              {ks.map((k) => (
                <td key={k} className="px-3 py-2 font-mono text-slate-900">
                  {getMetricMean(metrics, source, row.modality, `${row.metric}${k}`)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatMs(value: unknown): string {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return '-';
  if (n >= 1000) return `${(n / 1000).toFixed(1)}s`;
  return `${Math.round(n)}ms`;
}

function getEvalTiming(run: RetrievalEvalRun | null, path: string[]): string {
  let cur: any = run?.timings_ms;
  for (const key of path) cur = cur?.[key];
  return formatMs(cur);
}

function labelKey(queryId: string, modality: EvalModality, evidenceId: string): string {
  return `${queryId}::${modality}::${evidenceId}`;
}

function normalizePosixPath(path: string): string {
  const parts = String(path || '').replace(/\\/g, '/').split('/').filter(Boolean);
  const out: string[] = [];
  for (const part of parts) {
    if (part === '.') continue;
    if (part === '..') out.pop();
    else out.push(part);
  }
  return out.join('/');
}

function resolveChunkImageSrc(src: string, sourcePath?: string): string {
  const raw = String(src || '').trim();
  if (!raw || raw.startsWith('data:') || raw.startsWith('blob:') || raw.startsWith('http://') || raw.startsWith('https://') || raw.startsWith('/api/')) {
    return raw;
  }
  if (raw.startsWith('s3://') || raw.startsWith('/')) {
    return `/api/image?path=${encodeURIComponent(raw)}`;
  }
  const cleanSource = String(sourcePath || '').replace(/\\/g, '/');
  if (cleanSource.startsWith('s3://')) {
    const body = cleanSource.slice('s3://'.length);
    const slash = body.indexOf('/');
    const bucket = slash >= 0 ? body.slice(0, slash) : body;
    const key = slash >= 0 ? body.slice(slash + 1) : '';
    const keyBase = key.includes('/') ? key.slice(0, key.lastIndexOf('/')) : '';
    const joinedKey = normalizePosixPath(keyBase ? `${keyBase}/${raw}` : raw);
    return `/api/image?path=${encodeURIComponent(`s3://${bucket}/${joinedKey}`)}`;
  }
  const base = cleanSource.includes('/') ? cleanSource.slice(0, cleanSource.lastIndexOf('/')) : '';
  return `/api/processed-file?rel_path=${encodeURIComponent(normalizePosixPath(base ? `${base}/${raw}` : raw))}`;
}

function preprocessChunkMarkdown(text: string, sourcePath?: string): string {
  const toImage = (_match: string, rawValue: string) => {
    const imagePath = String(rawValue || '').split('|')[0]?.trim();
    return imagePath ? `![image](${resolveChunkImageSrc(imagePath, sourcePath)})` : '';
  };
  return String(text || '')
    .replace(/\[START_IMAGE_PATH\]\s*(.*?)\s*\[END_IMAGE_PATH\]/gs, toImage)
    .replace(/\[START_IMAGE\]\s*(.*?)\s*\[END_IMAGE\]/gs, toImage)
    .replace(/\[START_TABLE_CONTENT\]/g, '')
    .replace(/\[END_TABLE_CONTENT\]/g, '')
    .replace(/\[START_TABLE\]/g, '')
    .replace(/\[END_TABLE\]/g, '')
    .replace(/<!--\s*image\s*-->/gi, '\n\n> Image marker found, but this chunk does not include an artifact path.\n\n');
}

function ChunkMarkdownImage({ src, alt, sourcePath }: { src?: string; alt?: string; sourcePath?: string }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const resolvedSrc = typeof src === 'string' ? resolveChunkImageSrc(src, sourcePath) : '';
  const isApiImage = resolvedSrc.includes('/api/image?');
  const isProcessedFile = resolvedSrc.includes('/api/processed-file?');
  const path = isApiImage ? new URLSearchParams(resolvedSrc.split('?')[1] ?? '').get('path') : null;
  const relPath = isProcessedFile ? new URLSearchParams(resolvedSrc.split('?')[1] ?? '').get('rel_path') : null;

  useEffect(() => {
    setBlobUrl(null);
    setFailed(false);
    if (!path && !relPath) return;
    let canceled = false;
    let objectUrl = '';
    void apiClient
      .get(path ? '/image' : '/processed-file', {
        params: path ? { path } : { rel_path: relPath },
        responseType: 'blob',
      })
      .then(({ data }) => {
        if (canceled) return;
        objectUrl = URL.createObjectURL(data);
        setBlobUrl(objectUrl);
      })
      .catch(() => {
        if (!canceled) setFailed(true);
      });
    return () => {
      canceled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path, relPath]);

  if (!resolvedSrc) return null;
  if (!path && !relPath) {
    return <img src={resolvedSrc} alt={alt || 'chunk image'} className="my-2 max-h-80 max-w-full rounded border border-slate-100 object-contain" />;
  }
  if (failed) return <span className="text-xs text-amber-700">Image could not be loaded</span>;
  if (!blobUrl) return <span className="inline-block h-10 w-24 animate-pulse rounded bg-slate-100" />;
  return <img src={blobUrl} alt={alt || 'chunk image'} className="my-2 max-h-80 max-w-full rounded border border-slate-100 object-contain" />;
}

function ChunkMarkdown({ text, sourcePath, compact = false }: { text: string; sourcePath?: string; compact?: boolean }) {
  return (
    <div className={`${compact ? 'prose prose-sm' : 'prose prose-slate prose-sm'} max-w-none prose-table:block prose-table:overflow-x-auto prose-th:border prose-th:border-slate-300 prose-th:bg-slate-50 prose-th:px-2 prose-th:py-1 prose-td:border prose-td:border-slate-300 prose-td:px-2 prose-td:py-1`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{
          img: ({ src, alt }) => <ChunkMarkdownImage src={typeof src === 'string' ? src : undefined} alt={alt} sourcePath={sourcePath} />,
        }}
      >
        {preprocessChunkMarkdown(text, sourcePath)}
      </ReactMarkdown>
    </div>
  );
}

export default function SearchView({
  files,
  showRetrievalEval = false,
  showSearch = true,
}: SearchViewProps) {
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
  const [evalRun, setEvalRun] = useState<RetrievalEvalRun | null>(null);
  const [isEvalRunning, setIsEvalRunning] = useState(false);
  const [isSavingEvalLabels, setIsSavingEvalLabels] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [selectedEvalQueryId, setSelectedEvalQueryId] = useState<string>('');
  const [selectedEvalModality, setSelectedEvalModality] = useState<EvalModality>('text');
  const [selectedEvalDocumentIds, setSelectedEvalDocumentIds] = useState<string[]>([]);
  const [reuseGeneratedQuestions, setReuseGeneratedQuestions] = useState<boolean>(true);
  const [evalSearchScope, setEvalSearchScope] = useState<SearchScope>('both');
  const [evalRetrieverType, setEvalRetrieverType] = useState<RetrieverType>('hybrid');
  const [evalQuestionsPerCategory, setEvalQuestionsPerCategory] = useState<number>(5);
  const [evalRunIdInput, setEvalRunIdInput] = useState('');
  const [evalDraftLabels, setEvalDraftLabels] = useState<Record<string, number>>({});
  const [evalDraftRanks, setEvalDraftRanks] = useState<Record<string, number>>({});
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, Record<string, string>>>({});
  const [evalImageZoom, setEvalImageZoom] = useState<number>(1.8);
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
          setGenerationModel(models.includes(DEFAULT_KNOWLEDGE_EXPLORER_MODEL) ? DEFAULT_KNOWLEDGE_EXPLORER_MODEL : models[0]);
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

  useEffect(() => {
    const first = evalRun?.results?.[0]?.query_id || '';
    if (first && !selectedEvalQueryId) {
      setSelectedEvalQueryId(first);
    }
  }, [evalRun?.run_id, selectedEvalQueryId]);

  const eligibleEvalFiles = useMemo(
    () =>
      files.filter(
        (file) =>
          !!file.documentFolder &&
          (file.status === 'processed' || file.status === 'indexed'),
      ),
    [files],
  );

  useEffect(() => {
    if (!eligibleEvalFiles.length) {
      if (selectedEvalDocumentIds.length > 0) setSelectedEvalDocumentIds([]);
      return;
    }
    const validIds = selectedEvalDocumentIds.filter((id) => eligibleEvalFiles.some((file) => file.documentFolder === id));
    if (validIds.length !== selectedEvalDocumentIds.length) {
      setSelectedEvalDocumentIds(validIds);
    }
  }, [eligibleEvalFiles, selectedEvalDocumentIds]);

  useEffect(() => {
    if (!evalRun) return;
    const labels: Record<string, number> = {};
    const ranks: Record<string, number> = {};
    const answers: Record<string, Record<string, string>> = {};
    for (const result of evalRun.results || []) {
      const humanAnswer = result.human_answer_judgment || {};
      answers[result.query_id] = {
        correctness: humanAnswer.correctness || '',
        faithfulness: humanAnswer.faithfulness || '',
        answer_support: humanAnswer.answer_support || '',
        rationale: humanAnswer.rationale || '',
      };
      for (const modality of ['text', 'image'] as EvalModality[]) {
        const judgment = result.human_judgments?.[modality];
        for (const item of judgment?.labels || []) {
          labels[labelKey(result.query_id, modality, item.evidence_id)] = Number(item.relevance || 0);
        }
        (judgment?.ranked_evidence_ids || []).forEach((eid, idx) => {
          ranks[labelKey(result.query_id, modality, eid)] = idx + 1;
        });
      }
    }
    setEvalDraftLabels(labels);
    setEvalDraftRanks(ranks);
    setAnswerDrafts(answers);
  }, [evalRun?.run_id]);

  const selectedEvalResult = useMemo(() => {
    return (evalRun?.results || []).find((item) => item.query_id === selectedEvalQueryId) || null;
  }, [evalRun, selectedEvalQueryId]);

  const evalRunScope = evalScopeFromRun(evalRun, evalSearchScope);
  const activeEvalModalities = useMemo(() => evalModalitiesForScope(evalRunScope), [evalRunScope]);
  const evalMetricKValues = useMemo(() => evalKValuesFromRun(evalRun), [evalRun]);

  useEffect(() => {
    if (!activeEvalModalities.includes(selectedEvalModality)) {
      setSelectedEvalModality(activeEvalModalities[0] || 'text');
    }
  }, [activeEvalModalities, selectedEvalModality]);

  const selectedEvalEvidence: RetrievalEvalEvidence[] = useMemo(() => {
    if (!selectedEvalResult) return [];
    return selectedEvalResult.retrieved?.[selectedEvalModality] || [];
  }, [selectedEvalResult, selectedEvalModality]);

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

  const runRetrievalEval = async () => {
    setEvalError(null);
    if (selectedEvalDocumentIds.length === 0) {
      setEvalError('Please choose at least one eligible file before starting retrieval evaluation.');
      return;
    }
    setIsEvalRunning(true);
    try {
      const run = await createRetrievalEvalRun({
        top_k: 10,
        k_values: [1, 3, 5, 7, 10],
        retriever_type: evalRetrieverType,
        search_scope: evalSearchScope,
        questions_per_category: evalQuestionsPerCategory,
        selected_document_ids: selectedEvalDocumentIds,
        async_mode: true,
        reuse_generated_questions: reuseGeneratedQuestions,
      });
      setEvalRun(run);
      setSelectedEvalQueryId(run.results?.[0]?.query_id || '');

      let latest = run;
      for (let attempt = 0; attempt < 720 && latest.status !== 'completed' && latest.status !== 'failed'; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        latest = await getRetrievalEvalRun(run.run_id);
        setEvalRun(latest);
        if (!selectedEvalQueryId && latest.results?.[0]?.query_id) {
          setSelectedEvalQueryId(latest.results[0].query_id);
        }
      }
      if (latest.status === 'failed') {
        setEvalError(latest.error || 'Retrieval eval failed');
      } else if (latest.status !== 'completed') {
        setEvalError('Retrieval eval is still running. Refresh the run later.');
      }
    } catch (e) {
      const msg =
        e && typeof e === 'object' && 'response' in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || '')
          : e instanceof Error
            ? e.message
            : 'Retrieval eval failed';
      setEvalError(msg || 'Retrieval eval failed');
    } finally {
      setIsEvalRunning(false);
    }
  };

  const setEvalLabel = (evidenceId: string, relevance: number) => {
    if (!selectedEvalResult) return;
    const key = labelKey(selectedEvalResult.query_id, selectedEvalModality, evidenceId);
    setEvalDraftLabels((prev) => ({ ...prev, [key]: relevance }));
    if (relevance > 0) {
      setEvalDraftRanks((prev) => ({ ...prev, [key]: prev[key] || 1 }));
    }
  };

  const saveEvalLabels = async () => {
    if (!evalRun || !selectedEvalResult) return;
    setEvalError(null);
    setIsSavingEvalLabels(true);
    try {
      const labels = selectedEvalEvidence.map((item) => {
        const key = labelKey(selectedEvalResult.query_id, selectedEvalModality, item.evidence_id);
        return {
          evidence_id: item.evidence_id,
          relevance: Number(evalDraftLabels[key] ?? 0),
          rationale: '',
        };
      });
      const ranked_evidence_ids = selectedEvalEvidence
        .filter((item) => Number(evalDraftLabels[labelKey(selectedEvalResult.query_id, selectedEvalModality, item.evidence_id)] ?? 0) > 0)
        .sort((a, b) => {
          const ka = labelKey(selectedEvalResult.query_id, selectedEvalModality, a.evidence_id);
          const kb = labelKey(selectedEvalResult.query_id, selectedEvalModality, b.evidence_id);
          return Number(evalDraftRanks[ka] || 999) - Number(evalDraftRanks[kb] || 999);
        })
        .map((item) => item.evidence_id);
      const updated = await saveRetrievalEvalLabels(evalRun.run_id, {
        query_id: selectedEvalResult.query_id,
        modality: selectedEvalModality,
        labels,
        ranked_evidence_ids,
      });
      setEvalRun(updated);
    } catch (e) {
      const msg =
        e && typeof e === 'object' && 'response' in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || '')
          : e instanceof Error
            ? e.message
            : 'Could not save labels';
      setEvalError(msg || 'Could not save labels');
    } finally {
      setIsSavingEvalLabels(false);
    }
  };

  const setAnswerDraft = (field: string, value: string) => {
    if (!selectedEvalResult) return;
    setAnswerDrafts((prev) => ({
      ...prev,
      [selectedEvalResult.query_id]: {
        ...(prev[selectedEvalResult.query_id] || {}),
        [field]: value,
      },
    }));
  };

  const saveAnswerJudgment = async () => {
    if (!evalRun || !selectedEvalResult) return;
    const draft = answerDrafts[selectedEvalResult.query_id] || {};
    if (!draft.correctness || !draft.faithfulness || !draft.answer_support) {
      setEvalError('Please select correctness, faithfulness, and support before saving answer judgment.');
      return;
    }
    setEvalError(null);
    setIsSavingEvalLabels(true);
    try {
      const updated = await saveRetrievalEvalAnswerLabels(evalRun.run_id, {
        query_id: selectedEvalResult.query_id,
        correctness: draft.correctness as 'correct' | 'partially_correct' | 'incorrect',
        faithfulness: draft.faithfulness as 'faithful' | 'partially_faithful' | 'hallucinated',
        answer_support: draft.answer_support as 'fully_supported' | 'partially_supported' | 'not_supported',
        rationale: draft.rationale || '',
      });
      setEvalRun(updated);
    } catch (e) {
      setEvalError(e instanceof Error ? e.message : 'Could not save answer judgment');
    } finally {
      setIsSavingEvalLabels(false);
    }
  };

  const recomputeEval = async () => {
    if (!evalRun) return;
    setEvalError(null);
    try {
      setEvalRun(await recomputeRetrievalEvalRun(evalRun.run_id));
    } catch (e) {
      setEvalError(e instanceof Error ? e.message : 'Could not recompute metrics');
    }
  };

  const loadEvalRunById = async () => {
    const runId = evalRunIdInput.trim();
    if (!runId) return;
    setEvalError(null);
    try {
      const run = await getRetrievalEvalRun(runId);
      setEvalRun(run);
      setSelectedEvalQueryId(run.results?.[0]?.query_id || '');
    } catch (e) {
      setEvalError(e instanceof Error ? e.message : 'Could not load eval run');
    }
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

  useEffect(() => {
    if (selectedEvalModality !== 'image' || !selectedEvalResult) return;
    for (const item of selectedEvalEvidence) {
      const key = labelKey(selectedEvalResult.query_id, 'image', item.evidence_id);
      if (imagePreviewUrls[key] || imagePreviewLoading[key]) continue;
      void loadSourcePreview(
        {
          storage_uri: item.storage_uri,
          source_path: item.source_path,
          page: item.page,
        },
        key
      );
    }
  }, [selectedEvalModality, selectedEvalResult?.query_id, selectedEvalEvidence, imagePreviewUrls, imagePreviewLoading]);

  function AnswerImage({ src, alt }: { src?: string; alt?: string }) {
    const rawSrc = String(src || '');
    const citationId = rawSrc.startsWith('#image-') ? rawSrc.slice(1) : '';
    const citation = citationId ? citationsById[citationId] : undefined;
    const previewUrl = citationId ? imagePreviewUrls[citationId] : '';
    const isLoading = citationId ? imagePreviewLoading[citationId] : false;

    useEffect(() => {
      if (!citationId || !citation || previewUrl || isLoading) return;
      void loadSourcePreview(
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
      {showSearch && (
        <div className="bg-white/95 backdrop-blur-sm rounded-2xl p-6 border border-sky-100 shadow-[0_12px_26px_-22px_rgba(14,165,233,0.5)] shrink-0 space-y-2">
          <p className="text-xs text-slate-500">
            Retrieval + generation use your FastAPI backend <code className="bg-slate-100 px-1 rounded">POST /api/search</code>{' '}
            (Qdrant + configured LLM). Indexed sources in workspace: <strong>{totalFiles}</strong> input file(s) listed.
          </p>
        </div>
      )}

      {showRetrievalEval && (
        <div className="bg-white/95 backdrop-blur-sm rounded-2xl p-6 border border-emerald-100 shadow-[0_12px_26px_-22px_rgba(16,185,129,0.45)] shrink-0">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center text-emerald-700">
              <Beaker className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-800 uppercase tracking-tight">Retrieval Eval</h3>
              <p className="text-xs text-slate-500">
                LLM judge + human labels for text recall/nDCG and image recall/nDCG. Only processed or indexed files are shown.
                {evalRun?.status && <span className="ml-2 font-bold text-emerald-700">Status: {evalRun.status}</span>}
                {evalRun && (
                  <span className="ml-2 font-bold text-slate-600">
                    Queries: {evalRun.questions?.length || 0} · Results: {evalRun.results?.length || 0}
                  </span>
                )}
              </p>
            </div>
            <div className="ml-auto flex flex-col items-end gap-2">
              <div className="flex flex-col gap-1 w-[320px] max-h-40 overflow-y-auto border border-emerald-100 rounded-lg p-2 bg-emerald-50/50 text-xs custom-scrollbar">
                {eligibleEvalFiles.length === 0 ? (
                  <span className="text-slate-500 p-1">No eligible files</span>
                ) : (
                  <>
                    <label className="flex items-center gap-2 p-1 hover:bg-emerald-100/50 rounded cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={selectedEvalDocumentIds.length === eligibleEvalFiles.length && eligibleEvalFiles.length > 0} 
                        onChange={(e) => {
                          if (e.target.checked) setSelectedEvalDocumentIds(eligibleEvalFiles.map(f => f.documentFolder || ''));
                          else setSelectedEvalDocumentIds([]);
                        }}
                        className="rounded border-emerald-300 text-emerald-600 focus:ring-emerald-500"
                      />
                      <span className="font-bold">Select All</span>
                    </label>
                    {eligibleEvalFiles.map((file) => (
                      <label key={file.documentFolder} className="flex items-center gap-2 p-1 hover:bg-emerald-100/50 rounded cursor-pointer">
                        <input 
                          type="checkbox" 
                          checked={selectedEvalDocumentIds.includes(file.documentFolder || '')} 
                          onChange={(e) => {
                            if (e.target.checked) setSelectedEvalDocumentIds(prev => [...prev, file.documentFolder || '']);
                            else setSelectedEvalDocumentIds(prev => prev.filter(id => id !== file.documentFolder));
                          }}
                          className="rounded border-emerald-300 text-emerald-600 focus:ring-emerald-500"
                        />
                        <span className="truncate">{file.name}</span>
                      </label>
                    ))}
                  </>
                )}
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer mt-1">
                <input 
                  type="checkbox" 
                  checked={reuseGeneratedQuestions} 
                  onChange={(e) => setReuseGeneratedQuestions(e.target.checked)}
                  className="rounded border-emerald-300 text-emerald-600 focus:ring-emerald-500"
                />
                Use previous generated questions if available
              </label>
              <div className="flex flex-wrap items-end gap-2">
                <label className="text-xs text-slate-600">
                  Search scope
                  <select
                    value={evalSearchScope}
                    onChange={(e) => setEvalSearchScope(e.target.value as SearchScope)}
                    className="mt-1 w-44 rounded-lg border border-emerald-100 bg-emerald-50/50 px-2 py-1.5 text-sm"
                  >
                    <option value="both">Both text + image</option>
                    <option value="text">Text only</option>
                    <option value="image">Image only</option>
                  </select>
                </label>
                <label className="text-xs text-slate-600">
                  Text retrieval
                  <select
                    value={evalRetrieverType}
                    onChange={(e) => setEvalRetrieverType(e.target.value as RetrieverType)}
                    disabled={evalSearchScope === 'image'}
                    className="mt-1 w-36 rounded-lg border border-emerald-100 bg-emerald-50/50 px-2 py-1.5 text-sm disabled:opacity-50"
                  >
                    <option value="bm25">Keyword</option>
                    <option value="dense">Semantic</option>
                    <option value="hybrid">Hybrid</option>
                  </select>
                </label>
                <label className="text-xs text-slate-600">
                  Q/category
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={evalQuestionsPerCategory}
                    onChange={(e) => setEvalQuestionsPerCategory(Math.max(1, Math.min(10, Number(e.target.value || 5))))}
                    className="mt-1 w-20 rounded-lg border border-emerald-100 bg-emerald-50/50 px-2 py-1.5 text-sm"
                  />
                </label>
                <label className="text-xs text-slate-600">
                  Run ID
                  <input
                  type="text"
                  value={evalRunIdInput}
                  onChange={(e) => setEvalRunIdInput(e.target.value)}
                  placeholder="retrieval_eval_..."
                  className="mt-1 w-48 rounded-lg border border-emerald-100 bg-white px-2 py-1.5 text-sm"
                />
              </label>
              <button
                type="button"
                onClick={() => void loadEvalRunById()}
                disabled={!evalRunIdInput.trim()}
                className="inline-flex items-center gap-2 rounded-lg border border-emerald-200 bg-white px-3 py-2 text-xs font-bold text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
              >
                Load run
              </button>
              <button
                type="button"
                onClick={() => void runRetrievalEval()}
                disabled={isEvalRunning || selectedEvalDocumentIds.length === 0}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {isEvalRunning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Beaker className="w-4 h-4" />}
                Run eval
              </button>
              {evalRun && (
                <button
                  type="button"
                  onClick={() => void recomputeEval()}
                  className="inline-flex items-center gap-2 rounded-lg border border-emerald-200 bg-white px-3 py-2 text-xs font-bold text-emerald-700 hover:bg-emerald-50"
                >
                  <Sigma className="w-4 h-4" />
                  Recompute
                </button>
              )}
              </div>
            </div>
          </div>

          {evalError && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{evalError}</div>
          )}

          {evalRun && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                <RetrievalMetricTable title="LLM retrieval metrics" metrics={evalRun.metrics} source="llm" modalities={activeEvalModalities} kValues={evalMetricKValues} />
                <RetrievalMetricTable title="Human retrieval metrics" metrics={evalRun.metrics} source="human" modalities={activeEvalModalities} kValues={evalMetricKValues} />
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {[
                  ['Retrieval wall total', getEvalTiming(evalRun, ['retrieval', 'wall_total_ms'])],
                  ...(activeEvalModalities.includes('text') ? [
                    ['Text retrieve total', getEvalTiming(evalRun, ['retrieval', 'text', 'total_ms'])],
                    ['Text embed total', getEvalTiming(evalRun, ['retrieval', 'text', 'embed_ms'])],
                    ['Text rerank total', getEvalTiming(evalRun, ['retrieval', 'text', 'rerank_ms'])],
                  ] : []),
                  ...(activeEvalModalities.includes('image') ? [
                    ['Image retrieve total', getEvalTiming(evalRun, ['retrieval', 'image', 'total_ms'])],
                    ['Image embed total', getEvalTiming(evalRun, ['retrieval', 'image', 'embed_ms'])],
                    ['Image Qdrant total', getEvalTiming(evalRun, ['retrieval', 'image', 'qdrant_ms'])],
                    ['Image rerank total', getEvalTiming(evalRun, ['retrieval', 'image', 'rerank_ms'])],
                  ] : []),
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg border border-slate-100 bg-white px-3 py-2">
                    <p className="text-[10px] font-bold uppercase tracking-tight text-slate-500">{label}</p>
                    <p className="text-base font-black text-slate-900">{value}</p>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-[minmax(220px,0.9fr)_minmax(0,1.6fr)] gap-4">
                <div className="rounded-xl border border-emerald-100 bg-white p-3 max-h-96 overflow-auto">
                  <p className="mb-2 text-xs font-bold uppercase tracking-tight text-slate-600">
                    Run {evalRun.run_id}
                  </p>
                  {evalRun.artifact_path && (
                    <p className="mb-3 break-all rounded-md bg-slate-50 px-2 py-1 text-[10px] text-slate-500">
                      Saved JSON: {evalRun.artifact_path}
                    </p>
                  )}
                  {evalRun.config?.judge_model ? (
                    <p className="mb-3 rounded-md bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-800">
                      Judge: {String(evalRun.config.judge_model)}
                      {evalRun.config.judge_guardrail_enabled === false ? ' · guardrail off' : ''}
                    </p>
                  ) : null}
                  {evalRun.status === 'completed' && (evalRun.results || []).length === 0 && (
                    <p className="rounded-md border border-amber-200 bg-amber-50 px-2 py-2 text-xs text-amber-800">
                      Run completed without generated queries/results. Re-run eval after backend reload, or check the report error fields.
                    </p>
                  )}
                  {(evalRun.results || []).map((result) => (
                    <button
                      type="button"
                      key={result.query_id}
                      onClick={() => setSelectedEvalQueryId(result.query_id)}
                      className={`mb-2 w-full rounded-lg border px-3 py-2 text-left text-xs transition-colors ${
                        selectedEvalQueryId === result.query_id
                          ? 'border-emerald-300 bg-emerald-50 text-emerald-900'
                          : 'border-slate-100 bg-white text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      <span className="block font-bold">{result.question.category}</span>
                      <span className="line-clamp-2">{result.question.question}</span>
                    </button>
                  ))}
                </div>

                {selectedEvalResult && (
                  <div className="rounded-xl border border-emerald-100 bg-white p-4">
                    <div className="flex flex-wrap items-start gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-bold uppercase tracking-tight text-emerald-700">
                          {selectedEvalResult.question.doc_id} · {selectedEvalResult.question.category}
                        </p>
                        <p className="mt-1 text-sm font-semibold text-slate-900">{selectedEvalResult.question.question}</p>
                        {selectedEvalResult.question.reference_answer && (
                          <p className="mt-1 text-xs text-slate-500">{selectedEvalResult.question.reference_answer}</p>
                        )}
                      </div>
                      {activeEvalModalities.length > 1 && (
                        <div className="inline-flex rounded-lg border border-emerald-100 bg-emerald-50/50 p-1">
                          {activeEvalModalities.map((m) => (
                            <button
                              type="button"
                              key={m}
                              onClick={() => setSelectedEvalModality(m)}
                              className={`rounded-md px-3 py-1.5 text-xs font-bold ${selectedEvalModality === m ? 'bg-emerald-600 text-white' : 'text-emerald-700 hover:bg-white'}`}
                            >
                              {m === 'text' ? 'Text chunks' : 'Image pages'}
                            </button>
                          ))}
                        </div>
                      )}
	                    </div>

                    <div className="mt-4 rounded-lg border border-slate-100 bg-slate-50/60 p-3">
                      <div className="grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)]">
                        <div>
                          <p className="text-[10px] font-black uppercase tracking-tight text-slate-500">LLM answer</p>
                          {selectedEvalResult.generated_answer?.answer ? (
                            <div className="mt-2 rounded-md bg-white p-3">
                              <ChunkMarkdown text={selectedEvalResult.generated_answer.answer} compact />
                            </div>
                          ) : (
                            <p className="mt-2 text-sm text-slate-500">No generated answer stored for this run.</p>
                          )}
                          {selectedEvalResult.generated_answer?.rationale && (
                            <p className="mt-2 text-xs text-slate-500">{selectedEvalResult.generated_answer.rationale}</p>
                          )}
                        </div>
                        <div className="space-y-3">
                          <div className="rounded-md bg-white p-3">
                            <p className="text-[10px] font-black uppercase tracking-tight text-blue-700">LLM answer judgment</p>
                            <div className="mt-2 grid grid-cols-1 gap-1 text-xs text-slate-700">
                              <span>Correctness: <strong>{selectedEvalResult.llm_answer_judgment?.correctness || '-'}</strong></span>
                              <span>Faithfulness: <strong>{selectedEvalResult.llm_answer_judgment?.faithfulness || '-'}</strong></span>
                              <span>Support: <strong>{selectedEvalResult.llm_answer_judgment?.answer_support || '-'}</strong></span>
                            </div>
                            {selectedEvalResult.llm_answer_judgment?.rationale && (
                              <p className="mt-2 text-xs text-slate-500">{selectedEvalResult.llm_answer_judgment.rationale}</p>
                            )}
                          </div>
                          <div className="rounded-md bg-white p-3">
                            <p className="text-[10px] font-black uppercase tracking-tight text-emerald-700">Human answer judgment</p>
                            <div className="mt-2 grid grid-cols-1 gap-2">
                              <select
                                value={answerDrafts[selectedEvalResult.query_id]?.correctness || ''}
                                onChange={(e) => setAnswerDraft('correctness', e.target.value)}
                                className="rounded border border-slate-200 px-2 py-1 text-xs"
                              >
                                <option value="">Correctness</option>
                                <option value="correct">correct</option>
                                <option value="partially_correct">partially_correct</option>
                                <option value="incorrect">incorrect</option>
                              </select>
                              <select
                                value={answerDrafts[selectedEvalResult.query_id]?.faithfulness || ''}
                                onChange={(e) => setAnswerDraft('faithfulness', e.target.value)}
                                className="rounded border border-slate-200 px-2 py-1 text-xs"
                              >
                                <option value="">Faithfulness</option>
                                <option value="faithful">faithful</option>
                                <option value="partially_faithful">partially_faithful</option>
                                <option value="hallucinated">hallucinated</option>
                              </select>
                              <select
                                value={answerDrafts[selectedEvalResult.query_id]?.answer_support || ''}
                                onChange={(e) => setAnswerDraft('answer_support', e.target.value)}
                                className="rounded border border-slate-200 px-2 py-1 text-xs"
                              >
                                <option value="">Support</option>
                                <option value="fully_supported">fully_supported</option>
                                <option value="partially_supported">partially_supported</option>
                                <option value="not_supported">not_supported</option>
                              </select>
                              <textarea
                                value={answerDrafts[selectedEvalResult.query_id]?.rationale || ''}
                                onChange={(e) => setAnswerDraft('rationale', e.target.value)}
                                placeholder="Human rationale"
                                className="min-h-16 rounded border border-slate-200 px-2 py-1 text-xs"
                              />
                              <button
                                type="button"
                                onClick={() => void saveAnswerJudgment()}
                                disabled={isSavingEvalLabels}
                                className="inline-flex items-center justify-center gap-2 rounded bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-50"
                              >
                                <Save className="h-3 w-3" />
                                Save answer judgment
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

	                    <div className="mt-4 space-y-3 max-h-[32rem] overflow-auto pr-1">
	                      {selectedEvalEvidence.map((item) => {
	                        const key = labelKey(selectedEvalResult.query_id, selectedEvalModality, item.evidence_id);
	                        const rel = Number(evalDraftLabels[key] ?? 0);
	                        const llmRel = selectedEvalResult.llm_judgments?.[selectedEvalModality]?.labels?.find((x) => x.evidence_id === item.evidence_id)?.relevance;
	                        const previewKey = key;
	                        const displayText = String(item.text || item.text_preview || '');
                        const hasBareImageMarker = selectedEvalModality === 'text' && /<!--\s*image\s*-->/i.test(displayText);
                        const hasArtifactImagePath = selectedEvalModality === 'text' && (
                          Array.isArray(item.image_artifact_paths) && item.image_artifact_paths.length > 0
                            ? true
                            : /\[START_IMAGE(?:_PATH)?\]|!\[[^\]]*\]\(/i.test(displayText)
                        );
                        const sourcePreviewKey = `${key}::source-preview`;
                        const sourcePreviewPage = Number(item.page || item.metadata?.page || item.metadata?.page_number || 1);
                        const chunkSourcePath = String(item.storage_uri || item.source_path || item.source || '');
                        const canLoadSourcePreview = Boolean(item.storage_uri || item.source_path);
	                        return (
	                          <div key={item.evidence_id} className="rounded-lg border border-slate-100 bg-slate-50/50 p-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-xs font-bold text-slate-800">#{item.rank} · {item.evidence_id}</p>
                              <span className="rounded-full bg-white px-2 py-0.5 text-[10px] text-slate-500">score {Number(item.score || 0).toFixed(4)}</span>
                              {llmRel !== undefined && (
                                <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] text-blue-700">LLM rel {llmRel}</span>
                              )}
                            </div>
	                            {selectedEvalModality === 'image' ? (
	                              <div className="mt-3">
                                  <div className="mb-2 flex flex-wrap items-center gap-2">
                                    <button
                                      type="button"
                                      onClick={() => setEvalImageZoom((z) => Math.max(1, Number((z - 0.25).toFixed(2))))}
                                      className="rounded border border-slate-200 bg-white px-2 py-1 text-xs font-bold text-slate-700"
                                    >
                                      -
                                    </button>
                                    <span className="text-xs font-semibold text-slate-500">{Math.round(evalImageZoom * 100)}%</span>
                                    <button
                                      type="button"
                                      onClick={() => setEvalImageZoom((z) => Math.min(4, Number((z + 0.25).toFixed(2))))}
                                      className="rounded border border-slate-200 bg-white px-2 py-1 text-xs font-bold text-slate-700"
                                    >
                                      +
                                    </button>
                                    {imagePreviewUrls[previewKey] && (
                                      <a href={imagePreviewUrls[previewKey]} target="_blank" rel="noreferrer" className="ml-auto text-xs font-bold text-blue-700 hover:underline">
                                        Open full size
                                      </a>
                                    )}
                                  </div>
                                  {imagePreviewUrls[previewKey] ? (
                                    <div className="max-h-[42rem] overflow-auto rounded border border-slate-100 bg-white">
                                      <img
                                        src={imagePreviewUrls[previewKey]}
                                        alt={item.source || item.evidence_id}
                                        style={{ width: `${evalImageZoom * 100}%`, maxWidth: 'none' }}
                                        className="h-auto object-contain"
                                      />
                                    </div>
                                  ) : (
                                  <div className="rounded border border-slate-100 bg-white px-3 py-6 text-center text-xs text-slate-500">
                                    {imagePreviewLoading[previewKey] ? 'Loading page image...' : displayText || 'Page image unavailable'}
                                  </div>
                                )}
                              </div>
	                            ) : displayText ? (
	                              <div className="mt-2 rounded-md bg-white p-3">
		                                <ChunkMarkdown text={displayText} sourcePath={chunkSourcePath} compact />
                                  {hasBareImageMarker && !hasArtifactImagePath && (
	                                    <div className="mt-3 rounded-lg border border-amber-100 bg-amber-50/50 p-3">
                                        <p className="mb-2 text-xs text-amber-800">
                                          This chunk has a bare image marker, but no parsed image artifact path was preserved in the chunk text. DOCX/PDF artifact images render automatically when the chunk contains START_IMAGE_PATH or a markdown image path.
                                        </p>
	                                      {imagePreviewUrls[sourcePreviewKey] ? (
	                                        <img src={imagePreviewUrls[sourcePreviewKey]} alt="source preview" className="max-h-96 w-full rounded border border-amber-100 bg-white object-contain" />
	                                      ) : (
	                                        <button
	                                          type="button"
	                                          disabled={!canLoadSourcePreview || !!imagePreviewLoading[sourcePreviewKey]}
	                                          onClick={() =>
	                                            void loadSourcePreview(
	                                              {
	                                                storage_uri: item.storage_uri,
	                                                source_path: item.source_path,
	                                                page: sourcePreviewPage,
	                                              },
	                                              sourcePreviewKey
	                                            )
	                                          }
	                                          className="rounded border border-amber-200 bg-white px-2 py-1 text-xs font-bold text-amber-800 hover:bg-amber-100 disabled:opacity-50"
	                                        >
	                                          {imagePreviewLoading[sourcePreviewKey] ? 'Loading source preview...' : 'Load source preview'}
	                                        </button>
	                                      )}
	                                    </div>
	                                  )}
	                              </div>
                            ) : (
                              <p className="mt-2 text-sm text-slate-700">(no preview)</p>
                            )}
                            <div className="mt-3 flex flex-wrap items-center gap-2">
                              <button
                                type="button"
                                onClick={() => setEvalLabel(item.evidence_id, 2)}
                                className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-bold ${rel === 2 ? 'bg-emerald-600 text-white' : 'bg-white text-emerald-700 border border-emerald-200'}`}
                              >
                                <ThumbsUp className="w-3 h-3" />
                                Relevant
                              </button>
                              <button
                                type="button"
                                onClick={() => setEvalLabel(item.evidence_id, 1)}
                                className={`rounded-md px-2 py-1 text-xs font-bold ${rel === 1 ? 'bg-amber-500 text-white' : 'bg-white text-amber-700 border border-amber-200'}`}
                              >
                                Partial
                              </button>
                              <button
                                type="button"
                                onClick={() => setEvalLabel(item.evidence_id, 0)}
                                className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-bold ${rel === 0 ? 'bg-slate-700 text-white' : 'bg-white text-slate-600 border border-slate-200'}`}
                              >
                                <ThumbsDown className="w-3 h-3" />
                                Irrelevant
                              </button>
                              {rel > 0 && (
                                <label className="ml-auto text-xs text-slate-500">
                                  Human rank
                                  <input
                                    type="number"
                                    min={1}
                                    value={evalDraftRanks[key] || 1}
                                    onChange={(e) => setEvalDraftRanks((prev) => ({ ...prev, [key]: Math.max(1, Number(e.target.value || 1)) }))}
                                    className="ml-2 w-16 rounded border border-slate-200 bg-white px-2 py-1 text-xs"
                                  />
                                </label>
                              )}
                            </div>
                          </div>
                        );
                      })}
                      {selectedEvalEvidence.length === 0 && (
                        <p className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-sm text-slate-500">
                          No {selectedEvalModality} evidence for this query.
                        </p>
                      )}
                    </div>

                    <div className="mt-4 flex justify-end">
                      <button
                        type="button"
                        onClick={() => void saveEvalLabels()}
                        disabled={isSavingEvalLabels || selectedEvalEvidence.length === 0}
                        className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-50"
                      >
                        {isSavingEvalLabels ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        Save human labels
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {showSearch && (
        <>
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
                        <div className="mt-2 rounded-lg bg-slate-50/50 p-3">
                          <ChunkMarkdown
                            text={`${(expanded ? longText : (c.text || '')).slice(0, expanded ? undefined : 500)}${!expanded && (longText || '').length > 500 ? '...' : ''}`}
                            sourcePath={String(c.storage_uri || c.source_path || c.source || '')}
                            compact
                          />
                        </div>
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
        </>
      )}
    </div>
  );
}
