import { useState, useEffect, useMemo, useRef } from 'react';
import {
  ChevronRight,
  Search,
  MessageSquare,
  Sparkles,
  Loader2,
  RefreshCw,
  Video,
  FileText,
  Image as ImageIcon,
  Headphones,
  List,
  ScrollText,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import { FileItem } from '../App';
import {
  coerceBlobForPreview,
  getChunksByFile,
  getInputFile,
  getInputFileUrl,
  getProcessedByFile,
  getProcessedFile,
  postSummary,
  type ProcessedByFileResponse,
} from '../api/ragApi';

function scrollToElementForHashLink(href: string) {
  const id = href.startsWith('#') ? href.slice(1) : href;
  if (!id) return;
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

const LECTURE_MARKDOWN_COMPONENTS: Components = {
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
          onClick={() => scrollToElementForHashLink(link)}
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
};

type InputPreviewState =
  | { kind: 'none' }
  | { kind: 'blob'; url: string; mime: string }
  | { kind: 'text'; content: string }
  | { kind: 'html'; content: string }
  | { kind: 'office'; iframeSrc: string; sourceUrl: string };

function pickPrimaryProcessedMarkdownRelPath(data: ProcessedByFileResponse): string | null {
  const stageOrder = ['stage3_document_processed', 'stage4_rag_ready'] as const;
  for (const st of stageOrder) {
    const block = data.stages.find((s) => s.stage === st);
    const rows = (block?.files || []) as Array<{ name?: string; relative_path?: string; size_bytes?: number }>;
    const mds = rows.filter((r) => /\.md$/i.test(String(r.name || '')));
    if (mds.length === 0) continue;
    mds.sort((a, b) => (Number(b.size_bytes) || 0) - (Number(a.size_bytes) || 0));
    const rel = String(mds[0].relative_path || '').trim();
    if (rel) return rel;
  }
  return null;
}

interface LectureViewProps {
  files?: FileItem[];
}

const LENGTH_MAP = {
  brief: 'short',
  detailed: 'medium',
  comprehensive: 'long',
} as const;

const FOCUS_QUERY: Record<'general' | 'formulas' | 'definitions', string> = {
  general: '',
  formulas: 'Emphasize formulas, equations, and mathematical reasoning.',
  definitions: 'Emphasize definitions, terminology, and precise meanings.',
};

export default function LectureView({ files = [] }: LectureViewProps) {
  const [activeTab, setActiveTab] = useState<'transcript' | 'summary'>('summary');
  const [passagesPane, setPassagesPane] = useState<'chunks' | 'markdown'>('chunks');

  const [selectedFileId, setSelectedFileId] = useState<number | null>(files.length > 0 ? files[0].id : null);
  const [fileQuery, setFileQuery] = useState('');

  useEffect(() => {
    if (files.length > 0 && (!selectedFileId || !files.find((f) => f.id === selectedFileId))) {
      setSelectedFileId(files[0].id);
    }
  }, [files, selectedFileId]);

  const filteredFiles = useMemo(() => {
    const q = fileQuery.trim().toLowerCase();
    if (!q) return files;
    return files.filter((f) => f.name.toLowerCase().includes(q));
  }, [files, fileQuery]);

  const selectedFile = files.find((f) => f.id === selectedFileId);
  const scopeFile = selectedFile ?? files[0];

  const videoFetchGen = useRef(0);
  const videoBlobUrlRef = useRef<string | null>(null);

  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  useEffect(() => {
    const revokeAndClear = () => {
      if (videoBlobUrlRef.current) {
        URL.revokeObjectURL(videoBlobUrlRef.current);
        videoBlobUrlRef.current = null;
      }
      setVideoUrl(null);
    };

    if (!selectedFile || selectedFile.type !== 'video') {
      revokeAndClear();
      return () => {
        videoFetchGen.current += 1;
      };
    }

    const gen = ++videoFetchGen.current;

    void (async () => {
      try {
        if (selectedFile.originalFile) {
          const u = URL.createObjectURL(selectedFile.originalFile);
          if (gen !== videoFetchGen.current) {
            URL.revokeObjectURL(u);
            return;
          }
          revokeAndClear();
          videoBlobUrlRef.current = u;
          setVideoUrl(u);
          return;
        }
        const { body, mediaType } = await getInputFile(selectedFile.name);
        if (gen !== videoFetchGen.current) return;
        const coerced = coerceBlobForPreview(body, selectedFile.name, mediaType);
        const u = URL.createObjectURL(coerced);
        if (gen !== videoFetchGen.current) {
          URL.revokeObjectURL(u);
          return;
        }
        revokeAndClear();
        videoBlobUrlRef.current = u;
        setVideoUrl(u);
      } catch {
        if (gen === videoFetchGen.current) revokeAndClear();
      }
    })();

    return () => {
      videoFetchGen.current += 1;
      revokeAndClear();
    };
  }, [selectedFile?.id, selectedFile?.name, selectedFile?.type, selectedFile?.originalFile?.name, selectedFile?.originalFile?.lastModified]);

  const inputFetchGen = useRef(0);
  const inputBlobUrlRef = useRef<string | null>(null);

  const [inputPreview, setInputPreview] = useState<InputPreviewState>({ kind: 'none' });
  const [inputPreviewLoading, setInputPreviewLoading] = useState(false);
  const [inputPreviewError, setInputPreviewError] = useState<string | null>(null);

  useEffect(() => {
    const gen = ++inputFetchGen.current;

    const revokeInputBlob = () => {
      if (inputBlobUrlRef.current) {
        URL.revokeObjectURL(inputBlobUrlRef.current);
        inputBlobUrlRef.current = null;
      }
    };

    if (!selectedFile || selectedFile.type === 'video') {
      revokeInputBlob();
      setInputPreview({ kind: 'none' });
      setInputPreviewError(null);
      setInputPreviewLoading(false);
      return () => {
        inputFetchGen.current += 1;
      };
    }

    revokeInputBlob();
    setInputPreview({ kind: 'none' });
    setInputPreviewError(null);
    setInputPreviewLoading(true);

    void (async () => {
      try {
        const nameLower = selectedFile.name.toLowerCase();
        const ext = nameLower.includes('.') ? nameLower.slice(nameLower.lastIndexOf('.')) : '';
        const officeExt = ['.ppt', '.pptx', '.xls', '.xlsx', '.doc', '.docx'];
        if (ext === '.pdf' || selectedFile.type === 'pdf') {
          const u = await getInputFileUrl(selectedFile.name, 900);
          if (gen !== inputFetchGen.current) return;
          if (u?.url) {
            setInputPreview({
              kind: 'blob',
              url: u.url,
              mime: 'application/pdf',
            });
            return;
          }
        }
        if (officeExt.includes(ext)) {
          const u = await getInputFileUrl(selectedFile.name, 900);
          if (gen !== inputFetchGen.current) return;
          if (u?.url) {
            setInputPreview({
              kind: 'office',
              iframeSrc: `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(u.url)}`,
              sourceUrl: u.url,
            });
          } else {
            setInputPreview({
              kind: 'none',
            });
            setInputPreviewError('Office preview URL is not available for this file on current storage backend.');
          }
          return;
        }

        const { body, mediaType } = await getInputFile(selectedFile.name);
        if (gen !== inputFetchGen.current) return;

        const mime = (mediaType || '').split(';')[0].trim().toLowerCase();

        const binaryByExtension = /\.(xlsx|xls|xlsm|docx|doc|pptx|ppt|zip|bin|exe)$/i.test(nameLower);
        const textish =
          !binaryByExtension &&
          (mime.startsWith('text/') ||
            mime === 'application/json' ||
            /\.(txt|md|csv|json|log)$/i.test(nameLower));

        if ((mime === 'text/html' || ext === '.html' || ext === '.htm') && selectedFile.type !== 'pdf') {
          const text = await body.text();
          if (gen !== inputFetchGen.current) return;
          setInputPreview({ kind: 'html', content: text });
          return;
        }

        if (textish && mime !== 'application/pdf' && selectedFile.type !== 'pdf') {
          const text = await body.text();
          if (gen !== inputFetchGen.current) return;
          setInputPreview({ kind: 'text', content: text });
          return;
        }

        const coerced = coerceBlobForPreview(body, selectedFile.name, mediaType);
        const objectUrl = URL.createObjectURL(coerced);
        if (gen !== inputFetchGen.current) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        inputBlobUrlRef.current = objectUrl;
        setInputPreview({
          kind: 'blob',
          url: objectUrl,
          mime: coerced.type || mime || 'application/octet-stream',
        });
      } catch (e) {
        if (gen !== inputFetchGen.current) return;

        // Fallback for PDFs on S3: use presigned URL (helps when direct blob fetch fails intermittently).
        if (selectedFile.type === 'pdf') {
          try {
            const u = await getInputFileUrl(selectedFile.name, 900);
            if (gen !== inputFetchGen.current) return;
            if (u?.url) {
              setInputPreview({
                kind: 'blob',
                url: u.url,
                mime: 'application/pdf',
              });
              setInputPreviewError(null);
              return;
            }
          } catch {
            // Fall through to standard error handling below.
          }
        }

        setInputPreview({ kind: 'none' });
        setInputPreviewError(e instanceof Error ? e.message : 'Could not load file for preview.');
      } finally {
        if (gen === inputFetchGen.current) setInputPreviewLoading(false);
      }
    })();

    return () => {
      inputFetchGen.current += 1;
      revokeInputBlob();
    };
  }, [selectedFile?.id, selectedFile?.name, selectedFile?.type]);

  const processedMdFetchGen = useRef(0);

  const [processedMdLoading, setProcessedMdLoading] = useState(true);
  const [processedMarkdown, setProcessedMarkdown] = useState<string | null>(null);
  const [processedMdSourcePath, setProcessedMdSourcePath] = useState<string | null>(null);
  const [processedMdNotice, setProcessedMdNotice] = useState<string | null>(null);

  const hasOriginalPreviewInMain =
    selectedFile?.type === 'video'
      ? !!videoUrl
      : !inputPreviewLoading && inputPreview.kind !== 'none';

  const shouldFallbackToProcessedMarkdownMain = !!selectedFile && !hasOriginalPreviewInMain && !inputPreviewLoading;

  const shouldLoadProcessedMarkdown = !!scopeFile?.name && (
    shouldFallbackToProcessedMarkdownMain || (activeTab === 'transcript' && passagesPane === 'markdown')
  );

  useEffect(() => {
    if (!scopeFile?.name) {
      processedMdFetchGen.current += 1;
      setProcessedMarkdown(null);
      setProcessedMdSourcePath(null);
      setProcessedMdNotice(null);
      setProcessedMdLoading(false);
      return;
    }

    if (!shouldLoadProcessedMarkdown) {
      processedMdFetchGen.current += 1;
      setProcessedMdLoading(false);
      return;
    }

    const gen = ++processedMdFetchGen.current;
    setProcessedMdLoading(true);
    setProcessedMdNotice(null);
    setProcessedMarkdown(null);
    setProcessedMdSourcePath(null);

    void (async () => {
      try {
        const data = await getProcessedByFile(scopeFile.name);
        if (gen !== processedMdFetchGen.current) return;
        const rel = pickPrimaryProcessedMarkdownRelPath(data);
        if (!rel) {
          setProcessedMdNotice(
            'Processed tree exists but no markdown (.md) was found in stage 3 or 4. Re-run **Process** or check pipeline outputs.'
          );
          return;
        }
        const { body } = await getProcessedFile(rel);
        const text = await body.text();
        if (gen !== processedMdFetchGen.current) return;
        setProcessedMarkdown(text);
        setProcessedMdSourcePath(rel);
      } catch (e) {
        if (gen !== processedMdFetchGen.current) return;
        const status =
          e && typeof e === 'object' && 'response' in e
            ? Number((e as { response?: { status?: number } }).response?.status)
            : 0;
        if (status === 404) {
          setProcessedMdNotice('No processed artifacts for this file yet. Run **Process** in Knowledge Management, then refresh.');
        } else {
          const msg =
            e && typeof e === 'object' && 'response' in e
              ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || '')
              : e instanceof Error
                ? e.message
                : 'Could not load processed markdown.';
          setProcessedMdNotice(msg || 'Could not load processed markdown.');
        }
      } finally {
        if (gen === processedMdFetchGen.current) setProcessedMdLoading(false);
      }
    })();

    return () => {
      processedMdFetchGen.current += 1;
    };
  }, [scopeFile?.name, shouldLoadProcessedMarkdown]);

  const [isGenerating, setIsGenerating] = useState(false);
  const [summaryLength, setSummaryLength] = useState<'brief' | 'detailed' | 'comprehensive'>('detailed');
  const [summaryFocus, setSummaryFocus] = useState<'general' | 'formulas' | 'definitions'>('general');
  const [summaryMarkdown, setSummaryMarkdown] = useState<string | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  useEffect(() => {
    setSummaryMarkdown(null);
    setSummaryError(null);
    setIsGenerating(false);
    setPassagesPane('chunks');
  }, [selectedFileId]);

  const [transcriptQuery, setTranscriptQuery] = useState('');
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const [transcriptError, setTranscriptError] = useState<string | null>(null);
  const [transcriptChunks, setTranscriptChunks] = useState<Array<Record<string, unknown>>>([]);

  const chunksFetchGen = useRef(0);

  useEffect(() => {
    if (!scopeFile?.name) {
      chunksFetchGen.current += 1;
      setTranscriptChunks([]);
      setTranscriptLoading(false);
      setTranscriptError(null);
      return;
    }
    if (activeTab !== 'transcript' || passagesPane !== 'chunks') {
      setTranscriptLoading(false);
      return;
    }

    const gen = ++chunksFetchGen.current;
    setTranscriptChunks([]);
    setTranscriptLoading(true);
    setTranscriptError(null);

    void (async () => {
      try {
        const data = await getChunksByFile(scopeFile.name);
        if (gen !== chunksFetchGen.current) return;
        setTranscriptChunks((data.chunks as Array<Record<string, unknown>>) || []);
      } catch (e) {
        if (gen !== chunksFetchGen.current) return;
        const msg =
          e && typeof e === 'object' && 'response' in e
            ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || '')
            : e instanceof Error
              ? e.message
              : 'Load chunks failed';
        setTranscriptError(msg || 'Could not load chunks for this file.');
        setTranscriptChunks([]);
      } finally {
        if (gen === chunksFetchGen.current) setTranscriptLoading(false);
      }
    })();

    return () => {
      chunksFetchGen.current += 1;
    };
  }, [scopeFile?.name, activeTab, passagesPane]);

  const filteredChunks = useMemo(() => {
    const needle = transcriptQuery.trim().toLowerCase();
    if (!needle) return transcriptChunks;
    return transcriptChunks.filter((row) => {
      const t = String((row as { text?: string }).text || '').toLowerCase();
      const s = String((row as { source?: string }).source || '').toLowerCase();
      return t.includes(needle) || s.includes(needle);
    });
  }, [transcriptChunks, transcriptQuery]);

  const handleGenerateSummary = async () => {
    setIsGenerating(true);
    setSummaryError(null);
    try {
      const res = await postSummary({
        focus_query: FOCUS_QUERY[summaryFocus],
        depth: summaryLength,
        document_id: scopeFile?.documentFolder ?? null,
        tone: 'neutral',
        target_length: LENGTH_MAP[summaryLength],
      });
      if (res.error) {
        setSummaryMarkdown(null);
        setSummaryError(res.error);
        return;
      }
      const body = (res.summary || '').trim();
      if (!body) {
        setSummaryMarkdown(null);
        setSummaryError('Empty summary. Run **Process** on your materials so stage-3 markdown exists, then try again.');
        return;
      }
      setSummaryMarkdown(body);
    } catch (e) {
      console.error('Summary failed:', e);
      setSummaryMarkdown(null);
      setSummaryError(e instanceof Error ? e.message : 'Summary request failed');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="h-full flex flex-col lg:flex-row gap-8 max-w-[1600px] mx-auto">
      <div className="flex-1 flex flex-col gap-2 min-w-0">
        <div className="bg-white rounded-[2rem] p-6 border border-slate-200 shadow-sm flex flex-col gap-6 w-full">
          <div className="flex items-start gap-4 shrink-0">
            <div className="w-12 h-12 bg-sky-50 text-sky-600 rounded-2xl flex items-center justify-center shadow-sm shrink-0">
              {selectedFile?.type === 'video' ? (
                <Video className="w-6 h-6" />
              ) : selectedFile?.type === 'image' ? (
                <ImageIcon className="w-6 h-6" />
              ) : selectedFile?.type === 'audio' ? (
                <Headphones className="w-6 h-6" />
              ) : (
                <FileText className="w-6 h-6" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-lg font-black text-slate-900 tracking-tight">Lecture materials</h2>
              <div className="text-xs text-slate-500 font-medium leading-relaxed mt-1">
                Choose an upload to play video, preview PDFs and images, read processed markdown, and open passages or AI summary.
              </div>
            </div>
          </div>
          <div className="min-w-0 w-full flex flex-col gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                type="text"
                value={fileQuery}
                onChange={(e) => setFileQuery(e.target.value)}
                placeholder="Search by name"
                className="w-full border border-slate-200 rounded-2xl pl-10 pr-4 py-2.5 text-sm font-medium text-slate-700 focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none bg-white"
                aria-label="Filter uploaded files by name"
              />
              {fileQuery.trim() && (
                <button
                  type="button"
                  onClick={() => setFileQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-semibold text-sky-600 hover:text-sky-800 px-2 py-1 rounded-lg hover:bg-sky-50"
                >
                  Clear
                </button>
              )}
            </div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
              Your uploads ({files.length}) — click to select
            </p>
            <div
              className="border border-slate-200 rounded-2xl bg-slate-50/60 max-h-52 overflow-y-auto shadow-inner custom-scrollbar"
              role="listbox"
              aria-label="Uploaded files"
            >
              {files.length === 0 ? (
                <p className="p-4 text-sm text-slate-500 text-center">
                  No files yet. Upload materials from <strong>Knowledge Management → Upload</strong>.
                </p>
              ) : filteredFiles.length === 0 ? (
                <div className="p-4 text-center space-y-2">
                  <p className="text-sm text-slate-500">No files match “{fileQuery.trim()}”.</p>
                  <button
                    type="button"
                    onClick={() => setFileQuery('')}
                    className="text-xs font-bold text-sky-600 hover:underline"
                  >
                    Show all files
                  </button>
                </div>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {filteredFiles.map((file) => {
                    const active = file.id === selectedFileId;
                    return (
                      <li key={file.id}>
                        <button
                          type="button"
                          role="option"
                          aria-selected={active}
                          onClick={() => setSelectedFileId(file.id)}
                          className={`w-full text-left px-4 py-3 text-sm transition-colors flex items-start gap-3 ${active
                            ? 'bg-sky-50 border-l-4 border-l-sky-600 font-semibold text-slate-900'
                            : 'hover:bg-white text-slate-700 border-l-4 border-l-transparent'
                            }`}
                        >
                          <ChevronRight
                            className={`w-4 h-4 mt-0.5 shrink-0 ${active ? 'text-sky-600' : 'text-slate-300'}`}
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate" title={file.name}>
                              {file.name}
                            </span>
                            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-tight mt-0.5 block">
                              {file.type}
                              {file.status ? ` · ${file.status}` : ''}
                            </span>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        </div>
        {/* </div> */}

        {selectedFile?.type === 'video' && videoUrl ? (
          <div className="bg-slate-900 rounded-[2.5rem] overflow-hidden shadow-2xl relative aspect-video flex items-center justify-center border-4 border-white">
            <video src={videoUrl} controls className="w-full h-full object-contain" playsInline />
          </div>
        ) : (
          <div className="rounded-[2.5rem] border-4 border-white shadow-2xl overflow-hidden flex flex-col bg-white min-h-[min(560px,70vh)] max-h-[calc(100vh-12rem)]">
            {selectedFile?.type === 'video' && !videoUrl && (
              <div className="shrink-0 bg-slate-900 text-center px-6 py-5 border-b border-slate-800">
                <p className="text-white/50 text-xs font-bold uppercase tracking-widest">Video stream unavailable</p>
                <p className="text-white/35 text-[11px] mt-1 max-w-md mx-auto">
                  If this file lives in cloud storage only, open it from Upload or use processed markdown below.
                </p>
                <p className="text-white/60 text-sm font-medium mt-2 truncate" title={selectedFile.name}>
                  {selectedFile.name}
                </p>
              </div>
            )}
            {selectedFile && selectedFile.type !== 'video' && inputPreviewLoading && (
              <div className="shrink-0 flex flex-col items-center justify-center gap-2 py-10 border-b border-slate-100 bg-slate-50/50">
                <Loader2 className="w-8 h-8 text-sky-600 animate-spin" />
                <p className="text-xs font-bold text-slate-500">Loading original file preview…</p>
              </div>
            )}
            {selectedFile && selectedFile.type !== 'video' && inputPreviewError && !inputPreviewLoading && !shouldFallbackToProcessedMarkdownMain && (
              <div className="shrink-0 px-4 py-3 border-b border-red-100 bg-red-50/80 text-sm text-red-700">{inputPreviewError}</div>
            )}
            {selectedFile && selectedFile.type !== 'video' && !inputPreviewLoading && inputPreview.kind === 'text' && (
              <div className="flex-1 overflow-y-auto custom-scrollbar border-b border-slate-200 bg-slate-50/80 p-4">
                {selectedFile.name.toLowerCase().endsWith('.md') ? (
                  <div className="prose prose-sm prose-slate max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={LECTURE_MARKDOWN_COMPONENTS}>
                      {inputPreview.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <pre className="text-xs font-mono text-slate-700 whitespace-pre-wrap break-words leading-relaxed">
                    {inputPreview.content}
                  </pre>
                )}
              </div>
            )}
            {selectedFile &&
              selectedFile.type !== 'video' &&
              !inputPreviewLoading &&
              inputPreview.kind === 'office' && (
                <div className="flex-1 border-b border-slate-200 bg-slate-100 flex flex-col">
                  <iframe
                    title={`Office preview: ${selectedFile.name}`}
                    src={inputPreview.iframeSrc}
                    className="w-full h-full min-h-[400px] border-0 bg-white"
                  />
                </div>
              )}
            {selectedFile &&
              selectedFile.type !== 'video' &&
              !inputPreviewLoading &&
              inputPreview.kind === 'html' && (
                <div className="flex-1 border-b border-slate-200 bg-white">
                  <iframe
                    title={`HTML preview: ${selectedFile.name}`}
                    srcDoc={inputPreview.content}
                    sandbox=""
                    className="w-full h-full border-0"
                  />
                </div>
              )}
            {selectedFile &&
              selectedFile.type !== 'video' &&
              !inputPreviewLoading &&
              inputPreview.kind === 'blob' &&
              (selectedFile.type === 'image' || inputPreview.mime.startsWith('image/')) && (
                <div className="flex-1 bg-slate-100 border-b border-slate-200 flex items-center justify-center p-4">
                  <img
                    src={inputPreview.url}
                    alt={selectedFile.name}
                    className="max-w-full max-h-full object-contain rounded-lg shadow-sm"
                  />
                </div>
              )}
            {selectedFile &&
              selectedFile.type !== 'video' &&
              !inputPreviewLoading &&
              inputPreview.kind === 'blob' &&
              (selectedFile.type === 'pdf' || inputPreview.mime === 'application/pdf') && (
                <div className="flex-1 border-b border-slate-200 bg-slate-100 flex flex-col">
                  <iframe
                    title={`PDF: ${selectedFile.name}`}
                    src={inputPreview.url}
                    className="w-full h-full min-h-[400px] border-0 bg-white"
                  />
                </div>
              )}
            {selectedFile &&
              selectedFile.type !== 'video' &&
              !inputPreviewLoading &&
              inputPreview.kind === 'blob' &&
              (selectedFile.type === 'audio' || inputPreview.mime.startsWith('audio/')) && (
                <div className="shrink-0 px-6 py-5 border-b border-slate-200 bg-slate-50 flex-1 flex flex-col justify-center">
                  <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Audio</p>
                  <audio src={inputPreview.url} controls className="w-full" />
                </div>
              )}
            {selectedFile &&
              selectedFile.type !== 'video' &&
              !inputPreviewLoading &&
              inputPreview.kind === 'blob' &&
              selectedFile.type !== 'image' &&
              selectedFile.type !== 'pdf' &&
              selectedFile.type !== 'audio' &&
              !inputPreview.mime.startsWith('image/') &&
              inputPreview.mime !== 'application/pdf' &&
              !inputPreview.mime.startsWith('audio/') && (
                <div className="flex-1 px-6 py-5 border-b border-slate-200 bg-slate-50 text-center flex flex-col items-center justify-center space-y-3">
                  <p className="text-sm text-slate-600">Inline preview is not available for this MIME type.</p>
                  <a
                    href={inputPreview.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center justify-center rounded-xl bg-sky-600 text-white text-xs font-bold uppercase tracking-wide px-4 py-2.5 hover:bg-sky-700"
                  >
                    Open original file
                  </a>
                </div>
              )}
            {(shouldFallbackToProcessedMarkdownMain || !selectedFile) && (
              <div className="flex-1 overflow-y-auto custom-scrollbar p-6 min-h-[180px] min-h-0">
                {!selectedFile && (
                  <div className="h-full flex flex-col items-center justify-center text-center text-slate-400 py-12">
                    <FileText className="w-14 h-14 opacity-30 mb-3" />
                    <p className="text-sm font-medium">Select a file from your uploads</p>
                  </div>
                )}
                {selectedFile && shouldFallbackToProcessedMarkdownMain && processedMdLoading && (
                  <div className="flex flex-col items-center justify-center gap-3 py-16 text-sky-600">
                    <Loader2 className="w-10 h-10 animate-spin" />
                    <p className="text-sm font-bold">Loading processed markdown…</p>
                  </div>
                )}
                {selectedFile && shouldFallbackToProcessedMarkdownMain && !processedMdLoading && processedMarkdown && (
                  <div>
                    <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">Processed markdown</p>
                    <div className="prose prose-slate max-w-none text-slate-700 leading-7 prose-headings:my-3 prose-p:my-2 prose-li:my-1">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={LECTURE_MARKDOWN_COMPONENTS}>
                        {processedMarkdown}
                      </ReactMarkdown>
                    </div>
                    {processedMdSourcePath && (
                      <p className="text-[10px] text-slate-400 mt-6 font-mono truncate" title={processedMdSourcePath}>
                        {processedMdSourcePath}
                      </p>
                    )}
                  </div>
                )}
                {selectedFile && shouldFallbackToProcessedMarkdownMain && !processedMdLoading && !processedMarkdown && processedMdNotice && (
                  <div className="py-8 px-2">
                    <FileText className="w-12 h-12 text-slate-200 mx-auto mb-4" />
                    <div className="prose prose-sm prose-slate max-w-none text-center text-slate-600">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={LECTURE_MARKDOWN_COMPONENTS}>
                        {processedMdNotice}
                      </ReactMarkdown>
                    </div>
                    <p className="text-xs text-slate-500 text-center mt-4 font-medium truncate" title={selectedFile.name}>
                      {selectedFile.name}
                    </p>
                  </div>
                )}
                {selectedFile &&
                  shouldFallbackToProcessedMarkdownMain &&
                  selectedFile.type !== 'video' &&
                  !processedMdLoading &&
                  !processedMarkdown &&
                  !processedMdNotice &&
                  !inputPreviewLoading &&
                  inputPreview.kind === 'none' &&
                  !inputPreviewError && (
                    <div className="py-10 text-center text-slate-500">
                      <p className="text-sm font-medium">No preview loaded yet.</p>
                      <p className="text-xs mt-2">
                        Use <strong>Passages</strong> and <strong>AI Summary</strong> after processing.
                      </p>
                    </div>
                  )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex-1 bg-white rounded-[2.5rem] border border-slate-200 shadow-sm flex flex-col h-[calc(100vh-10rem)] overflow-hidden">
        <div className="flex items-center p-3 bg-slate-50/50 border-b border-slate-100 shrink-0">
          <button
            type="button"
            onClick={() => setActiveTab('transcript')}
            className={`flex-1 py-3 text-xs font-black uppercase tracking-widest rounded-2xl transition-all flex items-center justify-center gap-2 ${activeTab === 'transcript'
              ? 'bg-white text-sky-600 shadow-sm border border-slate-200'
              : 'text-slate-400 hover:text-slate-600 hover:bg-white/50'
              }`}
          >
            <MessageSquare className="w-4 h-4" />
            Passages
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('summary')}
            className={`flex-1 py-3 text-xs font-black uppercase tracking-widest rounded-2xl transition-all flex items-center justify-center gap-2 ${activeTab === 'summary'
              ? 'bg-white text-sky-600 shadow-sm border border-slate-200'
              : 'text-slate-400 hover:text-slate-600 hover:bg-white/50'
              }`}
          >
            <Sparkles className="w-4 h-4" />
            AI Summary
          </button>
        </div>

        <div className="flex-1 overflow-y-auto relative custom-scrollbar">
          {activeTab === 'transcript' ? (
            <div className="p-8 space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <p className="text-xs text-slate-500 font-medium leading-relaxed flex-1">
                  <strong>{scopeFile?.name || 'This file'}</strong> — switch between indexed chunks and full processed markdown.
                </p>
                <div className="flex rounded-2xl border border-slate-200 p-1 bg-slate-50 shrink-0">
                  <button
                    type="button"
                    onClick={() => setPassagesPane('chunks')}
                    className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all ${passagesPane === 'chunks'
                      ? 'bg-white text-sky-600 shadow-sm border border-slate-100'
                      : 'text-slate-500 hover:text-slate-700'
                      }`}
                  >
                    <List className="w-3.5 h-3.5" />
                    Chunks
                  </button>
                  <button
                    type="button"
                    onClick={() => setPassagesPane('markdown')}
                    className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all ${passagesPane === 'markdown'
                      ? 'bg-white text-sky-600 shadow-sm border border-slate-100'
                      : 'text-slate-500 hover:text-slate-700'
                      }`}
                  >
                    <ScrollText className="w-3.5 h-3.5" />
                    Full markdown
                  </button>
                </div>
              </div>

              {passagesPane === 'markdown' ? (
                <div className="space-y-4">
                  <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Processed markdown (same as pipeline output)</p>
                  {processedMdLoading && (
                    <div className="flex items-center gap-3 text-sky-600 text-sm font-bold py-8 justify-center">
                      <Loader2 className="w-6 h-6 animate-spin" />
                      Loading markdown…
                    </div>
                  )}
                  {!processedMdLoading && processedMarkdown && (
                    <div className="prose prose-sm prose-slate max-w-none text-slate-700 border border-slate-100 rounded-2xl p-4 bg-slate-50/50 max-h-[55vh] overflow-y-auto custom-scrollbar">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={LECTURE_MARKDOWN_COMPONENTS}>
                        {processedMarkdown}
                      </ReactMarkdown>
                    </div>
                  )}
                  {!processedMdLoading && !processedMarkdown && processedMdNotice && (
                    <div className="prose prose-sm prose-slate max-w-none text-slate-600 border border-slate-100 rounded-2xl p-4 bg-amber-50/40">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={LECTURE_MARKDOWN_COMPONENTS}>
                        {processedMdNotice}
                      </ReactMarkdown>
                    </div>
                  )}
                  {!processedMdLoading && !processedMarkdown && !processedMdNotice && (
                    <p className="text-sm text-slate-500">No processed markdown for this file yet.</p>
                  )}
                </div>
              ) : (
                <>
                  <div className="relative group">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-sky-500 transition-colors" />
                    <input
                      type="text"
                      value={transcriptQuery}
                      onChange={(e) => setTranscriptQuery(e.target.value)}
                      placeholder="Filter passages…"
                      className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-sky-500 focus:bg-white transition-all shadow-inner"
                    />
                  </div>
                  {transcriptLoading && (
                    <div className="flex items-center gap-3 text-sky-600 text-sm font-bold">
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Loading passages…
                    </div>
                  )}
                  {transcriptError && (
                    <p className="text-sm text-red-600 font-medium bg-red-50 border border-red-100 rounded-xl p-4">{transcriptError}</p>
                  )}
                  {!transcriptLoading && !transcriptError && filteredChunks.length === 0 && (
                    <p className="text-sm text-slate-500">
                      No chunks for this file. Run Process / Index, or open <strong>Full markdown</strong> if the pipeline produced .md only.
                    </p>
                  )}
                  <div className="space-y-3">
                    {filteredChunks.map((row, i) => {
                      const text = String((row as { text?: string }).text || '').trim();
                      const source = String((row as { source?: string }).source || '');
                      const start = Number((row as { start_time?: number | string }).start_time ?? 0);
                      const end = Number((row as { end_time?: number | string }).end_time ?? 0);
                      const fmt = (sec: number) => {
                        if (!Number.isFinite(sec) || sec < 0) return '00:00:00';
                        const s = Math.floor(sec);
                        const hh = String(Math.floor(s / 3600)).padStart(2, '0');
                        const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
                        const ss = String(s % 60).padStart(2, '0');
                        return `${hh}:${mm}:${ss}`;
                      };
                      const hasTimecode = (Number.isFinite(start) && start > 0) || (Number.isFinite(end) && end > 0);
                      if (!text) return null;
                      return (
                        <div
                          key={`${scopeFile?.name}-${source}-${i}`}
                          className="p-4 rounded-2xl border border-slate-100 bg-slate-50/50 hover:bg-sky-50/40 hover:border-sky-100 transition-all"
                        >
                          {source && (
                            <p className="text-[10px] font-black text-sky-500 uppercase tracking-widest mb-2 truncate" title={source}>
                              {source}
                            </p>
                          )}
                          <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">
                            {hasTimecode ? `${fmt(start)} – ${fmt(end)}` : 'Text segment'}
                          </p>
                          <p className="text-sm text-slate-700 font-medium leading-relaxed whitespace-pre-wrap">{text}</p>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="flex flex-col h-full">
              {!summaryMarkdown && !isGenerating ? (
                <div className="flex-1 flex flex-col items-center justify-center p-10 text-center m-6 bg-[#F8FAFC] rounded-[2rem] border border-slate-100 shadow-inner">
                  <div className="w-20 h-20 bg-white text-sky-600 rounded-[1.5rem] flex items-center justify-center mb-6 shadow-xl shadow-sky-100/50">
                    <Sparkles className="w-10 h-10" />
                  </div>
                  <h3 className="text-xl font-black text-slate-900 mb-3 tracking-tight">Lecture insight</h3>
                  <p className="text-sm text-slate-500 mb-6 max-w-xs font-medium leading-relaxed">
                    Summary is generated from <strong>processed markdown</strong> (pipeline stage 3), like the standalone AI service.
                  </p>
                  {summaryError && (
                    <p className="text-sm text-red-600 mb-6 max-w-sm text-left w-full bg-red-50 border border-red-100 rounded-xl p-4">{summaryError}</p>
                  )}

                  <div className="w-full max-w-sm space-y-5 mb-10 text-left">
                    {scopeFile && (
                      <p className="text-xs text-slate-500">
                        Scoped to document folder: <strong>{scopeFile.documentFolder || '—'}</strong> ({scopeFile.name})
                      </p>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => void handleGenerateSummary()}
                    disabled={!scopeFile}
                    className="w-full max-w-sm py-4 bg-sky-600 text-white font-black uppercase tracking-widest text-xs rounded-2xl hover:bg-sky-700 transition-all flex items-center justify-center gap-3 shadow-lg shadow-sky-200 hover:-translate-y-0.5 disabled:opacity-50 disabled:pointer-events-none"
                  >
                    <Sparkles className="w-5 h-5" />
                    Generate summary
                  </button>
                </div>
              ) : isGenerating ? (
                <div className="flex-1 flex flex-col items-center justify-center p-10 text-center m-6">
                  <div className="relative">
                    <div className="absolute inset-0 bg-sky-600/20 blur-2xl animate-pulse rounded-full"></div>
                    <Loader2 className="w-16 h-16 text-sky-600 animate-spin mb-8 relative" />
                  </div>
                  <h3 className="text-xl font-black text-slate-900 tracking-tight">Calling insights API…</h3>
                  <p className="text-sm text-slate-500 mt-3 font-medium max-w-[240px] mx-auto leading-relaxed">
                    POST /api/insights/summary — Bedrock or your configured generator.
                  </p>
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto p-8 space-y-6 custom-scrollbar">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <h3 className="font-black text-slate-900 text-xl tracking-tight">Summary</h3>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-1">From processed materials</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setSummaryMarkdown(null);
                        setSummaryError(null);
                      }}
                      className="p-2 text-sky-600 hover:bg-sky-50 rounded-xl transition-all border border-transparent hover:border-sky-100"
                      title="New summary"
                    >
                      <RefreshCw className="w-5 h-5" />
                    </button>
                  </div>
                  {summaryError && (
                    <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl p-4">{summaryError}</p>
                  )}
                  <article className="border border-slate-100 rounded-2xl p-6 bg-slate-50/50">
                    <div className="prose prose-slate max-w-none text-slate-700 leading-7 prose-headings:my-3 prose-p:my-2 prose-li:my-1">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={LECTURE_MARKDOWN_COMPONENTS}>
                        {summaryMarkdown}
                      </ReactMarkdown>
                    </div>
                  </article>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
